# GitOps Platform Generator CLI

A Python CLI tool for generating Kubernetes and ArgoCD manifests from declarative YAML configuration, designed for multi-tenant GitOps deployments.

## Features

- **Multi-tenant Support**: Generate resources for multiple tenants with isolated configurations
- **Multi-environment**: Support for dev, stage, prod, and custom environments
- **Multi-cluster**: Deploy across multiple Kubernetes clusters per environment
- **Auto-generation**: Automatically generate namespaces for all clusters
- **Network Policies**: Create Cilium NetworkPolicies with 4 policy types (deny-all, allow-namespace, allow-ingress, custom CIDR)
- **ArgoCD Integration**: Generate AppProjects and ApplicationSets with Git Generator
- **Configurable Output Paths**: Customize where each resource type is written
- **YAML Validation**: Validate generated YAML files for syntax errors before deployment
- **Git Operations**: Automatic branch creation, commits, and pushes for GitOps workflows
- **Post-deployment Validation**: Verify resources are correctly deployed to clusters (planned)
- **Rich CLI Output**: Beautiful terminal output with colors and tables

## Installation

### Using pip

```bash
# From source
git clone https://github.com/your-org/platform-generator.git
cd platform-generator
pip install -e .
```

### Using UV (recommended for fast dependency management)

```bash
# Install UV first
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/your-org/platform-generator.git
cd platform-generator
uv pip install -e .
```

## Quick Start

1. Create or use an existing `platform.yaml` configuration file (see `docs/platform.yaml` for example)

2. Validate your configuration:
```bash
platform-gen validate --config platform.yaml
```

3. Generate manifests:
```bash
platform-gen generate --config platform.yaml
```

4. Validate generated YAML files:
```bash
platform-gen validate-output --path generated/
```

5. (Optional) Review and commit changes:
```bash
cd generated/
git status
git add .
git commit -m "Update platform manifests"
git push
```

Or enable automatic git operations in `platform.yaml`:
```yaml
cli-config:
  git-enabled: true
  git-auto-push: true
```

## CLI Commands

### Command Reference

| Command | Purpose | Status |
|---------|---------|--------|
| `validate` | Validate platform.yaml configuration | ✅ Available |
| `generate` | Generate Kubernetes/ArgoCD manifests | ✅ Available |
| `validate-output` | Validate generated YAML syntax | ✅ Available |
| `validate-deployment` | Validate deployed resources | ⚠️ Planned |

### `platform-gen validate`

Validate the configuration file without generating manifests.

```bash
platform-gen validate --config platform.yaml
```

**Options:**
- `--config, -c PATH`: Path to platform.yaml (default: `platform.yaml`)

### `platform-gen generate`

Generate Kubernetes and ArgoCD manifests.

```bash
platform-gen generate [OPTIONS]
```

**Options:**
- `--config, -c PATH`: Path to platform.yaml (default: `platform.yaml`)
- `--tenant, -t TEXT`: Generate for specific tenant only
- `--environment, -e TEXT`: Generate for specific environment only
- `--resource-type TEXT`: Generate specific resource type only (namespace, quota, policy, appproject, applicationset)
- `--dry-run`: Print what would be generated without writing files
- `--verbose, -v`: Verbose output

**Examples:**
```bash
# Generate all resources for all tenants
platform-gen generate

# Generate only for tenant "bar"
platform-gen generate --tenant bar

# Generate only dev environment resources
platform-gen generate --environment dev

# Generate only namespaces
platform-gen generate --resource-type namespace

# Dry-run to preview what would be generated
platform-gen generate --dry-run

# Combine filters
platform-gen generate --tenant bar --environment dev --dry-run
```

### `platform-gen validate-output`

Validate generated YAML files for correct syntax.

```bash
platform-gen validate-output --path PATH
```

**Options:**
- `--path, -p PATH`: Path to YAML file or directory to validate (required)

**Description:**

This command validates that generated YAML files can be parsed correctly. It's useful for:
- Catching template rendering errors before deployment
- Validating syntax after making template changes
- CI/CD integration to ensure manifests are well-formed
- Debugging YAML parsing issues

