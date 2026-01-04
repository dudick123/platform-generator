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

                    # Merge labels
                    labels = self.get_auto_labels(tenant, env)
                    if application.common_labels:
                        labels.update(application.common_labels)

                    # Prepare template context
                    context = {
                        "applicationset_name": f"{application.name}-{env}",
                        "namespace": akp_instance.appproject_namespace,
                        "labels": labels,
                        "config_repo_url": application.config_repo.url,
                        "config_repo_revision": application.config_repo.revision,
                        "config_repo_files": application.config_repo.files,
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

                    # Write the ApplicationSet YAML file
                    filename = f"applicationset-{application.name}.yaml"
                    self.writer.write_file(
                        content=content,
                        path_template=self.get_output_path_template(),
                        variables=path_vars,
                        filename=filename,
                    )
                    count += 1

                    # Generate corresponding config.json file
                    config_json_count = self._generate_config_json(
                        tenant=tenant,
                        application=application,
                        env=env,
                    )
                    count += config_json_count

        return count

    def _resolve_config_json_path(
        self,
        path_pattern: str,
        tenant: str,
        app: str,
        env: str
    ) -> str:
        """
        Resolve config.json path pattern to actual path.

        Handles wildcard patterns like "apps/*/config.json" by replacing
        wildcards with actual values from tenant/app/env context.

        Args:
            path_pattern: Path pattern from config-repo.files (e.g., "apps/*/config.json")
            tenant: Tenant short name
            app: Application name
            env: Environment name

        Returns:
            Resolved path (e.g., "apps/bar-mfe-frontend/config.json")

        Examples:
            >>> _resolve_config_json_path("apps/*/config.json", "bar", "bar-mfe-frontend", "dev")
            "apps/bar-mfe-frontend/config.json"

            >>> _resolve_config_json_path("bom/dev/config.json", "bar", "bar-mfe-frontend", "dev")
            "bom/dev/config.json"
        """
        # Replace common wildcards with actual values
        resolved = path_pattern

        # Replace * with application name (common pattern)
        if "/*/" in resolved:
            resolved = resolved.replace("/*/", f"/{app}/")

        # Replace env placeholder if present
        if "{{env}}" in resolved:
            resolved = resolved.replace("{{env}}", env)

        return resolved

    def _generate_config_json(
        self,
        tenant: "Tenant",
        application: Application,
        env: str,
    ) -> int:
        """
        Generate config.json files for Git Generator.

        Creates JSON configuration files that define which applications
        should be deployed to which clusters. These files are consumed
        by ArgoCD's Git Generator.

        Args:
            tenant: Tenant configuration
            application: Application configuration
            env: Environment name

        Returns:
            Number of config.json files generated
        """
        import json

        # Get clusters for this environment from application.environments[env]
        env_clusters = application.environments.get(env, [])
        if not env_clusters:
            return 0

        # Build config.json structure
        config_entries = []
        for cluster_config in env_clusters:
            # Get cluster details from platform_clusters
            cluster_key = cluster_config.cluster
            platform_cluster = self.config.platform_clusters.get(cluster_key)
            if not platform_cluster:
                # Skip if cluster not found
                continue

            entry = {
                "name": f"{application.name}-{platform_cluster.name}",
                "source": application.repo_url,
                "revision": "main",  # Could be made configurable
                "manifestPath": cluster_config.repo_path,
                "project": tenant.name,
                "namespace": tenant.namespaces.get(env, f"{tenant.short_name}-gitops-{env}"),
                "cluster": platform_cluster.name,
            }
            config_entries.append(entry)

        # If no valid entries, skip generation
        if not config_entries:
            return 0

        # Convert to JSON
        json_content = json.dumps(config_entries, indent=2)

        # Use default output path for config files
        config_output_template = "tenants/{{tenant}}/config-repo/{{app}}/{{env}}"

        # Prepare path variables
        path_vars = {
            "tenant": tenant.short_name,
            "app": application.name,
            "env": env,
        }

        # Write config.json file
        self.writer.write_file(
            content=json_content,
            path_template=config_output_template,
            variables=path_vars,
            filename="config.json",
        )

        return 1
