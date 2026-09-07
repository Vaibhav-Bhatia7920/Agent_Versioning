import shelve
from app.node_template import Phase
from app.state_template import MonorepoState
from app.tools.node_helpers import _node_hash, _current_git_head_commit
import json
# Open (or create) the persistent dictionary file

def add_phase_to_dict(node_id: str, state: MonorepoState):
    node_data = make_phase_data(state)
    with shelve.open("my_dictionary") as db:
        db[node_id] = node_data
    return node_data

def get_phase_from_dict(node_id: str) -> Phase:
    with shelve.open("my_dictionary") as db:
        return db.get(node_id, None)

def make_phase_data(state: MonorepoState):
    Obj = Phase(
            PhaseId=state.get("current_phase_id"),
            ParentPhaseId=state.get("parent_phase_id"),
            PhaseHash=_node_hash(state.get("current_phase_id"), state, {"kind": "child"}),
            GitCommitSHA=_current_git_head_commit(state.get("project_root") or "."),
            PhaseQuery=state.get("user_query", ""),
            PhasePrompt=state.get("initial_context", ""),
            PhaseRawResponse=json.dumps(state.get("proposed_plan", {}), default=str),
        )
    return Obj