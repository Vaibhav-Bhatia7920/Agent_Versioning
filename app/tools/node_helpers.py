import json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from typing import Any, Dict, List, Optional, TypedDict, Union
from pathlib import Path
# from app.db import fetch_node, initialize_database, upsert_node
from app.state_template import MonorepoState
import hashlib
from app.tools.repository_service import RepositoryService

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


def read_local_file(file_path: str) -> str:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception as exc:
        return f"// Error reading file: {exc}"


def _node_hash(node_name: str, state: MonorepoState, payload: Any) -> str:
    digest_source = json.dumps(
        {
            "node": node_name,
            "issue_title": state.get("issue_title", ""),
            "issue_description": state.get("issue_description", ""),
            "project_root": state.get("project_root", ""),
            "payload": payload,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(digest_source.encode("utf-8")).hexdigest()

# def get_node_context(node_id: str, db_path: Optional[object] = None) -> str:
#     """Walk parent links from a node back to the root and return the raw context chain."""
#     context_parts: List[str] = []
#     current_node_id = node_id
#     visited_nodes = set()

#     while current_node_id and current_node_id not in visited_nodes:
#         visited_nodes.add(current_node_id)
#         row = fetch_node(current_node_id, db_path=db_path)
#         if row is None:
#             break

#         raw_response = row["raw_response"] if "raw_response" in row.keys() else row[4]
#         if raw_response:
#             context_parts.append(str(raw_response))

#         parent_id = row["parent_id"] if "parent_id" in row.keys() else row[1]
#         current_node_id = str(parent_id) if parent_id else ""

#     context_parts.reverse()
#     return "\n\n".join(context_parts)


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

def fetch_file_contents(file_paths: List[str]) -> Dict[str, str]:
    file_contents: Dict[str, str] = {}
    for path in file_paths:
        file_contents[path] = read_local_file(path)
    return file_contents



def _current_git_head_commit(project_root: str) -> str:
	return RepositoryService(project_root).current_head()


def _create_git_commit(project_root: str, commit_message: str) -> str:
	return RepositoryService(project_root).create_commit(commit_message)