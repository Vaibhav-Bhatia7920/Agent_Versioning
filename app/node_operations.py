import json
import hashlib
import subprocess
from typing import Any, Optional

from app.db import fetch_node, initialize_database, upsert_node
from app.template import Node
from app.node_template import *



def _current_git_head_commit(project_root: str) -> str:
	try:
		result = subprocess.run(
			["git", "rev-parse", "HEAD"],
			cwd=project_root,
			capture_output=True,
			text=True,
			check=False,
		)
		commit = result.stdout.strip()
		return commit or "unknown"
	except Exception:
		return "unknown"


def _create_git_commit(project_root: str, commit_message: str) -> str:
	try:
		add_result = subprocess.run(
			["git", "add", "-u"],
			cwd=project_root,
			capture_output=True,
			text=True,
			check=False,
		)
		if add_result.returncode != 0:
			return "unknown"

		commit_result = subprocess.run(
			["git", "commit", "-m", commit_message],
			cwd=project_root,
			capture_output=True,
			text=True,
			check=False,
		)
		if commit_result.returncode != 0:
			return _current_git_head_commit(project_root)

		return _current_git_head_commit(project_root)
	except Exception:
		return "unknown"


def _node_hash(state: MonorepoState, payload: Any) -> str:
	digest_source = json.dumps(
		{
			"issue_title": state.get("issue_title", ""),
			"issue_description": state.get("issue_description", ""),
			"project_root": state.get("project_root", ""),
			"payload": payload,
		},
		sort_keys=True,
		default=str,
	)
	return hashlib.sha256(digest_source.encode("utf-8")).hexdigest()


def initialize_root_phase(state: MonorepoState) -> Node:
	root_node_id = state.get("current_node_id") or "root"
	return Node(
		NodeId=root_node_id,
		ParentNodeId=None,
		NodeHash=_node_hash("root", state, {"kind": "root"}),
		GitCommitSHA=_current_git_head_commit(state.get("project_root") or "."),
		NodePrompt=state.get("issue_title", ""),
		NodeRawResponse=json.dumps({"kind": "root", "issue_title": state.get("issue_title", "")}, default=str),
	)


def create_child_phase(current_snap: Node, user_query: str, state: MonorepoState, raw_response: Any) -> Node:
	child_node_id = f"{current_snap.NodeId}:{_node_hash('child', state, {'parent': current_snap.NodeId, 'query': user_query})[:12]}"
	return Node(
		NodeId=child_node_id,
		ParentNodeId=current_snap.NodeId,
		NodeHash=_node_hash(child_node_id, state, {"parent": current_snap.NodeId, "query": user_query, "raw_response": raw_response}),
		GitCommitSHA=_current_git_head_commit(state.get("project_root") or "."),
		NodePrompt=user_query,
		NodeRawResponse=json.dumps(raw_response, default=str),
	)


def _persist_node(node_name: str, state: MonorepoState, payload: Any) -> None:
	project_root = state.get("project_root") or "."
	initialize_database()
	commit_message = f"Record {node_name} node state"
	git_commit_sha = _create_git_commit(project_root, commit_message)
	parent_id = state.get("current_node_id") or state.get("parent_id")
	upsert_node(
		node_id=node_name,
		parent_id=parent_id,
		node_hash=_node_hash(node_name, state, payload),
		git_commit_sha=git_commit_sha,
		raw_response=json.dumps(payload, default=str),
	)


def ensure_root_phase(state: MonorepoState) -> str:
	root_snap = initialize_root_phase(state)
	initialize_database()
	if fetch_node(root_snap.NodeId) is None:
		upsert_node(
			node_id=root_snap.NodeId,
			parent_id=root_snap.ParentNodeId,
			node_hash=root_snap.NodeHash,
			git_commit_sha=root_snap.GitCommitSHA,
			raw_response=root_snap.NodeRawResponse,
		)
	return root_snap.NodeId

def initialize_and_upsert_child(state: MonorepoState):
	Obj = Node(
		NodeId=state.get("current_node_id"),
		ParentNodeId=state.get("parent_node_id"),
		NodeHash=_node_hash(state.get("current_node_id"), state, {"kind": "child"}),
		GitCommitSHA=_current_git_head_commit(state.get("project_root") or "."),
		NodePrompt=state.get("user_query", ""),
		NodeRawResponse=json.dumps(state.get("payload", {}), default=str),
	)

	upsert_node(
		node_id=Obj.NodeId,
		parent_id=Obj.ParentNodeId,
		node_hash=Obj.NodeHash,
		git_commit_sha=Obj.GitCommitSHA,		
		raw_response=Obj.NodeRawResponse,
	)
	return Obj.NodeId



