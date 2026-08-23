import re
from typing import List

from app.template import SearchResultItem


def parse_ripgrep_output(raw_output: str) -> List[SearchResultItem]:
    items: List[SearchResultItem] = []

    for line in raw_output.splitlines():
        match = re.match(r"^([^:]+):(\d+):(.*)$", line.strip())
        if match:
            items.append(
                SearchResultItem(
                    file=match.group(1),
                    line=int(match.group(2)),
                    content=match.group(3).strip(),
                )
            )
        elif line.strip() and not line.startswith("..."):
            items.append(SearchResultItem(file="unknown", line=None, content=line.strip()))

    return items