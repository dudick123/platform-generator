"""Git operations for automated workflows."""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

console = Console()


@dataclass
class GitRepoInfo:
    """Information about a git repository and files to commit."""

    repo_path: Path  # Git repo root
    files: List[Path]  # Files written to this repo
    tenant: Optional[str]  # For branch naming
    environment: Optional[str]  # For branch naming


@dataclass
class GitOperationResult:
    """Result of git operations for a single repository."""

    repo_path: Path
    success: bool
    branch_name: Optional[str] = None
    commit_hash: Optional[str] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class GitOperations:
    """Handles git operations for platform generator."""

    def __init__(
        self,
        branch_pattern: str,
        commit_message_template: str,
        auto_push: bool = True,
        dry_run: bool = False,
    ):
        """
        Initialize git operations.

        Args:
            branch_pattern: Template for branch names
            commit_message_template: Template for commit messages
            auto_push: Whether to automatically push to remote
            dry_run: If True, print commands without executing
        """
        self.branch_pattern = branch_pattern
        self.commit_message_template = commit_message_template
        self.auto_push = auto_push
        self.dry_run = dry_run

    def detect_repo_root(self, file_path: Path) -> Optional[Path]:
        """
        Walk up directory tree from file_path looking for .git directory.

        Args:
            file_path: Path to a file

        Returns:
            Path to git repository root, or None if not found
        """
        current = file_path.parent

        # Walk up the tree
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent

        return None

    def _extract_tenant_from_path(self, path: Path) -> Optional[str]:
        """
        Extract tenant name from path.

        Args:
            path: File path

        Returns:
            Tenant name or None
        """
        parts = path.parts
        try:
            if "tenants" in parts:
                tenant_idx = parts.index("tenants")
                if len(parts) > tenant_idx + 1:
                    return parts[tenant_idx + 1]
        except (IndexError, ValueError):
            pass
        return None

    def _extract_env_from_path(self, path: Path) -> Optional[str]:
        """
        Extract environment from path.

        Args:
            path: File path

        Returns:
            Environment name or None
        """
        parts = path.parts
        try:
            # Check for common resource type patterns
            resource_types = [
                "namespaces",
                "resourcequotas",
                "networkpolicies",
                "appprojects",
            ]

            for resource_type in resource_types:
                if resource_type in parts:
                    idx = parts.index(resource_type)
                    if len(parts) > idx + 1:
                        return parts[idx + 1]

            # Check for applicationsets (env is 2 positions after)
            if "applicationsets" in parts:
                idx = parts.index("applicationsets")
                if len(parts) > idx + 2:
                    return parts[idx + 2]

        except (IndexError, ValueError):
            pass
        return None

    def group_files_by_repo(
        self, files: List[Path], output_directory: Path
    ) -> Dict[Path, GitRepoInfo]:
        """
        Group generated files by their git repository.

        Args:
            files: List of generated file paths
            output_directory: Base output directory

        Returns:
            Dictionary mapping repo paths to GitRepoInfo objects
        """
        repos: Dict[Path, GitRepoInfo] = {}

        for file_path in files:
            repo_root = self.detect_repo_root(file_path)

            if repo_root is None:
                continue  # Skip files not in a git repo

            if repo_root not in repos:
                # Extract metadata from first file in this repo
                tenant = self._extract_tenant_from_path(file_path)
                environment = self._extract_env_from_path(file_path)

                repos[repo_root] = GitRepoInfo(
                    repo_path=repo_root,
                    files=[file_path],
                    tenant=tenant,
                    environment=environment,
                )
            else:
                # Add file to existing repo group
                repos[repo_root].files.append(file_path)

        return repos

    def render_branch_name(
        self, tenant: Optional[str], environment: Optional[str]
    ) -> str:
        """
        Render branch name from template.

        Args:
            tenant: Tenant name
            environment: Environment name

        Returns:
            Rendered branch name
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        branch = self.branch_pattern
        branch = branch.replace("{{tenant}}", tenant or "unknown")
        branch = branch.replace("{{env}}", environment or "multi")
        branch = branch.replace("{{timestamp}}", timestamp)

        return branch

    def render_commit_message(
        self, tenant: Optional[str], environment: Optional[str], file_count: int
    ) -> str:
        """
        Render commit message from template.

        Args:
            tenant: Tenant name
            environment: Environment name
            file_count: Number of files generated

        Returns:
            Rendered commit message
        """
        message = self.commit_message_template
        message = message.replace("{{tenant}}", tenant or "unknown")
        message = message.replace("{{env}}", environment or "multi")
        message = message.replace("{{app}}", environment or "multi")  # Fallback

        message += f"\n\nGenerated {file_count} file(s)"

        return message

    def _run_git_command(
        self, repo_path: Path, args: List[str], check: bool = True
    ) -> subprocess.CompletedProcess:
        """
        Execute git command in repository.

        Args:
            repo_path: Repository root
            args: Command args (without 'git')
            check: Raise on non-zero exit

        Returns:
            CompletedProcess result
        """
        cmd = ["git"] + args

        if self.dry_run:
            console.print(f"[dim]Would run: {' '.join(cmd)}[/dim]")
            # Return mock result
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=b"", stderr=b""
            )

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=False,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            if check:
                raise
            return e

    def _create_branch(
        self, repo_path: Path, branch_name: str, result: GitOperationResult
    ) -> bool:
        """
        Create and checkout branch.

        Args:
            repo_path: Repository path
            branch_name: Branch name to create
            result: Result object to update

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if branch exists
            check_result = self._run_git_command(
                repo_path,
                ["rev-parse", "--verify", branch_name],
                check=False,
            )

            if check_result.returncode == 0:
                # Branch exists, checkout
                self._run_git_command(repo_path, ["checkout", branch_name])
                result.warnings.append(f"Branch {branch_name} already exists, checked out")
            else:
                # Create new branch
                self._run_git_command(repo_path, ["checkout", "-b", branch_name])

            return True

        except subprocess.CalledProcessError as e:
            result.error_message = f"Failed to create branch: {e.stderr.decode().strip()}"
            return False

    def _add_files(self, repo_path: Path, result: GitOperationResult) -> bool:
        """
        Stage all files in repository.

        Args:
            repo_path: Repository path
            result: Result object to update

        Returns:
            True if successful, False otherwise
        """
        try:
            self._run_git_command(repo_path, ["add", "."])
            return True
        except subprocess.CalledProcessError as e:
            result.error_message = f"Failed to add files: {e.stderr.decode().strip()}"
            return False

    def _commit(
        self, repo_path: Path, message: str, result: GitOperationResult
    ) -> bool:
        """
        Commit staged changes.

        Args:
            repo_path: Repository path
            message: Commit message
            result: Result object to update

        Returns:
            True if successful, False otherwise
        """
        try:
            commit_result = self._run_git_command(
                repo_path, ["commit", "-m", message], check=False
            )

            if commit_result.returncode != 0:
                stderr = commit_result.stderr.decode().strip()
                if "nothing to commit" in stderr:
                    result.warnings.append("No changes to commit")
                    return True
                else:
                    result.error_message = f"Failed to commit: {stderr}"
                    return False

            # Get commit hash
            hash_result = self._run_git_command(
                repo_path, ["rev-parse", "HEAD"]
            )
            result.commit_hash = hash_result.stdout.decode().strip()[:7]

            return True

        except subprocess.CalledProcessError as e:
            result.error_message = f"Failed to commit: {e.stderr.decode().strip()}"
            return False

    def _push(
        self, repo_path: Path, branch_name: str, result: GitOperationResult
    ) -> bool:
        """
        Push branch to remote.

        Args:
            repo_path: Repository path
            branch_name: Branch name to push
            result: Result object to update

        Returns:
            True if successful, False otherwise
        """
        try:
            self._run_git_command(
                repo_path, ["push", "-u", "origin", branch_name], check=False
            )
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode().strip() if e.stderr else str(e)
            result.warnings.append(
                f"Push failed: {stderr}. You may need to push manually"
            )
            return False

    def execute_git_workflow(self, repo_info: GitRepoInfo) -> GitOperationResult:
        """
        Execute complete git workflow for one repository.

        Args:
            repo_info: Repository information

        Returns:
            GitOperationResult with success status and details
        """
        result = GitOperationResult(
            repo_path=repo_info.repo_path,
            success=False,
        )

        # Render branch name and commit message
        branch_name = self.render_branch_name(
            repo_info.tenant, repo_info.environment
        )
        commit_message = self.render_commit_message(
            repo_info.tenant, repo_info.environment, len(repo_info.files)
        )

        result.branch_name = branch_name

        # Step 1: Create/checkout branch
        if not self._create_branch(repo_info.repo_path, branch_name, result):
            return result

        # Step 2: Add files
        if not self._add_files(repo_info.repo_path, result):
            return result

        # Step 3: Commit
        if not self._commit(repo_info.repo_path, commit_message, result):
            return result

        # Mark as successful (even if push fails)
        result.success = True

        # Step 4: Push (optional)
        if self.auto_push:
            self._push(repo_info.repo_path, branch_name, result)

        return result