The command accepts either a single file or a directory. When given a directory, it recursively finds all `.yaml` and `.yml` files and validates each one.

**Examples:**

```bash
# Validate a single file
platform-gen validate-output --path generated/tenants/bar/namespaces/dev/namespace.yaml

# Validate all files in a directory
platform-gen validate-output --path generated/tenants/bar/networkpolicies/dev/

# Validate all generated files
platform-gen validate-output --path generated/

# Short form
platform-gen validate-output -p generated/
```

**Output Example:**

```
Validating YAML files: generated/tenants/bar/networkpolicies/dev

Found 5 YAML file(s) to validate

✓ allow-same-namespace.yaml
✓ deny-all.yaml
✗ allow-from-ingress.yaml
  sequence entries are not allowed here

Validation Summary:
  ✓ 2 file(s) valid
  ✗ 1 file(s) invalid

Validation Errors:

generated/tenants/bar/networkpolicies/dev/allow-from-ingress.yaml
  sequence entries are not allowed here
  in "allow-from-ingress.yaml", line 16, column 15
```

**Exit Codes:**
- `0`: All files valid
- `1`: One or more files invalid or error occurred

### `platform-gen validate-deployment`

⚠️ **Note: This command is not yet implemented.**

Validate that resources were correctly deployed to Kubernetes clusters.

```bash
platform-gen validate-deployment --tenant TENANT --environment ENV [OPTIONS]
```

**Options:**
- `--config, -c PATH`: Path to platform.yaml (default: `platform.yaml`)
- `--tenant, -t TEXT`: Tenant to validate (required)
- `--environment, -e TEXT`: Environment to validate (required)
- `--kubeconfig PATH`: Path to kubeconfig file
- `--context TEXT`: Kubernetes context to use

**Planned Features:**

When implemented, this command will validate:
- Namespaces exist in all expected clusters
- ResourceQuotas are applied with correct limits
- Cilium NetworkPolicies exist (all 4 types)
- ArgoCD AppProject exists in control plane
- ArgoCD ApplicationSets exist with correct configuration

**Example:**

```bash
platform-gen validate-deployment \
  --tenant bar \
  --environment dev \
  --kubeconfig ~/.kube/config \
  --context my-dev-cluster
```

## CLI Process Flow

```mermaid
flowchart TD
    Start([User runs platform-gen]) --> ParseCLI[Parse CLI Arguments]
    ParseCLI --> LoadConfig[Load platform.yaml]
    LoadConfig --> ValidateSchema{Validate Schema}
    ValidateSchema -->|Invalid| Error1[Show Errors & Exit]
    ValidateSchema -->|Valid| CheckCommand{Which Command?}

    CheckCommand -->|validate| ValidateOnly[Validate Configuration]
    ValidateOnly --> Success1[Show Success & Exit]

    CheckCommand -->|generate| FilterCheck{Filters Applied?}
    FilterCheck -->|--tenant| FilterTenant[Filter by Tenant]
    FilterCheck -->|--environment| FilterEnv[Filter by Environment]
    FilterCheck -->|--resource-type| FilterResource[Filter by Resource Type]
    FilterCheck -->|No filters| ProcessAll[Process All Tenants]

    FilterTenant --> Generate
    FilterEnv --> Generate
    FilterResource --> Generate
    ProcessAll --> Generate

    Generate[Generate Resources] --> GenNamespaces[Generate Namespaces]
    GenNamespaces --> GenQuotas[Generate ResourceQuotas]
    GenQuotas --> GenPolicies[Generate NetworkPolicies]
    GenPolicies --> GenAppProjects[Generate AppProjects]
    GenAppProjects --> GenAppSets[Generate ApplicationSets]

    GenAppSets --> DryRun{Dry Run Mode?}
    DryRun -->|Yes| PrintOutput[Print Generated YAML]
    DryRun -->|No| WriteFiles[Write to Output Directory]

    PrintOutput --> Success2[Exit]
    WriteFiles --> ApplyPaths[Apply Configured Output Paths]
    ApplyPaths --> Success3[Show Summary & Exit]

    CheckCommand -->|validate-deployment| ValidateDeploy[Validate Deployment]
    ValidateDeploy --> ConnectClusters[Connect to K8s Clusters]
    ConnectClusters --> CheckNamespaces[Check Namespaces Exist]
    CheckNamespaces --> CheckQuotas[Check ResourceQuotas]
    CheckQuotas --> CheckPolicies[Check NetworkPolicies]
    CheckPolicies --> CheckArgoCD[Check ArgoCD Resources]
    CheckArgoCD --> ValidationResult{All Checks Pass?}
    ValidationResult -->|Yes| Success4[Show Success Report]
    ValidationResult -->|No| Error2[Show Failure Details]
```

