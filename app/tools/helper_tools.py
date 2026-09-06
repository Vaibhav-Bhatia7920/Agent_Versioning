
from typing import List, Dict, Optional, Sequence, Union

from app.node_template import SearchResultItem


def parse_ripgrep_output(raw_output: str) -> List[SearchResultItem]:
    return parse_search_results(raw_output)

def parse_search_results(
    raw_results: Union[str, Sequence[str]],
) -> List[SearchResultItem]:
    """Parse ripgrep output into validated search result models."""
    lines = raw_results.splitlines() if isinstance(raw_results, str) else raw_results
    results: List[SearchResultItem] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("..."):
            continue

        file, separator, remainder = line.partition(":")
        line_number, separator, content = remainder.partition(":")
        if separator and line_number.isdigit():
            results.append(
                SearchResultItem(
                    file=file,
                    line=int(line_number),
                    content=content.strip(),
                )
            )
        else:
            results.append(SearchResultItem(file="unknown", content=line))

    return results
