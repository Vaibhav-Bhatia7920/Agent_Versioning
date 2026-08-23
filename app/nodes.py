import json
from pathlib import Path
from typing import Any, Dict, List, TypedDict, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.llm import get_chat_model
from app.template import PatcherNodeResponse, PlannerCoderResponse, RepoNavigatorResponse, SearchResultItem
from app.tools.code_index import build_symbol_map, load_symbol_map
from app.tools.helper_tools import parse_ripgrep_output
from app.agent.llm_tools import NAVIGATOR_TOOLS, find_files, read_file_snippet, run_ripgrep, run_tree


class MonorepoState(TypedDict):
    issue_title: str
    issue_description: str
    config: Dict[str, Any]
    project_root: str
    target_packages: List[str]
    filesystem_map: str
    symbol_map: str
    search_results: Union[List[SearchResultItem], Dict[str, Any]]
    relevant_files: List[str]
    proposed_plan: str
    diffs_to_apply: List[Dict[str, Any]]
    test_command: str
    test_stdout: str
    test_stderr: str
    is_resolved: bool


TOOL_MAP = {
    "run_tree": run_tree,
    "run_ripgrep": run_ripgrep,
    "find_files": find_files,
    "read_file_snippet": read_file_snippet,
}


def normalize_tool_output(output: Any) -> str:
    if isinstance(output, tuple):
        stdout = output[0]
        stderr = output[1] if len(output) > 1 else ""
        if stdout:
            return str(stdout)
        if stderr:
            return f"Error: {stderr}"
        return ""
    if isinstance(output, dict):
        if output.get("exit_code", 0) != 0 and output.get("stderr"):
            return f"Error: {output['stderr']}"
        return str(output.get("stdout") or output.get("content") or output)
    return str(output)


def _tool_output_text(output: Any) -> str:
    if isinstance(output, tuple):
        stdout = output[0] if len(output) > 0 else ""
        stderr = output[1] if len(output) > 1 else ""
        return str(stdout or stderr or "")
    if isinstance(output, dict):
        return str(output.get("stdout") or output.get("content") or output.get("stderr") or output)
    return str(output)


def read_local_file(file_path: str) -> str:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception as exc:
        return f"// Error reading file: {exc}"


def convert_langchain_messages_to_completion_input(messages: List[Any]) -> List[Dict[str, Any]]:
    formatted_input = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            formatted_input.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            formatted_input.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            item: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if getattr(msg, "tool_calls", None):
                standard_tool_calls = []
                for tc in msg.tool_calls:
                    if isinstance(tc, dict) and "function" in tc:
                        standard_tool_calls.append(tc)
                    elif isinstance(tc, dict):
                        standard_tool_calls.append(
                            {
                                "id": tc.get("id", f"call_{tc.get('name')}"),
                                "type": "function",
                                "function": {
                                    "name": tc.get("name"),
                                    "arguments": json.dumps(tc.get("args", {}))
                                    if isinstance(tc.get("args"), dict)
                                    else str(tc.get("args", "{}")),
                                },
                            }
                        )
                if standard_tool_calls:
                    item["tool_calls"] = standard_tool_calls
            formatted_input.append(item)
        elif isinstance(msg, ToolMessage):
            formatted_input.append({"role": "tool", "tool_call_id": msg.tool_call_id, "content": str(msg.content)})
    return formatted_input


def repo_navigator_node(state: MonorepoState) -> MonorepoState:
    config = state.get("config", {})
    project_root = state.get("project_root") or "."
    if project_root == "/workspace":
        project_root = "."

    symbol_index = build_symbol_map(project_root)
    symbol_map = load_symbol_map(project_root)

    system_prompt = (
        "You are RepoNavigator, an autonomous codebase exploration agent.\n"
        "Your task is to explore the repository using tools (run_tree, run_ripgrep, find_files, read_file_snippet) "
        "and the cached symbol map to discover affected sub-packages and pinpoint relevant source files for the reported issue.\n"
        "Keep your tool calls minimal and focused."
    )

    user_prompt = f"Issue Title: {state['issue_title']}\nDescription: {state['issue_description']}"
    if symbol_map:
        user_prompt += f"\n\n=== SYMBOL MAP ===\n{symbol_map}"

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    captured_tree_outputs: List[str] = []
    captured_search_results: List[SearchResultItem] = []
    max_search_turns = config.get("max_search_turns", 4)

    for _ in range(max_search_turns):
        formatted_messages = convert_langchain_messages_to_completion_input(messages)
        kwargs = {"messages": formatted_messages}
        if NAVIGATOR_TOOLS:
            kwargs["tools"] = NAVIGATOR_TOOLS

        response = get_chat_model(config, **kwargs)
        choice = response.choices[0]
        message_output = choice.message
        content_text = message_output.content or ""
        tool_calls = getattr(message_output, "tool_calls", None)

        lc_tool_calls = []
        if tool_calls:
            for tc in tool_calls:
                t_name = tc.function.name if hasattr(tc, "function") else tc.get("name")
                t_args = tc.function.arguments if hasattr(tc, "function") else tc.get("arguments", {})
                t_id = tc.id if hasattr(tc, "id") else tc.get("id")
                if isinstance(t_args, str):
                    try:
                        t_args = json.loads(t_args)
                    except Exception:
                        t_args = {}
                lc_tool_calls.append({"name": t_name, "args": t_args, "id": t_id})

        messages.append(AIMessage(content=content_text, tool_calls=lc_tool_calls))
        if not lc_tool_calls:
            break

        for tool_call in lc_tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            if tool_name in TOOL_MAP:
                raw_result = TOOL_MAP[tool_name](**tool_args) if isinstance(tool_args, dict) else TOOL_MAP[tool_name](tool_args)
                clean_output = normalize_tool_output(raw_result)
                if tool_name == "run_tree":
                    captured_tree_outputs.append(clean_output)
                elif tool_name == "run_ripgrep":
                    captured_search_results.extend(parse_ripgrep_output(clean_output))
            else:
                clean_output = f"Error: Tool '{tool_name}' not recognized."

            messages.append(ToolMessage(content=clean_output, tool_call_id=tool_id))

    messages.append(
        HumanMessage(
            content=(
                "Consolidate your findings from the search tool results above.\n"
                "Return a valid JSON object matching the requested schema keys: "
                "target_packages (list of strings), filesystem_map (string), search_results (list), relevant_files (list of strings)."
            )
        )
    )

    formatted_messages = convert_langchain_messages_to_completion_input(messages)
    final_response = get_chat_model(config, messages=formatted_messages)
    content_text = final_response.choices[0].message.content or ""
    try:
        clean_json = content_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed_data = json.loads(clean_json)
    except Exception:
        parsed_data = {}

    state["target_packages"] = parsed_data.get("target_packages", [])
    state["filesystem_map"] = parsed_data.get("filesystem_map") or (captured_tree_outputs[-1] if captured_tree_outputs else "")
    state["symbol_map"] = symbol_map or json.dumps(symbol_index)
    state["search_results"] = parsed_data.get("search_results") or captured_search_results
    state["relevant_files"] = parsed_data.get("relevant_files", [])
    return state


