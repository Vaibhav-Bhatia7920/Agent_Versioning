import litellm
import inspect
from typing import Any, Dict, List, Optional
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool


def format_tool_for_completion(tool: Any) -> Dict[str, Any]:
    if isinstance(tool, BaseTool):
        return convert_to_openai_tool(tool)
    if callable(tool):
        signature = inspect.signature(tool)
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for name, parameter in signature.parameters.items():
            if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            annotation = parameter.annotation
            json_type = "string"
            if annotation in (int, "int"):
                json_type = "integer"
            elif annotation in (float, "float"):
                json_type = "number"
            elif annotation in (bool, "bool"):
                json_type = "boolean"
            properties[name] = {"type": json_type}
            if parameter.default is inspect._empty:
                required.append(name)

        description = inspect.getdoc(tool) or ""
        function_schema: Dict[str, Any] = {
            "name": getattr(tool, "__name__", "tool"),
            "description": description,
            "parameters": {"type": "object", "properties": properties, "additionalProperties": False},
        }
        if required:
            function_schema["parameters"]["required"] = required
        return {"type": "function", "function": function_schema}
    if isinstance(tool, dict):
        if tool.get("type") == "function" and "function" in tool:
            return tool
        if "name" in tool and "parameters" in tool:
            return {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            }
        return tool
    raise ValueError(f"Unsupported tool format: {tool}")


def get_chat_model(
    config: Dict[str, Any],
    messages: List[Dict[str, Any]],
    tools: Optional[List[Any]] = None,
    **extra_kwargs: Any,
) -> Any:
    model_name = config.get("llm_model", "gpt-4o")
    api_key = config.get("api_key") or config.get("api_token")
    api_base = config.get("api_base")
    reasoning_effort = config.get("reasoning_effort")

    call_kwargs: Dict[str, Any] = {"model": model_name, "messages": messages, **extra_kwargs}
    if api_key:
        call_kwargs["api_key"] = api_key
    if api_base:
        call_kwargs["api_base"] = api_base
    if reasoning_effort:
        call_kwargs["reasoning_effort"] = reasoning_effort
    if tools:
        call_kwargs["tools"] = [format_tool_for_completion(tool) for tool in tools]

    return litellm.completion(**call_kwargs)