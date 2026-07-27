<<<<<<< HEAD
# mal-search-bot

A standalone Discord bot for searching MyAnimeList content (anime/manga/movies) via
slash commands, and for posting notifications about newly announced/upcoming anime
and new episode releases for a watchlist.

This is **independent** from `mal-notify-bot` (which only posts newly-approved MAL
entries via polling). It has its own Discord application, its own bot token, its own
repo, and shares none of the other bot's polling logic. You can run both bots at the
same time in the same server without any conflict.

Data source: the [Jikan API](https://docs.api.jikan.moe/), a free/unofficial REST
wrapper around MyAnimeList. No OAuth or API key is required, which avoids MAL's
official app-approval process entirely.

## Features

- `/anime <name> [season] [year]` — search anime, optionally filtered by season/year
- `/manga <name>` — search manga
- `/movie <name>` — search anime movies (`type == Movie`), falls back to the closest
  anime match if no movie-type result is found
- `/watch <mal_id>` / `/unwatch <mal_id>` / `/watchlist` — manage the release-notification
  watchlist (requires the **Manage Server** permission)
- Background loop: posts newly-listed upcoming/announced anime to a configurable channel
- Background loop: posts "new episode airing today" notices for watchlisted anime,
  using Jikan's `/schedules` endpoint

All search commands respond with rich embeds (English title, score, status, episode/
volume counts, genres, synopsis, cover image, and a link back to the MAL page), and
defer their response so slow Jikan calls never cause a Discord interaction timeout.

## Project structure

```
mal-search-bot/
├── bot.py                  # entry point: bot setup, cog registration, command sync
├── config.py                # loads token + config.yaml / .env settings
├── config.yaml               # non-secret settings (channels, poll intervals)
├── jikan_client.py           # async Jikan API wrapper with rate limiting + retries
├── embeds.py                 # builds Discord embeds from Jikan anime/manga entries
├── storage.py                 # tiny JSON load/save helpers
├── cogs/
│   ├── search.py              # /anime, /manga, /movie
│   └── notifications.py       # background loops + /watch, /unwatch, /watchlist
├── Pipfile                    # dependencies (pipenv)
├── token.yaml.example         # copy to token.yaml (git-ignored)
├── .env.example                # copy to .env (git-ignored) — alternative to token.yaml
└── .gitignore
```

Runtime state files (`seen_upcoming.json`, `watchlist.json`, `release_state.json`) are
created automatically on first use and are git-ignored — they're local to each
deployment.

## 1. Create the Discord application & bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and
   click **New Application**. Name it something like `mal-search-bot` (this must be a
   **separate application** from `mal-notify-bot` — separate token, separate invite).
2. Under **Bot**, click **Add Bot**, then **Reset Token** to reveal and copy the bot token.
   - No privileged intents are required — this bot only uses slash commands, not the
     message content intent, and doesn't read member/presence data. Leave the
     "Privileged Gateway Intents" toggles off.
3. Under **OAuth2 → URL Generator**:
   - Scopes: `bot` and `applications.commands`
   - Bot permissions: `Send Messages`, `Embed Links`, `Use Slash Commands`
     (these correspond to permission integer `2147502080`)
   - Copy the generated URL, open it in a browser, and invite the bot to your server.

## 2. Install dependencies

This project uses `pipenv` (Pipfile-based, matching the conventions of similar
purarue-style Discord bots):

```powershell
pip install pipenv
cd mal-search-bot
pipenv install
```

Requires Python 3.11+.

## 3. Configure the bot token

Pick **one** of the following (both are supported; `.env` / `DISCORD_TOKEN` takes
precedence over `token.yaml` if both are present):

**Option A — token.yaml**
```powershell
Copy-Item token.yaml.example token.yaml
```
Edit `token.yaml` and paste your bot token as the `token:` value.

**Option B — .env**
```powershell
Copy-Item .env.example .env
```
Edit `.env` and set `DISCORD_TOKEN=...`.

Both `token.yaml` and `.env` are git-ignored — never commit your real token.

## 4. Configure notification channels

Edit `config.yaml` (or override any of these with the matching UPPER_CASE environment
variable in `.env` — env vars always win):

| Setting | Env var override | Purpose |
|---|---|---|
| `guild_id` | `GUILD_ID` | Optional: sync slash commands to a single guild instantly during development (global sync can take up to an hour to propagate) |
| `notify_channel_id` / `notify_channel_name` | `NOTIFY_CHANNEL_ID` / `NOTIFY_CHANNEL_NAME` | Channel for newly-announced/upcoming anime notifications |
| `release_channel_id` / `release_channel_name` | `RELEASE_CHANNEL_ID` / `RELEASE_CHANNEL_NAME` | Channel for new-episode notifications (falls back to the notify channel if unset) |
| `upcoming_poll_interval_hours` | `UPCOMING_POLL_INTERVAL_HOURS` | How often to poll Jikan's upcoming-seasons endpoint (default: 6) |
| `release_poll_interval_hours` | `RELEASE_POLL_INTERVAL_HOURS` | How often to poll Jikan's schedules endpoint for the watchlist (default: 24) |

`*_channel_id` takes priority over `*_channel_name` when both are set. Using the
channel ID is more robust (survives channel renames); the name lookup is a convenience
fallback that searches every guild the bot is in for a text channel with that name.

## 5. Run the bot

```powershell
pipenv run python bot.py
```

On startup the bot logs in, syncs its slash commands (`bot.tree.sync()`, or to a single
guild if `guild_id`/`GUILD_ID` is set), and starts both background notification loops.
Slash commands should appear in Discord within a few seconds (guild sync) or up to an
hour (global sync).

## Adding anime to the release watchlist

New-episode notifications only fire for anime you've explicitly added:

```
/watch <mal_id>      # e.g. /watch 52991  (requires Manage Server permission)
/watchlist            # list watched MAL IDs
/unwatch <mal_id>     # remove one
```

The MAL ID is the number in a MyAnimeList URL, e.g. `myanimelist.net/anime/52991/...`
→ `52991`.

## Notes on rate limiting

Jikan's public instance enforces roughly 3 requests/second and 60/minute.
`jikan_client.py` serializes all outbound requests through a small leaky-bucket
limiter and retries 429/5xx responses with backoff, so slash commands and the
background loops won't get throttled or crash on transient errors — API failures are
caught and surfaced as a friendly ephemeral message instead of hanging the interaction.

## Running alongside mal-notify-bot

Since this is a separate application with its own token, `Pipfile`, and process, you can
run it in parallel with `mal-notify-bot` (e.g. in a separate terminal, separate Docker
container, or separate systemd service) without any shared state or port conflicts.
=======
# DBot-Search
Discord bot created for servers in discord to use commands to search for anime and more all inside the server
>>>>>>> bf3dc9f4d72c2cbb89fe8b7418eaa0cf5a3a2736
