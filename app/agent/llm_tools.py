from app.tools.tools import run_command


def run_tree(path: str = ".", depth: int = 3) -> str:
    ignore_pattern = "node_modules|.git|__pycache__|.venv|*.egg-info|dist|build|.pytest_cache"
    cmd = f"tree -L {depth} -I '{ignore_pattern}' {path}"
    result = run_command(cmd)
    if result["exit_code"] != 0:
        return f"Error executing tree: {result['stderr']}"
    return result["stdout"]


def run_ripgrep(pattern: str, path: str = ".", context_lines: int = 2, max_count: int = 25) -> str:
    cmd = f"rg -i -n '{pattern}' -C {context_lines} --max-count {max_count} --color=never {path}"
    result = run_command(cmd)
    if result["exit_code"] == 1:
        return f"No matches found for pattern: '{pattern}'"
    if result["exit_code"] != 0:
        return f"Error executing ripgrep: {result['stderr']}"
    lines = result["stdout"].splitlines()
    if len(lines) > 80:
        return "\n".join(lines[:80]) + f"\n\n... [Truncated: {len(lines) - 80} additional lines omitted. Narrow your search path or query.]"
    return result["stdout"]


def find_files(pattern: str, path: str = ".") -> str:
    cmd = (
        f"find {path} -type f -name '{pattern}' "
        f"-not -path '*/.*' -not -path '*/node_modules/*' -not -path '*/__pycache__*' "
        f"| head -n 30"
    )
    result = run_command(cmd)
    if result["exit_code"] != 0:
        return f"Error finding files: {result['stderr']}"
    output = result["stdout"].strip()
    return output if output else f"No files matching '{pattern}' were found."


def read_file_snippet(file_path: str, start_line: int = 1, end_line: int = 60) -> str:
    if end_line - start_line > 100:
        end_line = start_line + 100
    cmd = f"sed -n '{start_line},{end_line}p' {file_path}"
    result = run_command(cmd)
    if result["exit_code"] != 0:
        return f"Error reading file {file_path}: {result['stderr']}"
    output = result["stdout"]
    if not output.strip():
        return f"File '{file_path}' is empty or lines {start_line}-{end_line} do not exist."
    numbered_lines = []
    for idx, line in enumerate(output.splitlines(), start=start_line):
        numbered_lines.append(f"{idx:4d} | {line}")
    return "\n".join(numbered_lines)


NAVIGATOR_TOOLS = [run_tree, run_ripgrep, find_files, read_file_snippet]