"""CLI interface for NVMe model storage management."""

import sys
import json
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import load_config
from .storage import NVMeStorageManager
from .validators import ValidationError

# Set up console for rich output
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.option('--config', '-c', type=click.Path(), help='Path to configuration file')
@click.pass_context
def cli(ctx, config):
    """NVMe Model Storage Management CLI.
    
    Manage AI model storage on NVMe drives with support for HuggingFace,
    Ollama, and vLLM models.
    """
    ctx.ensure_object(dict)
    ctx.obj['config'] = load_config(config)
    ctx.obj['storage'] = NVMeStorageManager(ctx.obj['config'].to_dict())


@cli.command()
@click.option('--no-verify-mount', is_flag=True, default=False,
              help='Skip NVMe mount verification')
@click.pass_context
def setup(ctx, no_verify_mount):
    """Initialize NVMe storage for AI models.
    
    This command will:
    - Create directory structure (/mnt/nvme/hf-cache, /mnt/nvme/models, /mnt/nvme/ollama)
    - Set up environment variables
    - Create symlinks for backward compatibility
    """
    storage = ctx.obj['storage']
    config = ctx.obj['config']
    
    # Check if NVMe is mounted
    if not no_verify_mount:
        if not storage.check_nvme_mounted():
            console.print('[red]Error: NVMe storage not mounted at /mnt/nvme[/red]')
            sys.exit(1)
    
    # Update config if needed
    if no_verify_mount:
        config.set('storage', 'require_mount', value=False)
    
    with console.status("[bold green]Setting up NVMe storage...") as status:
        try:
            if storage.setup_nvme():
                console.print("[green]✓[/green] NVMe storage setup complete!")
                
                # Show configuration
                table = Table(title="Storage Configuration")
                table.add_column("Path", style="cyan")
                table.add_column("Purpose", style="green")
                
                nvme_path = config.get('storage', 'nvme_path')
                table.add_row(f"{nvme_path}/hf-cache", "HuggingFace cache")
                table.add_row(f"{nvme_path}/models", "Downloaded models")
                table.add_row(f"{nvme_path}/ollama", "Ollama models")
                
                console.print(table)
                
                # Show disk usage
                usage = storage.get_disk_usage()
                console.print(f"\n[cyan]Disk space:[/cyan] {usage['available_gb']}GB available "
                            f"({usage['usage_percent']:.1f}% used)")
                
                console.print("\n[yellow]Note:[/yellow] Run 'source ~/.bashrc' or restart your "
                            "shell for environment changes to take effect")
            else:
                console.print("[red]✗[/red] Setup failed. Check logs for details.")
                sys.exit(1)
                
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)


@cli.command()
@click.argument('model_id')
@click.option('--provider', '-p', 
              type=click.Choice(['hf', 'huggingface', 'ollama', 'vllm'], case_sensitive=False),
              required=True, help='Model provider')
@click.option('--revision', '-r', help='Model revision/branch (HuggingFace only)')
@click.option('--token', '-t', help='Authentication token (HuggingFace only)')
@click.option('--no-verify-mount', is_flag=True, default=False,
              help='Skip NVMe mount verification')
