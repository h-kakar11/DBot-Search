# mal-search-bot

A standalone Discord bot for searching MyAnimeList (MAL) content via slash commands,
powered by the free, unauthenticated [Jikan API](https://docs.api.jikan.moe/).

This bot is fully independent — its own Discord application/token, its own repo, its own
process. It shares no code or state with any other bot.

## Features

- `/anime <name> [season] [year]` — search for an anime, optionally filtered/searched by
  season + year (uses Jikan's seasonal endpoint when both are given).
- `/manga <name>` — search for a manga.
- `/movie <name>` — search for an anime movie specifically (falls back to the closest
  anime match if no movie is found).
- Rich embeds with title, score, status, episode/volume counts, genres, synopsis, and
  cover art.
- A dropdown menu to switch between multiple search matches when more than one result
  is found.
- No privileged Discord intents required (Message Content and Server Members are off) —
  this bot only uses slash commands.

## Requirements

- Python 3.11+
- [pipenv](https://pipenv.pypa.io/) for dependency management

## 1. Create the Discord Application & Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and
   click **New Application**. Name it (e.g. "MAL Search Bot").
2. In the left sidebar, go to **Bot** and click **Add Bot** (or it may already exist).
3. Under **Privileged Gateway Intents**, leave everything **off**:
   - Presence Intent: off
   - Server Members Intent: off
   - Message Content Intent: off

   This bot only responds to slash commands, so it does not need any privileged intents.
4. Click **Reset Token** to reveal/generate the bot token, and copy it — you'll need it for
   `token.yaml` or `.env` below. Keep this secret.

## 2. Invite the Bot to Your Server

Build an invite URL using scopes `bot` and `applications.commands`, with permission integer
`2147502080` (Send Messages + Embed Links + Use Application Commands):

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=2147502080&scope=bot%20applications.commands
```

Replace `YOUR_APPLICATION_ID` with your application's **Application ID** (found on the
**General Information** page of the Developer Portal). Open the URL in a browser and add
the bot to your private server.

## 3. Install Dependencies

From the `mal-search-bot/` directory:

```powershell
pipenv install
```

This reads the `Pipfile` and installs `discord.py`, `aiohttp`, `pyyaml`, and
`python-dotenv` into a dedicated virtual environment.

## 4. Configure the Bot Token

Choose **one** of the following (both are supported; `.env`/`DISCORD_TOKEN` takes priority
if both are present):

**Option A — token.yaml:**

```powershell
Copy-Item token.yaml.example token.yaml
```

Edit `token.yaml` and paste your bot token:

```yaml
token: "your-actual-bot-token"
```

**Option B — .env:**

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```
DISCORD_TOKEN=your-actual-bot-token
```

Both `token.yaml` and `.env` are already listed in `.gitignore` and will never be
committed.

## 5. (Optional) Fast Command Sync for Development

Slash commands synced globally can take up to an hour to appear. For instant sync while
developing, set `guild_id` in `config.yaml` to your server's ID:

```yaml
guild_id: 123456789012345678
```

Leave it as `null` for a global sync (recommended once you're done testing, or for
production use across a single private server it's still fine to keep it set).

You can also override this with the `GUILD_ID` environment variable.

## 6. Run the Bot

```powershell
pipenv run python bot.py
```

On startup, the bot will:
1. Open its shared `aiohttp` session for calling the Jikan API.
2. Load the search cog (`/anime`, `/manga`, `/movie`).
3. Sync slash commands (to `guild_id` if set, otherwise globally).
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

## Project Structure

```
mal-search-bot/
  bot.py              # Entry point: bot setup, Jikan client lifecycle, command sync
  config.py           # Token + config loading (env vars > token.yaml / config.yaml)
  config.yaml         # Non-secret settings (guild_id, rate limits, etc.)
  jikan_client.py      # Rate-limited async Jikan API wrapper with retry/backoff
  embeds.py            # Embed builders for anime/manga results
  cogs/
    __init__.py
    search.py          # /anime, /manga, /movie commands + disambiguation dropdown
  Pipfile              # pipenv dependencies
  Pipfile.lock          # pinned dependency versions (generated by pipenv)
  token.yaml.example    # template for token.yaml (copy, don't commit the real one)
  .env.example          # template for .env (copy, don't commit the real one)
  .gitignore
  README.md
```

## Rate Limiting & Reliability

- Requests to Jikan are throttled by a leaky-bucket rate limiter tracking timestamps in a
  rolling window, respecting Jikan's ~3 requests/second and 60 requests/minute limits.
- HTTP 429 responses are retried after waiting for the duration in the `Retry-After`
  header.
- HTTP 5xx responses and network timeouts are retried with exponential backoff (up to
  `max_retries`, configurable in `config.yaml`).
- All Jikan errors are wrapped in a `JikanAPIError` and surfaced to the user as a friendly
  ephemeral message instead of leaving the interaction hanging or crashing the bot.

## Troubleshooting

- **Commands don't show up**: if you didn't set `guild_id`, global command sync can take
  up to an hour. Set `guild_id` in `config.yaml` for instant sync during development.
- **"No Discord bot token found" error**: make sure `token.yaml` or `.env` exists (copied
  from the `.example` file) and contains a real token, or that `DISCORD_TOKEN` is set in
  your environment.
- **429 / rate limit warnings in logs**: expected occasionally under heavy use; the bot
  automatically waits and retries.
