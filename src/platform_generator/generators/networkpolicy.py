"""Cilium NetworkPolicy generator."""

from typing import List

from ..config.models import NetworkPoliciesConfig, Tenant
from .base import BaseGenerator


class NetworkPolicyGenerator(BaseGenerator):
    """Generator for Cilium NetworkPolicy resources."""

    def get_output_path_template(self) -> str:
        """Get the output path template for network policies."""
        if self.config.cli_config.output_paths:
            return self.config.cli_config.output_paths.network_policies
        return "tenants/{{tenant}}/networkpolicies/{{env}}"

    def generate(
        self,
        tenants: List[Tenant] | None = None,
        environments: List[str] | None = None,
    ) -> int:
        """
        Generate Cilium NetworkPolicy manifests.

        Creates 4 types of network policies per environment:
        1. default-deny-all: Deny all ingress and egress by default
        2. allow-same-namespace: Allow pod-to-pod communication within namespace
        3. allow-from-ingress: Allow traffic from ingress controllers
        4. custom rules: CIDR-based custom policies

        Args:
            tenants: Optional list of tenants to generate for (None = all)
            environments: Optional list of environments to generate for (None = all)

        Returns:
            Number of network policies generated
        """
        count = 0

        # Default to all tenants and environments
        tenants_to_process = tenants or self.config.tenants
        environments_to_process = environments or self.config.defaults.environments

        for tenant in tenants_to_process:
            # Skip if network policies are not enabled or if it's just a string
            if isinstance(tenant.network_policies, str):
                continue

            network_policies: NetworkPoliciesConfig = tenant.network_policies

            if not network_policies.enabled:
                continue

            # Get global defaults if available
            global_defaults = self.config.global_network_policy_defaults

            # Iterate through environments
            for env in environments_to_process:
                # Skip if tenant doesn't have this environment
                if env not in tenant.namespaces:
                    continue

                namespace_name = tenant.namespaces[env]
                labels = self.get_auto_labels(tenant, env)

                # Prepare path variables
                path_vars = {
                    "tenant": tenant.short_name,
                    "env": env,
                }

                # 1. Generate default deny-all policy
                should_generate_deny = network_policies.default_deny_all
                if should_generate_deny or (
                    global_defaults and global_defaults.default_deny_all
                ):
                    count += self._generate_deny_all_policy(
                        namespace_name, labels, path_vars
                    )

                # 2. Generate allow-same-namespace policy
                should_generate_allow_ns = network_policies.allow_within_namespace
                if should_generate_allow_ns or (
                    global_defaults and global_defaults.allow_within_namespace
                ):
                    count += self._generate_allow_namespace_policy(
                        namespace_name, labels, path_vars
                    )

                # 3. Generate allow-from-ingress policy
                allow_ingress_config = network_policies.allow_from_ingress
                if allow_ingress_config and allow_ingress_config.enabled:
                    count += self._generate_allow_ingress_policy(
                        namespace_name,
                        labels,
                        path_vars,
                        allow_ingress_config.ingress_controller_namespaces,
                        allow_ingress_config.ingress_controller_labels,
                    )
                elif global_defaults and global_defaults.allow_from_ingress:
                    count += self._generate_allow_ingress_policy(
                        namespace_name,
                        labels,
                        path_vars,
                        global_defaults.allow_from_ingress.ingress_controller_namespaces,
                        global_defaults.allow_from_ingress.ingress_controller_labels,
                    )

                # 4. Generate custom rules
                for custom_rule in network_policies.custom_rules:
                    count += self._generate_custom_policy(
                        namespace_name, labels, path_vars, custom_rule
                    )

        return count

    def _generate_deny_all_policy(
        self, namespace_name: str, labels: dict, path_vars: dict
    ) -> int:
        """Generate default deny-all policy."""
        template = self.load_template("networkpolicy/deny-all.yaml.j2")

        context = {
            "namespace_name": namespace_name,
            "labels": labels,
        }

        content = template.render(**context)

        self.writer.write_file(
            content=content,
            path_template=self.get_output_path_template(),
            variables=path_vars,
            filename="deny-all.yaml",
        )

        return 1

    def _generate_allow_namespace_policy(
        self, namespace_name: str, labels: dict, path_vars: dict
    ) -> int:
        """Generate allow-same-namespace policy."""
        template = self.load_template("networkpolicy/allow-namespace.yaml.j2")

        context = {
            "namespace_name": namespace_name,
            "labels": labels,
        }

        content = template.render(**context)

        self.writer.write_file(
            content=content,
            path_template=self.get_output_path_template(),
            variables=path_vars,
            filename="allow-same-namespace.yaml",
        )

        return 1

    def _generate_allow_ingress_policy(
        self,
        namespace_name: str,
        labels: dict,
        path_vars: dict,
        ingress_namespaces: List[str],
        ingress_labels: List[dict],
    ) -> int:
        """Generate allow-from-ingress policy."""
        template = self.load_template("networkpolicy/allow-ingress.yaml.j2")

        context = {
            "namespace_name": namespace_name,
            "labels": labels,
            "ingress_namespaces": ingress_namespaces,
            "ingress_labels": ingress_labels,
        }

        content = template.render(**context)

        self.writer.write_file(
            content=content,
            path_template=self.get_output_path_template(),
            variables=path_vars,
            filename="allow-from-ingress.yaml",
        )

        return 1

    def _generate_custom_policy(
        self, namespace_name: str, labels: dict, path_vars: dict, custom_rule: any
    ) -> int:
        """Generate custom CIDR-based policy."""
        template = self.load_template("networkpolicy/custom.yaml.j2")

        context = {
            "policy_name": custom_rule.name,
            "namespace_name": namespace_name,
            "labels": labels,
            "description": custom_rule.description,
            "policy_type": custom_rule.policy_type,
            "ingress_rules": custom_rule.ingress,
            "egress_rules": custom_rule.egress,
        }

        content = template.render(**context)

        filename = f"custom-{custom_rule.name}.yaml"
        self.writer.write_file(
            content=content,
            path_template=self.get_output_path_template(),
            variables=path_vars,
            filename=filename,
        )

        return 1
