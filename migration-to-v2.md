# discord.py v1.5.1 → v2.x Migration Plan

## Already Done

- **Python 3.13**: `runtime.txt` and `Dockerfile` updated to Python 3.13
- **`requirements.txt`**: packages updated for Python 3.13 compatibility (see below for what changed and why)

---

## Install

```
pip install -U -r requirements.txt
```

---

## Files to Delete

These are being dropped entirely — do not migrate them:

| File | Notes |
|---|---|
| `cogs/covid.py` | |
| `cogs/discover.py` | |
| `cogs/food.py` | |
| `cogs/memeconomy.py` | |
| `cogs/polls.py` | |
| `cogs/ranks.py` | |
| `cogs/stocks.py` | Was already excluded from loading in `bot.py` |
| `cogs/topMessages.py` | |
| `cogs/waitTimes.py` | |
| `Slots.py` | Only used by `memeconomy.py` |

---

## Breaking Changes Required

### 1. `bot.py` — Bot initialization: pass `intents` explicitly (now required)

`intents` is already created but never passed to `commands.Bot`. In v2 this is a hard requirement.

```python
# before
intents = Intents.all()
client = commands.Bot(command_prefix=load_json('prefix'), case_insensitive=True)

# after
intents = Intents.all()
client = commands.Bot(command_prefix=load_json('prefix'), case_insensitive=True, intents=intents)
```

---

### 2. `bot.py` — Cog/extension loading must move to `setup_hook`

`load_extension` is now async and must be awaited. The module-level `for` loop won't work. The correct v2 pattern is a `setup_hook` coroutine on the Bot class. Since the deleted cogs are gone from disk, the `excluded_files` list in `bot.py` can be removed entirely.

```python
# before (module level, synchronous)
excluded_files = ['stocks.py']
for filename in os.listdir('./cogs'):
    if filename.endswith('.py') and filename not in excluded_files:
        client.load_extension(f'cogs.{filename[:-3]}')

# after (inside a Bot subclass)
class Bot(commands.Bot):
    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')

client = Bot(command_prefix=load_json('prefix'), case_insensitive=True, intents=intents)
```

---

### 3. Remaining cog files — `setup()` must be `async def` and `add_cog` must be awaited

```python
# before
def setup(client):
    client.add_cog(MyCog(client))

# after
async def setup(client):
    await client.add_cog(MyCog(client))
```

Files to update:
- `cogs/counting.py`
- `cogs/futurama.py`
- `cogs/memes.py`
- `cogs/randomStuff.py`
- `cogs/simpsons.py`
- `cogs/tiktok.py`
- `cogs/youtube.py`
- `utils/tvshows.py`

---

### 4. `counting.py` — `.flatten()` is removed

Same issue as the now-deleted `discover.py`. `channel.history().flatten()` must be replaced.

```python
# before
messages = await channel.history(limit=3).flatten()

# after
messages = [m async for m in channel.history(limit=3)]
```

---

### 5. `dispander` — likely incompatible with discord.py 2.x

`randomStuff.py` calls `await dispand(message)` in `on_message`. `dispander` is itself a discord.py wrapper and was almost certainly written against v1.x. After upgrading, test whether it works. If it breaks, the `await dispand(message)` call in `randomStuff.py` should be removed (it expands Discord message links — the mobile link conversion below it can stay).

---

## Additional Recommendations

### Clean up `bot.py` error handler

`on_command_error` has specific `BadArgument` branches for `discover`, `pay`, `deposit`, and `slots` — all from deleted cogs. Those dead branches should be removed.

### Clean up `requirements.txt`

These packages are no longer needed after the deletions:

| Package | Reason |
|---|---|
| `youtube-dl` | Imported in `tiktok.py` but never actually called — `yt_dlp` is used instead. `youtube-dl` is also unmaintained. |
| `Pillow>=8.2.0` | Only used by `discover.py` (deleted) |
| `numpy>=1.21.3` | Only used by `Slots.py` (deleted) |
| `num2words==0.5.10` | Only used by `memeconomy.py` (deleted) |
| `holidays==0.10.5.2` | Only used by the market hours functions in `Utils.py` (being deleted) |
| `us~=2.0.1` | Only used by `waitTimes.py` (deleted) |
| `fuzzywuzzy==0.18.0` | Only used by `waitTimes.py` (deleted) |
| `python-Levenshtein==0.12.0` | Companion to fuzzywuzzy (deleted) |

### Add missing environment variables to README

`memes.py` and `tiktok.py` both use `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` but these aren't documented in the README alongside the other required env vars.

### Python version inconsistency

`runtime.txt` specifies Python 3.9.4 but `Dockerfile` uses `python:3.8.4`. Both are EOL. Worth aligning them and upgrading to 3.11 or 3.12.

---

## What You Get After Upgrading discord.py

- **Native thread support**: `guild.threads`, `channel.threads`, look up threads by name — no more hardcoding thread IDs if you don't want to.
- **`on_presence_update`**: presence/status changes split out from `on_member_update`.
- **Slash commands / app commands**: `discord.app_commands` module available.

---

## Order of Operations

1. Delete the files listed above
2. Update `requirements.txt` (remove unused packages per recommendations above)
3. Update `bot.py` (intents + `setup_hook`, remove `excluded_files`, clean up error handler)
4. Update `setup()` in the 8 remaining cog files
5. Fix `.flatten()` in `counting.py`
6. Run the bot and check console output — each cog prints its own ready message so you can see what loaded
7. Test `!futurama` and `!simpsons` — verify `compuglobal` works on Python 3.13
8. Test `dispander` in `randomStuff.py` — if Discord message link expansion is broken, remove the `await dispand(message)` line