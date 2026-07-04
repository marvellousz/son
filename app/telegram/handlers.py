import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from app.tools.todo import (
    add_todo as tool_add_todo,
    list_todos as tool_list_todos,
    complete_todo as tool_complete_todo,
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
from app.agent.agent import SonAgent
from app.tools.clipboard import (
    get_clipboard_history as tool_get_clipboard,
    write_to_clipboard as tool_write_clipboard,
)
from app.tools.filesystem import (
    fuzzy_find_local_file as tool_find_files,
    send_local_file as tool_send_file,
)
from app.database.session import get_db_ctx
from app.database.models import Conversation
from app.tools.todo import get_or_create_user

logger = logging.getLogger(__name__)


async def safe_reply_markdown(update: Update, text: str) -> None:
    """Send a markdown message to the user, falling back to plain text if formatting is invalid."""
    import re
    
    # Escape underscores that are outside of backticks (code blocks / inline code)
    parts = text.split("`")
    for i in range(len(parts)):
        if i % 2 == 0:
            parts[i] = re.sub(r'(?<!\\)_', r'\_', parts[i])
    escaped_text = "`".join(parts)

    try:
        await update.message.reply_text(escaped_text, parse_mode="Markdown")
    except BadRequest as e:
        if "Can't parse entities" in str(e) or "can't parse" in str(e).lower():
            logger.warning(
                f"Markdown parsing failed for text, falling back to plain text. Error: {e}"
            )
            clean_text = text.replace("*", "").replace("_", "").replace("`", "")
            await update.message.reply_text(clean_text)
        else:
            raise e



def get_user_history(db, user_id: int, limit: int = 10) -> list:
    """Retrieve the last N messages for conversation memory."""
    history = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.asc())
        .all()
    )

    # Slice the last N messages
    last_messages = history[-limit:] if len(history) > limit else history

    return [{"role": msg.role, "content": msg.content} for msg in last_messages]


def save_message(db, user_id: int, role: str, content: str) -> None:
    """Save a single message to persistent database memory."""
    msg = Conversation(user_id=user_id, role=role, content=content)
    db.add(msg)
    db.commit()


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command. Registers the user."""
    tg_user = update.effective_user
    if not tg_user:
        return

    with get_db_ctx() as db:
        user = get_or_create_user(db, tg_user.id)
        if tg_user.username:
            user.username = tg_user.username
        if tg_user.first_name:
            user.first_name = tg_user.first_name
        db.commit()

    welcome_text = (
        f"👋 Hello {tg_user.first_name or 'there'}!\n\n"
        "I am **Son**, your personal AI operating assistant.\n"
        "I run locally and can help you organize your life using integrated tools.\n\n"
        "💬 You can chat with me normally, or use these commands:\n"
        "• `/todo add <title>` - Add a new task\n"
        "• `/todo list` - List pending tasks\n"
        "• `/todo done <id>` - Complete a task\n"
        "• `/remind <time> <text>` - Schedule a notification (e.g. `in 2 hours call Mom`)\n"
        "• `/note <text>` - Save a markdown note (auto-categorized)\n"
        "• `/news [query]` - Fetch latest news (e.g. `/news sports`)\n"
        "• `/google <query>` - Search the web for real-time answers\n"
        "• `/profile <weight> <height> [goal]` - Set up calorie & protein goals\n"
        "• `/eat <meal> <cal> <prot> <food>` - Log food eaten (breakfast/lunch/dinner/snack)\n"
        "• `/macros` - View daily calorie & protein progress bars\n"
        "• `/search <query>` - Keyword search in your notes\n"
        "• `/daily` - Generate a summary of your day\n"
        "• `/help` - Show this guide"
    )
    await safe_reply_markdown(update, welcome_text)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = (
        "💡 **Son Help Guide**\n\n"
        "Commands:\n"
        "• `/todo add <title>`: Add a task\n"
        "• `/todo list [pending|completed|all]`: Filter and list tasks\n"
        "• `/todo done <id>`: Mark todo complete\n"
        "• `/remind <time expression> <message>`: E.g., `/remind tomorrow 8pm gym` or `/remind in 1 hour check stove`\n"
        "• `/note [work|personal|docs] <text>`: Save notes. Categorize by starting with prefix `work` or `personal`, or default to `docs`\n"
        "• `/news [query]`: Summarize latest news headlines\n"
        "• `/google <query>`: Search the web for general answers or news\n"
        "• `/profile <weight_kg> <height_cm> [goal]`: Setup calorie/protein goals (goal: bulk/cut/maintain)\n"
        "• `/eat <breakfast|lunch|dinner|snack> <calories> <protein_g> <food name>`: Log food\n"
        "• `/macros [YYYY-MM-DD]`: View daily calories & macros dashboard\n"
        "• `/search <query>`: Keyword search your saved notes\n"
        "• `/daily`: Daily summary of completed tasks, notes, and reminders\n\n"
        "🧠 **Son Natural Language:**\n"
        "You can also tell me items directly: 'remember I like dark themes' or 'add buy milk to my todo list'. I will reason and use the proper tool dynamically."
    )
    await safe_reply_markdown(update, help_text)


async def todo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /todo command."""
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "Usage:\n`/todo add <title>`\n`/todo list [status]`\n`/todo done <id>`",
            parse_mode="Markdown",
        )
        return

    subcommand = args[0].lower()

    if subcommand == "add":
        title = " ".join(args[1:])
        if not title:
            await update.message.reply_text("Please specify a todo title.")
            return
        res = tool_add_todo(telegram_id=chat_id, title=title)
        await update.message.reply_text(res)

    elif subcommand == "list":
        status = args[1].lower() if len(args) > 1 else "pending"
        res = tool_list_todos(telegram_id=chat_id, status=status)
        await update.message.reply_text(res)

    elif subcommand == "done":
        if len(args) < 2:
            await update.message.reply_text("Please specify the todo ID.")
            return
        try:
            todo_id = int(args[1])
        except ValueError:
            await update.message.reply_text("Todo ID must be an integer.")
            return
        res = tool_complete_todo(telegram_id=chat_id, todo_id=todo_id)
        await update.message.reply_text(res)

    else:
        await update.message.reply_text(
            f"Unknown subcommand: '{subcommand}'. Use `/help` for guidance."
        )


