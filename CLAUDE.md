# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot (requires environment variables)
python bot.py
```

### Required Environment Variables
- `DISCORD_TOKEN` — Bot token from the Discord developer portal
- `MONGODB_ADDRESS` — MongoDB connection string
- `IEX_PUB` — IEX Cloud API key (for stocks, if re-enabled)

### Docker
```bash
docker build . -t discord-bot
docker run -e DISCORD_TOKEN=<token> -e MONGODB_ADDRESS=<address> -e IEX_PUB=<key> discord-bot
```

## Architecture

**Entry point:** `bot.py` — Initializes the `discord.py` bot, loads all cogs from `./cogs/` (except `stocks.py`, which is explicitly excluded), and sets up an APScheduler job to post Epic Games free game links every Thursday at 11:03 AM ET.

**Cog system:** Each file in `cogs/` is a `commands.Cog` subclass auto-loaded by `bot.py`. Each cog connects to MongoDB independently using `os.environ.get('MONGODB_ADDRESS')`. There is no shared DB connection object — each cog creates its own `MongoClient` at module load time.

**MongoDB databases in use:**
- `Discord` — Image URLs for the `!discover`/`!pick` system (keyed by guild ID)
- `Discover_Images` — Temporary state for `!pick` reaction flow (keyed by guild ID)
- `Economy` — Meme bucks balances (`memeconomy.py`)
- `Ranks` — XP and level data (`ranks.py`)
- `Reactions` — Reaction given/received counts (`randomStuff.py`)
- `Logs` — Command error logs (in `bot.py`)

**Shared utilities (`Utils.py`):** `Calc` (AST-based expression evaluator), `Reel` (slot machine symbols enum), stock market hours helpers (`is_market_closed`, `pre_market_closed`, `post_market_closed`), and URL expansion helpers.

**Slots logic (`Slots.py` + `Utils.py`):** `SlotMachine` class in `Slots.py` uses the `Reel` enum from `Utils.py`. `memeconomy.py` imports both to run the `!slots` command.

**`stocks.py` is excluded from auto-loading** (hardcoded in `bot.py`'s `excluded_files` list). To re-enable it, remove `'stocks.py'` from that list. It uses Yahoo Finance's unofficial API and polls live price updates every 5 seconds while the market is open.

**`config.json`** stores the command prefix (`!`) and 8-ball responses. It is read at runtime by multiple cogs using a local `load_json()` helper (duplicated in each cog — not imported from a shared module).

**`utils/tvshows.py`** contains a utility for TV show lookups, loaded as a cog like the others.

## Key Patterns

- All collections are namespaced by `str(ctx.guild.id)` or `str(message.guild.id)`, making the bot multi-server safe.
- The `!pick` command downloads images locally to `./cogs/images/` (created on demand), combines them with Pillow, sends the combo image, then deletes the local files.
- `discord.py` version is pinned at `1.5.1` — this is an older API version. Use `client.load_extension()`, `commands.Cog`, and `ctx.history().flatten()` (not the newer async iterator pattern).
