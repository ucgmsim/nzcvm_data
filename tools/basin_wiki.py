"""
Generate Markdown files for basins from nzcvm_registry.yaml and provide related utilities.

This script reads the nzcvm_registry.yaml file to perform operations related to basins,
such as generating wiki pages or listing available basins.

Usage examples:
  # List all available basins
  python basin_wiki.py list-basins

  # Generate wiki page for a single basin
  python basin_wiki.py generate-wiki Canterbury

  # Generate wiki pages for all basins
  python basin_wiki.py generate-wiki all

  # Generate wiki pages for all basins and scale images
  python basin_wiki.py generate-wiki all --scale-images

  # Use a specific registry file
  python basin_wiki.py list-basins --registry /path/to/my_registry.yaml
"""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated

import pytz
import typer

try:
    from velocity_modelling.registry import get_basin_versions
except ImportError as e:
    typer.echo(
        "Error: Failed to import velocity_modelling.registry.get_basin_versions\n"
        "Please install the velocity_modelling package:\n"
        " pip install git+https://github.com/ucgmsim/velocity_modelling.git\n",
        err=True,
    )
    raise typer.Exit(code=1) from e

app = typer.Typer(pretty_exceptions_enable=False)


def _remove_timestamp_line(content: str) -> str:
    """
    Remove the timestamp line from markdown content for comparison.

    Parameters
    ----------
    content : str
        The markdown content as a string.

    Returns
    -------
    str
        The markdown content without the timestamp line.
    """
    lines = content.splitlines()
    if lines and lines[-1].startswith("*Page generated on:"):
        lines = lines[:-1]
    return "\n".join(lines)


@app.command()
def list_basins(
    registry: Annotated[
        Path,
        typer.Option(
            "--registry",
            help="Path to the nzcvm_registry.yaml file (default: ../nzcvm_registry.yaml)",
            default_factory=lambda: Path(__file__).parent.parent
            / "nzcvm_registry.yaml",
        ),
    ],
):
    """
    List all available basins in the registry

    Parameters
    ----------
    registry : Path
        Path to the nzcvm_registry.yaml file.

    """

    basin_versions = get_basin_versions(registry)
    for basin_name in sorted(basin_versions.keys()):
        print(basin_name)


