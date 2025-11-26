from config import ensue_token
from berserk import Client
import chess.pgn
import io

from argparse import ArgumentParser

import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.exceptions import McpError
import base64


def get_games(args):
    print("Fetching games from Lichess...")
    games = list(
        Client().games.export_by_player(
            args.user, as_pgn=True, clocks=True, max=args.max, until=args.until
        )
    )
    print(f"{len(games)} games successfully retreived!")
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


async def ensue_publish(games, user):
    print("Connecting to Ensue...")

    async with streamablehttp_client(
        "https://www.ensue-network.ai/api/",
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
            for game in games:
                game = game_metadata(game, user)
                key_name = key(game, user)
                args = {
                    "key_name": key_name,
                    "description": description(game, user),
                    "value": game["content"],
                    "embed": True,
                    "embed_source": "value",
                }
                try:
                    await session.call_tool("create_memory", args)
                    print(f"Memory '{key_name}' created.")
                    created_memory_counter += 1
                except McpError as e:
                    msg = str(e)
                    if (
                        'duplicate key value violates unique constraint "memories_pkey"'
                        in msg
                    ):
                        print(f"[SKIP] found an existing memory for key {key_name}")
                        skipped_memory_counter += 1
                    else:
                        raise
            print(
                f"Done! {created_memory_counter} memories successfully created, {skipped_memory_counter} skipped."
            )


async def main():
    parser = ArgumentParser(
        description="Get the most recent games played by the given player"
    )
    parser.add_argument(
        "user", type=str, help="The name of the user to get the games from"
    )
    parser.add_argument(
        "--max", type=int, default=5000, help="The maximum number of games to export"
    )
    parser.add_argument(
        "--until",
        type=int,
        default=None,
        help="The latest date to get the games from (timestamp UNIX in milliseconds)",
    )
    args = parser.parse_args()
    games = get_games(args)
    await ensue_publish(games, args.user)


if __name__ == "__main__":
    asyncio.run(main())