def fetch_file_contents(file_paths: List[str]) -> Dict[str, str]:
    file_contents: Dict[str, str] = {}
    for path in file_paths:
        file_contents[path] = read_local_file(path)
    return file_contents


def planner_node(state: MonorepoState) -> MonorepoState:
    config = state.get("config", {})
    relevant_files = state.get("relevant_files", [])
    file_contents = fetch_file_contents(relevant_files)

    system_prompt = (
        "You are an expert Monorepo Software Engineer and Planner.\n"
        "Your task is to analyze the issue and target files, formulate a step-by-step fix, "
        "and generate exact search-and-replace code diffs in JSON format.\n\n"
        "STRICT PATCHING RULES:\n"
        "1. NEVER rewrite the entire file. Only output minimal search-and-replace blocks.\n"
        "2. The `search` block MUST exist verbatim in the target file, including exact whitespace and indentation.\n"
        "3. Keep `search` blocks unique enough (3–10 lines) to match only the target location.\n"
        "4. Provide a targeted test command (e.g., `pytest packages/core/tests/test_auth.py`) to verify the fix."
    )

    formatted_code_context = ""
    for path, content in file_contents.items():
        formatted_code_context += f"\n--- FILE: {path} ---\n{content}\n"

    retry_context = ""
    if state.get("test_stderr"):
        retry_context = f"""
        🚨 PREVIOUS TEST FAILED (Iteration {state.get('iteration_count', 0)}):
        Command: {state.get('test_command')}
        Stderr / Stacktrace:
        {state.get('test_stderr')}

        Please analyze the failure stack trace above, adjust your plan, and output corrected diffs.
        """

    user_prompt = f"""
    Issue Title: {state['issue_title']}
    Issue Description: {state['issue_description']}
    Target Packages: {state.get('target_packages', [])}

    === TARGET FILE CONTENTS ===
    {formatted_code_context}
    {retry_context}
    """

    response = get_chat_model(config, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
    content_text = response.choices[0].message.content or ""
    try:
        clean_json = content_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed_response = json.loads(clean_json)
    except Exception:
        parsed_response = {}

    state["proposed_plan"] = parsed_response.get("proposed_plan", "")
    state["test_command"] = parsed_response.get("test_command", "")
    state["diffs_to_apply"] = parsed_response.get("diffs_to_apply", [])
    return state


def patcher_node(state: MonorepoState) -> MonorepoState:
    config = state.get("config", {})
    relevant_files = state.get("relevant_files", [])
    file_contents = fetch_file_contents(relevant_files)

    system_prompt = (
        "You are an execution-phase patcher.\n"
        "Your task is to review the current plan, the relevant file contents, and the prior state, then propose the exact minimal diffs to apply.\n"
        "Return JSON with keys: proposed_plan (string) and diffs_to_apply (list of search/replace objects).\n\n"
        "STRICT PATCHING RULES:\n"
        "1. Do not edit files directly.\n"
        "2. Only propose minimal search-and-replace diffs.\n"
        "3. Each search block must exist verbatim in the target file.\n"
        "4. Keep diffs narrowly scoped to the relevant files."
    )

    formatted_code_context = ""
    for path, content in file_contents.items():
        formatted_code_context += f"\n--- FILE: {path} ---\n{content}\n"

    user_prompt = f"""
    Issue Title: {state['issue_title']}
    Issue Description: {state['issue_description']}
    Prior Plan: {state.get('proposed_plan', '')}
    Relevant Files: {relevant_files}

    === TARGET FILE CONTENTS ===
    {formatted_code_context}
    """

    response = get_chat_model(config, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
    content_text = response.choices[0].message.content or ""
    try:
        clean_json = content_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed_response = PatcherNodeResponse.model_validate_json(clean_json)
    except Exception:
        parsed_response = PatcherNodeResponse(proposed_plan=state.get("proposed_plan", ""), diffs_to_apply=state.get("diffs_to_apply", []))

    state["proposed_plan"] = parsed_response.proposed_plan
    state["diffs_to_apply"] = [diff.model_dump() for diff in parsed_response.diffs_to_apply]
    return state