async def news_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /news command."""
    args = context.args
    category = " ".join(args) if args else "world"
    res = tool_get_news(category=category)
    await safe_reply_markdown(update, res)


async def remind_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remind command by forwarding to Son Agent."""
    chat_id = update.effective_chat.id
    message_text = update.message.text

    # Check if they provided arguments
    if not context.args:
        await safe_reply_markdown(
            update,
            "Usage: `/remind <time expression> <message>`\nExample: `/remind tomorrow 8pm gym`",
        )
        return

    # Let the agent parse and schedule
    await update.message.reply_chat_action("typing")

    with get_db_ctx() as db:
        user = get_or_create_user(db, chat_id)
        history = get_user_history(db, user.id)

    agent = SonAgent(telegram_id=chat_id)
    # Give the agent context about the user's command
    agent_prompt = f"Handle this command: {message_text}"
    response = await asyncio.to_thread(agent.run, agent_prompt, history)

    with get_db_ctx() as db:
        user = get_or_create_user(db, chat_id)
        save_message(db, user.id, "user", message_text)
        save_message(db, user.id, "assistant", response)

    await safe_reply_markdown(update, response)


async def note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /note command."""
    chat_id = update.effective_chat.id
    if not context.args:
        await safe_reply_markdown(
            update, "Usage: `/note [work|personal|docs] <note content>`"
        )
        return

    note_content = " ".join(context.args)
    # Determine classification automatically inside note tool
    from app.tools.note import add_note as tool_add_note

    res = tool_add_note(telegram_id=chat_id, text=note_content)
    await update.message.reply_text(res)


async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search command."""
    if not context.args:
        await safe_reply_markdown(update, "Usage: `/search <query>`")
        return

    query = " ".join(context.args)
    res = tool_search_knowledge(query=query)
    await safe_reply_markdown(update, res)


async def daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /daily command."""
    chat_id = update.effective_chat.id
    res = tool_generate_daily_summary(telegram_id=chat_id)
    await safe_reply_markdown(update, res)


async def chat_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle normal chat messages through Son Agent."""
    chat_id = update.effective_chat.id
    user_msg = update.message.text

    # Ignore commands starting with /
    if user_msg.startswith("/"):
        return

    await update.message.reply_chat_action("typing")

    with get_db_ctx() as db:
        user = get_or_create_user(db, chat_id)
        # Fetch history for conversation memory context
        history = get_user_history(db, user.id)

    agent = SonAgent(telegram_id=chat_id)
    response = await asyncio.to_thread(agent.run, user_msg, history)

    # Save conversation state in memory database
    with get_db_ctx() as db:
        user = get_or_create_user(db, chat_id)
        save_message(db, user.id, "user", user_msg)
        save_message(db, user.id, "assistant", response)

    await safe_reply_markdown(update, response)