## Configuration Reference

### platform.yaml Structure

```yaml
version: v1

metadata:
  description: "GitOps Platform Generator configuration"

cli-config:
  output-directory: "./generated"
  validate-before-apply: true
  dry-run-default: true
  git-commit-message-template: "chore: update {{tenant}}/{{app}}"
  # Git operations (optional)
  git-enabled: false  # Set to true to enable automatic git operations
  git-branch-pattern: "feat/platform-{{tenant}}-{{env}}-{{timestamp}}"
  git-auto-push: true
  output-paths:
    namespaces: "tenants/{{tenant}}/namespaces/{{env}}/{{cluster}}"
    resource-quotas: "tenants/{{tenant}}/resourcequotas/{{env}}"
    network-policies: "tenants/{{tenant}}/networkpolicies/{{env}}"
    app-projects: "tenants/{{tenant}}/argocd/appprojects/{{env}}"
    application-sets: "tenants/{{tenant}}/argocd/applicationsets/{{app}}/{{env}}"

defaults:
  environments:
    - dev
    - stage
    - prod

akp-instances:
  akp-dev:
    environment: dev
    url: "https://dev.akp.example.com"
    appproject-namespace: "argocd"

platform-clusters:
  dev-wus3:
    name: example-gitops-wus3-dev
    env: dev
    region: wus3

tenants:
  - name: tenant-example
    short-name: example
    long-name: "Example Tenant"
    description: "GitOps Tenant for Example Team"

    namespace-config:
      naming-pattern: "{{short-name}}-gitops-{{env}}"
      auto-generate-per-cluster: true

    namespaces:
      dev: example-gitops-dev
      stage: example-gitops-stage
      prod: example-gitops-prod

    resource-quotas:
      - dev:
          cpu: "10"
          memory: "20Gi"

    network-policies:
      enabled: true
      default-deny-all: true
      allow-within-namespace: true
      allow-from-ingress:
        enabled: true
        ingress-controller-namespaces:
          - ingress-nginx
      custom-rules:
        - name: allow-to-database
          description: "Allow egress to database"
          policy-type: egress
          egress:
            - to:
              - ipBlock:
                  cidr: 10.100.0.0/16
              ports:
                - protocol: TCP
                  port: 5432

    appproject:
      description: "AppProject for Example Team"
      source-repos:
        - "https://github.com/example-org/*"
      destinations:
        dev:
          - cluster: "example-gitops-wus3-dev"
            namespace: "example-gitops-dev"

    applications:
      - name: example-app
        argo-app-type: applicationset
        generator-type: git-generator
        repo-url: "https://github.com/example-org/example-app"
        config-repo:
          url: "https://github.com/example-org/example-config"
          revision: HEAD
          files:
            - path: "apps/*/config.json"
        environments:
          dev:
            - cluster: dev-wus3
              repo-path: "manifests/dev"
              sync-policy:
                automated:
                  prune: true
                  selfHeal: true
```

### Output Path Templates

Configure where each resource type is written using template variables:

**Available Variables:**
- `{{tenant}}` - Tenant name or short-name
- `{{env}}` - Environment name (dev/stage/prod)
- `{{cluster}}` - Cluster name
- `{{app}}` - Application name

**Default Paths:**
```yaml
output-paths:
  namespaces: "tenants/{{tenant}}/namespaces/{{env}}/{{cluster}}"
  resource-quotas: "tenants/{{tenant}}/resourcequotas/{{env}}"
  network-policies: "tenants/{{tenant}}/networkpolicies/{{env}}"
  app-projects: "tenants/{{tenant}}/argocd/appprojects/{{env}}"
  application-sets: "tenants/{{tenant}}/argocd/applicationsets/{{app}}/{{env}}"
```

