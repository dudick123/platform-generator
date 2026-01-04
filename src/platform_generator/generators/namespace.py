"""Namespace generator."""

from typing import List

from ..config.models import Tenant
from .base import BaseGenerator


class NamespaceGenerator(BaseGenerator):
    """Generator for Kubernetes Namespace resources."""

    def get_output_path_template(self) -> str:
        """Get the output path template for namespaces."""
        if self.config.cli_config.output_paths:
            return self.config.cli_config.output_paths.namespaces
        return "tenants/{{tenant}}/namespaces/{{env}}/{{cluster}}"

    def generate(
        self,
        tenants: List[Tenant] | None = None,
        environments: List[str] | None = None,
    ) -> int:
        """
        Generate Namespace manifests for all clusters.

        Auto-generates namespaces for every cluster in each environment
        based on the tenant's namespace configuration.

        Args:
            tenants: Optional list of tenants to generate for (None = all)
            environments: Optional list of environments to generate for (None = all)

        Returns:
            Number of namespaces generated
        """
        template = self.load_template("namespace.yaml.j2")
        count = 0

        # Default to all tenants and environments
        tenants_to_process = tenants or self.config.tenants
        environments_to_process = environments or self.config.defaults.environments

        for tenant in tenants_to_process:
            # Get namespace config (use default if not specified)
            namespace_config = tenant.namespace_config

            # Iterate through environments that have namespace definitions
            for env in environments_to_process:
                # Skip if this tenant doesn't have this environment
                if env not in tenant.namespaces:
                    continue

                namespace_name = tenant.namespaces[env]

                # Get all clusters for this environment
                clusters = self.config.get_clusters_for_environment(env)

                # Auto-generate namespace for each cluster
                for cluster in clusters:
                    # Prepare template context
                    context = {
                        "namespace_name": namespace_name,
                        "labels": self.get_auto_labels(tenant, env, cluster.name),
                        "annotations": self.get_auto_annotations(tenant),
                    }

                    # Render the template
                    content = template.render(**context)

                    # Prepare path variables
                    path_vars = {
                        "tenant": tenant.short_name,
                        "env": env,
                        "cluster": cluster.name,
                    }

                    # Write the file
                    self.writer.write_file(
                        content=content,
                        path_template=self.get_output_path_template(),
                        variables=path_vars,
                        filename="namespace.yaml",
                    )

                    count += 1

        return count
