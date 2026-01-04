"""Pydantic models for platform.yaml schema."""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class OutputPaths(BaseModel):
    """Configurable output paths for each resource type."""

    namespaces: str = "tenants/{{tenant}}/namespaces/{{env}}/{{cluster}}"
    resource_quotas: str = Field(
        "tenants/{{tenant}}/resourcequotas/{{env}}", alias="resource-quotas"
    )
    network_policies: str = Field(
        "tenants/{{tenant}}/networkpolicies/{{env}}", alias="network-policies"
    )
    app_projects: str = Field(
        "tenants/{{tenant}}/argocd/appprojects/{{env}}", alias="app-projects"
    )
    application_sets: str = Field(
        "tenants/{{tenant}}/argocd/applicationsets/{{app}}/{{env}}", alias="application-sets"
    )

    class Config:
        populate_by_name = True


class CLIConfig(BaseModel):
    """CLI configuration settings."""

    output_directory: str = Field("./generated", alias="output-directory")
    validate_before_apply: bool = Field(True, alias="validate-before-apply")
    dry_run_default: bool = Field(True, alias="dry-run-default")
    git_commit_message_template: str = Field(
        "chore: update {{tenant}}/{{app}}", alias="git-commit-message-template"
    )
    git_enabled: bool = Field(False, alias="git-enabled")
    git_branch_pattern: str = Field(
        "feat/platform-{{tenant}}-{{env}}-{{timestamp}}",
        alias="git-branch-pattern",
    )
    git_auto_push: bool = Field(True, alias="git-auto-push")
    output_paths: Optional[OutputPaths] = Field(None, alias="output-paths")

    class Config:
        populate_by_name = True


class Metadata(BaseModel):
    """Platform metadata."""

    description: str


class Defaults(BaseModel):
    """Default configuration values."""

    environments: List[str]


class AKPInstance(BaseModel):
    """ArgoCD Kubernetes Platform instance configuration."""

    environment: str
    url: str
    appproject_namespace: str = Field("argocd", alias="appproject-namespace")

    class Config:
        populate_by_name = True


class PlatformCluster(BaseModel):
    """Kubernetes cluster configuration."""

    name: str
    env: str
    region: str


class AllowFromIngress(BaseModel):
    """Configuration for allowing traffic from ingress controllers."""

    enabled: bool = True
    ingress_controller_namespaces: List[str] = Field(
        default_factory=list, alias="ingress-controller-namespaces"
    )
    ingress_controller_labels: List[Dict[str, str]] = Field(
        default_factory=list, alias="ingress-controller-labels"
    )

    class Config:
        populate_by_name = True


class IPBlock(BaseModel):
    """IP block configuration for network policies."""

    cidr: str


class NetworkPolicyPort(BaseModel):
    """Port configuration for network policies."""

    protocol: str = "TCP"
    port: Union[int, str]


class NetworkPolicyPeer(BaseModel):
    """Network policy peer (from/to) configuration."""

    ipBlock: Optional[IPBlock] = Field(None, alias="ipBlock")

    class Config:
        populate_by_name = True


class NetworkPolicyRule(BaseModel):
    """Network policy ingress/egress rule."""

    to: Optional[List[NetworkPolicyPeer]] = None
    from_: Optional[List[NetworkPolicyPeer]] = Field(None, alias="from")
    ports: Optional[List[NetworkPolicyPort]] = None

    class Config:
        populate_by_name = True


class CustomNetworkPolicyRule(BaseModel):
    """Custom network policy rule configuration."""

    name: str
    description: Optional[str] = None
    policy_type: Literal["ingress", "egress"] = Field(alias="policy-type")
    ingress: Optional[List[NetworkPolicyRule]] = None
    egress: Optional[List[NetworkPolicyRule]] = None

    class Config:
        populate_by_name = True


class NetworkPoliciesConfig(BaseModel):
    """Network policies configuration for a tenant."""

    enabled: bool = True
    default_deny_all: bool = Field(True, alias="default-deny-all")
    allow_within_namespace: bool = Field(True, alias="allow-within-namespace")
    allow_from_ingress: Optional[AllowFromIngress] = Field(None, alias="allow-from-ingress")
    custom_rules: List[CustomNetworkPolicyRule] = Field(default_factory=list, alias="custom-rules")

    class Config:
        populate_by_name = True


class GlobalNetworkPolicyDefaults(BaseModel):
    """Global network policy defaults."""

    default_deny_all: bool = Field(True, alias="default-deny-all")
    allow_within_namespace: bool = Field(True, alias="allow-within-namespace")
    allow_from_ingress: Optional[AllowFromIngress] = Field(None, alias="allow-from-ingress")

    class Config:
        populate_by_name = True


