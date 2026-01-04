# Requirements Document: GitOps Platform Generator CLI

## Project Overview

Build a Python CLI tool that reads a declarative YAML configuration file (`platform.yaml`) and generates Kubernetes and ArgoCD manifests for multi-tenant GitOps deployments across multiple environments and clusters.

## Core Requirements

### Multi-Tenancy Support
- Support multiple tenants with isolated configurations
- Each tenant has its own namespaces, resource quotas, network policies, and ArgoCD resources
- Tenant-level common labels and annotations inherited by all resources
- Tenant short-name used for resource naming and labels

### Multi-Environment Support
- Support for dev, stage, prod, and custom environments
- Environment-specific configurations for resource quotas and sync policies
- Environment-to-cluster mapping via cluster `env` field
- Environment-specific ArgoCD Kubernetes Platform (AKP) instances

### Multi-Cluster Support
- Deploy resources across multiple Kubernetes clusters per environment
- Auto-generate namespace manifests for every cluster in an environment
- Cluster-specific labels applied to resources
- Cluster filtering based on environment association

## YAML Schema Requirements

### 1. Enhanced Network Policies Configuration

Replace simple boolean flag with detailed policy configuration supporting 4 policy types:

```yaml
network-policies:
  enabled: true
  default-deny-all: true                    # Generate default deny ingress/egress
  allow-within-namespace: true              # Allow pod-to-pod within namespace
  allow-from-ingress:                       # Allow from ingress controllers
    enabled: true
    ingress-controller-namespaces:
      - ingress-nginx
    ingress-controller-labels:
      - app: nginx-ingress
  custom-rules:                             # Custom CIDR-based rules
    - name: allow-to-database
      description: "Allow egress to database CIDR"
      policy-type: egress
      egress:
        - to:
          - ipBlock:
              cidr: 10.100.0.0/16
          ports:
            - protocol: TCP
              port: 5432
```

### 2. Namespace Auto-Generation Configuration

Add configuration for automatic namespace generation:

```yaml
namespace-config:
  naming-pattern: "{{short-name}}-gitops-{{env}}"
  auto-generate-per-cluster: true
```

Keep existing `namespaces` section for backward compatibility.

### 3. Git Generator Config Repository

Add to each application for ArgoCD Git Generator support:

```yaml
config-repo:
  url: "https://dev.azure.com/foo-org/Team-Bar/_git/bar-gitops-config"
  revision: HEAD
  files:
    - path: "apps/*/config.json"
```

The Git Generator will read `config.json` files from the tenant's config repository containing:

```json
{
  "cluster": "foo-gitops-wus3-dev",
  "region": "wus3",
  "environment": "dev",
  "path": "manifests/dev"
}
```

### 4. AKP Instance AppProject Namespace

Add namespace specification for AppProject deployment:

```yaml
akp-instances:
  akp-dev:
    environment: dev
    url: "https://dev.akp.foo-org.com"
    appproject-namespace: "argocd"
```

### 5. Configurable Output Paths

Add to `cli-config` section to specify where each resource type should be written:

```yaml
cli-config:
  output-directory: "./generated"
  validate-before-apply: true
  dry-run-default: true
  git-commit-message-template: "chore: update {{tenant}}/{{app}}"
  output-paths:
    namespaces: "tenants/{{tenant}}/namespaces/{{env}}/{{cluster}}"
    resource-quotas: "tenants/{{tenant}}/resourcequotas/{{env}}"
    network-policies: "tenants/{{tenant}}/networkpolicies/{{env}}"
    app-projects: "tenants/{{tenant}}/argocd/appprojects/{{env}}"
    application-sets: "tenants/{{tenant}}/argocd/applicationsets/{{app}}/{{env}}"
```

**Template Variables Available**:
- `{{tenant}}` - Tenant name or short-name
- `{{env}}` - Environment name (dev/stage/prod)
- `{{cluster}}` - Cluster name
- `{{app}}` - Application name

### 6. Global Network Policy Defaults (Optional)

Add top-level section for organization-wide defaults:

```yaml
global-network-policy-defaults:
  default-deny-all: true
  allow-within-namespace: true
  allow-from-ingress:
    enabled: true
    ingress-controller-namespaces:
      - ingress-nginx
```

## CLI Tool Requirements

### Technology Stack

**Required Technologies**:
- **Python 3.11+**: Modern Python with type hints
- **UV**: Package manager for fast, reliable dependency management
- **Typer**: CLI framework with elegant syntax and rich output
- **Jinja2**: Template engine for YAML generation
- **Pydantic**: Schema validation with type hints
- **ruamel.yaml**: YAML parser preserving comments and formatting
- **Rich**: Beautiful terminal output with colors and tables
- **kubernetes**: Python client for Kubernetes API (for validation)