@click.pass_context
def download(ctx, model_id, provider, revision, token, no_verify_mount):
    """Download a model with validation.
    
    Examples:
    
    \b
    # Download HuggingFace model
    nvme-models download meta-llama/Llama-2-7b-hf --provider hf
    
    \b
    # Download Ollama model
    nvme-models download llama2:7b --provider ollama
    """
    storage = ctx.obj['storage']
    
    # Check if NVMe is mounted
    if not no_verify_mount:
        if not storage.check_nvme_mounted():
            console.print('[red]Error: NVMe storage not mounted at /mnt/nvme[/red]')
            sys.exit(1)
    
    # Normalize provider name
    if provider in ['hf', 'huggingface']:
        provider = 'hf'
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"Downloading {model_id}...", total=None)
        
        try:
            # Check disk space first
            from .models import get_provider_handler
            handler = get_provider_handler(provider, ctx.obj['config'].to_dict())
            
            if handler:
                estimated_size = handler.estimate_model_size(model_id)
                progress.update(task, description=f"Checking disk space (need ~{estimated_size*2}GB)...")
                
                if not storage.check_disk_space(estimated_size * 2):
                    usage = storage.get_disk_usage()
                    console.print(f"[red]Error:[/red] Insufficient disk space. "
                                f"Required: {estimated_size*2}GB, Available: {usage['available_gb']}GB")
                    sys.exit(1)
                
                progress.update(task, description=f"Downloading {model_id}...")
                
                # Prepare kwargs for download
                kwargs = {}
                if revision:
                    kwargs['revision'] = revision
                if token:
                    kwargs['token'] = token
                
                if handler.download(model_id, **kwargs):
                    progress.update(task, description="Download complete!")
                    console.print(f"[green]✓[/green] Successfully downloaded {model_id}")
                    
                    # Show model info
                    models = handler.list_models()
                    for model in models:
                        if model_id in model.get('name', '') or model_id == model.get('model_id', ''):
                            console.print(f"  Location: {model.get('path', 'unknown')}")
                            if 'size_gb' in model:
                                console.print(f"  Size: {model['size_gb']:.2f}GB")
                            break
                else:
                    console.print(f"[red]✗[/red] Download failed")
                    sys.exit(1)
            else:
                console.print(f"[red]Error:[/red] Unknown provider: {provider}")
                sys.exit(1)
                
        except ValidationError as e:
            console.print(f"[red]Validation Error:[/red] {e}")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)


@cli.command()
@click.option('--format', '-f', 
              type=click.Choice(['text', 'json'], case_sensitive=False),
              default='text', help='Output format')
@click.option('--no-verify-mount', is_flag=True, default=False,
              help='Skip NVMe mount verification')
@click.pass_context
def verify(ctx, format, no_verify_mount):
    """Verify NVMe storage configuration.
    
    Checks:
    - NVMe mount status
    - Directory structure
    - Environment variables
    - Disk usage
    - Downloaded models
    """
    storage = ctx.obj['storage']
    
    # Check if NVMe is mounted
    if not no_verify_mount:
        if not storage.check_nvme_mounted():
            console.print('[red]Error: NVMe storage not mounted at /mnt/nvme[/red]')
            sys.exit(1)
    
    with console.status("[bold green]Verifying configuration...") as status:
        results = storage.verify(output_format=format)
    
    if format == 'json':
        # Output JSON
        click.echo(json.dumps(results, indent=2))
    else:
        # Output formatted text
        console.print("\n[bold]NVMe Storage Verification[/bold]\n")
        
        # Create status table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Check", style="cyan", width=30)
        table.add_column("Status", width=10)
        table.add_column("Details", style="dim")
        
        # Add checks to table
        for check in results.get('success', []):
            table.add_row(
                check['message'],
                "[green]✓[/green]",
                check.get('size', '') if 'size' in check else ''
            )
        
        for check in results.get('warnings', []):
            table.add_row(
                check['message'],
                "[yellow]⚠[/yellow]",
                ''
            )
        
        for check in results.get('errors', []):
            table.add_row(
                check['message'],
                "[red]✗[/red]",
                ''
            )
        
        console.print(table)
        
        # Show summary
        summary = results.get('summary', {})
        console.print("\n[bold]Summary:[/bold]")
        
        if summary.get('nvme_mounted'):
            console.print("  [green]✓[/green] NVMe is mounted")
        else:
            console.print("  [red]✗[/red] NVMe is not mounted")
        
        if summary.get('directories_created'):
            console.print("  [green]✓[/green] Directory structure created")
        else:
            console.print("  [red]✗[/red] Directory structure incomplete")
        
        if summary.get('environment_configured'):
            console.print("  [green]✓[/green] Environment variables configured")
        else:
            console.print("  [yellow]⚠[/yellow] Environment variables not fully configured")
        
        # Disk usage
        if 'disk_usage' in summary:
            usage = summary['disk_usage']
            console.print(f"\n[bold]Disk Usage:[/bold]")
            console.print(f"  Total: {usage['total_gb']}GB")
            console.print(f"  Used: {usage['used_gb']}GB ({usage['usage_percent']:.1f}%)")
            console.print(f"  Available: {usage['available_gb']}GB")
        
        # Model count
        model_count = summary.get('model_files_found', 0)
        if model_count > 0:
            console.print(f"\n[green]Found {model_count} model files[/green]")
        else:
            console.print("\n[yellow]No model files found yet[/yellow]")
        
        # Overall status
        if results['status'] == 'success':
            console.print("\n[green bold]All checks passed! ✓[/green bold]")
        elif results['status'] == 'warning':
            console.print("\n[yellow bold]Configuration has warnings ⚠[/yellow bold]")
        else:
            console.print("\n[red bold]Configuration has errors ✗[/red bold]")
            sys.exit(1)


