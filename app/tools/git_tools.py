from app.tools.command_executor import run_command


def git_add():
    """Stage all changes for the next commit."""
    return run_command("git add .")


def git_commit(message):
    """Create a git commit with the provided message."""
    return run_command(f'git commit -m "{message}"')


def git_reset_hard(commit_id):
    """Reset the repository hard to the provided commit id."""
    return run_command(f"git reset --hard {commit_id}")