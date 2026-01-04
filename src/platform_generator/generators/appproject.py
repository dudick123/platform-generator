"""ArgoCD AppProject generator."""

from typing import List

from ..config.models import Tenant
from .base import BaseGenerator


class AppProjectGenerator(BaseGenerator):
    """Generator for ArgoCD AppProject resources."""

    def get_output_path_template(self) -> str:
        """Get the output path template for app projects."""
        if self.config.cli_config.output_paths:
            return self.config.cli_config.output_paths.app_projects
        return "tenants/{{tenant}}/argocd/appprojects/{{env}}"

    def generate(
        self,
        tenants: List[Tenant] | None = None,
        environments: List[str] | None = None,
    ) -> int:
        """
        Generate ArgoCD AppProject manifests.

        Creates one AppProject per tenant per environment, deployed to the
        corresponding AKP (ArgoCD Kubernetes Platform) control plane instance.

        Args:
            tenants: Optional list of tenants to generate for (None = all)
            environments: Optional list of environments to generate for (None = all)

        Returns:
            Number of app projects generated
        """
        template = self.load_template("argocd/appproject.yaml.j2")
        count = 0

        # Default to all tenants and environments
        tenants_to_process = tenants or self.config.tenants
        environments_to_process = environments or self.config.defaults.environments

        for tenant in tenants_to_process:
            appproject = tenant.appproject

            # Get unique environments from destinations
            tenant_environments = set(appproject.destinations.keys())

            # Filter to requested environments
            for env in tenant_environments:
                if env not in environments_to_process:
                    continue

                # Get AKP instance for this environment
                akp_instance = self.config.get_akp_instance_for_environment(env)
                if not akp_instance:
                    # Skip if no AKP instance found for environment
                    continue

                # Get destinations for this environment
                destinations = appproject.destinations[env]

                # Build destination list for AppProject
                destination_list = []
                for dest in destinations:
                    destination_list.append({
                        "name": dest.cluster,
                        "namespace": dest.namespace,
                        # In real deployment, you'd map cluster names to server URLs
                        # For now, using the cluster name
                        "server": f"https://{dest.cluster}",
                    })

                # Prepare template context
                context = {
                    "project_name": f"{tenant.name}",
                    "namespace": akp_instance.appproject_namespace,
                    "description": appproject.description,
                    "source_repos": appproject.source_repos,
                    "destinations": destination_list,
                    "labels": self.get_auto_labels(tenant, env),
                    "annotations": self.get_auto_annotations(tenant),
                    "akp_instance_url": akp_instance.url,
                }

                # Render the template
                content = template.render(**context)

                # Prepare path variables
                path_vars = {
                    "tenant": tenant.short_name,
                    "env": env,
                }

                # Write the file
                filename = f"appproject-{tenant.short_name}.yaml"
                self.writer.write_file(
                    content=content,
                    path_template=self.get_output_path_template(),
                    variables=path_vars,
                    filename=filename,
                )

                count += 1

        return count
