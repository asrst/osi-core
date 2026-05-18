import json
import typer
import yaml
from pathlib import Path
from typing import Optional

from .serializer import load_osi_model, dump_osi_model, dump_osi_yaml, load_osi_yaml
from .validator import validate_schema
from .converters import discover_converters

app = typer.Typer()


@app.command()
def validate(
    file: Path,
):
    """Validate an OSI model file."""
    try:
        data = load_osi_yaml(file)
        errors = validate_schema(data)
        if errors:
            for err in errors:
                typer.echo(f"  {err}", err=True)
            raise typer.Exit(1)
        typer.echo(f"Valid OSI model: {file}")
    except Exception as e:
        typer.echo(f"Invalid: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def convert(
    input_file: Path = typer.Option(..., "-i", "--input", help="Input file"),
    from_format: Optional[str] = typer.Option(
        None, "--from", help="Source format (default: OSI when --to is set)"
    ),
    to_format: Optional[str] = typer.Option(
        None, "--to", help="Target format (default: OSI when --from is set)"
    ),
    output: Optional[Path] = typer.Option(None, "-o", help="Output file"),
):
    """Convert between OSI and vendor formats.

    Specify either --from <vendor> (convert TO OSI) or --to <vendor> (convert FROM OSI).
    The unset side defaults to OSI.
    """
    if from_format and to_format:
        typer.echo("Specify only one of --from or --to, not both.", err=True)
        raise typer.Exit(1)
    if not from_format and not to_format:
        typer.echo("Specify either --from <vendor> or --to <vendor>.", err=True)
        raise typer.Exit(1)

    target_is_osi = bool(from_format)        # --from: we're importing INTO osi
    vendor = from_format if target_is_osi else to_format  # the non-osi vendor

    converters = discover_converters()
    converter = converters.get(vendor)
    if not converter:
        available = ", ".join(converters.keys()) if converters else "none registered"
        typer.echo(f"No converter for vendor '{vendor}'. Available: {available}", err=True)
        raise typer.Exit(1)

    try:
        if target_is_osi:
            raw = input_file.read_text()
            native = yaml.safe_load(raw) if vendor == "snowflake" else json.loads(raw)
            result = converter.to_osi(native)
            result_text = dump_osi_yaml(result)
        else:
            osi_dict = load_osi_yaml(input_file)
            result = converter.from_osi(osi_dict)
            if vendor == "gooddata":
                result_text = json.dumps(result, indent=2)
            else:
                result_text = yaml.dump(result, sort_keys=False, default_flow_style=False)

        if output:
            output.write_text(result_text)
            typer.echo(f"Wrote {output}")
        else:
            typer.echo(result_text)
    except Exception as e:
        typer.echo(f"Conversion failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def diff(old: Path, new: Path):
    """Diff two OSI model files."""
    from .diff import ModelDiff

    try:
        old_model = load_osi_model(old)
        new_model = load_osi_model(new)
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
        if diff_result.added_datasets:
            added = [d.name for d in diff_result.added_datasets]
            typer.echo(f"Added datasets: {added}")
        if diff_result.removed_datasets:
            removed = [d.name for d in diff_result.removed_datasets]
            typer.echo(f"Removed datasets: {removed}")
        if diff_result.breaking_changes:
            typer.echo("Breaking changes detected!", err=True)
    except Exception as e:
        typer.echo(f"Diff failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def list_converters():
    """List available converters."""
    converters = discover_converters()
    if not converters:
        typer.echo("No converters registered")
    for name in sorted(converters.keys()):
        typer.echo(f"  {name}")


if __name__ == "__main__":
    app()