def process_git_operations(
    files: List[Path],
    output_directory: Path,
    config,  # CLIConfig instance
    dry_run: bool = False,
) -> List[GitOperationResult]:
    """
    Main entry point for git operations from CLI.

    Args:
        files: List of generated file paths
        output_directory: Base output directory
        config: CLI configuration object
        dry_run: If True, simulate operations without executing

    Returns:
        List of GitOperationResult objects
    """
    # Check if git operations are enabled
    if not config.git_enabled:
        return []

    # Check if git is available
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("[red]✗[/red] Git not found in PATH. Install git or disable git-enabled")
        return []

    # Create git operations instance
    git_ops = GitOperations(
        branch_pattern=config.git_branch_pattern,
        commit_message_template=config.git_commit_message_template,
        auto_push=config.git_auto_push,
        dry_run=dry_run,
    )

    # Group files by repository
    repos = git_ops.group_files_by_repo(files, output_directory)

    if not repos:
        console.print("[yellow]No git repositories found in output directories[/yellow]")
        return []

    # Execute workflow for each repo
    results = []
    for repo_path, repo_info in repos.items():
        console.print(f"\nProcessing repository: [cyan]{repo_path.relative_to(output_directory)}[/cyan]")

        result = git_ops.execute_git_workflow(repo_info)
        results.append(result)

        # Display result
        if result.success:
            console.print(
                f"[green]✓[/green] Successfully committed {len(repo_info.files)} file(s) "
                f"to branch [yellow]{result.branch_name}[/yellow]"
            )
            if result.commit_hash:
                console.print(f"  Commit: [dim]{result.commit_hash}[/dim]")

            # Show warnings
            for warning in result.warnings:
                console.print(f"  [yellow]⚠[/yellow] {warning}")
        else:
            console.print(
                f"[red]✗[/red] Git operations failed: {result.error_message}"
            )

    return results
