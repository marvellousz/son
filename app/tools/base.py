from typing import Callable, Any, Dict, List
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        # Maps tool name to dict containing the OpenAI schema and the actual handler function
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(
        self, name: str, description: str, parameters: Dict[str, Any], handler: Callable
    ) -> None:
        """Register a tool with its schema and handler function."""
        self._tools[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "handler": handler,
        }
        logger.info(f"Registered tool: {name}")

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Return the list of tool schemas to be passed to the LLM."""
        return [tool["schema"] for tool in self._tools.values()]

    def execute(self, name: str, **kwargs) -> str:
        """Execute a tool handler and return its output as a string."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found in registry.")

        handler = self._tools[name]["handler"]
        try:
            logger.debug(f"Executing tool {name} with args: {kwargs}")
            result = handler(**kwargs)
            return str(result)
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return f"Error executing tool {name}: {str(e)}"


# Singleton registry
registry = ToolRegistry()


def tool(name: str, description: str, parameters: Dict[str, Any]):
    """Decorator to easily register a function as an agent tool."""

    def decorator(func: Callable):
        registry.register(name, description, parameters, func)
        return func

    return decorator
