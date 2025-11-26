# 📘 CHEnSSue — Export Lichess Games into Ensue shared memory

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
