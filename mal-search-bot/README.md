# mal-search-bot

A standalone Discord bot for searching MyAnimeList (MAL) content via slash commands,
powered by the free, unauthenticated [Jikan API](https://docs.api.jikan.moe/). No MAL
Client ID, OAuth, or API key is required.

This bot is fully independent — its own Discord application/token, its own process. It
shares no code or runtime state with any other bot.

## Features

- `/anime name:<string> [season] [year]` — search for an anime. If both `season` and
  `year` are given, queries Jikan's seasonal endpoint and matches by name; if only `year`
  is given, filters search results by aired year.
- `/manga name:<string>` — search for a manga.
- `/movie name:<string>` — search anime results restricted to `type == "Movie"`, falling
  back to the closest anime match (with a note) if no movie is found.
- Rich embeds: English title (falls back to the default MAL title), score, status,
  episode/volume/chapter counts, genres, synopsis (truncated to fit embed limits), cover
  art, and a clickable MAL link.
- A dropdown (`discord.ui.Select`) to switch between up to 5 additional matches when a
  search returns more than one strong result. The dropdown auto-disables after 60 seconds.
- Async, non-blocking HTTP via `aiohttp`, with a leaky-bucket rate limiter respecting
  Jikan's ~3 req/sec, 60 req/min limits, `Retry-After`-aware 429 handling, and exponential
  backoff for 5xx errors/timeouts.
- No privileged Discord intents required (Message Content and Server Members are off) —
  this bot only uses slash commands.
- Centralized, environment-based configuration — no hardcoded secrets.
- Structured logging for startup, command usage, and Jikan API errors.

## Project Structure

```
mal-search-bot/
  bot.py                    # Entry point: bot setup, command registration/sync, Jikan lifecycle
  config.py                 # Centralized env-based config loading (DISCORD_TOKEN, GUILD_ID, etc.)
  commands/
    __init__.py
    anime.py                 # /anime command
    manga.py                 # /manga command
    movie.py                 # /movie command
  services/
    __init__.py
    jikan_client.py           # Rate-limited, retrying async Jikan API client
  ui/
    __init__.py
    result_select.py           # Disambiguation dropdown/view + shared reply helper
  utils/
    __init__.py
    embed_builder.py            # Embed builders + title/genre/synopsis formatting helpers
  requirements.txt             # pip dependencies
  Pipfile / Pipfile.lock        # pipenv dependencies (equivalent, for pipenv users)
  .env.example                  # template for .env (copy, don't commit the real one)
  .gitignore
  README.md
```

## Requirements

- Python 3.11+
- Either `pip` + `venv`, or [pipenv](https://pipenv.pypa.io/)

## 1. Create the Discord Application & Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and
   click **New Application**. Name it (e.g. "MAL Search Bot").
2. In the left sidebar, go to **Bot** and click **Add Bot** (or it may already exist).
3. Under **Privileged Gateway Intents**, leave everything **off**:
   - Presence Intent: off
   - Server Members Intent: off
   - Message Content Intent: off

   This bot only responds to slash commands, so no privileged intents are needed.
4. Click **Reset Token** to reveal/generate the bot token, and copy it — you'll need it for
   `.env` below. Keep this secret; never commit it.

## 2. Invite the Bot to Your Server

Build an invite URL using scopes `bot` and `applications.commands`, with permission integer
`2147502080` (Send Messages + Embed Links + Use Application Commands):

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=2147502080&scope=bot%20applications.commands
```

Replace `YOUR_APPLICATION_ID` with your application's **Application ID** (found on the
**General Information** page of the Developer Portal). Open the URL in a browser and add
the bot to your server.

## 3. Install Dependencies

From the `mal-search-bot/` directory, using **pip**:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Or using **pipenv**:

```powershell
pipenv install
```

## 4. Configure Environment Variables

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```
DISCORD_TOKEN=your-actual-bot-token
```

`.env` is already listed in `.gitignore` and will never be committed.

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | Yes | — | Your bot's Discord token. |
| `GUILD_ID` | No | unset (global sync) | Dev guild ID for instant slash-command sync. |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `JIKAN_BASE_URL` | No | `https://api.jikan.moe/v4` | Jikan API base URL. |
| `JIKAN_RATE_LIMIT_PER_SECOND` | No | `3` | Max Jikan requests per rolling second. |
| `JIKAN_RATE_LIMIT_PER_MINUTE` | No | `60` | Max Jikan requests per rolling minute. |
| `JIKAN_MAX_RETRIES` | No | `3` | Max retries for Jikan 5xx errors/timeouts. |

Setting `GUILD_ID` to your server's ID makes slash commands appear instantly while
developing (global sync can take up to an hour to propagate). Leave it unset for a
global sync.

## 5. Run the Bot

With pip/venv:

```powershell
python bot.py
```

With pipenv:

```powershell
pipenv run python bot.py
```

On startup, the bot will:
1. Open its shared `aiohttp` session for calling the Jikan API.
2. Register the `/anime`, `/manga`, and `/movie` slash commands.
3. Sync commands (to `GUILD_ID` if set, otherwise globally).
4. Log in and start listening for interactions.

Press `Ctrl+C` to stop it; the Jikan HTTP session is closed cleanly on shutdown.

## Usage Examples

```
/anime name:Frieren
/anime name:One Piece season:fall year:1999
/anime name:Attack on Titan year:2013

/manga name:Berserk

/movie name:Your Name
/movie name:Spirited Away
```

If a search matches more than one title, the top match is shown as the main embed, and a
dropdown below it lets you switch to any of the other matches (up to 5 extra). The
dropdown automatically disables itself after 60 seconds of inactivity.

## Manual Test Checklist

- [ ] `/anime name:Frieren` — returns an embed with English title, score, status,
      episodes, season/year, genres, synopsis, and cover image.
- [ ] `/anime name:Naruto` — returns multiple matches; dropdown appears below the embed
      and lets you switch to a different result; dropdown disables after 60s idle.
- [ ] `/anime name:One Piece season:fall year:1999` — seasonal lookup returns the 1999
      One Piece entry specifically.
- [ ] `/anime name:qwidfjqwoifjqwoifj` (gibberish) — replies ephemerally with
      "No anime found matching '...'".
- [ ] `/manga name:Berserk` — returns an embed with volumes/chapters, genres, synopsis.
- [ ] `/manga name:qwidfjqwoifjqwoifj` — ephemeral "No manga found" message.
- [ ] `/movie name:Your Name` — returns the movie-type entry.
- [ ] `/movie name:<anime with no movie release>` — falls back to the closest anime
      match with a "no movie match was found" note in the embed footer.
- [ ] Trigger a Jikan outage/timeout (e.g. temporarily point `JIKAN_BASE_URL` at an
      invalid host) — command replies ephemerally with a friendly error instead of
      hanging or crashing the bot.

## Rate Limiting & Reliability

- Requests to Jikan are throttled by a leaky-bucket rate limiter tracking timestamps in a
  rolling window, respecting Jikan's ~3 requests/second and 60 requests/minute limits.
- HTTP 429 responses are retried after waiting for the duration in the `Retry-After`
  header.
- HTTP 5xx responses and network timeouts are retried with exponential backoff (up to
  `JIKAN_MAX_RETRIES`).
- All Jikan errors are wrapped in a `JikanAPIError` and surfaced to the user as a friendly
  ephemeral message instead of leaving the interaction hanging or crashing the bot.
- Slash command handlers `defer()` immediately (Jikan calls can exceed Discord's 3-second
  response window) and reply via `followup.send()`.

## Troubleshooting

- **Commands don't show up**: if you didn't set `GUILD_ID`, global command sync can take
  up to an hour. Set `GUILD_ID` in `.env` for instant sync during development.
- **"Configuration error: DISCORD_TOKEN environment variable is not set"**: make sure
  `.env` exists (copied from `.env.example`) and contains a real token, or that
  `DISCORD_TOKEN` is set in your shell environment.
- **429 / rate limit warnings in logs**: expected occasionally under heavy use; the bot
  automatically waits and retries.
