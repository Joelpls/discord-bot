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
| `cogs/covid.py` | ✅ Deleted |
| `cogs/discover.py` | **Kept but excluded from loading** — added to `excluded_files` in `bot.py`. Not a migration priority. A replacement will be built later. |
| `cogs/food.py` | ✅ Deleted |
| `cogs/memeconomy.py` | ✅ Deleted |
| `cogs/polls.py` | ✅ Deleted |
| `cogs/ranks.py` | ✅ Deleted |
| `cogs/stocks.py` | ✅ Deleted |
| `cogs/topMessages.py` | ✅ Deleted |
| `cogs/waitTimes.py` | ✅ Deleted |
| `Slots.py` | ✅ Deleted |

Also update `Dockerfile` — remove `COPY Slots.py /` line (file no longer exists). ✅ Done

---

## Breaking Changes Required

### 1. `bot.py` — Bot initialization: pass `intents` explicitly (now required) ✅ Done

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

### 2. `bot.py` — Cog/extension loading must move to `setup_hook` ✅ Done

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

**Note:** The APScheduler setup in `on_ready` can stay as-is, but `on_ready` can fire multiple times on reconnects. Consider moving the `scheduler.start()` and `scheduler.add_job(...)` calls into `setup_hook` instead so the scheduler is only initialized once.

---

### 3. Remaining cog files — `setup()` must be `async def` and `add_cog` must be awaited ✅ Done

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
- `utils/tvshows.py` — **note**: `tvshows.py` has no `setup()` function. It's a base class imported by futurama.py and simpsons.py, not loaded as an extension. No change needed here.

---

### 4. `counting.py` — `.flatten()` is removed ✅ Done

`AsyncIterator.flatten()` no longer exists in discord.py 2.x. Replace with an async list comprehension.

```python
# before
messages = await channel.history(limit=3).flatten()

# after
messages = [m async for m in channel.history(limit=3)]
```

---

### 5. `bot.py` — `datetime.datetime.utcnow()` is deprecated ✅ Done

`utcnow()` was deprecated in Python 3.12 and emits `DeprecationWarning` on Python 3.13. It returns a naive datetime which is error-prone. The `print_log` function in `bot.py` uses it.

```python
# before
utc_time = datetime.datetime.utcnow()

# after
utc_time = datetime.datetime.now(datetime.timezone.utc)
```

---

### 6. `Utils.py` — `ast.Num` and `visit_Num` are deprecated (removed in Python 3.14)

The `Calc` class uses `visit_Num(self, node): return node.n`. In Python 3.12+, `ast.Num` is deprecated; in Python 3.14 it will be removed and `visit_Num` will never be called. On Python 3.13 this still works but emits a `DeprecationWarning`. The fix:

```python
# before
def visit_Num(self, node):
    return node.n

# after
def visit_Constant(self, node):
    return node.value
```

This is not blocking for Python 3.13 but **will break on Python 3.14**. Worth fixing now.

---

### 7. ~~`dispander` — incompatible with discord.py 2.x~~ ✅ Done

Removed `dispander` from `requirements.txt`, removed the import, the `await dispand(message)` call, the entire `on_message` listener (including the mobile link conversion), and the now-unused `import re` from `randomStuff.py`.

---

### 8. `tiktok.py` — remove dead `youtube_dl` import

`tiktok.py` line 3 imports `youtube_dl` but never uses it (all actual downloading uses `yt_dlp`). Remove the import — `youtube-dl` is also being removed from `requirements.txt`.

---

## Additional Recommendations

### Clean up `bot.py` error handler ✅ Done

`on_command_error` has specific `BadArgument` branches for `discover`, `pay`, `deposit`, and `slots` — all from deleted cogs. Those dead branches should be removed.

### Clean up `requirements.txt` ✅ Done

