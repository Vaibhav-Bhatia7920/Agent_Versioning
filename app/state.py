from langgraph.graph import START, StateGraph, END
from app.node_operations import MonorepoState, _node_hash,ensure_root_phase, initialize_and_upsert_child, initialize_root_phase, initialize_root_snap, patcher_node, planner_node, repo_navigator_node

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


def add_root_phase():
    initial_state: MonorepoState = {
        "issue_title": "NA",
        "issue_description": "NA",
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
        "iteration_count": 0,
    }

    flow = initialize_state_graph()
    app = flow.compile()
    final_state = app.invoke(initial_state)
    final_state["current_node_id"] = _node_hash(final_state, {"kind": "root"})
    root_phase_id = ensure_root_phase(final_state)
    return root_phase_id

def add_phase(parent_node_id: str, state: MonorepoState, user_query: str, payload: dict) -> str:
    state["parent_node_id"] = parent_node_id
    state["user_query"] = user_query
    state["payload"] = payload
    flow = initialize_state_graph()
    app = flow.compile()
    final_state = app.invoke(state)
    final_state["current_node_id"] = _node_hash(final_state, {"kind": "child"})
    phase_id = initialize_and_upsert_child(final_state)
    return phase_id


if __name__ == "__main__":
    initial_state: MonorepoState = {
        "issue_title": "Hi need to add comment in top of 1 state.py",
        "issue_description": "Help in adding comment",
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
        "iteration_count": 0,
    }


