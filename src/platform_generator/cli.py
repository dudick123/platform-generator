"""Typer CLI for platform-generator."""

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from . import __version__
from .config.parser import ConfigParser, ConfigParseError
from .generators.applicationset import ApplicationSetGenerator
from .generators.appproject import AppProjectGenerator
from .generators.namespace import NamespaceGenerator
from .generators.networkpolicy import NetworkPolicyGenerator
from .generators.resourcequota import ResourceQuotaGenerator
from .git.operations import process_git_operations
from .writers.filesystem import FileWriter

app = typer.Typer(
    name="platform-gen",
    help="GitOps Platform Generator CLI for Kubernetes and ArgoCD manifests",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"platform-gen version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True, help="Show version"
    ),
) -> None:
    """GitOps Platform Generator CLI."""
    pass


@app.command()
def validate(
    config: Path = typer.Option(
        Path("platform.yaml"),
        "--config",
        "-c",
        help="Path to platform.yaml configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """
    Validate the platform.yaml configuration file.

    Checks the configuration file for syntax errors and schema validation
    without generating any manifests.
    """
    console.print(f"[bold blue]Validating configuration:[/bold blue] {config}")

    parser = ConfigParser()
    is_valid, error_msg = parser.validate_file(config)

    if is_valid:
        console.print("[bold green]✓[/bold green] Configuration is valid!")

        # Show summary
        try:
            platform_config = parser.load_file(config)
            table = Table(title="Configuration Summary")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="magenta")

            table.add_row("Version", platform_config.version)
            table.add_row("Tenants", str(len(platform_config.tenants)))
            table.add_row("Clusters", str(len(platform_config.platform_clusters)))
            table.add_row("AKP Instances", str(len(platform_config.akp_instances)))
            table.add_row("Environments", ", ".join(platform_config.defaults.environments))

            console.print(table)
        except ConfigParseError:
            pass

        raise typer.Exit(0)
    else:
        console.print(f"[bold red]✗[/bold red] Configuration validation failed:\n")
        console.print(error_msg)
        raise typer.Exit(1)


@app.command()
def generate(
    config: Path = typer.Option(
        Path("platform.yaml"),
        "--config",
        "-c",
        help="Path to platform.yaml configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    tenant: Optional[str] = typer.Option(
        None, "--tenant", "-t", help="Generate for specific tenant only"
    ),
    environment: Optional[str] = typer.Option(
        None, "--environment", "-e", help="Generate for specific environment only"
    ),
    resource_type: Optional[str] = typer.Option(
        None,
        "--resource-type",
        help="Generate specific resource type only (namespace, quota, policy, appproject, applicationset)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print what would be generated without writing files"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """
    Generate Kubernetes and ArgoCD manifests from platform.yaml.

    Creates namespaces, resource quotas, network policies, AppProjects,
    and ApplicationSets based on the configuration.
    """
    console.print(f"[bold blue]Loading configuration:[/bold blue] {config}")

    parser = ConfigParser()
    try:
        platform_config = parser.load_file(config)
    except ConfigParseError as e:
        console.print(f"[bold red]✗[/bold red] Failed to load configuration:\n{e}")
        raise typer.Exit(1)

    console.print("[bold green]✓[/bold green] Configuration loaded successfully")

    # Apply filters
    tenants_to_process = platform_config.tenants
    if tenant:
        tenants_to_process = [t for t in platform_config.tenants if t.name == tenant or t.short_name == tenant]
        if not tenants_to_process:
            console.print(f"[bold red]✗[/bold red] Tenant '{tenant}' not found")
            raise typer.Exit(1)
        console.print(f"[cyan]Filter:[/cyan] Tenant = {tenant}")

    environments_to_process = platform_config.defaults.environments
    if environment:
        if environment not in platform_config.defaults.environments:
            console.print(f"[bold red]✗[/bold red] Environment '{environment}' not found")
            raise typer.Exit(1)
        environments_to_process = [environment]
        console.print(f"[cyan]Filter:[/cyan] Environment = {environment}")

    if resource_type:
        console.print(f"[cyan]Filter:[/cyan] Resource Type = {resource_type}")

    if dry_run:
        console.print(
            "[yellow]⚠ Dry-run mode enabled - no files or git operations will be executed[/yellow]"
        )

    # Get template directory
    template_dir = Path(__file__).parent / "templates"

    # Initialize file writer
    output_dir = platform_config.cli_config.output_directory
    writer = FileWriter(
        output_directory=output_dir, dry_run=dry_run, quiet=not verbose
    )

    # Track total resources generated
    total_generated = 0

    # Generate namespaces
    if not resource_type or resource_type == "namespace":
        console.print("\n[bold]Generating Namespaces...[/bold]")
        namespace_gen = NamespaceGenerator(platform_config, writer, template_dir)
        count = namespace_gen.generate(
            tenants=tenants_to_process,
            environments=environments_to_process
        )
        console.print(f"[green]✓[/green] Generated {count} namespace(s)")
        total_generated += count

    # Generate resource quotas
    if not resource_type or resource_type == "quota":
        console.print("\n[bold]Generating ResourceQuotas...[/bold]")
        quota_gen = ResourceQuotaGenerator(platform_config, writer, template_dir)
        count = quota_gen.generate(
            tenants=tenants_to_process,
            environments=environments_to_process
        )
        console.print(f"[green]✓[/green] Generated {count} resource quota(s)")
        total_generated += count

    # Generate network policies
    if not resource_type or resource_type == "policy":
        console.print("\n[bold]Generating NetworkPolicies...[/bold]")
        policy_gen = NetworkPolicyGenerator(platform_config, writer, template_dir)
        count = policy_gen.generate(
            tenants=tenants_to_process,
            environments=environments_to_process
        )
        console.print(f"[green]✓[/green] Generated {count} network policy(ies)")
        total_generated += count

    # Generate app projects
    if not resource_type or resource_type == "appproject":
        console.print("\n[bold]Generating ArgoCD AppProjects...[/bold]")
        appproject_gen = AppProjectGenerator(platform_config, writer, template_dir)
        count = appproject_gen.generate(
            tenants=tenants_to_process,
            environments=environments_to_process
        )
        console.print(f"[green]✓[/green] Generated {count} app project(s)")
        total_generated += count

    # Generate application sets
    if not resource_type or resource_type == "applicationset":
        console.print("\n[bold]Generating ArgoCD ApplicationSets...[/bold]")
        appset_gen = ApplicationSetGenerator(platform_config, writer, template_dir)
        count = appset_gen.generate(
            tenants=tenants_to_process,
            environments=environments_to_process
        )
        console.print(f"[green]✓[/green] Generated {count} application set(s)")
        total_generated += count

    # Git operations (if enabled)
    if platform_config.cli_config.git_enabled and not dry_run:
        console.print("\n[bold]Processing Git Operations...[/bold]")
        git_results = process_git_operations(
            files=writer.files_written,
            output_directory=Path(output_dir),
            config=platform_config.cli_config,
            dry_run=dry_run,
        )

        if git_results:
            console.print(f"\n[bold]Git Summary:[/bold]")
            success_count = sum(1 for r in git_results if r.success)
            console.print(
                f"  {success_count}/{len(git_results)} repositories processed successfully"
            )

    # Show kubectl-style summary
    console.print(f"\n[bold]Resources Generated:[/bold]\n")

    detailed_summary = writer.get_detailed_summary()

    if detailed_summary:
        # Color map for resource types
        resource_colors = {
            "namespace": "cyan",
            "resourcequota": "blue",
            "networkpolicy": "magenta",
            "appproject": "yellow",
            "applicationset": "green",
        }

        # Print kubectl-style: "resourcetype/name created" or "would be created"
        action = "would be created" if dry_run else "created"
        for resource_info in detailed_summary:
            color = resource_colors.get(resource_info.resource_type, "white")

            if verbose:
                # Show full relative path in verbose mode
                console.print(
                    f"[{color}]{resource_info.resource_type}/{resource_info.resource_name}[/{color}] "
                    f"{action} -> {resource_info.relative_path}"
                )
            else:
                # Compact kubectl style
                console.print(
                    f"[{color}]{resource_info.resource_type}/{resource_info.resource_name}[/{color}] {action}"
                )

        # Summary statistics
        summary = writer.get_output_summary()
        console.print(f"\n[bold green]Summary:[/bold green]")
        for resource_type, count in summary.items():
            console.print(f"  {count} {resource_type}")

        console.print(f"\n[dim]Output directory: {output_dir}[/dim]")
    else:
        console.print("[yellow]No resources generated[/yellow]")

    raise typer.Exit(0)


@app.command()
def validate_deployment(
    config: Path = typer.Option(
        Path("platform.yaml"),
        "--config",
        "-c",
        help="Path to platform.yaml configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant to validate (required)"),
    environment: str = typer.Option(
        ..., "--environment", "-e", help="Environment to validate (required)"
    ),
    kubeconfig: Optional[Path] = typer.Option(
        None,
        "--kubeconfig",
        help="Path to kubeconfig file (uses default if not specified)",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    context: Optional[str] = typer.Option(
        None, "--context", help="Kubernetes context to use"
    ),
) -> None:
    """
    Validate that resources were correctly deployed to Kubernetes clusters.

    Connects to clusters and verifies that namespaces, quotas, policies,
    and ArgoCD resources exist and are configured correctly.
    """
    console.print(f"[bold blue]Loading configuration:[/bold blue] {config}")

    parser = ConfigParser()
    try:
        platform_config = parser.load_file(config)
    except ConfigParseError as e:
        console.print(f"[bold red]✗[/bold red] Failed to load configuration:\n{e}")
        raise typer.Exit(1)

    # Find tenant
    tenant_obj = platform_config.get_tenant_by_name(tenant)
    if not tenant_obj:
        console.print(f"[bold red]✗[/bold red] Tenant '{tenant}' not found")
        raise typer.Exit(1)

    # Validate environment
    if environment not in platform_config.defaults.environments:
        console.print(f"[bold red]✗[/bold red] Environment '{environment}' not found")
        raise typer.Exit(1)

    console.print(f"[bold green]✓[/bold green] Configuration loaded")
    console.print(f"[cyan]Validating:[/cyan] Tenant '{tenant}' in environment '{environment}'")

    if kubeconfig:
        console.print(f"[cyan]Using kubeconfig:[/cyan] {kubeconfig}")
    if context:
        console.print(f"[cyan]Using context:[/cyan] {context}")

    # TODO: Implement validation logic
    console.print("\n[bold yellow]⚠ Deployment validation not yet implemented[/bold yellow]")
    console.print("This command will validate:")
    console.print("  • Namespaces exist in all clusters")
    console.print("  • ResourceQuotas are applied correctly")
    console.print("  • CiliumNetworkPolicies exist")
    console.print("  • ArgoCD AppProject exists")
    console.print("  • ArgoCD ApplicationSets exist")

    raise typer.Exit(0)


@app.command()
def validate_output(
    path: Path = typer.Option(
        ...,
        "--path",
        "-p",
        help="Path to YAML file or directory to validate",
        exists=True,
    ),
) -> None:
    """
    Validate generated YAML files for correct syntax.

    Checks that YAML files can be parsed without errors. Accepts either
    a single file or a directory (will validate all .yaml/.yml files).
    """
    console.print(f"[bold blue]Validating YAML files:[/bold blue] {path}\n")

    # Collect files to validate
    files_to_validate = []
    if path.is_file():
        if path.suffix.lower() in [".yaml", ".yml"]:
            files_to_validate.append(path)
        else:
            console.print(f"[bold red]✗[/bold red] File {path} is not a YAML file")
            raise typer.Exit(1)
    elif path.is_dir():
        # Find all YAML files recursively
        files_to_validate.extend(path.rglob("*.yaml"))
        files_to_validate.extend(path.rglob("*.yml"))
        files_to_validate.sort()

    if not files_to_validate:
        console.print(f"[yellow]⚠[/yellow] No YAML files found in {path}")
        raise typer.Exit(0)

    console.print(f"Found {len(files_to_validate)} YAML file(s) to validate\n")

    # Validate each file
    valid_count = 0
    invalid_count = 0
    errors = []

    for yaml_file in files_to_validate:
        try:
            with open(yaml_file, "r") as f:
                # Try to parse the YAML
                yaml.safe_load(f)
            console.print(f"[green]✓[/green] {yaml_file.relative_to(path.parent if path.is_file() else path)}")
            valid_count += 1
        except yaml.YAMLError as e:
            console.print(f"[red]✗[/red] {yaml_file.relative_to(path.parent if path.is_file() else path)}")
            error_msg = str(e)
            # Show first line of error for brevity
            first_line = error_msg.split("\n")[0] if "\n" in error_msg else error_msg
            console.print(f"  [dim]{first_line}[/dim]")
            errors.append((yaml_file, e))
            invalid_count += 1
        except Exception as e:
            console.print(f"[red]✗[/red] {yaml_file.relative_to(path.parent if path.is_file() else path)}")
            console.print(f"  [dim]Error reading file: {e}[/dim]")
            errors.append((yaml_file, e))
            invalid_count += 1

    # Summary
    console.print(f"\n[bold]Validation Summary:[/bold]")
    console.print(f"  [green]✓[/green] {valid_count} file(s) valid")
    console.print(f"  [red]✗[/red] {invalid_count} file(s) invalid")

    if errors:
        console.print(f"\n[bold red]Validation Errors:[/bold red]")
        for yaml_file, error in errors:
            console.print(f"\n[yellow]{yaml_file}[/yellow]")
            console.print(f"  {error}")

    # Exit with error code if any files are invalid
    if invalid_count > 0:
        raise typer.Exit(1)

    console.print(f"\n[bold green]✓ All YAML files are valid![/bold green]")
    raise typer.Exit(0)


if __name__ == "__main__":
    app()
