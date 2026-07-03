import asyncio
import logging
import discord
from discord.ext import commands

from app.config.settings import settings
from app.agent.agent import SonAgent
from app.database.session import get_db_ctx
from app.tools.todo import (
    add_todo as tool_add_todo,
    list_todos as tool_list_todos,
    complete_todo as tool_complete_todo,
    get_or_create_user,
)
from app.tools.news import get_news as tool_get_news
from app.tools.search import search_knowledge as tool_search_knowledge
from app.tools.summary import generate_daily_summary as tool_generate_daily_summary
from app.tools.search_web import search_web as tool_search_web
from app.tools.profile import setup_user_profile as tool_setup_user_profile
from app.tools.calories import (
    log_food as tool_log_food,
    get_daily_macros as tool_get_daily_macros,
)
from app.telegram.handlers import get_user_history, save_message

logger = logging.getLogger(__name__)

# Global bot instance
discord_bot = None

def get_discord_bot_instance() -> commands.Bot | None:
    """Access the global Discord bot instance."""
    return discord_bot

def split_message(text: str, limit: int = 1990) -> list[str]:
    """Split a message into chunks below the Discord character limit."""
    if not text:
        return ["I couldn't generate a response."]
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > 0:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Find last newline before limit
        split_idx = text.rfind("\n", 0, limit)
        if split_idx == -1:
            split_idx = text.rfind(" ", 0, limit)
        if split_idx == -1:
            split_idx = limit
        chunks.append(text[:split_idx])
        text = text[split_idx:].lstrip()
    return chunks

