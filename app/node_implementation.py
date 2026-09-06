import json

from typing import Any, Dict, List, Optional, TypedDict, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.llm import get_chat_model

from app.node_template import Node, PatcherNodeResponse, PlannerCoderResponse, RepoNavigatorResponse, SearchResultItem
from app.tools.code_index import build_symbol_map, load_symbol_map
from app.tools.helper_tools import parse_ripgrep_output
from app.agent.llm_tools import NAVIGATOR_TOOLS, find_files, read_file_snippet, run_ripgrep, run_tree, change_line_in_file
from app.tools.node_helpers import convert_langchain_messages_to_completion_input,fetch_file_contents, normalize_tool_output
# from app.nodes import _persist_node
from app.state_template import MonorepoState




TOOL_MAP = {
    "run_tree": run_tree,
    "run_ripgrep": run_ripgrep,
    "find_files": find_files,
    "read_file_snippet": read_file_snippet,
    "change_line_in_file": change_line_in_file,
}







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
    # _persist_node(
    #     "repo_navigator",
    #     state,
    #     {
    #         "target_packages": state["target_packages"],
    #         "filesystem_map": state["filesystem_map"],
    #         "symbol_map": state["symbol_map"],
    #         "search_results": state["search_results"],
    #         "relevant_files": state["relevant_files"],
    #     },
    # )
    # target_package,filesystem_map,search_results,relevant_files
    print(f"Target Packages: {state['target_packages']}")
    print(f"Filesystem Map: {state['filesystem_map']}")
    print(f"Search Results: {state['search_results']}")
    print(f"Relevant Files: {state['relevant_files']}")
    return RepoNavigatorResponse(
        target_packages=state["target_packages"],
        filesystem_map=state["filesystem_map"],
        search_results=state["search_results"],
        relevant_files=state["relevant_files"],
    ).model_dump()




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
        "5. The output format MUST be valid JSON with keys: proposed_plan (string), test_command (string), diffs_to_apply (list of dicts with keys: file, search, replace)."

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
    print(f"Planner Node Response:\n{content_text}\n")
    try:
        clean_json = content_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed_response = json.loads(clean_json)
    except Exception:
        parsed_response = {}

    state["proposed_plan"] = parsed_response.get("proposed_plan", "")
    state["test_command"] = parsed_response.get("test_command", "")
    state["diffs_to_apply"] = parsed_response.get("diffs_to_apply", [])
    # _persist_node(
    #     "planner",
    #     state,
    #     {
    #         "proposed_plan": state["proposed_plan"],
    #         "test_command": state["test_command"],
    #         "diffs_to_apply": state["diffs_to_apply"],
    #     },
    # )
    print(f"Proposed Plan: {state['proposed_plan']}")
    print(f"Test Command: {state['test_command']}")
    print(f"Diffs to Apply: {state['diffs_to_apply']}")
    return PlannerCoderResponse(
        proposed_plan=state["proposed_plan"],
        test_command=state["test_command"],
        diffs_to_apply=state["diffs_to_apply"],
    ).model_dump()


def patcher_node(state: MonorepoState) -> MonorepoState:
    config = state.get("config", {})
    relevant_files = state.get("relevant_files", [])
    file_contents = fetch_file_contents(relevant_files)

    system_prompt = (
        "You are an execution-phase patcher.\n"
        "Your task is to apply the proposed diffs to the target files, run the provided test command.\n"
        "Use the tools provided to make changes to the files and verify the fix.\n"
        "STRICT PATCHING RULES:\n"
        "1. NEVER rewrite the entire file. Only do minimal changes line by line as mentioned in current_state[proposed_diffs].\n"
    )

    formatted_code_context = ""
    for path, content in file_contents.items():
        formatted_code_context += f"\n--- FILE: {path} ---\n{content}\n"

    user_prompt = f"""
    Issue Title: {state['issue_title']}
    Issue Description: {state['issue_description']}
    Prior Plan: {state.get('proposed_plan', '')}
    Relevant Files: {relevant_files}
    Diffs to Apply: {state.get('diffs_to_apply', [])}

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
    # _persist_node(
    #     "patcher",
    #     state,
    #     {
    #         "proposed_plan": state["proposed_plan"],
    #         "diffs_to_apply": state["diffs_to_apply"],
    #     },
    # )
    return state