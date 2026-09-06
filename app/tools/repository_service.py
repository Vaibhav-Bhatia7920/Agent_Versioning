import subprocess
from dataclasses import dataclass

from app.tools.command_executor import CommandResult


@dataclass(frozen=True)
class RepositoryService:
    project_root: str

    def current_head(self) -> str:
        return self._run_git(["rev-parse", "HEAD"]).stdout.strip() or "unknown"

    def create_commit(self, commit_message: str) -> str:
        add_result = self._run_git(["add", "-u"])
        if add_result.exit_code != 0:
            return "unknown"

        commit_result = self._run_git(["commit", "-m", commit_message])
        if commit_result.exit_code != 0:
            return self.current_head()

        return self.current_head()

    def _run_git(self, args: list[str]) -> CommandResult:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            return CommandResult(stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode)
        except Exception as error:
            return CommandResult(stdout="", stderr=str(error), exit_code=1)