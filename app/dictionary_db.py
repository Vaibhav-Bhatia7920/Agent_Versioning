import shelve
from app.template import Node
from app.state_template import MonorepoState
from app.tools.node_helpers import _node_hash, _current_git_head_commit
import json
# Open (or create) the persistent dictionary file

def add_node_to_dict(node_id: str, state: MonorepoState):
    node_data = make_node_data(state)
    with shelve.open("my_dictionary") as db:
        db[node_id] = node_data
    return node_data

def get_node_from_dict(node_id: str) -> Node:
    with shelve.open("my_dictionary") as db:
        return db.get(node_id, None)

def make_node_data(state: MonorepoState):
    Obj = Node(
            NodeId=state.get("current_node_id"),
            ParentNodeId=state.get("parent_node_id"),
            NodeHash=_node_hash(state.get("current_node_id"), state, {"kind": "child"}),
            GitCommitSHA=_current_git_head_commit(state.get("project_root") or "."),
            NodePrompt=state.get("user_query", ""),
            NodeRawResponse=json.dumps(state.get("payload", {}), default=str),
        )
    return Obj