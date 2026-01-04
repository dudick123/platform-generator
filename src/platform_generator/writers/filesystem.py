"""Filesystem writer with configurable path templates."""

import re
from pathlib import Path
from typing import Dict, Optional

from rich.console import Console

console = Console()


class FileWriter:
    """Write generated manifests to filesystem with configurable paths."""

    def __init__(self, output_directory: str, dry_run: bool = False):
        """
        Initialize the file writer.

        Args:
            output_directory: Base output directory path
            dry_run: If True, print what would be written without creating files
        """
        self.output_directory = Path(output_directory)
        self.dry_run = dry_run
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
            console.print(f"[dim]Would write:[/dim] {full_path}")
            console.print(f"[dim]Content:[/dim]\n{content}\n")
            return None

        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        with open(full_path, "w") as f:
            f.write(content)

        self.files_written.append(full_path)
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
