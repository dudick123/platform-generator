# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install the package in editable mode
pip install -e .

# Or using UV (recommended)
uv pip install -e .

# Run the CLI
platform-gen --help
platform-gen validate --config docs/platform.yaml
platform-gen generate --config docs/platform.yaml

# Generate for specific tenant/environment
platform-gen generate --config docs/platform.yaml --tenant bar
platform-gen generate --config docs/platform.yaml --environment dev
platform-gen generate --config docs/platform.yaml --dry-run

# Run tests (when implemented)
pytest
pytest tests/test_generators.py -v

# Code formatting
black src/ tests/
ruff check src/ tests/
mypy src/
```

## Architecture Overview

### Generator Pattern

All resource generators inherit from `BaseGenerator` (src/platform_generator/generators/base.py):

- **Pydantic Models**: Schema validation happens through comprehensive Pydantic models in `config/models.py`. The root model is `PlatformConfig` which validates the entire `platform.yaml` file.

- **Auto-Label System**: `BaseGenerator.get_auto_labels()` automatically generates standard labels (`platform.foo-org.com/tenant`, `platform.foo-org.com/environment`, etc.) which are merged with tenant-level `common_labels`.

- **Template Path Resolution**: Each generator uses `writer.render_path_template()` to resolve configurable output paths from `cli-config.output-paths` in platform.yaml. Path templates support variables: `{{tenant}}`, `{{env}}`, `{{cluster}}`, `{{app}}`.

### The Five Generators

Each generator follows the same pattern but creates different resource types:

1. **NamespaceGenerator**: Auto-generates one namespace per cluster per environment using `config.get_clusters_for_environment(env)`

2. **ResourceQuotaGenerator**: One quota per environment (applies to all clusters via GitOps)

3. **NetworkPolicyGenerator**: Generates 4 Cilium NetworkPolicy types using separate templates:
   - `deny-all.yaml.j2` - Default deny ingress/egress
   - `allow-namespace.yaml.j2` - Allow pod-to-pod within namespace
   - `allow-ingress.yaml.j2` - Allow from ingress controller namespaces/labels
   - `custom.yaml.j2` - Custom CIDR-based rules (one file per custom rule)

4. **AppProjectGenerator**: One ArgoCD AppProject per tenant per environment. Uses `config.get_akp_instance_for_environment()` to determine which AKP instance URL to include in the comment header.

5. **ApplicationSetGenerator**: ArgoCD ApplicationSets with Git Generator. **Important**: Uses double-templating via `{% raw %}{{ argocd_var }}{% endraw %}` to preserve ArgoCD template variables (like `{{ cluster }}`, `{{ path }}`, `{{ server }}`) in the final YAML while still processing Jinja2 variables.

### Jinja2 Template Whitespace Control

**Critical**: Use `{% if ... %}` (NOT `{%- if ... %}`) for proper YAML formatting. The `-` trim control causes single-line concatenation which breaks YAML structure. The Jinja2 environment is configured with `trim_blocks=True` and `lstrip_blocks=True` globally.

Example from applicationset.yaml.j2:

```jinja2
        namespace: {{ destination_namespace }}
{% if sync_policy %}          # Correct - creates newline before syncPolicy
      syncPolicy:
```

Not:

```jinja2
        namespace: {{ destination_namespace }}
{%- if sync_policy %}         # Wrong - concatenates on same line
      syncPolicy:
```

### Path Template System

The `FileWriter` class (writers/filesystem.py) handles configurable output paths:

```python
# Example path template from platform.yaml
"tenants/{{tenant}}/argocd/applicationsets/{{app}}/{{env}}"

# Gets rendered as:
"tenants/bar/argocd/applicationsets/bar-mfe-frontend/dev"
```

Variables are replaced via simple string substitution in `render_path_template()`. All generators must call:

```python
self.writer.write_file(
    content=rendered_yaml,
    path_template=self.get_output_path_template(),
    variables={"tenant": "bar", "env": "dev", ...},
    filename="resource.yaml"
)
```

### FileWriter Summary and kubectl-style Output

The `FileWriter` class provides detailed resource tracking and kubectl-style summary output:

**Quiet Mode**: Initialize with `quiet=True` to suppress individual file write messages during generation:

```python
writer = FileWriter(output_directory="./generated", dry_run=False, quiet=True)
# No "✓ Wrote {path}" messages will be printed
```

**Resource Extraction**: The `_extract_resource_info()` method extracts resource type and name from file paths:

```python
# Example: "tenants/bar/namespaces/dev/foo-wus3-dev/namespace.yaml"
# Returns: ("namespace", "foo-wus3-dev")
```

**Detailed Summary**: The `get_detailed_summary()` method returns structured resource information:

```python
summary = writer.get_detailed_summary()
# Returns: List[ResourceCreationInfo] with fields:
#   - resource_type: str (e.g., "namespace", "resourcequota")
#   - resource_name: str (extracted from path)
#   - file_path: Path (full path)
#   - relative_path: Path (relative to output_directory)
```

**CLI Integration**: The CLI uses quiet mode and detailed summary to provide kubectl-style output:

```bash
$ platform-gen generate --config platform.yaml --tenant bar

Resources Generated:

namespace/foo-gitops-wus3-dev created
resourcequota/bar-dev created
networkpolicy/deny-all created
appproject/bar created
applicationset/bar-mfe-frontend created

Summary:
  6 namespaces
  3 resource-quotas
  12 network-policies
  3 app-projects
  3 application-sets
```

Use `--verbose` flag to show full file paths:

```bash
$ platform-gen generate --config platform.yaml --tenant bar --verbose

