from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from langgraph.graph import START, StateGraph, END
from app.node_operations import MonorepoState, patcher_node, planner_node, repo_navigator_node
from app.dictionary_db import add_phase_to_dict, get_phase_from_dict
from app.node_operations import step_back
import uuid

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
        "current_phase_id": str(uuid.uuid4()),
        "parent_phase_id": "",
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
    Phase = add_phase_to_dict(final_state["current_phase_id"], final_state)
    return Phase.PhaseId


def add_phase(parent_phase_id: str, state: MonorepoState, user_query: str, payload: dict) -> str:
    state["parent_phase_id"] = parent_phase_id
    state["user_query"] = user_query
    state["payload"] = payload
    parent_phase = get_phase_from_dict(parent_phase_id)
    state["initial_context"] = parent_phase["initial_context"] + "\n\n" + parent_phase["proposed_plan"] if parent_phase else ""
    flow = initialize_state_graph()
    app = flow.compile()
    final_state = app.invoke(state)
    Phase = add_phase_to_dict(final_state["current_phase_id"], final_state)
    return Phase.PhaseId


def move_back_in_phase(steps : int, current_phase_id: str) -> str:
    state = get_phase_from_dict(current_phase_id)
    if not state:
        raise ValueError(f"Phase with ID {current_phase_id} not found in the dictionary.")
    new_phase_id = step_back(steps, state)
    return new_phase_id



def attach_next_phase(parent_phase_id: str):
    parent_phase = get_phase_from_dict(parent_phase_id)
    child_state: MonorepoState = {
                "current_phase_id": str(uuid.uuid4()),
                "parent_phase_id": parent_phase_id,
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
    child_phase_id = add_phase(parent_phase_id, child_state, next_query, {"kind": "follow_up"})
    print(f"child_phase_id={child_phase_id}")
    return child_phase_id
    



if __name__ == "__main__":
    first_query = input("Enter first query: ").strip()
    root_phase_id = add_root_phase(first_query, project_root=".")
    print(f"root_phase_id={root_phase_id}")

    next_query = input("Enter next query (or leave blank to exit): ").strip()
    parent_phase_id = root_phase_id
    while next_query:
        child_phase_id = attach_next_phase(parent_phase_id)
        parent_phase_id = child_phase_id
        next_query = input("Enter next query (or leave blank to exit): ").strip()
        
    