### CLI Commands

#### 1. `platform-gen validate`

Validate the configuration file without generating manifests.

```bash
platform-gen validate --config platform.yaml
```

**Options**:
- `--config, -c PATH`: Path to platform.yaml (default: `platform.yaml`)

**Functionality**:
- Parse YAML file
- Validate against Pydantic schema
- Check for configuration errors
- Display summary of configuration (tenants, clusters, environments)
- Exit with code 0 if valid, 1 if invalid

#### 2. `platform-gen generate`

Generate Kubernetes and ArgoCD manifests.

```bash
platform-gen generate [OPTIONS]
```

**Options**:
- `--config, -c PATH`: Path to platform.yaml (default: `platform.yaml`)
- `--tenant, -t TEXT`: Generate for specific tenant only
- `--environment, -e TEXT`: Generate for specific environment only
- `--resource-type TEXT`: Generate specific resource type only
- `--dry-run`: Print what would be generated without writing files
- `--verbose, -v`: Verbose output

**Functionality**:
- Load and validate configuration
- Apply filters if specified
- Generate all resource types in sequence:
  1. Namespaces
  2. ResourceQuotas
  3. NetworkPolicies
  4. ArgoCD AppProjects
  5. ArgoCD ApplicationSets
- Write files to configurable output paths
- Display summary table of generated resources
- Exit with code 0 if successful, 1 if errors

#### 3. `platform-gen validate-deployment`

Validate that resources were correctly deployed to Kubernetes clusters.

```bash
platform-gen validate-deployment --tenant TENANT --environment ENV [OPTIONS]
```

**Options**:
- `--config, -c PATH`: Path to platform.yaml (default: `platform.yaml`)
- `--tenant, -t TEXT`: Tenant to validate (required)
- `--environment, -e TEXT`: Environment to validate (required)
- `--kubeconfig PATH`: Path to kubeconfig file
- `--context TEXT`: Kubernetes context to use

**Functionality**:
- Connect to Kubernetes clusters using kubeconfig
- Validate namespaces exist in all expected clusters
- Validate ResourceQuotas are applied with correct limits
- Validate all 4 NetworkPolicy types exist
- Validate ArgoCD AppProject exists in control plane
- Validate ArgoCD ApplicationSets exist with correct configuration
- Display validation report with pass/fail status
- Exit with code 0 if all validations pass, 1 if any fail

## Resource Generation Requirements

### 1. Kubernetes Namespaces

**Generation Logic**:
- Auto-generate namespace manifest for **every cluster** in each environment
- Use namespace name from `tenant.namespaces[environment]`
- Filter clusters by matching `cluster.env == environment`

**Output Path**: `generated/tenants/{tenant}/namespaces/{env}/{cluster}/namespace.yaml`

**Labels (auto-generated)**:
- `platform.foo-org.com/tenant`: `{tenant.short_name}`
- `platform.foo-org.com/environment`: `{environment}`
- `platform.foo-org.com/cluster`: `{cluster.name}`
- `platform.foo-org.com/managed-by`: `"platform-generator"`
- Plus tenant's `common-labels`

**Annotations**: Inherit from tenant's `common-annotations`

### 2. Kubernetes ResourceQuotas

**Generation Logic**:
- One ResourceQuota per environment (applies to all clusters via GitOps)
- Extract CPU and memory limits from `tenant.resource-quotas[environment]`
- Set both requests and limits for cpu and memory

**Output Path**: `generated/tenants/{tenant}/resourcequotas/{env}/resourcequota.yaml`

**Spec Requirements**:
```yaml
spec:
  hard:
    requests.cpu: "10"
    requests.memory: "20Gi"
    limits.cpu: "10"
    limits.memory: "20Gi"
```

### 3. Cilium NetworkPolicies

**Generation Logic**:
- Generate per environment (one set per environment)
- Create 4 separate policy files
- Use `cilium.io/v2` API version
- Only generate if `network-policies.enabled == true`

**Output Path**: `generated/tenants/{tenant}/networkpolicies/{env}/`

**Policy Types**:

1. **deny-all.yaml** - Default deny all ingress and egress
   ```yaml
   spec:
     endpointSelector: {}
     # Empty ingress/egress rules = deny all
   ```