namespace/foo-gitops-wus3-dev created -> tenants/bar/namespaces/dev/foo-gitops-wus3-dev/namespace.yaml
```

**Dry-run Tracking**: Files are tracked in `files_written` even in dry-run mode, enabling summary generation without actually writing files.

### Git Operations

When `git-enabled: true` in platform.yaml, the generator automatically performs git operations after file generation:

**Workflow:**
1. Detects git repositories in output directories (walks up tree looking for `.git`)
2. Groups generated files by repository
3. For each repository:
   - Creates or checks out branch using `git-branch-pattern` template
   - Stages all changes with `git add .`
   - Commits with `git-commit-message-template`
   - Pushes to remote (if `git-auto-push: true`)

**Configuration:**
```yaml
cli-config:
  git-enabled: true
  git-branch-pattern: "feat/platform-{{tenant}}-{{env}}-{{timestamp}}"
  git-auto-push: true
  git-commit-message-template: "chore: update {{tenant}}/{{env}}"
```

**Branch Pattern Variables:**
- `{{tenant}}`: Tenant short-name extracted from path (`tenants/bar/...` → `"bar"`)
- `{{env}}`: Environment name extracted from path (after resource type)
- `{{timestamp}}`: Current datetime in `YYYYMMDD-HHMMSS` format

**Error Handling:**
- Git failures are non-fatal - warnings shown, generation continues
- Each repository is processed independently
- Push failures don't block commit success
- If no git repositories found, operations are skipped with info message

**Repository Detection:**
- Assumes each resource type directory is a git repository
- Example: `tenants/bar/namespaces/` has `.git/` directory
- Example: `tenants/bar/networkpolicies/` has `.git/` directory

**Output Example:**
```
Processing Git Operations...

Processing repository: tenants/bar/namespaces
✓ Successfully committed 6 file(s) to branch feat/platform-bar-dev-20260104-143022
  Commit: a1b2c3d
⚠ Push failed: no remote configured. You may need to push manually

Git Summary:
  1/1 repositories processed successfully
```

**Dry-Run Behavior:**
Git operations are skipped in dry-run mode. Commands that would be executed are shown with `Would run: git ...`.

**Assumptions:**
- Output path directories are already initialized as git repositories
- Git credentials are configured system-wide
- Remotes are configured (if using `git-auto-push`)

### PlatformConfig Helper Methods

The `PlatformConfig` Pydantic model (config/models.py) includes critical helper methods:

- `get_clusters_for_environment(env: str)` - Returns list of clusters for an environment
- `get_akp_instance_for_environment(env: str)` - Returns AKP instance config for an environment
- `get_default_output_paths()` - Returns OutputPaths with defaults if not configured

These are used throughout generators to avoid repetitive iteration logic.

### CLI Command Structure

The CLI (cli.py) uses Typer with three main commands:

1. **validate** - Parses and validates platform.yaml schema using Pydantic
2. **generate** - Instantiates all 5 generators and calls their `generate()` methods with optional filters
3. **validate-deployment** - Skeleton exists but not yet implemented

The `generate` command supports filters (`--tenant`, `--environment`, `--resource-type`) that get passed to each generator's `generate()` method.

## Key Implementation Details

### Pydantic Field Aliases

All Pydantic models use `Field(alias="kebab-case")` for YAML keys since platform.yaml uses kebab-case naming:

```python
class CLIConfig(BaseModel):
    output_directory: str = Field("./generated", alias="output-directory")

    class Config:
        populate_by_name = True  # Required to accept both snake_case and kebab-case
```

### Double-Templating Pattern

ApplicationSets require special handling because:

1. Jinja2 processes the template to generate the ApplicationSet YAML
2. ArgoCD processes the ApplicationSet template variables at deployment time

Use `{% raw %}...{% endraw %}` blocks to escape ArgoCD variables from Jinja2:

```jinja2
name: {% raw %}'{{ cluster }}-{{ app }}'{% endraw %}
# Jinja2 renders this as: name: '{{ cluster }}-{{ app }}'
# ArgoCD then interpolates {{ cluster }} and {{ app }} from config.json
```

### Environment-Cluster Mapping

Clusters are filtered by environment via the `env` field in `platform-clusters`:

```yaml
platform-clusters:
  dev-wus3:
    name: foo-gitops-wus3-dev
    env: dev          # This cluster belongs to 'dev' environment
```

Namespaces are auto-generated for ALL clusters where `cluster.env == environment`.

## Testing Philosophy

When implementing tests:

- Use `tests/fixtures/platform.yaml` as test configuration
- Test each generator independently with mock `FileWriter` in dry-run mode
- Validate generated YAML is syntactically correct using `yaml.safe_load()`
- Test path template resolution with various variable combinations
- Test Pydantic validation with invalid configurations (should raise ValidationError)

## Common Modifications

### Adding a New Generator

1. Create `src/platform_generator/generators/newresource.py` inheriting from `BaseGenerator`
2. Implement `generate()` method and `get_output_path_template()` method
3. Create Jinja2 template in `src/platform_generator/templates/newresource.yaml.j2`
4. Add output path to `OutputPaths` model in `config/models.py`
5. Import and instantiate in `cli.py` generate command
6. Add resource count to summary table in CLI

### Extending platform.yaml Schema

1. Add/modify Pydantic models in `config/models.py`
2. Use `Field(alias="kebab-case")` for YAML keys
3. Add `class Config: populate_by_name = True` for backward compatibility
4. Update `docs/platform.yaml` with examples
5. Validators should use `@field_validator` decorator for custom validation

### Modifying Output Structure

1. Update `OutputPaths` defaults in `config/models.py`
2. Update generator's `get_output_path_template()` to return the new path key
3. Document in README.md configuration reference
