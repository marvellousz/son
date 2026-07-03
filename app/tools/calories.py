import logging
import datetime
from app.tools.base import tool
from app.database.session import get_db_ctx
from app.database.models import FoodLog, UserProfile
from app.tools.todo import get_or_create_user

logger = logging.getLogger(__name__)


@tool(
    name="log_food",
    description="Log a food item with its calories and protein under a specific meal category (breakfast, lunch, dinner, snack).",
    parameters={
        "type": "object",
        "properties": {
            "food_name": {
                "type": "string",
                "description": "The name of the food item (e.g. 'grilled chicken breast')",
            },
            "calories": {
                "type": "integer",
                "description": "The amount of calories in kcal (e.g. 250)",
            },
            "protein_g": {
                "type": "number",
                "description": "The amount of protein in grams (default 0.0)",
                "default": 0.0,
            },
            "meal_type": {
                "type": "string",
                "enum": ["breakfast", "lunch", "dinner", "snack"],
                "description": "The meal category (default 'snack')",
                "default": "snack",
            },
        },
        "required": ["food_name", "calories"],
    },
)
def log_food(
    food_name: str,
    calories: int,
    protein_g: float = 0.0,
    meal_type: str = "snack",
    telegram_id: int = None,
) -> str:
    """Log food intake for the user."""
    if not telegram_id:
        return "Error: telegram_id is required."

    food_name = food_name.strip()
    calories = int(calories)
    protein_g = float(protein_g)
    meal_type = meal_type.lower().strip()
    if meal_type not in ["breakfast", "lunch", "dinner", "snack"]:
        meal_type = "snack"

    today_date = datetime.date.today()

    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)

        log_entry = FoodLog(
            user_id=user.id,
            food_name=food_name,
            calories=calories,
            protein_g=protein_g,
            meal_type=meal_type,
            logged_date=today_date,
        )
        db.add(log_entry)
        db.commit()

    return f"🍽️ **Logged successfully, son!**\n• Food: *{food_name}*\n• Meal: *{meal_type.capitalize()}*\n• Calories: *{calories} kcal*\n• Protein: *{protein_g} g*"


def make_progress_bar(current: float, target: float, length: int = 10) -> str:
    if target <= 0:
        return "`[----------]` 0%"
    percent = min(1.0, max(0.0, current / target))
    filled = int(percent * length)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"`[{bar}]` {int(percent * 100)}%"


@tool(
    name="get_daily_macros",
    description="Get a summary of food eaten today, showing total calories and protein consumed vs. daily goals.",
    parameters={
        "type": "object",
        "properties": {
            "date_str": {
                "type": "string",
                "description": "Optional date string in YYYY-MM-DD format (defaults to today)",
                "default": "",
            }
        },
    },
)
def get_daily_macros(date_str: str = "", telegram_id: int = None) -> str:
    """Retrieve daily food logs and return a summary report with progress bars."""
    if not telegram_id:
        return "Error: telegram_id is required."

    # Parse date
    if date_str:
        try:
            target_date = datetime.datetime.strptime(
                date_str.strip(), "%Y-%m-%d"
            ).date()
        except ValueError:
            return "Error: Invalid date format. Please use YYYY-MM-DD."
    else:
        target_date = datetime.date.today()

    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)

        # Fetch profile
        profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()

        # Fetch food logs for target date
        logs = (
            db.query(FoodLog)
            .filter(FoodLog.user_id == user.id, FoodLog.logged_date == target_date)
            .all()
        )

    # Summarize logs
    total_calories = 0
    total_protein = 0.0
    meals = {"breakfast": [], "lunch": [], "dinner": [], "snack": []}

    for log in logs:
        total_calories += log.calories
        total_protein += log.protein_g
        meals[log.meal_type].append(log)

    date_display = target_date.strftime("%A, %B %d, %Y")

    # Header and progress bars
    report = f"📊 **Calorie & Macro Summary ({date_display})**\n\n"

    if profile:
        cal_goal = profile.target_calories
        prot_goal = profile.target_protein_g

        cal_bar = make_progress_bar(total_calories, cal_goal)
        prot_bar = make_progress_bar(total_protein, prot_goal)

        report += f"🔥 **Calories:** {total_calories} / {cal_goal} kcal\n{cal_bar}\n\n"
        report += f"🍗 **Protein:** {total_protein:.1f} / {prot_goal} g\n{prot_bar}\n\n"
    else:
        report += (
            f"🔥 **Calories consumed:** {total_calories} kcal\n"
            f"🍗 **Protein consumed:** {total_protein:.1f} g\n\n"
            f"⚠️ *Note: You haven't set up your fitness profile yet! Run `/profile <weight> <height> <goal>` or tell me to set it up so I can calculate your daily targets!*\n\n"
        )

    # Meal breakdown
    report += "📝 **Meal Breakdown:**\n"
    meal_emoji = {
        "breakfast": "🍳 Breakfast",
        "lunch": "🍱 Lunch",
        "dinner": "🥩 Dinner",
        "snack": "🍌 Snacks",
    }

    has_food = False
    for meal, logs_list in meals.items():
        if logs_list:
            has_food = True
            report += f"\n*{meal_emoji[meal]}:*\n"
            for log in logs_list:
                report += (
                    f"• {log.food_name} ({log.calories} kcal | {log.protein_g}g P)\n"
                )

    if not has_food:
        report += (
            "\n*No meals logged yet today, son! Hit the gym and get eating! 🏋️‍♂️*"
        )

    return report
