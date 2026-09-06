import json

from typing import Any

# from app.db import fetch_node, initialize_database, upsert_node
from app.template import Node
from app.node_template import *

from app.state_template import MonorepoState
from app.dictionary_db import add_node_to_dict, get_node_from_dict




# def _node_hash(state: MonorepoState, payload: Any) -> str:
# 	digest_source = json.dumps(
# 		{
# 			"issue_title": state.get("issue_title", ""),
# 			"issue_description": state.get("issue_description", ""),
# 			"project_root": state.get("project_root", ""),
# 			"payload": payload,
# 		},
# 		sort_keys=True,
# 		default=str,
# 	)
# 	return hashlib.sha256(digest_source.encode("utf-8")).hexdigest()








# def _persist_node(node_name: str, state: MonorepoState, payload: Any) -> None:
# 	project_root = state.get("project_root") or "."
# 	initialize_database()
# 	commit_message = f"Record {node_name} node state"
# 	git_commit_sha = _create_git_commit(project_root, commit_message)
# 	parent_id = state.get("current_node_id") or state.get("parent_id")
# 	upsert_node(
# 		node_id=node_name,
# 		parent_id=parent_id,
# 		node_hash=_node_hash(node_name, state, payload),
# 		git_commit_sha=git_commit_sha,
# 		raw_response=json.dumps(payload, default=str),
# 	)


# def ensure_root_phase(state: MonorepoState) -> str:
# 	root_snap = initialize_root_phase(state)
# 	initialize_database()
# 	if fetch_node(root_snap.NodeId) is None:
# 		upsert_node(
# 			node_id=root_snap.NodeId,
# 			parent_id=root_snap.ParentNodeId,
# 			node_hash=root_snap.NodeHash,
# 			git_commit_sha=root_snap.GitCommitSHA,
# 			raw_response=root_snap.NodeRawResponse,
# 		)
# 	return root_snap.NodeId

# def initialize_and_upsert_child(state: MonorepoState):
# 	Obj = Node(
# 		NodeId=state.get("current_node_id"),
# 		ParentNodeId=state.get("parent_node_id"),
# 		NodeHash=_node_hash(state.get("current_node_id"), state, {"kind": "child"}),
# 		GitCommitSHA=_current_git_head_commit(state.get("project_root") or "."),
# 		NodePrompt=state.get("user_query", ""),
# 		NodeRawResponse=json.dumps(state.get("payload", {}), default=str),
# 	)

# 	upsert_node(
# 		node_id=Obj.NodeId,
# 		parent_id=Obj.ParentNodeId,
# 		node_hash=Obj.NodeHash,
# 		git_commit_sha=Obj.GitCommitSHA,		
# 		raw_response=Obj.NodeRawResponse,
# 	)
# 	return Obj.NodeId

def step_back(no_steps : int, current_node_id: str):

	current_node = get_node_from_dict(current_node_id)
	if not current_node:
		raise ValueError(f"Node with ID {current_node_id} not found.")

	for _ in range(no_steps):
		if current_node.ParentNodeId is None:
			break  # Reached the root node
		current_node = get_node_from_dict(current_node.ParentNodeId)
		if not current_node:
			raise ValueError(f"Parent node with ID {current_node.ParentNodeId} not found.")

	return current_node.NodeId	
    