2. **allow-same-namespace.yaml** - Allow pod-to-pod within namespace
   ```yaml
   spec:
     endpointSelector: {}
     ingress:
       - fromEndpoints:
         - matchLabels:
             k8s:io.kubernetes.pod.namespace: <namespace>
     egress:
       - toEndpoints:
         - matchLabels:
             k8s:io.kubernetes.pod.namespace: <namespace>
   ```

3. **allow-from-ingress.yaml** - Allow from ingress controllers
   ```yaml
   spec:
     endpointSelector: {}
     ingress:
       - fromEndpoints:
         - matchLabels:
             k8s:io.kubernetes.pod.namespace: ingress-nginx
   ```

4. **custom-{rule-name}.yaml** - Custom CIDR-based rules
   - One file per custom rule
   - Support both ingress and egress
   - Support CIDR blocks and port specifications

### 4. ArgoCD AppProjects

**Generation Logic**:
- One AppProject per tenant per environment
- Determine environments from `tenant.appproject.destinations` keys
- Find matching AKP instance by environment
- Include comment header: `# Deploy to AKP instance: {akp_instance.url}`
- Deploy to namespace specified in `akp-instance.appproject-namespace`

**Output Path**: `generated/tenants/{tenant}/argocd/appprojects/{env}/appproject-{tenant}.yaml`

**Spec Requirements**:
```yaml
spec:
  description: "{tenant.appproject.description}"
  sourceRepos:
    - "https://github.com/example/*"
  destinations:
    - server: "{cluster.api_server}"
      namespace: "{namespace}"
  clusterResourceWhitelist:
    - group: '*'
      kind: '*'
```

### 5. ArgoCD ApplicationSets

**Generation Logic**:
- One ApplicationSet per application per environment
- Use Git Generator pointing to tenant's config repository
- Template uses variables from config.json: `{{cluster}}`, `{{path}}`, `{{server}}`
- Apply sync policies from `application.environments[env][cluster].sync-policy`
- Reference AppProject: `tenant-{tenant.name}`

**Output Path**: `generated/tenants/{tenant}/argocd/applicationsets/{app-name}/{env}/applicationset-{app-name}.yaml`

**Git Generator Configuration**:
```yaml
spec:
  generators:
    - git:
        repoURL: "{config-repo.url}"
        revision: "{config-repo.revision}"
        files:
          - path: "apps/*/config.json"
```

**Template Requirements**:
- Use ArgoCD template variables: `{{ cluster }}`, `{{ app }}`, `{{ path }}`, `{{ server }}`
- These must be preserved in final YAML (not processed by Jinja2)
- Use `{% raw %}{{ variable }}{% endraw %}` in Jinja2 templates

## Architecture Requirements

### Project Structure

```
platform-generator/
├── src/
│   └── platform_generator/
│       ├── __init__.py
│       ├── cli.py                     # Typer CLI entrypoint
│       ├── config/
│       │   ├── __init__.py
│       │   ├── models.py              # Pydantic models for schema
│       │   ├── parser.py              # YAML parser
│       │   └── validator.py           # Schema validation
│       ├── generators/
│       │   ├── __init__.py
│       │   ├── base.py                # Base generator class
│       │   ├── namespace.py           # Namespace generator
│       │   ├── resourcequota.py       # ResourceQuota generator
│       │   ├── networkpolicy.py       # NetworkPolicy generator
│       │   ├── appproject.py          # AppProject generator
│       │   └── applicationset.py      # ApplicationSet generator
│       ├── writers/
│       │   ├── __init__.py
│       │   └── filesystem.py          # File writer with path templates
│       ├── validators/
│       │   ├── __init__.py
│       │   ├── kubernetes.py          # K8s resource validation
│       │   └── deployment.py          # Post-deployment validation
│       └── templates/                 # Jinja2 templates
│           ├── namespace.yaml.j2
│           ├── resourcequota.yaml.j2
│           ├── networkpolicy/
│           │   ├── deny-all.yaml.j2
│           │   ├── allow-namespace.yaml.j2
│           │   ├── allow-ingress.yaml.j2
│           │   └── custom.yaml.j2
│           └── argocd/
│               ├── appproject.yaml.j2
│               └── applicationset.yaml.j2
├── tests/
│   ├── __init__.py
│   ├── test_generators.py
│   ├── test_validation.py
│   └── fixtures/
│       └── platform.yaml
├── docs/
│   └── platform.yaml                  # Example configuration
├── pyproject.toml                     # UV/pip configuration
├── uv.lock                            # UV lock file
└── README.md
```

### Design Patterns

#### 1. Base Generator Pattern

All generators inherit from `BaseGenerator` abstract class:

