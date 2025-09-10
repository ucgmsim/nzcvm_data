"""
Combine multiple GeoJSON files into a single file with color styling.

This module provides functionality to read multiple GeoJSON files, apply
color styling based on their parent directories, and combine them into
a single GeoJSON FeatureCollection.
"""

import json
import os
from itertools import cycle
from pathlib import Path
from typing import Annotated

import matplotlib.pyplot as plt
import typer

app = typer.Typer(pretty_exceptions_enable=False)


def generate_colors(n: int) -> list[dict[str, str | int | float]]:
    """
    Generate n distinct colors using matplotlib colormap.

    Parameters
    ----------
    n : int
        Number of colors to generate.

    Returns
    -------
    list
        List of color dictionaries with stroke, fill, and opacity properties.
    """
    cmap = plt.get_cmap("brg")  # You can choose different colormaps from matplotlib
    color_list = [cmap(random.random()) for _ in range(n)]
    colors = []
    for i in range(n):
        color = color_list[i]
        stroke = f"#{int(color[0] * 255):02x}{int(color[1] * 255):02x}{int(color[2] * 255):02x}"
        fill = f"#{int(color[0] * 255):02x}{int(color[1] * 255):02x}{int(color[2] * 255):02x}"
        colors.append(
            {"stroke": stroke, "fill": fill, "stroke-width": 1, "fill-opacity": 0.3}
        )
    return colors


def read_geojson(file_path: str | Path) -> dict:
    """
    Read a GeoJSON file and return its contents.

    Parameters
    ----------
    file_path : str or Path
        Path to the GeoJSON file.

    Returns
    -------
    dict
        GeoJSON data as a dictionary.
    """
    with open(file_path, "r") as file:
        return json.load(file)


def read_file_list(file_list_path: str | Path) -> list[Path]:
    """
    Read a list of file paths from a text file.

    Parameters
    ----------
    file_list_path : str or Path
        Path to the file containing list of GeoJSON files.

    Returns
    -------
    list
        List of Path objects for each GeoJSON file.
    """
    with open(file_list_path, "r") as file:
        return [Path(line.strip()) for line in file.readlines()]


def combine_geojson(files: list[Path]) -> dict:
    """
    Combine multiple GeoJSON files into a single FeatureCollection.

    Parameters
    ----------
    files : list
        List of Path objects pointing to GeoJSON files.

    Returns
    -------
    dict
        Combined GeoJSON FeatureCollection with color styling.
    """
    combined_features = []
    groups = {}
    for b in files:
        parent = b.parent
        if parent in groups:
            groups[parent].append(b)
        else:
            groups[parent] = [b]

    print(groups)
    colors = generate_colors(len(groups))
    # Use a default color for all groups (uncomment and modify as needed)
    color_text = "#ba0045"
    colors = [
        {
            "stroke": color_text,
            "fill": color_text,
            "stroke-width": 1,
            "fill-opacity": 0.3,
        }
    ] * len(groups)
    color_cycle = cycle(colors)

    for parent, group in groups.items():
        color = next(color_cycle)
        print(f"{parent} {color}")
        for file_path in group:
            geojson = read_geojson(file_path)
            for feature in geojson["features"]:
                feature["properties"].update(color)
                feature["properties"]["source_file"] = os.path.basename(file_path)
                combined_features.append(feature)

    combined_geojson = {"type": "FeatureCollection", "features": combined_features}
    return combined_geojson


def write_geojson_to_file(geojson: dict, output_file_path: str | Path) -> None:
    """
    Write GeoJSON data to a file.

    Parameters
    ----------
    geojson : dict
        GeoJSON data to write.
    output_file_path : str or Path
        Path where to write the output file.
    """
    with open(output_file_path, "w") as file:
        json.dump(geojson, file, indent=4)


@app.command()
def main(
    input_file_list: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="Text file containing list of GeoJSON files (one per line)"
        ),
    ],
    output_file: Annotated[
        Path,
        typer.Argument(
            dir_okay=False,
            help="Output GeoJSON file path"
        ),
    ],
) -> None:
    """
    Combine multiple GeoJSON files into a single file with color styling.

    Parameters
    ----------
    input_file_list : Path
        Text file containing list of GeoJSON files (one per line).
    output_file : Path
        Output GeoJSON file path.
    """
    input_files = read_file_list(input_file_list)

    for input_file in input_files:
        if not input_file.exists():
            print(f"Error: File '{input_file}' not found.")
            raise typer.Exit(1)

    combined_geojson = combine_geojson(input_files)
    write_geojson_to_file(combined_geojson, output_file)
    print(f"Combined GeoJSON file created: {output_file}")


if __name__ == "__main__":
    app()
