import typer
from pathlib import Path
from typing import Optional

from .translator import Translator
from .registry import discover_adapters
from .resolver import resolve

app = typer.Typer()

adapters = discover_adapters()
if not adapters:
    from .adapters import OsiAdapter, MetricFlowAdapter
    adapters = {"osi": OsiAdapter(), "metricflow": MetricFlowAdapter()}

translator = Translator(adapters)


@app.command()
def validate(
    file: Path,
    format: str = typer.Option("osi", help="Format to validate"),
    version: Optional[str] = typer.Option(None, help="Input spec version"),
):
    """Validate a metric file."""
    try:
        model = translator.parse_to_model(file, format, version)
        typer.echo(f"Valid {format} file: {model.name}")
    except Exception as e:
        typer.echo(f"Invalid: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def translate(
    file: Path,
    from_format: str = typer.Option("osi", help="Source format"),
    to_format: str = typer.Option("osi", help="Target format"),
    output: Path = typer.Option(None, help="Output file"),
    input_version: Optional[str] = typer.Option(None, help="Input spec version"),
    output_version: Optional[str] = typer.Option(None, help="Output spec version"),
):
    """Translate between formats."""
    try:
        result = translator.translate(file, from_format, to_format, input_version, output_version)
        if output:
            output.write_text(result)
            typer.echo(f"Translated to {output}")
        else:
            typer.echo(result)
    except Exception as e:
        typer.echo(f"Translation failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def migrate(
    file: Path,
    from_version: str = typer.Option(..., help="Source OSI spec version"),
    to_version: str = typer.Option(..., help="Target OSI spec version"),
    output: Optional[Path] = typer.Option(None, help="Output file"),
    in_place: bool = typer.Option(False, help="Overwrite input file"),
):
    """Migrate a file between OSI spec versions."""
    try:
        result = translator.translate(file, "osi", "osi", from_version, to_version)
        if in_place:
            file.write_text(result)
            typer.echo(f"Migrated {file} from {from_version} to {to_version}")
        elif output:
            output.write_text(result)
            typer.echo(f"Migrated to {output}")
        else:
            typer.echo(result)
    except Exception as e:
        typer.echo(f"Migration failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def diff(old: Path, new: Path):
    """Diff two metric files."""
    from .diff import ModelDiff

    try:
        old_model = translator.parse_to_model(old, "osi")
        new_model = translator.parse_to_model(new, "osi")
        differ = ModelDiff()
        diff_result = differ.compare(old_model, new_model)

        if not diff_result.has_changes():
            typer.echo("No changes")
            return

        if diff_result.added_metrics:
            added = [m.name for m in diff_result.added_metrics]
            typer.echo(f"Added metrics: {added}")
        if diff_result.removed_metrics:
            removed = [m.name for m in diff_result.removed_metrics]
            typer.echo(f"Removed metrics: {removed}")
        if diff_result.changed_metrics:
            changed = [c['id'] for c in diff_result.changed_metrics]
            typer.echo(f"Changed metrics: {changed}")
        if diff_result.breaking_changes:
            typer.echo("Breaking changes detected!", err=True)
    except Exception as e:
        typer.echo(f"Diff failed: {e}", err=True)
        raise typer.Exit(1)


@app.command("adapters")
def list_adapters():
    """List available adapters."""
    from .registry import discover_adapters
    discovered = discover_adapters()
    for name in sorted(adapters.keys()):
        version_info = ""
        if name in discovered:
            version_info = " (discovered)"
        typer.echo(f"  {name}{version_info}")


if __name__ == "__main__":
    app()