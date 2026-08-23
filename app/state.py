import operator
from langgraph.graph import START, StateGraph, END
from app.nodes import MonorepoState, patcher_node, planner_node, repo_navigator_node

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


if __name__ == "__main__":
    initial_state: MonorepoState = {
        "issue_title": "Add comment with name BluntBoy on tope of state.py file",
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
        "iteration_count": 0
    }

    flow = initialize_state_graph()
    app = flow.compile()
    final_state = app.invoke(initial_state)
    print(final_state)