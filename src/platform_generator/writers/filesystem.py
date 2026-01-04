"""Filesystem writer with configurable path templates."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

console = Console()


@dataclass
class ResourceCreationInfo:
    """Information about a created resource."""

    resource_type: str  # "namespace", "resourcequota", etc.
    resource_name: str  # Extracted from path
    file_path: Path  # Full path to file
    relative_path: Path  # Relative to output_directory


class FileWriter:
    """Write generated manifests to filesystem with configurable paths."""

    def __init__(
        self, output_directory: str, dry_run: bool = False, quiet: bool = False
    ):
        """
        Initialize the file writer.

        Args:
            output_directory: Base output directory path
            dry_run: If True, print what would be written without creating files
            quiet: If True, suppress individual file write messages
        """
        self.output_directory = Path(output_directory)
        self.dry_run = dry_run
        self.quiet = quiet
        self.files_written: list[Path] = []

    def render_path_template(
        self, template: str, variables: Dict[str, str]
    ) -> Path:
        """
        Render a path template with variables.

        Args:
            template: Path template string with {{variable}} placeholders
            variables: Dictionary of variable names to values

        Returns:
            Rendered path

        Example:
            >>> render_path_template(
            ...     "tenants/{{tenant}}/{{env}}/namespace.yaml",
            ...     {"tenant": "bar", "env": "dev"}
            ... )
            Path("tenants/bar/dev/namespace.yaml")
        """
        # Replace {{variable}} with value
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)

        # Validate no unreplaced templates remain
        if "{{" in rendered:
            remaining = re.findall(r"\{\{(\w+)\}\}", rendered)
            raise ValueError(
                f"Unresolved template variables in path: {remaining}. "
                f"Template: {template}, Variables: {variables}"
            )

        return Path(rendered)

    def write_file(
        self,
        content: str,
        path_template: str,
        variables: Dict[str, str],
        filename: str,
    ) -> Optional[Path]:
        """
        Write content to a file using a path template.

        Args:
            content: The YAML content to write
            path_template: Path template with {{variable}} placeholders
            variables: Dictionary of variables for path rendering
            filename: Filename (e.g., "namespace.yaml")

        Returns:
            Path to the written file, or None if dry-run

        Example:
            >>> writer.write_file(
            ...     content="apiVersion: v1...",
            ...     path_template="tenants/{{tenant}}/namespaces/{{env}}",
            ...     variables={"tenant": "bar", "env": "dev"},
            ...     filename="namespace.yaml"
            ... )
        """
        # Render the path template
        rendered_path = self.render_path_template(path_template, variables)
        full_path = self.output_directory / rendered_path / filename

        if self.dry_run:
            if not self.quiet:
                console.print(f"[dim]Would write:[/dim] {full_path}")
                console.print(f"[dim]Content:[/dim]\n{content}\n")
            # Track files even in dry-run mode for summary generation
            self.files_written.append(full_path)
            return None

        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        with open(full_path, "w") as f:
            f.write(content)

        self.files_written.append(full_path)
        if not self.quiet:
            console.print(f"[green]✓[/green] Wrote {full_path}")
        return full_path

    def get_output_summary(self) -> Dict[str, int]:
        """
        Get summary of written files.

        Returns:
            Dictionary with file counts by type
        """
        summary: Dict[str, int] = {}
        for path in self.files_written:
            # Extract resource type from path
            parts = path.parts
            if "namespaces" in parts:
                summary["namespaces"] = summary.get("namespaces", 0) + 1
            elif "resourcequotas" in parts:
                summary["resource-quotas"] = summary.get("resource-quotas", 0) + 1
            elif "networkpolicies" in parts:
                summary["network-policies"] = summary.get("network-policies", 0) + 1
            elif "appprojects" in parts:
                summary["app-projects"] = summary.get("app-projects", 0) + 1
            elif "applicationsets" in parts:
                summary["application-sets"] = summary.get("application-sets", 0) + 1

        return summary

    def _extract_resource_info(self, path: Path) -> tuple[str, str]:
        """
        Extract resource type and name from file path.

        Args:
            path: Full file path

        Returns:
            Tuple of (resource_type, resource_name)

        Example:
            >>> _extract_resource_info(
            ...     Path("tenants/bar/namespaces/dev/foo-gitops-wus3-dev/namespace.yaml")
            ... )
            ("namespace", "foo-gitops-wus3-dev")
        """
        parts = path.parts
        filename = path.stem  # Without .yaml extension

        try:
            # Namespaces: extract from directory name before filename
            if "namespaces" in parts:
                ns_idx = parts.index("namespaces")
                # The namespace name is typically 2 positions after "namespaces"
                # e.g., tenants/bar/namespaces/dev/foo-gitops-wus3-dev/namespace.yaml
                if len(parts) > ns_idx + 2:
                    return ("namespace", parts[ns_idx + 2])
                return ("namespace", filename)

            # ResourceQuotas: extract tenant-env from path
            elif "resourcequotas" in parts:
                # Extract tenant and env from path
                tenant = self._get_tenant_from_path(parts)
                env = self._get_env_from_path(parts)
                if tenant and env:
                    return ("resourcequota", f"{tenant}-{env}")
                return ("resourcequota", filename)

            # NetworkPolicies: use filename (deny-all, allow-namespace, etc.)
            elif "networkpolicies" in parts:
                # Use filename as the policy name
                return ("networkpolicy", filename)

            # AppProjects: extract from filename (appproject-bar.yaml -> bar)
            elif "appprojects" in parts:
                name = filename.replace("appproject-", "")
                return ("appproject", name)

            # ApplicationSets: extract from filename
            elif "applicationsets" in parts:
                name = filename.replace("applicationset-", "")
                return ("applicationset", name)

            # Fallback for unknown types
            return ("resource", filename)

        except (IndexError, ValueError):
            # Graceful fallback to filename-based naming
            return ("resource", filename)

    def _get_tenant_from_path(self, parts: tuple) -> Optional[str]:
        """
        Extract tenant name from path parts.

        Args:
            parts: Path parts tuple

        Returns:
            Tenant name or None
        """
        try:
            # Typically: tenants/bar/...
            if "tenants" in parts:
                tenant_idx = parts.index("tenants")
                if len(parts) > tenant_idx + 1:
                    return parts[tenant_idx + 1]
        except (IndexError, ValueError):
            pass
        return None

    def _get_env_from_path(self, parts: tuple) -> Optional[str]:
        """
        Extract environment from path parts.

        Args:
            parts: Path parts tuple

        Returns:
            Environment name or None
        """
        try:
            # Check for common env positions in paths
            # e.g., tenants/bar/resourcequotas/dev/resourcequota.yaml
            if "resourcequotas" in parts:
                quota_idx = parts.index("resourcequotas")
                if len(parts) > quota_idx + 1:
                    return parts[quota_idx + 1]
            elif "networkpolicies" in parts:
                policy_idx = parts.index("networkpolicies")
                if len(parts) > policy_idx + 1:
                    return parts[policy_idx + 1]
            elif "appprojects" in parts:
                project_idx = parts.index("appprojects")
                if len(parts) > project_idx + 1:
                    return parts[project_idx + 1]
            elif "applicationsets" in parts:
                # applicationsets path might be: tenants/bar/argocd/applicationsets/app/env
                appset_idx = parts.index("applicationsets")
                if len(parts) > appset_idx + 2:
                    return parts[appset_idx + 2]
            elif "namespaces" in parts:
                ns_idx = parts.index("namespaces")
                if len(parts) > ns_idx + 1:
                    return parts[ns_idx + 1]
        except (IndexError, ValueError):
            pass
        return None

    def get_detailed_summary(self) -> List[ResourceCreationInfo]:
        """
        Get detailed list of all created resources.

        Returns:
            List of ResourceCreationInfo objects for each written file
        """
        results = []
        for path in self.files_written:
            resource_type, resource_name = self._extract_resource_info(path)
            try:
                relative = path.relative_to(self.output_directory)
            except ValueError:
                # If path is not relative to output_directory, use the path as-is
                relative = path
            results.append(
                ResourceCreationInfo(
                    resource_type=resource_type,
                    resource_name=resource_name,
                    file_path=path,
                    relative_path=relative,
                )
            )
        return results
