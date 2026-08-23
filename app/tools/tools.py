import subprocess

def run_command(command):
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return {"stdout": result.stdout.decode('utf-8'), "stderr": result.stderr.decode('utf-8'), "exit_code": result.returncode}
    except subprocess.CalledProcessError as e:
        return {"stdout": e.stdout.decode('utf-8'), "stderr": e.stderr.decode('utf-8'), "exit_code": e.returncode}


def git_add():
    """Stage all changes for the next commit."""
    return run_command("git add .")

def git_commit(message):
    """Create a git commit with the provided message."""
    return run_command(f'git commit -m "{message}"')


def git_reset_hard(commit_id):
    """Reset the repository hard to the provided commit id."""
    return run_command(f"git reset --hard {commit_id}")