class NamespaceConfig(BaseModel):
    """Namespace generation configuration."""

    naming_pattern: str = Field("{{short-name}}-gitops-{{env}}", alias="naming-pattern")
    auto_generate_per_cluster: bool = Field(True, alias="auto-generate-per-cluster")

    class Config:
        populate_by_name = True


class ResourceQuotaSpec(BaseModel):
    """Resource quota specifications."""

    cpu: str
    memory: str


class AppProjectDestination(BaseModel):
    """ArgoCD AppProject destination configuration."""

    cluster: str
    namespace: str


class AppProjectConfig(BaseModel):
    """ArgoCD AppProject configuration."""

    description: str
    source_repos: List[str] = Field(alias="source-repos")
    destinations: Dict[str, List[AppProjectDestination]]

    class Config:
        populate_by_name = True


class ConfigRepo(BaseModel):
    """Git Generator config repository configuration."""

    url: str
    revision: str = "HEAD"
    files: List[Dict[str, str]]


class SyncPolicyAutomated(BaseModel):
    """ArgoCD sync policy automated configuration."""

    prune: bool = False
    selfHeal: bool = Field(False, alias="selfHeal")

    class Config:
        populate_by_name = True


class SyncPolicy(BaseModel):
    """ArgoCD sync policy configuration."""

    automated: SyncPolicyAutomated


class ApplicationEnvironmentCluster(BaseModel):
    """Application deployment configuration for a specific cluster."""

    cluster: str
    repo_path: str = Field(alias="repo-path")
    labels: Optional[Dict[str, str]] = None
    sync_policy: Optional[SyncPolicy] = Field(None, alias="sync-policy")

    class Config:
        populate_by_name = True


class Application(BaseModel):
    """Application configuration."""

    name: str
    argo_app_type: str = Field(alias="argo-app-type")
    generator_type: str = Field(alias="generator-type")
    repo_url: str = Field(alias="repo-url")
    config_repo: Optional[ConfigRepo] = Field(None, alias="config-repo")
    common_labels: Optional[Dict[str, str]] = Field(default_factory=dict, alias="common-labels")
    common_annotations: Optional[Dict[str, str]] = Field(
        default_factory=dict, alias="common-annotations"
    )
    environments: Dict[str, List[ApplicationEnvironmentCluster]]

    class Config:
        populate_by_name = True


class Tenant(BaseModel):
    """Tenant configuration."""

    name: str
    short_name: str = Field(alias="short-name")
    long_name: str = Field(alias="long-name")
    description: str
    ado_project_url: str = Field(alias="ado-project-url")
    appproject: AppProjectConfig
    namespace_config: Optional[NamespaceConfig] = Field(None, alias="namespace-config")
    namespaces: Dict[str, str]
    resource_quotas: List[Dict[str, ResourceQuotaSpec]] = Field(alias="resource-quotas")
    network_policies: Union[str, NetworkPoliciesConfig] = Field(alias="network-policies")
    common_labels: Optional[Dict[str, str]] = Field(default_factory=dict, alias="common-labels")
    common_annotations: Optional[Dict[str, str]] = Field(
        default_factory=dict, alias="common-annotations"
    )
    applications: List[Application]

    class Config:
        populate_by_name = True

    @field_validator("network_policies", mode="before")
    @classmethod
    def parse_network_policies(cls, v: Any) -> Union[str, NetworkPoliciesConfig]:
        """Parse network_policies - can be 'enabled' string or config object."""
        if isinstance(v, str):
            return v
        return v


class PlatformConfig(BaseModel):
    """Root platform configuration."""

    version: str
    metadata: Metadata
    cli_config: CLIConfig = Field(alias="cli-config")
    platform_base_repo_url: str = Field(alias="platform-base-repo-url")
    defaults: Defaults
    akp_instances: Dict[str, AKPInstance] = Field(alias="akp-instances")
    platform_clusters: Dict[str, PlatformCluster] = Field(alias="platform-clusters")
    global_network_policy_defaults: Optional[GlobalNetworkPolicyDefaults] = Field(
        None, alias="global-network-policy-defaults"
    )
    tenants: List[Tenant]

    class Config:
        populate_by_name = True

    def get_clusters_for_environment(self, env: str) -> List[PlatformCluster]:
        """Get all clusters for a specific environment."""
        return [cluster for cluster in self.platform_clusters.values() if cluster.env == env]

    def get_akp_instance_for_environment(self, env: str) -> Optional[AKPInstance]:
        """Get AKP instance for a specific environment."""
        for instance in self.akp_instances.values():
            if instance.environment == env:
                return instance
        return None

    def get_tenant_by_name(self, name: str) -> Optional[Tenant]:
        """Get tenant by name."""
        for tenant in self.tenants:
            if tenant.name == name or tenant.short_name == name:
                return tenant
        return None
