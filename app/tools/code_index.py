import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from tree_sitter import Language, Parser

try:
    from tree_sitter_python import language as python_language
except ImportError:
    python_language = None

try:
    from tree_sitter_javascript import language as javascript_language
except ImportError:
    javascript_language = None


@dataclass
class SymbolEntry:
    path: str
    kind: str
    name: str
    signature: str
    imports: List[str]
    line: int


def _repo_root(project_root: str) -> Path:
    root = Path(project_root).expanduser()
    return root if root.is_absolute() else Path.cwd() / root


def _db_path(project_root: str) -> Path:
    return _repo_root(project_root) / ".agent_versioning" / "symbol_map.sqlite3"


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            digest TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            signature TEXT NOT NULL,
            imports TEXT NOT NULL,
            line INTEGER NOT NULL,
            FOREIGN KEY(path) REFERENCES files(path) ON DELETE CASCADE
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_symbols_path ON symbols(path)")


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def _iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in {".git", ".venv", "__pycache__", "node_modules", "dist", "build"} for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx"}:
            continue
        yield path


def _language_for_path(path: Path) -> Optional[Any]:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return python_language() if python_language is not None else None
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return javascript_language() if javascript_language is not None else None
    return None


def _parser_for_language(language: Any) -> Parser:
    parser = Parser()
    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:
        parser.language = Language(language)
    return parser


def _parser_for_path(path: Path) -> Optional[Parser]:
    language = _language_for_path(path)
    if language is None:
        return None
    return _parser_for_language(language)


def build_symbol_map(project_root: str) -> Dict[str, Any]:
    root = _repo_root(project_root)
    db_path = _db_path(project_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    try:
        _ensure_schema(connection)
        connection.execute("DELETE FROM symbols")
        connection.execute("DELETE FROM files")

        file_count = 0
        symbol_count = 0
        for path in _iter_source_files(root):
            source_text = path.read_text(encoding="utf-8", errors="ignore")
            parser = _parser_for_path(path)
            if parser is None:
                continue
            tree = parser.parse(source_text.encode("utf-8", errors="ignore"))
            connection.execute(
                "INSERT OR REPLACE INTO files(path, digest) VALUES (?, ?)",
                (str(path.relative_to(root)), _digest(source_text)),
            )
            file_count += 1
            symbol_count += 1
        connection.commit()
        return {"project_root": str(root), "file_count": file_count, "symbol_count": symbol_count}
    finally:
        connection.close()


def load_symbol_map(project_root: str) -> str:
    db_path = _db_path(project_root)
    if not db_path.exists():
        return ""
    return f"symbol_map:{db_path}"