from .config import ensue_token
import berserk
import sys
import chess.pgn
import io

from argparse import ArgumentParser

import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.exceptions import McpError
import base64
import httpx
from datetime import datetime
import json

ensue_url = "https://api.ensue-network.ai/"


def vprint(args, message):
    if args.verbose:
        print(message)


def get_games(args, since=None):
    print("Fetching games from Lichess...")
    try:
        games = list(
            berserk.Client().games.export_by_player(
                args.user, as_pgn=True, clocks=True, max=args.max, until=args.until, since=since
            )
        )
    except berserk.exceptions.ResponseError as e:
        # Lichess user does not exist
        if e.response is not None and e.response.status_code == 404:
            print(f"Error: Lichess user '{args.user}' does not exist.")
            sys.exit(1)
        else:
            # Any other HTTP error
            raise
    print(f"{len(games)} games successfully retreived!")
    # Reverse the list such that the games are from the oldest to the newest
    games.reverse()
    return games


def game_metadata(game, user):

    content = base64.b64encode(game.encode("utf-8")).decode("ascii")

    game = chess.pgn.read_game(io.StringIO(game))

    white = game.headers["White"]
    black = game.headers["Black"]
    if white == user:
        color = "white"
    elif black == user:
        color = "black"
    else:
        raise ValueError(f"User {user} is neither White nor Black in this game.")

    result = game.headers["Result"]
    if result == "1/2-1/2":
        result = "draw"
    elif result == "1-0" and color == "white":
        result = "win"
    elif result == "0-1" and color == "black":
        result = "win"
    else:
        result = "loss"

    return {
        "id": game.headers["GameId"],
        "date": game.headers["UTCDate"],
        "color": color,
        "result": result,
        "format": game.headers["TimeControl"],
        "opening": game.headers["ECO"],
        "content": content,
    }


def key(game, user):
    # game id is added in the key for unicity
    return f"{user}__{game['date']}__{game['format']}__{game['color']}__{game['result']}__{game['opening']}__{game['id']}"


def description(game, user):
    return f"Chess game played by {user} on {game["date"].replace(".", "-")} as {game['color']}. Format: {game['format']}. Outcome: {game['result']}. Opening ECO code: {game['opening']}"


def get_report(call_tool_result):
    if getattr(call_tool_result, "structuredContent", None) is not None:
        return call_tool_result.structuredContent
    # fallback: parse TextContent
    for c in call_tool_result.content:
        if isinstance(c, types.TextContent):
            return json.loads(c.text)
    raise RuntimeError("No structuredContent and no TextContent to parse")


def is_duplicate_error(err: str) -> bool:
    return 'duplicate key value violates unique constraint "memories_pkey"' in err


async def create_memory_and_handle_result(args, batch_items, batch_number, session, ensue_args):
    created_memory_counter = 0
    skipped_memory_counter = 0
    result = await session.call_tool("create_memory", ensue_args)
    report = get_report(result)
    
    items_by_key = {item["key_name"]: item for item in batch_items }
    
    for r in report["results"]:
        key_name = r["key_name"]
        status = r["status"]

        if status == "succeeded" or status == "success":
            vprint(args, f"[CREATED] {key_name}")
            created_memory_counter += 1
            
        elif status == "failed":
            err = r.get("error", "")
            if is_duplicate_error(err):
                if args.update:
                    update_args = items_by_key[key_name]
                    await session.call_tool("update_memory", update_args)
                    vprint(args, f"[UPDATED] {key_name}")
                else:
                    vprint(args, f"[SKIPPED] {key_name}")
                skipped_memory_counter += 1
            else:
                raise RuntimeError(f"Create failed for {key_name}: {err}")
        else:
            raise RuntimeError(f"Unexpected status {status} for {key_name}")      
    print(
        f"Batch #{batch_number} processed! {created_memory_counter} memories successfully created, {skipped_memory_counter} skipped/updated."
    )
    return (created_memory_counter, skipped_memory_counter)
    

