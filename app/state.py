from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from langgraph.graph import START, StateGraph, END
from app.node_operations import MonorepoState, patcher_node, planner_node, repo_navigator_node
from app.dictionary_db import add_node_to_dict, get_node_from_dict
from app.node_operations import step_back

def initialize_state_graph() -> StateGraph:
    graph = StateGraph(MonorepoState)
    graph.add_node("repo_navigator", repo_navigator_node)
    graph.add_node("planner", planner_node)
    graph.add_node("patcher", patcher_node)

    graph.add_edge(START, "repo_navigator")
    graph.add_edge("repo_navigator", "planner")
    graph.add_edge("planner", "patcher")
    graph.add_edge("patcher", END)

    return graph

def add_root_phase(user_query: str, project_root: str = ".", issue_description: str = "") -> str:
    initial_state: MonorepoState = {
        "current_node_id": "1",
        "parent_node_id": "",
        "issue_title": user_query,
        "issue_description": issue_description or user_query,
        "config": {"max_search_turns": 3},
        "project_root": project_root,
        "target_packages": [],
        "filesystem_map": "",
        "symbol_map": "",
        "search_results": [],
        "relevant_files": [],
        "proposed_plan": "",
        "diffs_to_apply": [],
        "test_command": "",
        "test_stdout": "",
        "test_stderr": "",
        "is_resolved": False,
    }

    flow = initialize_state_graph()
    app = flow.compile()
    final_state = app.invoke(initial_state)
    Node = add_node_to_dict(final_state["current_node_id"], final_state)
    return Node.NodeId


def add_phase(parent_node_id: str, state: MonorepoState, user_query: str, payload: dict) -> str:
    state["parent_node_id"] = parent_node_id
    state["user_query"] = user_query
    state["payload"] = payload
    flow = initialize_state_graph()
    app = flow.compile()
    final_state = app.invoke(state)
    Node = add_node_to_dict(final_state["current_node_id"], final_state)
    return Node.NodeId


def move_back_in_phase(steps : int, current_node_id: str) -> str:
    state = get_node_from_dict(current_node_id)
    if not state:
        raise ValueError(f"Node with ID {current_node_id} not found in the dictionary.")
    new_node_id = step_back(steps, state)
    return new_node_id



    


if __name__ == "__main__":
    first_query = input("Enter first query: ").strip()
    root_phase_id = add_root_phase(first_query, project_root=".")
    print(f"root_phase_id={root_phase_id}")

    next_query = input("Enter next query (or leave blank to exit): ").strip()
    if next_query:
        child_state: MonorepoState = {
            "current_node_id": root_phase_id,
            "parent_node_id": root_phase_id,
            "issue_title": first_query,
            "issue_description": first_query,
            "config": {"max_search_turns": 3},
            "project_root": ".",
            "target_packages": [],
            "filesystem_map": "",
            "symbol_map": "",
            "search_results": [],
            "relevant_files": [],
            "proposed_plan": "",
            "diffs_to_apply": [],
            "test_command": "",
            "test_stdout": "",
            "test_stderr": "",
            "is_resolved": False,
        }
        child_phase_id = add_phase(root_phase_id, child_state, next_query, {"kind": "follow_up"})
        print(f"child_phase_id={child_phase_id}")
    