```python
class BaseGenerator(ABC):
    def __init__(self, config: PlatformConfig, writer: FileWriter, template_dir: Path):
        self.config = config
        self.writer = writer
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))

    def get_auto_labels(self, tenant: Tenant, environment: str, cluster_name: str | None = None) -> Dict[str, str]:
        """Auto-generate standard labels for resources"""

    def get_auto_annotations(self, tenant: Tenant) -> Dict[str, str]:
        """Auto-generate standard annotations for resources"""

    @abstractmethod
    def generate(self, tenants: List[Tenant] | None = None, environments: List[str] | None = None) -> int:
        """Generate resources - must be implemented by subclasses"""
        pass

    def get_output_path_template(self) -> str:
        """Get the output path template for this generator"""
        pass
```

#### 2. Path Template Resolution

The `FileWriter` class resolves path templates with variables:

```python
def render_path_template(self, template: str, variables: Dict[str, str]) -> Path:
    """
    Render path template: "tenants/{{tenant}}/{{env}}"
    With variables: {"tenant": "bar", "env": "dev"}
    Returns: Path("tenants/bar/dev")
    """
```

#### 3. Pydantic Schema Validation

All configuration is validated through Pydantic models:

```python
class PlatformConfig(BaseModel):
    version: str
    metadata: Metadata
    cli_config: CLIConfig = Field(alias="cli-config")
    tenants: List[Tenant]

    # Helper methods
    def get_clusters_for_environment(self, env: str) -> List[PlatformCluster]:
        """Get all clusters for an environment"""

    def get_akp_instance_for_environment(self, env: str) -> AKPInstance:
        """Get AKP instance for an environment"""
```

#### 4. Jinja2 Double-Templating

For ArgoCD ApplicationSets, use `{% raw %}...{% endraw %}` to preserve ArgoCD variables:

```jinja2
name: {% raw %}'{{ cluster }}-{{ app }}'{% endraw %}
# Jinja2 renders as: name: '{{ cluster }}-{{ app }}'
# ArgoCD then processes {{ cluster }} and {{ app }} from config.json
```

## Implementation Phases

### Phase 1: Foundation ✅ COMPLETED
- [x] Initialize Python project with UV
- [x] Configure pyproject.toml with dependencies
- [x] Define Pydantic models (20+ models for complete schema)
- [x] Implement YAML parser with ruamel.yaml
- [x] Create CLI skeleton with Typer
- [x] Implement `validate` command

### Phase 2: Namespace & ResourceQuota Generators ✅ COMPLETED
- [x] Implement base generator class
- [x] Implement namespace generator with auto-generation logic
- [x] Implement resource quota generator
- [x] Create Jinja2 templates for both resources
- [x] Implement filesystem writer with path template support
- [x] Test end-to-end generation

### Phase 3: Network Policy Generator ✅ COMPLETED
- [x] Implement NetworkPolicyGenerator
- [x] Create 4 Jinja2 templates (deny-all, allow-namespace, allow-ingress, custom)
- [x] Handle custom CIDR rules parsing and validation
- [x] Add CIDR format validation
- [x] Test all 4 policy types

### Phase 4: ArgoCD AppProject Generator ✅ COMPLETED
- [x] Implement AppProjectGenerator
- [x] Create AppProject Jinja2 template
- [x] Implement AKP instance lookup by environment
- [x] Handle multi-cluster destinations
- [x] Test with multiple environments

### Phase 5: ArgoCD ApplicationSet Generator ✅ COMPLETED
- [x] Implement ApplicationSetGenerator with Git Generator
- [x] Create ApplicationSet Jinja2 template with double-templating
- [x] Implement sync policy merging
- [x] Handle label/annotation inheritance
- [x] Test Git Generator configuration

### Phase 6: Post-Deployment Validation ⏳ NOT STARTED
- [ ] Add kubernetes Python library dependency
- [ ] Implement `validators/kubernetes.py` for resource checks
- [ ] Implement `validators/deployment.py` for orchestration
- [ ] Create `validate-deployment` command in CLI
- [ ] Add kubeconfig and context selection support
- [ ] Implement validation report output

### Phase 7: Documentation & Polish ✅ COMPLETED
- [x] Create README.md with usage examples
- [x] Add Mermaid process flow diagram
- [x] Add `--dry-run` mode with rich output
- [x] Add `--tenant` and `--environment` filtering
- [x] Improve error messages
- [x] Create example platform.yaml
- [x] Create CLAUDE.md for AI assistant guidance

