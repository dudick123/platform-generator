"""ArgoCD ApplicationSet generator."""

from typing import Dict, List

from ..config.models import Application, Tenant
from .base import BaseGenerator


class ApplicationSetGenerator(BaseGenerator):
    """Generator for ArgoCD ApplicationSet resources with Git Generator."""

    def get_output_path_template(self) -> str:
        """Get the output path template for application sets."""
        if self.config.cli_config.output_paths:
            return self.config.cli_config.output_paths.application_sets
        return "tenants/{{tenant}}/argocd/applicationsets/{{app}}/{{env}}"

    def generate(
        self,
        tenants: List[Tenant] | None = None,
        environments: List[str] | None = None,
    ) -> int:
        """
        Generate ArgoCD ApplicationSet manifests with Git Generator.

        Creates ApplicationSets that use Git Generator for self-service
        deployments. The Git Generator reads config.json files from a
        per-tenant configuration repository.

        Args:
            tenants: Optional list of tenants to generate for (None = all)
            environments: Optional list of environments to generate for (None = all)

        Returns:
            Number of application sets generated
        """
        template = self.load_template("argocd/applicationset.yaml.j2")
        count = 0

        # Default to all tenants and environments
        tenants_to_process = tenants or self.config.tenants
        environments_to_process = environments or self.config.defaults.environments

        for tenant in tenants_to_process:
            # Iterate through applications
            for application in tenant.applications:
                # Skip if not an applicationset with git-generator
                if (
                    application.argo_app_type != "applicationset"
                    or application.generator_type != "git-generator"
                ):
                    continue

                # Check if config-repo is defined
                if not application.config_repo:
                    # Skip if no config repo defined
                    continue

                # Get environments for this application
                app_environments = set(application.environments.keys())

                # Filter to requested environments
                for env in app_environments:
                    if env not in environments_to_process:
                        continue

                    # Get AKP instance for this environment
                    akp_instance = self.config.get_akp_instance_for_environment(env)
                    if not akp_instance:
                        continue

                    # Get namespace for this environment
                    if env not in tenant.namespaces:
                        continue
                    namespace_name = tenant.namespaces[env]

                    # Get clusters for this environment
                    env_clusters = application.environments[env]

                    # Get sync policy (use first cluster's policy as default)
                    sync_policy = None
                    if env_clusters and env_clusters[0].sync_policy:
                        sync_policy = env_clusters[0].sync_policy

                    # Merge labels
                    labels = self.get_auto_labels(tenant, env)
                    if application.common_labels:
                        labels.update(application.common_labels)

                    # Merge annotations
                    annotations = self.get_auto_annotations(tenant)
                    if application.common_annotations:
                        annotations.update(application.common_annotations)

                    # Prepare template context
                    context = {
                        "applicationset_name": f"{application.name}-{env}",
                        "namespace": akp_instance.appproject_namespace,
                        "project_name": tenant.name,
                        "labels": labels,
                        "annotations": annotations,
                        "config_repo_url": application.config_repo.url,
                        "config_repo_revision": application.config_repo.revision,
                        "config_repo_files": application.config_repo.files,
                        "app_repo_url": application.repo_url,
                        "destination_namespace": namespace_name,
                        "sync_policy": sync_policy,
                        "akp_instance_url": akp_instance.url,
                    }

                    # Render the template
                    content = template.render(**context)

                    # Prepare path variables
                    path_vars = {
                        "tenant": tenant.short_name,
                        "app": application.name,
                        "env": env,
                    }

                    # Write the file
                    filename = f"applicationset-{application.name}.yaml"
                    self.writer.write_file(
                        content=content,
                        path_template=self.get_output_path_template(),
                        variables=path_vars,
                        filename=filename,
                    )

                    count += 1

        return count
