# son

your personal assistant that actually does stuff. no corporate fluff, no bloated ui, just a telegram bot running on python 3.12+ that manages your life and runs local/cloud llms with custom tools.

it has an agent reasoning loop under the hood, meaning it doesn't just match keywords. it actually thinks, chooses the right tools, compiles the response, and keeps track of what you told it.

---

## features

### 🧠 agent reasoning loop
- powered by ollama (defaults to `qwen2.5:7b`) or gemini (if you provide an api key).
- runs up to 6 iterations per message, so it can call a tool, look at the result, and decide if it needs to call another one before replying to you.

### 📝 markdown notes
- save notes via chat or `/note`.
- automatically classifies them into categories like `work`, `personal`, or `docs`.
- dumps them as clean markdown files in the `knowledge/` directory so you actually own your data.

### 🏋️ calorie & macro tracking
- setup your profile with `/profile <weight> <height> [goal]`. it calculates your bmr, tdee, daily calorie and protein targets (e.g., bulk/cut/maintain).
- log what you eat using `/eat <meal_type> <calories> <protein> <food_name>` or just tell the agent.
- run `/macros` to see a nice visual progress bar of your daily intake.

### ⏳ smart reminders
- schedule reminders using natural language (e.g., `/remind in 2 hours check the oven` or `/remind tomorrow 8pm hit the gym`).
- background scheduler polls every minute to push notifications to your telegram.

### 📋 todos
- simple task list managed right inside telegram or through fastapi.
- add, check off, or list your tasks.

### 🌐 web search & scrape
- searches duckduckgo (no api keys needed, parses html directly) for real-time info.
- can fetch and scrape raw text from any webpage (up to 3000 chars) to answer complex queries.

### 📰 news feeds
- fetches news from google news rss based on whatever search query you want.

### 📂 local filesystem access
- read text files and list directory contents on your local laptop.
- supports path expansion (e.g., `~/documents` or relative/absolute paths) and line capping to prevent context overflow.

### 🌅 daily summary
- run `/daily` to get a neat summary of everything you did in the last 24 hours: completed tasks, scheduled reminders, and notes created.

---

## directory layout

here's where everything lives:

- `app/`
  - `agent/` — the core `SonAgent` reasoning loop and system prompts
  - `api/` — fastapi routes to fetch todos/notes programmatically or do health checks
  - `config/` — pydantic settings for loading env variables
  - `database/` — sqlalchemy models (users, todos, food logs, notes) and sqlite session setup
  - `scheduler/` — background task configuration via apscheduler for triggering due reminders
  - `telegram/` — command handlers, bot polling logic, and telegram integration
  - `tools/` — all the functions the agent can run (macros, web scraping, notes, etc.)
- `alembic/` — db migrations database history
- `data/` — directory where your local sqlite database is stored

---

## setup

### 1. clone & install dependencies
make sure you have python 3.12+ and `uv` installed. then install the packages:

```bash
uv sync
```

### 2. environment config
copy the example env file:

```bash
cp .env.example .env
```

open `.env` and fill out your variables:
- `TELEGRAM_BOT_TOKEN`: get this from [@botfather](https://t.me/botfather).
- `DISCORD_BOT_TOKEN`: (optional) get a bot token from the discord developer portal.
- `OLLAMA_BASE_URL`: point this to your local ollama instance (defaults to `http://localhost:11434/v1`).
- `MODEL`: the ollama model name (e.g., `qwen2.5:7b`).
- `DATABASE_URL`: connection string for sqlite (`sqlite:///data/hermes.db`).
- `GEMINI_API_KEY`: (optional) if you want to use gemini instead of local ollama, paste your api key here.

### 3. start the assistant

just run main:

```bash
uv run main.py
```

*note: database migrations run automatically on startup using alembic, so no need to run migration commands manually.*

---

## discord setup notes
if you want to run the discord bot:
1. create an application on the [discord developer portal](https://discord.com/developers/applications).
2. add a bot user to the application, copy the bot token, and paste it under `DISCORD_BOT_TOKEN` in your `.env`.
3. **important:** scroll down in the bot tab and toggle **message content intent** to enabled so the bot can read commands and chat prompts.
4. generate an invite link under oauth2 -> url generator (select scopes: `bot` and permissions: `send messages`, `read message history`). invite the bot to your server.

---

## assistant commands

you can talk to the bot in natural language, or use these commands directly (**`/`** prefix for telegram, **`!`** prefix for discord):

| command (tg / discord) | description | example |
| --- | --- | --- |
| `/start` | registers you and shows welcome screen | `/start` |
| `/help` / `!help` | shows the help menu | `!help` |
| `/todo add` / `!todo add <title>` | adds a task to your checklist | `/todo add buy milk` |
| `/todo list` / `!todo list` | lists pending/completed/all tasks | `/todo list pending` |
| `/todo done` / `!todo done <id>` | completes a task by its database id | `/todo done 1` |
| `/remind` / `!remind <time> <msg>` | schedules a reminder notification | `/remind tomorrow 8pm gym` |
| `/note` / `!note <text>` | saves a note (prefix `work` or `personal` to force category) | `/note work discuss project goals` |
| `/search` / `!search <query>` | searches your notes for a keyword | `/search project` |
| `/google` / `!google <query>` | searches the web for live answers | `/google who won the game last night` |
| `/profile` / `!profile <w> <h> <g>` | sets up your body profile & goals | `/profile 80 180 cut` |
| `/eat` / `!eat <meal> <cal> <p> <name>` | logs food eaten | `/eat lunch 600 40 chicken rice` |
| `/macros` / `!macros` | shows calorie/protein progress bar dashboard | `/macros` |
| `/daily` / `!daily` | summarizes your last 24h activity | `/daily` |
| (natural language) | lists files in any folder on your laptop | `show me what is in ~/downloads` |
| (natural language) | reads the content of a local file | `read main.py` |

---

## api endpoints
if you want to hook up other services, fastapi serves these endpoints on port `8000`:
- `GET /health` — simple health check
- `GET /todos` — lists all todos in the system
- `POST /todo` — create a new todo programmatically
- `GET /notes` — lists all notes metadata