@app.command()
def generate_wiki(
    basin: Annotated[
        str,
        typer.Argument(
            help="Basin name to generate wiki for, or 'all' for all basins.",
        ),
    ],
    registry: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            help="Path to the nzcvm_registry.yaml file",
        ),
    ] = Path(__file__).parent.parent / "nzcvm_registry.yaml",
    scale_images: Annotated[
        bool,
        typer.Option(
            help="Scale images to 75% size with a clickable link to full size",
        ),
    ] = False,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Directory to write basin subdirectories to (default: ../regional)",
        ),
    ] = Path(__file__).parent.parent / "regional",
) -> None:
    """
    Generate README.md files for basins from nzcvm_registry.yaml

    Parameters
    ----------
    basin : str
        Basin name to generate wiki for, or 'all' for all basins.
    registry : Path, optional
        Path to the nzcvm_registry.yaml file.
    scale_images : bool, optional
        Scale images to 75% size with a clickable link to full size.
    output_dir : Path, optional
        Directory to write basin subdirectories to (default: ../regional).

    """
    basin_versions = get_basin_versions(registry)

    if basin != "all":
        if basin not in basin_versions:
            print(f"Error: Basin '{basin}' not found in registry.")
            print(f"Available basins: {', '.join(sorted(basin_versions.keys()))}")
            raise typer.Exit(code=1)
        basin_versions = {basin: basin_versions[basin]}

    output_dir.mkdir(parents=True, exist_ok=True)

    for basin_name, versions in basin_versions.items():
        latest_version = max(versions, key=lambda x: x["version_tuple"])
        older_versions = [v for v in versions if v != latest_version]

        version = latest_version["version"]
        basin_data = latest_version["data"]

        basin_type = basin_data.get("type", "N/A")
        author = basin_data.get("author", "Unknown")
        images = basin_data.get("wiki_images", [])
        notes = basin_data.get("notes", [])
        boundaries = basin_data.get("boundaries", [])
        surfaces = basin_data.get("surfaces", [])
        smoothing = basin_data.get("smoothing", "N/A")

        created = "Unknown"
        if "p" in version:
            year, month = version.split("p")
            year = f"20{year}"
            month = f"{int(month):02d}"
            created = f"{year}-{month}"

        md_content = f"# Basin : {basin_name}\n\n"

        # Overview Section
        md_content += "## Overview\n"
        md_content += "|         |                     |\n"
        md_content += "|---------|---------------------|\n"
        md_content += f"| Version | {version}           |\n"
        md_content += f"| Type    | {basin_type}        |\n"
        md_content += f"| Author  | {author}            |\n"
        md_content += f"| Created | {created}           |\n"
        if older_versions:
            md_content += (
                "| Older Versions | "
                + ", ".join(v["version"] for v in older_versions)
                + " |\n"
            )
        md_content += "\n\n"

        # Images Section
        if images:
            md_content += "## Images\n"
            for i, img in enumerate(images):
                description = (
                    "Location"
                    if i == 0
                    else " ".join([s.capitalize() for s in Path(img).stem.split("_")])
                )

                if scale_images:
                    md_content += f'<a href="{img}"><img src="{img}" width="75%"></a>\n\n*Figure {i + 1} {description}*\n\n'
                else:
                    md_content += f"![]({img})\n\n*Figure {i + 1} {description}*\n\n"
            md_content += "\n"

        # Notes Section
        if notes:
            md_content += "## Notes\n"
            for note in notes:
                md_content += f"- {note}\n"
            md_content += "\n"

        # Data Section
        md_content += "## Data\n"

        if boundaries:
            md_content += "### Boundaries\n"
            for boundary in boundaries:
                file_path = Path(boundary)
                base_path = file_path.parent / file_path.stem
                geojson_path = f"{base_path}.geojson"
                txt_path = f"{base_path}.txt"

                links = []
                if (output_dir.parent / txt_path).exists():
                    links.append(f"[TXT]({txt_path})")
                if (output_dir.parent / geojson_path).exists():
                    links.append(f"[GeoJSON]({geojson_path})")

                link_text = " / ".join(links)
                md_content += f"- {file_path.stem} : {link_text}\n"
            md_content += "\n"

        if surfaces:
            md_content += "### Surfaces\n"
            for surface in surfaces:
                surface_path = surface.get("path", "Path not found")
                file_path = Path(surface_path)
                base_path = file_path.parent / file_path.stem
                submodel = surface.get("submodel", "N/A")

                h5_path = f"{base_path}.h5"
                in_path = f"{base_path}.in"

                links = []
                if (output_dir.parent / h5_path).exists():
                    links.append(f"[HDF5]({h5_path})")
                if (output_dir.parent / in_path).exists():
                    links.append(f"[TXT]({in_path})")

                link_text = " / ".join(links)
                md_content += (
                    f"- {file_path.stem} : {link_text} (Submodel: {submodel})\n"
                )
            md_content += "\n"

        if smoothing != "N/A":
            md_content += "### Smoothing Boundaries\n"
            smoothing_filename = Path(smoothing).name
            md_content += f"- [{smoothing_filename}]({smoothing})\n"
            md_content += "\n"

        nz_tz = pytz.timezone("Pacific/Auckland")
        timestamp = datetime.now(nz_tz).strftime("%B %d, %Y, %H:%M NZST/NZDT")

        # Older versions section
        if older_versions:
            md_content += "## Older Versions\n\n"
            sorted_older_versions = sorted(
                older_versions, key=lambda x: x["version_tuple"], reverse=True
            )

            for old_version in sorted_older_versions:
                old_version_data = old_version["data"]
                old_version_name = old_version["version"]

                old_created = "Unknown"
                if "p" in old_version_name:
                    year, month = old_version_name.split("p")
                    year = f"20{year}"
                    month = f"{int(month):02d}"
                    old_created = f"{year}-{month}"

                md_content += f"### {old_version_name}\n\n"
                md_content += "|         |                     |\n"
                md_content += "|---------|---------------------|\n"
                md_content += f"| Version | {old_version_name}  |\n"
                md_content += f"| Type    | {old_version_data.get('type', 'N/A')} |\n"
                md_content += (
                    f"| Author  | {old_version_data.get('author', 'Unknown')} |\n"
                )
                md_content += f"| Created | {old_created}       |\n\n"

                old_images = old_version_data.get("wiki_images", [])
                unique_old_images = [img for img in old_images if img not in images]

                if unique_old_images:
                    md_content += "**Images:**\n"
                    for i, img in enumerate(unique_old_images):
                        description = (
                            "Location"
                            if i == 0
                            else " ".join(
                                [s.capitalize() for s in Path(img).stem.split("_")]
                            )
                        )

                        if scale_images:
                            md_content += f'<a href="{img}"><img src="{img}" width="75%"></a>\n\n*Figure {i + 1} {description}*\n\n'
                        else:
                            md_content += (
                                f"![]({img})\n\n*Figure {i + 1} {description}*\n\n"
                            )
                    md_content += "\n"

                old_notes = old_version_data.get("notes", [])
                if old_notes:
                    md_content += "**Notes:**\n"
                    for note in old_notes:
                        md_content += f"- {note}\n"
                    md_content += "\n"

                old_boundaries = old_version_data.get("boundaries", [])
                old_surfaces = old_version_data.get("surfaces", [])
                old_smoothing = old_version_data.get("smoothing", "N/A")

                if old_boundaries or old_surfaces or old_smoothing != "N/A":
                    md_content += "**Data:**\n"

                    if old_boundaries:
                        md_content += "*Boundaries:*\n"
                        for boundary in old_boundaries:
                            file_path = Path(boundary)
                            base_path = file_path.parent / file_path.stem
                            geojson_path = f"{base_path}.geojson"
                            txt_path = f"{base_path}.txt"

                            links = []
                            if (output_dir.parent / txt_path).exists():
                                links.append(f"[TXT]({txt_path})")
                            if (output_dir.parent / geojson_path).exists():
                                links.append(f"[GeoJSON]({geojson_path})")

                            link_text = " / ".join(links)
                            md_content += f"- {file_path.stem} : {link_text}\n"
                        md_content += "\n"

                    if old_surfaces:
                        md_content += "*Surfaces:*\n"
                        for surface in old_surfaces:
                            surface_path = surface.get("path", "Path not found")
                            file_path = Path(surface_path)
                            base_path = file_path.parent / file_path.stem
                            submodel = surface.get("submodel", "N/A")

                            h5_path = f"{base_path}.h5"
                            in_path = f"{base_path}.in"

                            links = []
                            if (output_dir.parent / h5_path).exists():
                                links.append(f"[HDF5]({h5_path})")
                            if (output_dir.parent / in_path).exists():
                                links.append(f"[TXT]({in_path})")

                            link_text = " / ".join(links)
                            md_content += f"- {file_path.stem} : {link_text} (Submodel: {submodel})\n"
                        md_content += "\n"

                    if old_smoothing != "N/A":
                        md_content += "*Smoothing Boundaries:*\n"
                        smoothing_filename = Path(old_smoothing).name
                        md_content += f"- [{smoothing_filename}]({old_smoothing})\n"
                        md_content += "\n"

                md_content += "\n"

        md_content += f"---\n*Page generated on: {timestamp}*\n"

        basin_dir = output_dir / basin_name
        basin_dir.mkdir(parents=True, exist_ok=True)
        readme_path = basin_dir / "README.md"

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, suffix=".md"
        ) as temp_file:
            temp_file.write(md_content)
            temp_path = Path(temp_file.name)

        try:
            if readme_path.exists():
                with open(readme_path, "r", encoding="utf-8") as f:
                    existing_content = _remove_timestamp_line(f.read())

                with open(temp_path, "r", encoding="utf-8") as f:
                    new_content = _remove_timestamp_line(f.read())

                if existing_content == new_content:
                    print(f"No changes detected for {readme_path} - skipping")
                    temp_path.unlink()
                    continue
                else:
                    print(f"Changes detected - updating {readme_path}")
            else:
                print(f"Creating new file {readme_path}")

            shutil.move(str(temp_path), str(readme_path))

        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise e

    print(f"Processed {len(basin_versions)} basins under {output_dir}")


if __name__ == "__main__":
    app()
