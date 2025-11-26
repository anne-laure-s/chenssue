# ♟️ CHEnSSue — Export Lichess Games into Ensue shared memory

`chenssue` is a command-line tool that:

- fetches games from Lichess for a given user,
- extracts structured metadata (result, color, PGN, ECO, time control, date…),
- encodes the PGN,
- generates a deterministic and unique memory key,
- creates (or updates) this game as a memory inside an Ensue MCP server.

# 📦 Installation

## 1. Clone the repository

```bash
git clone https://gitlab.com/Anne-Laure_S/chenssue.git
cd chenssue
```
## 2. Create and activate a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate    # Linux / macOS
# OR
.\.venv\Scripts\activate     # Windows PowerShell

```
## 3. Install the project in editable mode

This makes the `chenssue` CLI command available instantly.

```bash
pip install -e .
```

## 4. Set your Ensue authentication key

Set your Ensue authentication token via the `ENSUE_API_KEY` environment variable or in a `.env` file:

```bash
export ENSUE_API_KEY="your_token_here"
```
The program loads it via `config.py`.

If the variable is missing, the program fails early.

## 5. Verify installation

```bash
chenssue --help
```
If you see the CLI usage message, you are ready to use CHEnSSue! 🎉

# 🕹️ Usage

## Export 100 most recent games (default)
```bash
chenssue <lichess username>
```
If the user has less than 100 games, all of the games will be exported.

## Limit the number of games
```bash
chenssue <lichess username> --max 5000
```
Note: Exporting 5000 games from Lichess to Ensue takes about 45 minutes.

## Export games up to a given timestamp (UNIX ms)
```bash
chenssue <lichess username> --until 1731880000000
```
## Overwrite existing memories instead of skipping them

By default, the program skip already existing memories. This default behavior can be changed with the `--update` flag:

```bash
chenssue <lichess username> --update
```

# 🧠 In Ensue

## Value

The fetched games PGN are stored as values; they are of the following form:
```
[Event "casual blitz game"]
[Site "https://lichess.org/RN3FFIqr"]
[Date "2020.09.19"]
[White "STL_Grischuk"]
[Black "STL_Carlsen"]
[Result "1/2-1/2"]
[GameId "RN3FFIqr"]
[UTCDate "2020.09.19"]
[UTCTime "21:20:10"]
[WhiteElo "1500"]
[BlackElo "1500"]
[WhiteTitle "GM"]
[BlackTitle "GM"]
[Variant "Standard"]
[TimeControl "300+3"]
[ECO "C67"]
[Termination "Normal"]

1. e4 { [%clk 0:05:00] } 1... e5 { [%clk 0:05:00] } 2. Nf3 { [%clk 0:05:02] } 2... Nc6 { [%clk 0:05:01] } 3. Bb5 { [%clk 0:05:03] } 3... Nf6 { [%clk 0:05:03] } 4. O-O { [%clk 0:04:58] } 4... Nxe4 { [%clk 0:05:05] } 5. d4 { [%clk 0:04:57] } 5... Nd6 { [%clk 0:05:06] } 6. dxe5 { [%clk 0:04:57] } 6... Nxb5 { [%clk 0:05:08] } 7. a4 { [%clk 0:04:59] } 7... Nbd4 { [%clk 0:05:09] } 8. Nxd4 { [%clk 0:05:01] } 8... d5 { [%clk 0:05:09] } 9. exd6 { [%clk 0:05:03] } 9... Nxd4 { [%clk 0:05:11] } 10. Qxd4 { [%clk 0:05:05] } 10... Qxd6 { [%clk 0:05:13] } 11. Qe4+ { [%clk 0:05:08] } 11... Qe6 { [%clk 0:05:16] } 12. Qd4 { [%clk 0:05:10] } 12... Qd6 { [%clk 0:05:18] } 13. Qe4+ { [%clk 0:05:13] } 13... Qe6 { [%clk 0:05:21] } 14. Qd4 { [%clk 0:05:16] } 14... Qd6 { [%clk 0:05:24] } 1/2-1/2
```

## Key

Each game is given a unique key of this form:
```
<user>__<game date>__<game format>__<user’s color>__<outcome>__<opening ECO>__<game id>"
```
The game ID is added for uniqueness.
The previous example gives the following key:
```
STL_Carlsen__2020.09.19__300+3__black__draw__C67__RN3FFIqr
```

## Embedding

The game’s PGN is embedded in Ensue.