| Package | Status |
|---|---|
| ~~`youtube-dl`~~ | ✅ Removed |
| `Pillow>=8.2.0` | ✅ Commented out (used by `discover.py`, re-enable when discover returns) |
| ~~`numpy>=1.21.3`~~ | ✅ Removed (`Slots.py` deleted) |
| ~~`num2words==0.5.10`~~ | ✅ Removed (`memeconomy.py` deleted) |
| ~~`holidays==0.10.5.2`~~ | ✅ Removed |
| ~~`us~=2.0.1`~~ | ✅ Removed (`waitTimes.py` deleted) |
| ~~`fuzzywuzzy==0.18.0`~~ | ✅ Removed (`waitTimes.py` deleted) |
| ~~`python-Levenshtein==0.12.0`~~ | ✅ Removed |
| ~~`dispander`~~ | ✅ Removed |
| ~~`requests-cache>=1.2.0`~~ | ✅ Removed |
| ~~`pandas`~~ | ✅ Removed |
| ~~`urlexpander`~~ | ✅ Removed (also remove `import urlexpander` from `tiktok.py`) |
| ~~`brotli`~~ | ✅ Removed |

### `compuglobal` compatibility

`compuglobal` v0.2.7 (latest) depends only on `requests` and `aiohttp` — it has **no dependency on discord.py** so the v2 upgrade doesn't affect it. Its classifiers list Python 3.6–3.10 but it has no `python_requires` constraint and its dependencies are simple, so it will likely work on Python 3.13. Test `!futurama` and `!simpsons` after upgrading to verify.

### `tvshows.py` — `self.bot.LOGGING` may crash

`tvshows.py` line 24 references `self.bot.LOGGING` in the error handler for `APIPageStatusError`. If the bot object doesn't have a `LOGGING` attribute, this will raise `AttributeError` at runtime. Check whether this was set up somewhere in the deleted cogs or if it was always broken.

### `pytz` is deprecated for new Python

`pytz==2020.1` is used in `Utils.py`. Since Python 3.9, the standard library `zoneinfo` module replaces `pytz`. On Python 3.13, `pytz` still works but is considered legacy. Since you're keeping `Utils.py` as-is this isn't blocking, but it's worth knowing for future work.

### Add missing environment variables to README

`memes.py` and `tiktok.py` both use `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` but these aren't documented in the README alongside the other required env vars.

### Python version inconsistency — FIXED

`runtime.txt` and `Dockerfile` have already been updated to Python 3.13.

---

## What You Get After Upgrading discord.py

- **Native thread support**: `guild.threads`, `channel.threads`, look up threads by name — no more hardcoding thread IDs if you don't want to.
- **`on_presence_update`**: presence/status changes split out from `on_member_update`.
- **Slash commands / app commands**: `discord.app_commands` module available.

---

## Order of Operations

1. ✅ Create a git branch for the migration
2. ✅ Delete the cog files and `Slots.py` listed above
3. ✅ Update `Dockerfile` (remove `COPY Slots.py /` line)
4. ✅ Update `requirements.txt` (remove unused packages)
5. ✅ Remove `dispander` and `on_message` listener from `randomStuff.py`
6. ✅ Update `bot.py`:
   - Pass `intents=intents` to `commands.Bot`
   - Refactor to `Bot` subclass with `setup_hook` for extension loading
   - Move scheduler init from `on_ready` to `setup_hook` (avoids double-fire on reconnect)
   - Clean up dead `BadArgument` branches in error handler
   - Replace `datetime.datetime.utcnow()` with `datetime.datetime.now(datetime.timezone.utc)`
   - Remove unused `from itertools import cycle` import
7. ✅ Update `setup()` in the 7 remaining cog files (not `tvshows.py` — it has no `setup()`)
8. ✅ Fix `.flatten()` in `counting.py`
9. Remove `import youtube_dl` and `import urlexpander` from `tiktok.py`
10. Fix `visit_Num` → `visit_Constant` in `Utils.py`
11. Run the bot and check console output — each cog prints its own ready message so you can see what loaded
12. Test `!futurama` and `!simpsons` — verify `compuglobal` works on Python 3.13
13. Test `!calc` — verify the `visit_Constant` fix works