async def google_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /google command to search the web."""
    if not context.args:
        await safe_reply_markdown(update, "Usage: `/google <search query>`")
        return

    query = " ".join(context.args)
    await update.message.reply_chat_action("typing")
    res = tool_search_web(query=query)
    await safe_reply_markdown(update, res)


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command to set up biometric info."""
    chat_id = update.effective_chat.id
    args = context.args

    if len(args) < 2:
        await safe_reply_markdown(
            update,
            "Usage: `/profile <weight_kg> <height_cm> [goal] [age] [gender] [activity_level]`\n"
            "Example: `/profile 80 180 cut 22 male active`",
        )
        return

    try:
        weight_kg = float(args[0])
        height_cm = float(args[1])
    except ValueError:
        await update.message.reply_text("Weight and height must be numbers, son!")
        return

    goal = args[2].lower() if len(args) > 2 else "maintain"
    if goal not in ["bulk", "cut", "maintain"]:
        goal = "maintain"

    age = 25
    if len(args) > 3:
        try:
            age = int(args[3])
        except ValueError:
            pass

    gender = args[4].lower() if len(args) > 4 else "male"
    if gender not in ["male", "female"]:
        gender = "male"

    activity_level = args[5].lower() if len(args) > 5 else "active"
    if activity_level not in [
        "sedentary",
        "light",
        "moderate",
        "active",
        "very_active",
    ]:
        activity_level = "active"

    await update.message.reply_chat_action("typing")
    res = tool_setup_user_profile(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        gender=gender,
        activity_level=activity_level,
        goal=goal,
        telegram_id=chat_id,
    )
    await safe_reply_markdown(update, res)


async def eat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /eat command to quickly log food: /eat <meal_type> <calories> <protein> <food_name...>"""
    chat_id = update.effective_chat.id
    args = context.args

    if len(args) < 4:
        await safe_reply_markdown(
            update,
            "Usage: `/eat <breakfast|lunch|dinner|snack> <calories> <protein_g> <food name...>`\n"
            "Example: `/eat lunch 600 45 chicken breast and rice`",
        )
        return

    meal_type = args[0].lower()
    if meal_type not in ["breakfast", "lunch", "dinner", "snack"]:
        await update.message.reply_text(
            "Meal type must be breakfast, lunch, dinner, or snack!"
        )
        return

    try:
        calories = int(args[1])
        protein_g = float(args[2])
    except ValueError:
        await update.message.reply_text("Calories and protein must be numbers!")
        return

    food_name = " ".join(args[3:])

    await update.message.reply_chat_action("typing")
    res = tool_log_food(
        food_name=food_name,
        calories=calories,
        protein_g=protein_g,
        meal_type=meal_type,
        telegram_id=chat_id,
    )
    await safe_reply_markdown(update, res)


async def macros_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /macros command to view daily calories and macros."""
    chat_id = update.effective_chat.id
    args = context.args
    date_str = args[0] if args else ""

    await update.message.reply_chat_action("typing")
    res = tool_get_daily_macros(date_str=date_str, telegram_id=chat_id)
    await safe_reply_markdown(update, res)


async def clip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clip command to sync laptop clipboard."""
    chat_id = update.effective_chat.id
    args = context.args

    await update.message.reply_chat_action("typing")

    if not args:
        # Show history and active clipboard
        res = tool_get_clipboard(limit=5, telegram_id=chat_id)
    else:
        # User wants to copy text
        if args[0].lower() == "copy" and len(args) > 1:
            text_to_copy = " ".join(args[1:])
        else:
            text_to_copy = " ".join(args)
            
        res = tool_write_clipboard(text=text_to_copy, telegram_id=chat_id)
        
    await safe_reply_markdown(update, res)


async def find_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /find command to search files on laptop."""
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        await safe_reply_markdown(
            update, "Usage: `/find <query> [start_path]`\nExample: `/find DECISIONS ~/downloads`"
        )
        return

    query = args[0]
    path = args[1] if len(args) > 1 else "~"

    await update.message.reply_chat_action("typing")
    res = tool_find_files(query=query, path=path, telegram_id=chat_id)
    await safe_reply_markdown(update, res)


async def send_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /send command to transfer local file to chat."""
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        await safe_reply_markdown(
            update, "Usage: `/send <file_path>`\nExample: `/send ~/downloads/son.jpg`"
        )
        return

    file_path = args[0]
    await update.message.reply_chat_action("upload_document")
    
    res = await asyncio.to_thread(tool_send_file, path=file_path, telegram_id=chat_id)
    
    if "Error:" in res or "successfully" not in res:
        await safe_reply_markdown(update, res)