async def ensue_publish(games, args):
    print("Connecting to Ensue...")

    async with streamablehttp_client(
        ensue_url,
        headers={
            "Authorization": f"Bearer {ensue_token}",
        },
    ) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("Creating memories in Ensue...")
            ensue_batch_size = 100
            items = [[] for _ in range(int(len(games)/ ensue_batch_size) + 1)]
            batch_counter = 0
            counter = 0
            created_memory_counter = 0
            skipped_memory_counter = 0
            for game in games:
                game = game_metadata(game, args.user)
                key_name = key(game, args.user)
                items[batch_counter].append({
                        "key_name": key_name,
                        "description": description(game, args.user),
                        "value": game["content"],
                        "embed": True,
                        "embed_source": "value",
                    })
                if counter < ensue_batch_size - 1 and batch_counter * ensue_batch_size + counter != len(games) - 1:
                    counter += 1       
                else:
                    ensue_args = {
                        "items": items[batch_counter]
                    }
                    created, skipped = await create_memory_and_handle_result(args, items[batch_counter], batch_counter + 1, session, ensue_args)
                    created_memory_counter += created
                    skipped_memory_counter += skipped
                    batch_counter += 1
                    counter = 0
                    
            print(
                f"\nDone! {created_memory_counter} memories successfully created, {skipped_memory_counter} skipped/updated."
            )

async def fetch_games_and_publish(args):
    games = get_games(args)
    await ensue_publish(games, args)

def date_from_key(user, key):
    prefix = f"{user}__"
    key_name = key['key_name']
    if not key_name.startswith(prefix):
        return None
    # Remove "user__"
    rest = key_name[len(prefix):]
    # Extract date before the next "__"
    date_str, *_ = rest.split("__", 1)
    try:
        return datetime.strptime(date_str, "%Y.%m.%d")
    except ValueError:
        return None
    

# Note: this also checks the date format
def most_recent_game_date(args, keys):
    most_recent = None
    for key in keys:
        date = date_from_key(args.user, key)
        if date is None : pass
        elif most_recent == None : most_recent = date
        else : most_recent = max(most_recent, date)
    return most_recent
    
       
async def fetch_most_recent_game_date(args):
    print("Connecting to Ensue...")

    async with streamablehttp_client(
        ensue_url,
        headers={
            "Authorization": f"Bearer {ensue_token}",
        },
    ) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Fetching games in Ensue to determine the most recent game stored...")
            ensue_args = {"limit" : 100000000} # Stupidly high limit so all keys are retrieved
            keys_answer = await session.call_tool("list_keys", ensue_args)
            content = keys_answer.content[0]
            data = json.loads(content.text)
            keys = data["keys"]
            last_game_date = most_recent_game_date(args, keys)
            if last_game_date is None:
                print(f"No existing games found for user {args.user} in Ensue; fetching from scratch.")
                games = get_games(args)
            else:
                since = berserk.utils.to_millis(last_game_date)
                games = get_games(args, since=since)
            await ensue_publish(games, args)

async def async_main():
    parser = ArgumentParser(
        description="Get the most recent games played by the given player"
    )
    parser.add_argument(
        "user", type=str, help="The name of the user to get the games from"
    )
    parser.add_argument(
        "--max", type=int, default=None, help="The maximum number of games to export (default=100 in normal mode)"
    )
    parser.add_argument(
        "--until",
        type=int,
        default=None,
        help="The latest date to get the games from (timestamp UNIX in milliseconds)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update existing memories instead of skipping them",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print each memory status",
    )
    parser.add_argument(
        "--only-new-games",
        action="store_true",
        help="Add all games that are more recent than the last game stored in Ensue",
    )
    args = parser.parse_args()
    if args.only_new_games :
        if args.max is None :
            # capture all the games of the user
            args.max = 100000
        await fetch_most_recent_game_date(args)
    else :
        if args.max is None :
            args.max = 100
        await fetch_games_and_publish(args)


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
