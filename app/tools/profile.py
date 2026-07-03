import logging
from app.tools.base import tool
from app.database.session import get_db_ctx
from app.database.models import UserProfile
from app.tools.todo import get_or_create_user

logger = logging.getLogger(__name__)


@tool(
    name="setup_user_profile",
    description="Set up or update the user's height, weight, age, activity level, and goal (bulk/cut/maintain) to calculate calorie and protein targets.",
    parameters={
        "type": "object",
        "properties": {
            "weight_kg": {
                "type": "number",
                "description": "User weight in kilograms (e.g. 78.5)",
            },
            "height_cm": {
                "type": "number",
                "description": "User height in centimeters (e.g. 175)",
            },
            "age": {
                "type": "integer",
                "description": "User age in years (default 25)",
                "default": 25,
            },
            "gender": {
                "type": "string",
                "enum": ["male", "female"],
                "description": "User gender for BMR calculation (default 'male')",
                "default": "male",
            },
            "activity_level": {
                "type": "string",
                "enum": ["sedentary", "light", "moderate", "active", "very_active"],
                "description": "User activity level: sedentary (office job), light (light workouts), moderate (3-5 days gym), active (6-7 days gym), very_active (hard labor/athlete)",
                "default": "active",
            },
            "goal": {
                "type": "string",
                "enum": ["bulk", "cut", "maintain"],
                "description": "Fitness goal: bulk (weight gain), cut (fat loss), maintain (weight maintenance)",
                "default": "maintain",
            },
        },
        "required": ["weight_kg", "height_cm"],
    },
)
def setup_user_profile(
    weight_kg: float,
    height_cm: float,
    age: int = 25,
    gender: str = "male",
    activity_level: str = "active",
    goal: str = "maintain",
    telegram_id: int = None,
) -> str:
    """Calculate TDEE and macros, then save the profile to the database."""
    if not telegram_id:
        return "Error: telegram_id is required."

    weight_kg = float(weight_kg)
    height_cm = float(height_cm)

    # 1. Calculate BMR (Mifflin-St Jeor)
    if gender.lower() == "female":
        bmr = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age - 161.0
    else:
        bmr = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age + 5.0

    # 2. Calculate TDEE
    multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    tdee = bmr * multipliers.get(activity_level.lower(), 1.725)

    # 3. Calculate target calories based on goal
    if goal.lower() == "cut":
        target_calories = int(round(tdee - 500.0))
    elif goal.lower() == "bulk":
        target_calories = int(round(tdee + 500.0))
    else:
        target_calories = int(round(tdee))

    # 4. Target protein (2.0g per kg of bodyweight)
    target_protein = int(round(2.0 * weight_kg))

    # Save to database
    with get_db_ctx() as db:
        user = get_or_create_user(db, telegram_id)

        # Check if profile already exists
        profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        if not profile:
            profile = UserProfile(
                user_id=user.id,
                weight_kg=weight_kg,
                height_cm=height_cm,
                age=age,
                gender=gender,
                activity_level=activity_level,
                goal=goal,
                target_calories=target_calories,
                target_protein_g=target_protein,
            )
            db.add(profile)
        else:
            profile.weight_kg = weight_kg
            profile.height_cm = height_cm
            profile.age = age
            profile.gender = gender
            profile.activity_level = activity_level
            profile.goal = goal
            profile.target_calories = target_calories
            profile.target_protein_g = target_protein
        db.commit()

    # Format setup summary
    report = (
        f"💪 **Fitness Profile Setup Complete!**\n\n"
        f"📏 **Biometrics:**\n"
        f"• Height: {height_cm} cm\n"
        f"• Weight: {weight_kg} kg\n"
        f"• Age: {age} | Gender: {gender.capitalize()}\n"
        f"• Activity Level: {activity_level.replace('_', ' ').capitalize()}\n"
        f"• Goal: **{goal.upper()}**\n\n"
        f"🔥 **Calculated Targets:**\n"
        f"• Basal Metabolic Rate (BMR): {int(round(bmr))} kcal/day\n"
        f"• Maintenance Calories (TDEE): {int(round(tdee))} kcal/day\n"
        f"• **Daily Calorie Goal:** **{target_calories} kcal**\n"
        f"• **Daily Protein Goal:** **{target_protein} g** (2.0g/kg)\n\n"
        f"Let's get tracking, son! Tell me what you ate today! 🍼🏋️‍♂️"
    )
    return report