### Generated Resources

The CLI generates the following Kubernetes and ArgoCD resources:

1. **Namespaces** - Auto-generated for every cluster in each environment
2. **ResourceQuotas** - CPU and memory limits per environment
3. **Cilium NetworkPolicies** - 4 types:
   - `deny-all.yaml` - Default deny ingress/egress
   - `allow-namespace.yaml` - Allow pod-to-pod within namespace
   - `allow-ingress.yaml` - Allow from ingress controllers
   - `custom-{name}.yaml` - Custom CIDR-based rules
4. **ArgoCD AppProjects** - One per tenant per environment
5. **ArgoCD ApplicationSets** - With Git Generator for self-service deployments

## Git Operations

The platform generator can automatically create git branches, commit changes, and push to remotes after generating manifests.

### Enabling Git Operations

Add to your `platform.yaml`:

```yaml
cli-config:
  git-enabled: true
  git-branch-pattern: "feat/platform-{{tenant}}-{{env}}-{{timestamp}}"
  git-auto-push: true
  git-commit-message-template: "chore: update {{tenant}}/{{env}}"
```

### How It Works

1. **Detects Git Repositories**: Walks up from generated files looking for `.git` directories
2. **Groups Files**: Organizes files by repository (assumes each resource type dir is a separate repo)
3. **Creates Branches**: Uses template pattern with variables like `{{tenant}}`, `{{env}}`, `{{timestamp}}`
4. **Commits Changes**: Stages all changes with `git add .` and commits
5. **Pushes** (optional): Pushes branch to remote if `git-auto-push: true`

### Branch Naming Variables

- `{{tenant}}`: Tenant short-name (extracted from path)
- `{{env}}`: Environment name (extracted from path)
- `{{timestamp}}`: Current datetime in `YYYYMMDD-HHMMSS` format

Example: `feat/platform-bar-dev-20260104-143022`

### Output Example

```
Processing Git Operations...

Processing repository: tenants/bar/namespaces
✓ Successfully committed 6 file(s) to branch feat/platform-bar-dev-20260104-143022
  Commit: a1b2c3d

Git Summary:
  1/1 repositories processed successfully
```

### Error Handling

- Git failures are non-fatal (show warnings, continue generation)
- Push failures are treated as warnings
- Each repository is processed independently
- Files are always generated successfully regardless of git status

### Requirements

- Git must be installed and in PATH
- Output directories must already be git repositories with `.git/`
- Git credentials configured system-wide
- Remotes configured (if using `git-auto-push`)

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/your-org/platform-generator.git
cd platform-generator

# Install with development dependencies
pip install -e '.[dev]'

# Or with UV
uv pip install -e '.[dev]'
```

### Installing Dependencies

#### Runtime Dependencies Only
```bash
# Install only what's needed to run the CLI
pip install -e .

# Or with UV (recommended)
uv pip install -e .
```

#### With Development Dependencies
```bash
# Install runtime + development tools (pytest, black, ruff, mypy)
pip install -e '.[dev]'

# Or with UV
uv pip install -e '.[dev]'
```

#### Individual Development Tools
```bash
# Install just testing tools
pip install pytest pytest-cov

# Install just code quality tools
pip install black ruff mypy

