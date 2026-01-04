"""Base generator class for all resource generators."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, Template

from ..config.models import PlatformConfig, Tenant
from ..writers.filesystem import FileWriter


class BaseGenerator(ABC):
    """Base class for all resource generators."""

    def __init__(
        self,
        config: PlatformConfig,
        writer: FileWriter,
        template_dir: Path,
    ):
        """
        Initialize the generator.

        Args:
            config: Platform configuration
            writer: File writer for output
            template_dir: Directory containing Jinja2 templates
        """
        self.config = config
        self.writer = writer
        self.template_dir = template_dir

        # Set up Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def load_template(self, template_name: str) -> Template:
        """
        Load a Jinja2 template.

        Args:
            template_name: Name of the template file

        Returns:
            Loaded Jinja2 template
        """
        return self.jinja_env.get_template(template_name)

    def get_auto_labels(
        self,
        tenant: Tenant,
        environment: str,
        cluster_name: str | None = None,
    ) -> Dict[str, str]:
        """
        Get auto-generated labels for a resource.

        Args:
            tenant: Tenant configuration
            environment: Environment name
            cluster_name: Optional cluster name

        Returns:
            Dictionary of labels
        """
        labels = {
            "platform.foo-org.com/tenant": tenant.short_name,
            "platform.foo-org.com/environment": environment,
            "platform.foo-org.com/managed-by": "platform-generator",
        }

        if cluster_name:
            labels["platform.foo-org.com/cluster"] = cluster_name

        # Merge with tenant's common labels
        if tenant.common_labels:
            labels.update(tenant.common_labels)

        return labels

    def get_auto_annotations(self, tenant: Tenant) -> Dict[str, str]:
        """
        Get auto-generated annotations for a resource.

        Args:
            tenant: Tenant configuration

        Returns:
            Dictionary of annotations
        """
        annotations = {}

        # Merge with tenant's common annotations
        if tenant.common_annotations:
            annotations.update(tenant.common_annotations)

        return annotations

    @abstractmethod
    def generate(
        self,
        tenants: List[Tenant] | None = None,
        environments: List[str] | None = None,
    ) -> int:
        """
        Generate resources.

        Args:
            tenants: Optional list of tenants to generate for (None = all)
            environments: Optional list of environments to generate for (None = all)

        Returns:
            Number of resources generated
        """
        pass

    def get_output_path_template(self) -> str:
        """
        Get the output path template for this generator.

        Returns:
            Path template string
        """
        # Default implementation - subclasses should override if they use
        # a specific output path from cli-config.output-paths
        return "generated/{{tenant}}/{{resource_type}}/{{env}}"
