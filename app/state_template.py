
from typing import Any, Dict, List, Optional, TypedDict, Union

from app.node_template import SearchResultItem

class MonorepoState(TypedDict):
    current_phase_id: str
    parent_phase_id: str = Optional[str]
    user_query: str = Optional[str]
    initial_context: str = Optional[str]
    issue_title: str
    issue_description: str
    config: Dict[str, Any]
    project_root: str
    target_packages: List[str]
    filesystem_map: str
    symbol_map: str
    search_results: Union[List[SearchResultItem], Dict[str, Any]]
    relevant_files: List[str]
    proposed_plan: str
    diffs_to_apply: List[Dict[str, Any]]
    test_command: str
    test_stdout: str
    test_stderr: str
    is_resolved: bool