# Or install everything from pyproject.toml
pip install typer[all] pydantic ruamel.yaml jinja2 rich kubernetes pytest pytest-cov black ruff mypy
```

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

## Architecture

### Project Structure

```
platform-generator/
├── src/platform_generator/
│   ├── __init__.py
│   ├── cli.py                    # Typer CLI entrypoint
│   ├── config/
│   │   ├── models.py             # Pydantic models
│   │   ├── parser.py             # YAML parser
│   │   └── validator.py          # Validation logic
│   ├── generators/
│   │   ├── base.py               # Base generator class
│   │   ├── namespace.py          # Namespace generator
│   │   ├── resourcequota.py      # ResourceQuota generator
│   │   ├── networkpolicy.py      # NetworkPolicy generator
│   │   ├── appproject.py         # AppProject generator
│   │   └── applicationset.py     # ApplicationSet generator
│   ├── writers/
│   │   └── filesystem.py         # File writer
│   ├── validators/
│   │   ├── kubernetes.py         # K8s validation
│   │   └── deployment.py         # Deployment validation
│   └── templates/                # Jinja2 templates
│       ├── namespace.yaml.j2
│       ├── resourcequota.yaml.j2
│       ├── networkpolicy/
│       └── argocd/
├── tests/
├── docs/
│   └── platform.yaml             # Example configuration
├── pyproject.toml
└── README.md
```

### Technology Stack

#### Core Dependencies

**[Typer](https://typer.tiangolo.com/) - CLI Framework**
- **Version**: >= 0.12.0
- **Purpose**: Modern CLI framework built on Click with automatic help generation and comprehensive type hints support
- **Usage in Project**:
  - Primary CLI application framework in `src/platform_generator/cli.py`
  - Command definitions: `validate`, `generate`, `validate-output`, `validate-deployment`
  - Option parsing and validation with rich help text
  - Integration with Rich for beautiful terminal output
- **Links**:
  - [Documentation](https://typer.tiangolo.com/)
  - [Repository](https://github.com/tiangolo/typer)
  - [PyPI](https://pypi.org/project/typer/)

**[Pydantic](https://docs.pydantic.dev/) - Data Validation**
- **Version**: >= 2.5.0
- **Purpose**: Data validation library using Python type annotations for robust schema validation
- **Usage in Project**:
  - Complete schema validation for `platform.yaml` configuration in `src/platform_generator/config/models.py`
  - All configuration models: `PlatformConfig`, `Tenant`, `CLIConfig`, `AKPInstance`, `PlatformCluster`, etc.
  - Automatic kebab-case to snake_case field conversion via `Field(alias=...)`
  - Custom validators for complex configuration logic
- **Links**:
  - [Documentation](https://docs.pydantic.dev/)
  - [Repository](https://github.com/pydantic/pydantic)
  - [PyPI](https://pypi.org/project/pydantic/)

**[ruamel.yaml](https://yaml.readthedocs.io/) - YAML Parser**
- **Version**: >= 0.18.0
- **Purpose**: YAML 1.2 parser and emitter that preserves comments, formatting, and structure during round-trip operations
- **Usage in Project**:
  - Configuration file parsing in `src/platform_generator/config/parser.py`
  - Loads `platform.yaml` files while preserving original formatting and comments
  - More advanced than PyYAML with better round-trip support
- **Links**:
  - [Documentation](https://yaml.readthedocs.io/)
  - [Repository](https://sourceforge.net/projects/ruamel-yaml/)
  - [PyPI](https://pypi.org/project/ruamel.yaml/)

**[Jinja2](https://jinja.palletsprojects.com/) - Template Engine**
- **Version**: >= 3.1.0
- **Purpose**: Modern and designer-friendly templating language for Python, used for generating dynamic YAML manifests
- **Usage in Project**:
  - Template rendering in `src/platform_generator/generators/base.py` and all generator classes
  - Generates Kubernetes and ArgoCD manifests from templates in `src/platform_generator/templates/`
  - Template files: `namespace.yaml.j2`, `resourcequota.yaml.j2`, `networkpolicy.yaml.j2`, `appproject.yaml.j2`, `applicationset.yaml.j2`
  - Special feature: Supports double-templating via `{% raw %}...{% endraw %}` blocks to preserve ArgoCD template variables
- **Links**:
  - [Documentation](https://jinja.palletsprojects.com/)
  - [Repository](https://github.com/pallets/jinja)
  - [PyPI](https://pypi.org/project/Jinja2/)

**[Rich](https://rich.readthedocs.io/) - Terminal Formatting**
- **Version**: >= 13.7.0
- **Purpose**: Python library for rich text and beautiful formatting in the terminal with colors, tables, and progress indicators
- **Usage in Project**:
  - CLI output formatting throughout `src/platform_generator/cli.py`
  - File operation logging in `src/platform_generator/writers/filesystem.py`
  - Git operation status in `src/platform_generator/git/operations.py`
  - Provides colored output (green ✓, red ✗, yellow ⚠, cyan, blue, magenta, dim text)
  - Creates formatted tables for configuration summaries and resource listings
- **Links**:
  - [Documentation](https://rich.readthedocs.io/)
  - [Repository](https://github.com/Textualize/rich)
  - [PyPI](https://pypi.org/project/rich/)

**[Kubernetes Python Client](https://github.com/kubernetes-client/python) - K8s API**
- **Version**: >= 28.1.0
- **Purpose**: Official Python client library for Kubernetes, providing access to the Kubernetes API
- **Usage in Project**:
  - Currently imported for planned `validate-deployment` command functionality
  - **Status**: Command skeleton exists but validation features not yet implemented
  - **Future Use**: Will validate that generated resources (namespaces, quotas, policies, ArgoCD resources) exist correctly in live Kubernetes clusters
- **Links**:
  - [Documentation](https://github.com/kubernetes-client/python)
  - [Repository](https://github.com/kubernetes-client/python)
  - [PyPI](https://pypi.org/project/kubernetes/)

### Development Dependencies

The project includes comprehensive development tooling for code quality, testing, and type safety:

**[pytest](https://docs.pytest.org/) - Testing Framework**
- **Version**: >= 7.4.0
- **Purpose**: Full-featured, mature testing framework for Python with simple syntax and powerful features
- **Usage in Project**:
  - Unit tests in `tests/` directory
  - Tests for FileWriter, resource extraction, path helpers, and summary generation
  - Run with: `pytest` or `PYTHONPATH=src:$PYTHONPATH pytest tests/ -v`
- **Links**:
  - [Documentation](https://docs.pytest.org/)
  - [Repository](https://github.com/pytest-dev/pytest)
  - [PyPI](https://pypi.org/project/pytest/)

**[pytest-cov](https://pytest-cov.readthedocs.io/) - Coverage Plugin**
- **Version**: >= 4.1.0
- **Purpose**: Coverage plugin for pytest that generates test coverage reports
- **Usage**: `pytest --cov=src --cov-report=html` to measure test coverage and generate HTML reports
- **Links**:
  - [Documentation](https://pytest-cov.readthedocs.io/)
  - [Repository](https://github.com/pytest-dev/pytest-cov)
  - [PyPI](https://pypi.org/project/pytest-cov/)

**[Black](https://black.readthedocs.io/) - Code Formatter**
- **Version**: >= 23.12.0
- **Purpose**: Uncompromising Python code formatter that enforces consistent style
- **Configuration**: Line length 100, target versions py311/py312 (from `pyproject.toml`)
- **Usage**: `black src/ tests/` to format all Python code
- **Links**:
  - [Documentation](https://black.readthedocs.io/)
  - [Repository](https://github.com/psf/black)
  - [PyPI](https://pypi.org/project/black/)

**[Ruff](https://docs.astral.sh/ruff/) - Fast Linter**
- **Version**: >= 0.1.9
- **Purpose**: Extremely fast Python linter written in Rust, replacing Flake8, isort, and more
- **Configuration**: Line length 100, target version py311 (from `pyproject.toml`)
- **Usage**: `ruff check src/ tests/` to lint codebase for style and quality issues
- **Links**:
  - [Documentation](https://docs.astral.sh/ruff/)
  - [Repository](https://github.com/astral-sh/ruff)
  - [PyPI](https://pypi.org/project/ruff/)

**[mypy](https://mypy-lang.org/) - Static Type Checker**
- **Version**: >= 1.8.0
- **Purpose**: Static type checker for Python that validates type hints and catches type errors
- **Configuration**: Strict mode enabled, Python version 3.11, warn on return_any (from `pyproject.toml`)
- **Usage**: `mypy src/` to perform static type checking on source code
- **Links**:
  - [Documentation](https://mypy-lang.org/)
  - [Repository](https://github.com/python/mypy)
  - [PyPI](https://pypi.org/project/mypy/)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or contributions, please open an issue on GitHub.
