"""SQLite persistence helpers for node rows."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "node_store.db"


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Open a SQLite connection with row access by column name."""
    connection = sqlite3.connect(str(db_path or DEFAULT_DB_PATH))
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: Optional[Path | str] = None) -> None:
    """Create the node table if it does not already exist."""
    with get_connection(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS node (
                node_id TEXT PRIMARY KEY,
                parent_id TEXT,
                node_hash TEXT NOT NULL,
                git_commit_sha TEXT NOT NULL,
                raw_response TEXT NOT NULL
            )
            """
        )


def upsert_node(
    node_id: str,
    parent_id: Optional[str],
    node_hash: str,
    git_commit_sha: str,
    raw_response: str,
    db_path: Optional[Path | str] = None,
) -> None:
    """Insert or replace a node row."""
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO node (node_id, parent_id, node_hash, git_commit_sha, raw_response)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                parent_id = excluded.parent_id,
                node_hash = excluded.node_hash,
                git_commit_sha = excluded.git_commit_sha,
                raw_response = excluded.raw_response
            """,
            (node_id, parent_id, node_hash, git_commit_sha, raw_response),
        )


def fetch_node(node_id: str, db_path: Optional[Path | str] = None) -> Optional[sqlite3.Row]:
    """Fetch a node row by node id."""
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "SELECT node_id, parent_id, node_hash, git_commit_sha, raw_response FROM node WHERE node_id = ?",
            (node_id,),
        )
        return cursor.fetchone()


def list_nodes(db_path: Optional[Path | str] = None) -> Iterable[sqlite3.Row]:
    """Return all node rows."""
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "SELECT node_id, parent_id, node_hash, git_commit_sha, raw_response FROM node ORDER BY node_id"
        )
        return cursor.fetchall()