@cli.command(name='list')
@click.option('--provider', '-p', 
              type=click.Choice(['all', 'hf', 'huggingface', 'ollama', 'vllm'], case_sensitive=False),
              default='all', help='Filter by provider')
@click.option('--no-verify-mount', is_flag=True, default=False,
              help='Skip NVMe mount verification')
@click.pass_context
def list_models(ctx, provider, no_verify_mount):
    """List downloaded models.
    
    Shows all downloaded models with their sizes and providers.
    """
    storage = ctx.obj['storage']
    
    # Check if NVMe is mounted
    if not no_verify_mount:
        if not storage.check_nvme_mounted():
            console.print('[red]Error: NVMe storage not mounted at /mnt/nvme[/red]')
            sys.exit(1)
    
    # Get models from all providers
    all_models = []
    
    if provider in ['all', 'hf', 'huggingface']:
        from .models.huggingface import HuggingFaceHandler
        hf_handler = HuggingFaceHandler(ctx.obj['config'].to_dict())
        all_models.extend(hf_handler.list_models())
    
    if provider in ['all', 'ollama']:
        from .models.ollama import OllamaHandler
        ollama_handler = OllamaHandler(ctx.obj['config'].to_dict())
        all_models.extend(ollama_handler.list_models())
    
    if provider in ['all', 'vllm']:
        from .models.vllm import VLLMHandler
        vllm_handler = VLLMHandler(ctx.obj['config'].to_dict())
        all_models.extend(vllm_handler.list_models())
    
    if not all_models:
        console.print("[yellow]No models found[/yellow]")
        return
    
    # Create table
    table = Table(title="Downloaded Models")
    table.add_column("Name", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Size", style="yellow")
    table.add_column("Path", style="dim")
    
    total_size = 0
    for model in all_models:
        size_str = ""
        if 'size_gb' in model:
            size_gb = model['size_gb']
            size_str = f"{size_gb:.2f}GB"
            total_size += size_gb
        elif 'size' in model:
            size_str = model['size']
        
        table.add_row(
            model['name'],
            model.get('provider', 'unknown'),
            size_str,
            model.get('path', '')
        )
    
    console.print(table)
    
    if total_size > 0:
        console.print(f"\n[bold]Total size:[/bold] {total_size:.2f}GB")
    
    # Show disk usage
    usage = storage.get_disk_usage()
    console.print(f"[bold]Disk usage:[/bold] {usage['used_gb']}GB used, "
                  f"{usage['available_gb']}GB available")


@cli.command()
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
@click.option('--no-verify-mount', is_flag=True, default=False,
              help='Skip NVMe mount verification')
@click.pass_context
def clean(ctx, yes, no_verify_mount):
    """Clean up temporary files and old backups.
    
    Removes:
    - Temporary download directories (.tmp_*)
    - Old backup files (*.backup.*)
    """
    # Ensure storage and config are available from context
    # The context should always be initialized by the parent cli group, 
    # but we add defensive checks in case the command is called directly
    if ctx.obj is None:
        ctx.obj = {}
    
    if 'config' not in ctx.obj or ctx.obj['config'] is None:
        from .config import load_config
        ctx.obj['config'] = load_config(None)
    
    if 'storage' not in ctx.obj or ctx.obj['storage'] is None:
        ctx.obj['storage'] = NVMeStorageManager(ctx.obj['config'].to_dict())
    
    storage = ctx.obj['storage']
    config = ctx.obj['config']
    
    # Check if NVMe is mounted
    if not no_verify_mount:
        if not storage.check_nvme_mounted():
            console.print('[red]Error: NVMe storage not mounted at /mnt/nvme[/red]')
            sys.exit(1)
    
    nvme_path = Path(config.get('storage', 'nvme_path'))
    
    # Find temporary files
    temp_files = list(nvme_path.rglob('.tmp_*'))
    backup_files = list(nvme_path.rglob('*.backup.*'))
    
    if not temp_files and not backup_files:
        console.print("[green]No temporary files to clean[/green]")
        return
    
    # Show what will be deleted
    console.print("[bold]Files to be removed:[/bold]")
    
    total_size = 0
    if temp_files:
        console.print(f"\n[yellow]Temporary files ({len(temp_files)}):[/yellow]")
        for f in temp_files[:5]:  # Show first 5
            size = sum(p.stat().st_size for p in Path(f).rglob('*') if p.is_file()) if f.is_dir() else f.stat().st_size
            total_size += size
            console.print(f"  • {f.name} ({size / (1024**2):.1f}MB)")
        if len(temp_files) > 5:
            console.print(f"  ... and {len(temp_files) - 5} more")
    
    if backup_files:
        console.print(f"\n[yellow]Backup files ({len(backup_files)}):[/yellow]")
        for f in backup_files[:5]:  # Show first 5
            size = sum(p.stat().st_size for p in Path(f).rglob('*') if p.is_file()) if f.is_dir() else f.stat().st_size
            total_size += size
            console.print(f"  • {f.name} ({size / (1024**2):.1f}MB)")
        if len(backup_files) > 5:
            console.print(f"  ... and {len(backup_files) - 5} more")
    
    console.print(f"\n[bold]Total space to recover:[/bold] {total_size / (1024**3):.2f}GB")
    
    # Confirm deletion
    if not yes:
        if not click.confirm("Do you want to proceed with cleanup?"):
            console.print("[yellow]Cleanup cancelled[/yellow]")
            return
    
    # Perform cleanup
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Cleaning up...", total=len(temp_files) + len(backup_files))
        
        removed = 0
        for f in temp_files + backup_files:
            try:
                if f.is_dir():
                    import shutil
                    shutil.rmtree(f)
                else:
                    f.unlink()
                removed += 1
                progress.update(task, advance=1)
            except Exception as e:
                logger.warning(f"Failed to remove {f}: {e}")
    
    console.print(f"[green]✓[/green] Removed {removed} items, recovered {total_size / (1024**3):.2f}GB")


@cli.command()
@click.argument('model_name')
@click.option('--provider', '-p', 
              type=click.Choice(['hf', 'huggingface', 'ollama', 'vllm'], case_sensitive=False),
              required=True, help='Model provider')
@click.option('--no-verify-mount', is_flag=True, default=False,
              help='Skip NVMe mount verification')
@click.pass_context
def info(ctx, model_name, provider, no_verify_mount):
    """Show detailed information about a model.
    
    Displays model configuration, size, and verification status.
    """
    storage = ctx.obj['storage']
    
    # Check if NVMe is mounted
    if not no_verify_mount:
        if not storage.check_nvme_mounted():
            console.print('[red]Error: NVMe storage not mounted at /mnt/nvme[/red]')
            sys.exit(1)
    
    # Normalize provider name
    if provider in ['hf', 'huggingface']:
        provider = 'hf'
    
    from .models import get_provider_handler
    handler = get_provider_handler(provider, ctx.obj['config'].to_dict())
    
    if not handler:
        console.print(f"[red]Error:[/red] Unknown provider: {provider}")
        sys.exit(1)
    
    # Verify model
    results = handler.verify_model(model_name)
    
    console.print(f"\n[bold]Model Information: {model_name}[/bold]\n")
    
    # Show verification results
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="cyan", width=30)
    table.add_column("Status", width=10)
    table.add_column("Details")
    
    for check in results.get('checks', []):
        status_icon = {
            'passed': '[green]✓[/green]',
            'failed': '[red]✗[/red]',
            'warning': '[yellow]⚠[/yellow]'
        }.get(check['status'], '?')
        
        table.add_row(
            check['message'],
            status_icon,
            check.get('detail', '')
        )
    
    console.print(table)
    
    # Show model info if available
    if 'model_info' in results:
        console.print("\n[bold]Model Details:[/bold]")
        console.print(results['model_info'])
    
    # Overall status
    status_msg = {
        'success': '[green bold]Model is ready to use ✓[/green bold]',
        'warning': '[yellow bold]Model has warnings but may be usable ⚠[/yellow bold]',
        'error': '[red bold]Model has errors and may not work ✗[/red bold]'
    }.get(results['status'], '[dim]Unknown status[/dim]')
    
    console.print(f"\n{status_msg}")


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except Exception as e:
        console.print(f"[red bold]Error:[/red bold] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()