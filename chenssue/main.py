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
            created_memory_counter = 0
            skipped_memory_counter = 0
            items = []
            for game in games:
                game = game_metadata(game, args.user)
                key_name = key(game, args.user)
                items.append({
                        "key_name": key_name,
                        "description": description(game, args.user),
                        "value": game["content"],
                        "embed": True,
                        "embed_source": "value",
                    })
            ensue_args = {
                "items": items
            }
            
            result = await session.call_tool("create_memory", ensue_args)
            report = get_report(result)
            
            items_by_key = {item["key_name"]: item for item in items}
            
            for r in report["results"]:
                key_name = r["key_name"]
                status = r["status"]

                if status == "succeeded":
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
                f"Done! {created_memory_counter} memories successfully created, {skipped_memory_counter} skipped/updated."
            )


async def async_main():
    parser = ArgumentParser(
        description="Get the most recent games played by the given player"
    )
    parser.add_argument(
        "user", type=str, help="The name of the user to get the games from"
    )
    parser.add_argument(
        "--max", type=int, default=100, help="The maximum number of games to export"
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
    args = parser.parse_args()
    games = get_games(args)
    await ensue_publish(games, args)


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
