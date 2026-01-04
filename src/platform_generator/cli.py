"""Typer CLI for platform-generator."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config.parser import ConfigParser, ConfigParseError
from .generators.applicationset import ApplicationSetGenerator
from .generators.appproject import AppProjectGenerator
from .generators.namespace import NamespaceGenerator
from .generators.networkpolicy import NetworkPolicyGenerator
from .generators.resourcequota import ResourceQuotaGenerator
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
        console.print("[yellow]⚠ Dry-run mode enabled - no files will be written[/yellow]")

    # Get template directory
    template_dir = Path(__file__).parent / "templates"

    # Initialize file writer
    output_dir = platform_config.cli_config.output_directory
    writer = FileWriter(output_directory=output_dir, dry_run=dry_run)

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

    # Show summary
    console.print(f"\n[bold green]✓ Generation complete![/bold green]")
    console.print(f"Total resources generated: {total_generated}")

    if not dry_run:
        summary = writer.get_output_summary()
        if summary:
            table = Table(title="Generated Resources")
            table.add_column("Resource Type", style="cyan")
            table.add_column("Count", style="magenta")

            for resource_type, count in summary.items():
                table.add_row(resource_type, str(count))

            console.print(table)
            console.print(f"\n[dim]Output directory: {output_dir}[/dim]")

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


if __name__ == "__main__":
    app()