### Phase 8: Testing ⏳ NOT STARTED
- [ ] Create pytest test structure
- [ ] Add tests for all generators
- [ ] Add tests for validators
- [ ] Add tests for path template resolution
- [ ] Add tests for Pydantic schema validation
- [ ] Add integration tests for end-to-end generation

## Key Design Decisions

### 1. Python + UV + Typer
Modern Python stack for rapid development, excellent CLI UX with type hints, and fast dependency management.

### 2. Jinja2 Templates
Powerful, widely-used template engine with excellent ecosystem and familiar syntax for DevOps teams.

### 3. Configurable Output Paths
Allow users to customize output directory structure via `cli-config.output-paths` with template variables.

### 4. Auto-Generate Namespaces
Automatically create namespace manifests for every cluster in an environment rather than requiring explicit definitions.

### 5. Environment-Wide Resource Quotas
One quota definition per environment applies to all clusters (via GitOps replication).

### 6. Separate Network Policy Files
Each policy type in its own file for easier GitOps management.

### 7. AppProject Per Environment
Separate AppProjects for dev/stage/prod, each deployed to the corresponding AKP instance.

### 8. Git Generator with Per-Tenant Config Repo
Self-service model where teams manage their own `config.json` files in a separate repository.

### 9. Tenant-First Directory Structure
Organize output by tenant → resource type → environment → cluster for clear multi-tenant boundaries (but configurable).

### 10. Rich CLI Output
Use Rich library for beautiful, readable terminal output with colors, tables, and progress indicators.

### 11. Setuptools Build Backend
Use setuptools instead of hatchling due to pathspec compatibility issues.

### 12. Jinja2 Whitespace Control
Use `{% if %}` (not `{%- if %}`) to prevent YAML single-line concatenation. Configure `trim_blocks=True` and `lstrip_blocks=True` globally.

## Success Criteria

- ✅ CLI parses and validates platform.yaml using Pydantic models
- ✅ Generates namespaces for all clusters in each environment
- ✅ Generates resource quotas per environment
- ✅ Generates all 4 Cilium network policy types
- ✅ Generates ArgoCD AppProjects per environment
- ✅ Generates ArgoCD ApplicationSets with Git Generator
- ✅ Output directory structure uses configurable paths from platform.yaml
- ✅ All generated YAML is syntactically valid
- ✅ Dry-run mode works correctly with rich formatted output
- ✅ `--tenant` and `--environment` filtering works correctly
- ✅ Validation provides helpful error messages
- ⏳ `validate-deployment` command successfully verifies deployed resources
- ⏳ All tests pass
- ✅ README includes Mermaid diagram showing CLI process flow
- ✅ UV successfully manages dependencies and creates reproducible environment

## Example Output Directory Structure

```
generated/
└── tenants/
    └── bar/
        ├── namespaces/
        │   ├── dev/
        │   │   ├── foo-gitops-wus3-dev/namespace.yaml
        │   │   └── foo-gitops-eus-dev/namespace.yaml
        │   ├── stage/
        │   │   ├── foo-gitops-wus3-stage/namespace.yaml
        │   │   └── foo-gitops-eus-stage/namespace.yaml
        │   └── prod/
        │       ├── foo-gitops-wus3-prod/namespace.yaml
        │       └── foo-gitops-eus-prod/namespace.yaml
        ├── resourcequotas/
        │   ├── dev/resourcequota.yaml
        │   ├── stage/resourcequota.yaml
        │   └── prod/resourcequota.yaml
        ├── networkpolicies/
        │   ├── dev/
        │   │   ├── deny-all.yaml
        │   │   ├── allow-same-namespace.yaml
        │   │   ├── allow-from-ingress.yaml
        │   │   └── custom-allow-to-database.yaml
        │   ├── stage/...
        │   └── prod/...
        └── argocd/
            ├── appprojects/
            │   ├── dev/appproject-bar.yaml
            │   ├── stage/appproject-bar.yaml
            │   └── prod/appproject-bar.yaml
            └── applicationsets/
                └── bar-mfe-frontend/
                    ├── dev/applicationset-bar-mfe-frontend.yaml
                    ├── stage/applicationset-bar-mfe-frontend.yaml
                    └── prod/applicationset-bar-mfe-frontend.yaml
```

## Current Status

**Completed**: 23 of 29 planned tasks (79%)

**Remaining Work**:
1. Post-deployment validation implementation (Phase 6)
2. Comprehensive test suite (Phase 8)

All core generators are implemented and functional. The CLI successfully generates production-ready Kubernetes and ArgoCD manifests for complete multi-tenant GitOps platforms.
