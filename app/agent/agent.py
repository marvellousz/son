import json
import logging
import time
import openai
from openai import OpenAI
from app.config.settings import settings
from app.agent.prompts import SYSTEM_PROMPT
from app.tools import registry

logger = logging.getLogger(__name__)


class SonAgent:
    def __init__(self, telegram_id: int):
        self.telegram_id = telegram_id
        # Initialize OpenAI client pointing to local Ollama or Gemini compatible endpoint
        self.client = OpenAI(
            base_url=settings.OLLAMA_BASE_URL,
            api_key=settings.GEMINI_API_KEY if settings.GEMINI_API_KEY else "ollama",
        )
        self.model = settings.MODEL

    def run(self, user_message: str, history_messages: list = None) -> str:
        """Executes the agent reasoning loop, calling tools as decided by Son."""
        from datetime import datetime

        current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        dynamic_prompt = f"{SYSTEM_PROMPT}\n\nCurrent Date & Time: {current_time}\n"
        messages = [{"role": "system", "content": dynamic_prompt}]

        # Hydrate conversation history
        if history_messages:
            for msg in history_messages:
                content = msg.get("content", "")
                # Skip error messages to prevent memory pollution
                if content.startswith(
                    "Sorry, I encountered an error"
                ) or content.startswith("I apologize, but I exceeded"):
                    continue
                messages.append({"role": msg.get("role", "user"), "content": content})

        messages.append({"role": "user", "content": user_message})

        tools = registry.get_schemas()

        max_iterations = 6
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            try:
                logger.debug(
                    f"Agent loop iteration {iteration} for user {self.telegram_id}"
                )

                # Setup request arguments
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                }

                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                # Call chat completions with exponential backoff on rate limits (HTTP 429)
                max_retries = 3
                backoff_factor = 2
                for attempt in range(max_retries):
                    try:
                        response = self.client.chat.completions.create(**kwargs)
                        break
                    except openai.RateLimitError as e:
                        if attempt == max_retries - 1:
                            raise e
                        sleep_time = backoff_factor ** (attempt + 1)
                        logger.warning(
                            f"Rate limit hit. Retrying in {sleep_time} seconds... Error: {e}"
                        )
                        time.sleep(sleep_time)
                response_message = response.choices[0].message

                content = response_message.content
                tool_calls = response_message.tool_calls

                # Append assistant message to history
                messages.append(response_message)

                # If the LLM did not request any tool, we're done
                if not tool_calls:
                    return content or "I couldn't generate a response."

                # Execute tool calls sequentially
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args_str = tool_call.function.arguments

                    try:
                        tool_args = json.loads(tool_args_str) if tool_args_str else {}
                    except json.JSONDecodeError:
                        logger.error(
                            f"Failed to parse tool arguments JSON: {tool_args_str}",
                            exc_info=True,
                        )
                        tool_args = {}

                    # Force inject telegram_id to ensure context boundaries
                    tool_args["telegram_id"] = self.telegram_id

                    logger.info(
                        f"Agent calling tool '{tool_name}' for user {self.telegram_id} with args: {tool_args}"
                    )
                    tool_result = registry.execute(tool_name, **tool_args)

                    # Append tool result to context
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": tool_result,
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Exception in SonAgent reasoning loop: {e}", exc_info=True
                )
                return f"Sorry, I encountered an error while reasoning about your request: {str(e)}"

        return "I apologize, but I exceeded my reasoning capacity without resolving your request."