async def init_bot() -> commands.Bot | None:
    """Initializes the Discord bot, setting up intents and commands."""
    global discord_bot
    if not settings.DISCORD_BOT_TOKEN or settings.DISCORD_BOT_TOKEN == "your_discord_bot_token_here":
        logger.warning("DISCORD_BOT_TOKEN is not configured. Discord bot will not start.")
        return None

    logger.info("Initializing Discord bot application...")
    intents = discord.Intents.default()
    intents.message_content = True

    discord_bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

    # Core events
    @discord_bot.event
    async def on_ready():
        logger.info(f"Discord bot logged in successfully as {discord_bot.user}")

    @discord_bot.event
    async def on_message(message: discord.Message):
        if message.author.bot:
            return

        # 1. Process commands starting with !
        if message.content.startswith("!"):
            await discord_bot.process_commands(message)
            return

        # 2. Process DM conversations or server mentions in natural language
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = discord_bot.user.mentioned_in(message)

        if is_dm or is_mentioned:
            async with message.channel.typing():
                user_id = message.author.id
                user_msg = message.clean_content

                # Remove mention tag from prompt text if mentioned in public channel
                if is_mentioned and not is_dm:
                    # Strip the bot's username mention
                    bot_mention = f"@{discord_bot.user.name}"
                    user_msg = user_msg.replace(bot_mention, "").strip()

                with get_db_ctx() as db:
                    user = get_or_create_user(db, user_id)
                    user.username = message.author.name
                    user.first_name = message.author.global_name or message.author.name
                    db.commit()
                    history = get_user_history(db, user.id)

                agent = SonAgent(telegram_id=user_id)
                response = await asyncio.to_thread(agent.run, user_msg, history)

                with get_db_ctx() as db:
                    user = get_or_create_user(db, user_id)
                    save_message(db, user.id, "user", user_msg)
                    save_message(db, user.id, "assistant", response)

                chunks = split_message(response)
                for chunk in chunks:
                    await message.reply(chunk)

    @discord_bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("error: missing arguments for command. check `!help` for correct usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("error: invalid argument formats provided.")
        elif isinstance(error, commands.CommandNotFound):
            pass # Ignore invalid command prefixes
        else:
            logger.error(f"Discord command error in {ctx.command}: {error}", exc_info=True)
            await ctx.send(f"error: failed to execute command: {str(error)}")

    # Commands list mapping to tools
    @discord_bot.command(name="help")
    async def help_cmd(ctx):
        help_text = (
            "💡 **son discord help guide**\n\n"
            "commands:\n"
            "• `!todo add <title>`: add a task\n"
            "• `!todo list [pending|completed|all]`: filter and list tasks\n"
            "• `!todo done <id>`: mark todo complete\n"
            "• `!remind <time expression> <message>`: e.g., `!remind tomorrow 8pm gym` or `!remind in 1 hour check stove`\n"
            "• `!note [work|personal|docs] <text>`: save notes. categorize by starting with prefix `work` or `personal`, or default to `docs`\n"
            "• `!news [query]`: summarize latest news headlines\n"
            "• `!google <query>`: search the web for general answers or news\n"
            "• `!profile <weight_kg> <height_cm> [goal]`: setup calorie/protein goals (goal: bulk/cut/maintain)\n"
            "• `!eat <breakfast|lunch|dinner|snack> <calories> <protein_g> <food name>`: log food\n"
            "• `!macros [YYYY-MM-DD]`: view daily calories & macros dashboard\n"
            "• `!search <query>`: keyword search your saved notes\n"
            "• `!daily`: daily summary of completed tasks, notes, and reminders\n\n"
            "🧠 **natural language:**\n"
            "you can also DM me directly or mention me in a server: 'remember i like dark themes' or 'add buy milk to my todo list'. i will reason and use the proper tool dynamically."
        )
        await ctx.send(help_text)

    @discord_bot.group(name="todo", invoke_without_command=True)
    async def todo_group(ctx):
        await ctx.send("usage:\n`!todo add <title>`\n`!todo list [status]`\n`!todo done <id>`")

    @todo_group.command(name="add")
    async def todo_add(ctx, *, title: str = None):
        if not title:
            await ctx.send("please specify a todo title.")
            return
        res = tool_add_todo(telegram_id=ctx.author.id, title=title)
        await ctx.send(res)

    @todo_group.command(name="list")
    async def todo_list(ctx, status: str = "pending"):
        res = tool_list_todos(telegram_id=ctx.author.id, status=status)
        await ctx.send(res)

    @todo_group.command(name="done")
    async def todo_done(ctx, todo_id: int = None):
        if todo_id is None:
            await ctx.send("please specify the todo ID.")
            return
        res = tool_complete_todo(telegram_id=ctx.author.id, todo_id=todo_id)
        await ctx.send(res)

    @discord_bot.command(name="remind")
    async def remind_cmd(ctx, *, args: str = None):
        if not args:
            await ctx.send("usage: `!remind <time expression> <message>`\nexample: `!remind tomorrow 8pm gym`")
            return
        
        async with ctx.typing():
            with get_db_ctx() as db:
                user = get_or_create_user(db, ctx.author.id)
                history = get_user_history(db, user.id)
            
            agent = SonAgent(telegram_id=ctx.author.id)
            agent_prompt = f"Handle this command: !remind {args}"
            response = await asyncio.to_thread(agent.run, agent_prompt, history)
            
            with get_db_ctx() as db:
                user = get_or_create_user(db, ctx.author.id)
                save_message(db, user.id, "user", f"!remind {args}")
                save_message(db, user.id, "assistant", response)
                
        await ctx.send(response)

    @discord_bot.command(name="note")
    async def note_cmd(ctx, *, content: str = None):
        if not content:
            await ctx.send("usage: `!note [work|personal|docs] <note content>`")
            return
        res = tool_add_note(telegram_id=ctx.author.id, text=content)
        await ctx.send(res)

    @discord_bot.command(name="search")
    async def search_cmd(ctx, *, query: str = None):
        if not query:
            await ctx.send("usage: `!search <query>`")
            return
        res = tool_search_knowledge(query=query)
        await ctx.send(res)

    @discord_bot.command(name="google")
    async def google_cmd(ctx, *, query: str = None):
        if not query:
            await ctx.send("usage: `!google <search query>`")
            return
        async with ctx.typing():
            res = tool_search_web(query=query)
        await ctx.send(res)

    @discord_bot.command(name="news")
    async def news_cmd(ctx, *, query: str = "world"):
        async with ctx.typing():
            res = tool_get_news(category=query)
        await ctx.send(res)

    @discord_bot.command(name="profile")
    async def profile_cmd(ctx, weight_kg: float = None, height_cm: float = None, goal: str = "maintain", age: int = 25, gender: str = "male", activity_level: str = "active"):
        if weight_kg is None or height_cm is None:
            await ctx.send("usage: `!profile <weight_kg> <height_cm> [goal] [age] [gender] [activity_level]`\nexample: `!profile 80 180 cut`")
            return
        async with ctx.typing():
            res = tool_setup_user_profile(
                weight_kg=weight_kg,
                height_cm=height_cm,
                age=age,
                gender=gender,
                activity_level=activity_level,
                goal=goal,
                telegram_id=ctx.author.id
            )
        await ctx.send(res)

    @discord_bot.command(name="eat")
    async def eat_cmd(ctx, meal_type: str = None, calories: int = None, protein_g: float = None, *, food_name: str = None):
        if not meal_type or calories is None or protein_g is None or not food_name:
            await ctx.send("usage: `!eat <breakfast|lunch|dinner|snack> <calories> <protein_g> <food name...>`\nexample: `!eat lunch 600 45 chicken and rice`")
            return
        if meal_type not in ["breakfast", "lunch", "dinner", "snack"]:
            await ctx.send("meal type must be breakfast, lunch, dinner, or snack!")
            return
        async with ctx.typing():
            res = tool_log_food(
                food_name=food_name,
                calories=calories,
                protein_g=protein_g,
                meal_type=meal_type,
                telegram_id=ctx.author.id
            )
        await ctx.send(res)

    @discord_bot.command(name="macros")
    async def macros_cmd(ctx, date_str: str = ""):
        async with ctx.typing():
            res = tool_get_daily_macros(date_str=date_str, telegram_id=ctx.author.id)
        await ctx.send(res)

    @discord_bot.command(name="daily")
    async def daily_cmd(ctx):
        async with ctx.typing():
            res = tool_generate_daily_summary(telegram_id=ctx.author.id)
        await ctx.send(res)

    return discord_bot

async def start_discord_bot() -> None:
    """Start the Discord bot polling task loop."""
    global discord_bot
    if discord_bot is None:
        await init_bot()

    if discord_bot:
        logger.info("Starting Discord bot gateway loop...")
        try:
            await discord_bot.start(settings.DISCORD_BOT_TOKEN)
        except Exception as e:
            logger.error(f"Error starting Discord bot: {e}", exc_info=True)

async def stop_discord_bot() -> None:
    """Shuts down the Discord bot client gracefully."""
    global discord_bot
    if discord_bot and not discord_bot.is_closed():
        logger.info("Stopping Discord bot client connection...")
        await discord_bot.close()
        logger.info("Discord bot shutdown complete.")
