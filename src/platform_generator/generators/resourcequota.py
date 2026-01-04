"""ResourceQuota generator."""

from typing import List

from ..config.models import Tenant
from .base import BaseGenerator


class ResourceQuotaGenerator(BaseGenerator):
    """Generator for Kubernetes ResourceQuota resources."""

    def get_output_path_template(self) -> str:
        """Get the output path template for resource quotas."""
        if self.config.cli_config.output_paths:
            return self.config.cli_config.output_paths.resource_quotas
        return "tenants/{{tenant}}/resourcequotas/{{env}}"

    def generate(
        self,
        tenants: List[Tenant] | None = None,
        environments: List[str] | None = None,
    ) -> int:
        """
        Generate ResourceQuota manifests per environment.

        Creates one ResourceQuota per environment that applies to all clusters
        in that environment (via GitOps replication).

        Args:
            tenants: Optional list of tenants to generate for (None = all)
            environments: Optional list of environments to generate for (None = all)

        Returns:
            Number of resource quotas generated
        """
        template = self.load_template("resourcequota.yaml.j2")
        count = 0

        # Default to all tenants and environments
        tenants_to_process = tenants or self.config.tenants
        environments_to_process = environments or self.config.defaults.environments

        for tenant in tenants_to_process:
            # Iterate through resource quotas
            for quota_dict in tenant.resource_quotas:
                # Each item in resource_quotas is a dict with env as key
                for env, quota_spec in quota_dict.items():
                    # Skip if not in requested environments
                    if env not in environments_to_process:
                        continue

                    # Skip if tenant doesn't have namespace for this environment
                    if env not in tenant.namespaces:
                        continue

                    namespace_name = tenant.namespaces[env]

                    # Prepare template context
                    context = {
                        "quota_name": f"{tenant.short_name}-quota",
                        "namespace_name": namespace_name,
                        "cpu": quota_spec.cpu,
                        "memory": quota_spec.memory,
                        "labels": self.get_auto_labels(tenant, env),
                        "annotations": self.get_auto_annotations(tenant),
                    }

                    # Render the template
                    content = template.render(**context)

                    # Prepare path variables
                    path_vars = {
                        "tenant": tenant.short_name,
                        "env": env,
                    }

                    # Write the file
                    self.writer.write_file(
                        content=content,
                        path_template=self.get_output_path_template(),
                        variables=path_vars,
                        filename="resourcequota.yaml",
                    )

                    count += 1

        return count
