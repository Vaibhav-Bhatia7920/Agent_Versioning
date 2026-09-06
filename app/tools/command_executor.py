import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int


def run_command(command: str) -> CommandResult:
    """Run a shell command and return captured output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return CommandResult(
            stdout=result.stdout.decode("utf-8"),
            stderr=result.stderr.decode("utf-8"),
            exit_code=result.returncode,
        )
    except subprocess.CalledProcessError as error:
        return CommandResult(
            stdout=error.stdout.decode("utf-8"),
            stderr=error.stderr.decode("utf-8"),
            exit_code=error.returncode,
        )