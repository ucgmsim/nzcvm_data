"""
Convert a GeoJSON geometry/Feature/FeatureCollection into a TXT outline file.

Default TXT format:
- One coordinate per line as: <lon><sep><lat>
- Rings are separated by a blank line
- Multiple polygons are written sequentially, separated by a blank line
- Optional header/comment lines start with '#'

You can customize separator, precision and ring separation style to match your pipeline.

```
Examples
--------
# Basic usage (output will be input.txt)
python boundary_geojson2txt.py input.geojson

# Explicit output filename
python boundary_geojson2txt.py input.geojson --output output.txt

# Use comma separator and fixed 7 decimals
python boundary_geojson2txt.py basins.geojson  --precision 7 --sep ","

# Select a single feature by property
python boundary_geojson2txt.py basins.geojson --where "name=Canterbury"

# Multi-polygon with 'END' ring separators (common in some seismic tools)
python boundary_geojson2txt.py poly.geojson  --ring-sep end

```

"""

import json
from pathlib import Path
from typing import Any, Iterable, Optional

import typer

app = typer.Typer(pretty_exceptions_enable=False)

Coord = tuple[float, float]


def _fmt_coord(coord: Coord, precision: int, sep: str) -> str:
    """
    Format a coordinate tuple as a string.

    Parameters
    ----------
    coord : Coord
        (lon, lat) tuple.
    precision : int
        Decimal places.
    sep : str
        Separator between numbers.

    Returns
    -------
    str
        Formatted coordinate string.
    """
    lon, lat = coord
    fmt = f"{{:.{precision}f}}"
    return f"{fmt.format(lon)}{sep}{fmt.format(lat)}"


def _get_nan_sep_line(sep: str) -> str:
    """
    Return a 'NaN' separator line.

    Parameters
    ----------
    sep : str
        Separator between numbers.

    Returns
    -------
    str
        'NaN' separator line.
    """
    return f"nan{sep}nan"


def _iter_features(geojson: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """
    Yield features from a GeoJSON object, handling FeatureCollection, Feature, or Geometry.

    Parameters
    ----------
    geojson : dict[str, Any]
        GeoJSON object.

    Yields
    ------
    dict[str, Any]
        GeoJSON Feature dictionaries.
    Raises
    ------
    ValueError
        If the GeoJSON root type is unsupported.
    """
    t = geojson.get("type")
    if t == "FeatureCollection":
        for feat in geojson.get("features", []):
            yield feat
    elif (
        t == "Feature"
        or (t and t.endswith("Geometry"))
        or t in {"Polygon", "MultiPolygon", "LineString", "MultiLineString"}
    ):
        # Wrap single geometry as a Feature for uniform handling
        if t == "Feature":
            yield geojson
        else:
            yield {"type": "Feature", "properties": {}, "geometry": geojson}
    else:
        raise ValueError(f"Unsupported GeoJSON root type: {t}")


def _extract_rings(geom: dict[str, Any]) -> list[list[Coord]]:
    """
    Return list of rings, each a list of (lon,lat). For LineString(s), treat as a single ring.

    Parameters
    ----------
    geom : dict[str, Any]
        GeoJSON geometry dictionary.

    Returns
    -------
    list[list[Coord]]
        List of rings, each a list of (lon, lat) tuples.

    Raises
    ------
    ValueError
        If geometry type is unsupported.

    """
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not gtype or not coords:
        raise ValueError("Geometry must have 'type' and 'coordinates'.")

    rings: list[list[Coord]] = []  # List of rings to return

    if gtype == "Polygon":
        for ring in coords:
            rings.append([(float(x), float(y)) for x, y, *rest in ring])
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                rings.append([(float(x), float(y)) for x, y, *rest in ring])
    elif gtype == "LineString":
        rings.append([(float(x), float(y)) for x, y, *rest in coords])
    elif gtype == "MultiLineString":
        for line in coords:
            rings.append([(float(x), float(y)) for x, y, *rest in line])
    else:
        raise ValueError(
            f"Geometry type '{gtype}' not supported. Use Polygon/MultiPolygon/LineString/MultiLineString."
        )
    return rings


def _where_match(props: dict[str, Any], where: Optional[str]) -> bool:
    """
    Check if properties match the --where filter.

    Parameters
    ----------
    props : dict[str, Any]
        Feature properties.
    where : Optional[str]
        Filter string in the form "key=value".

    Returns
    -------
    bool
        True if properties match the filter or if no filter is set.

    """
    if not where:
        return True
    if "=" not in where:
        raise ValueError("--where must look like key=value")
    key, value = where.split("=", 1)
    return str(props.get(key)) == value


def convert(
    geojson_path: Path,
    txt_path: Path,
    sep: str = " ",
    precision: int = 8,
    ring_sep: str = "blank",
    header_key: Optional[str] = None,
    where: Optional[str] = None,
):
    """
    Convert GeoJSON to TXT outline format.

    Parameters
    ----------
    geojson_path :  Path
        Path to input GeoJSON file.
    txt_path : Path
        Path to output TXT file.
    sep : str
        Separator between numbers in output lines. Default: space
    precision : int
        Decimal places for coordinates. Default: 8
    ring_sep : str
        Separator between rings. One of: "blank", "nan", "end". Default: "blank"
    header_key : Optional[str]
        If set, write a '# Feature: key=value' line using this property.
    where : Optional[str]
        If set, filter to a single feature by property equality: key=value.
    """

    with geojson_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    out_lines: list[str] = []
    feature_count = 0

    for feat in _iter_features(data):
        props = feat.get("properties", {}) or {}
        if not _where_match(props, where):
            continue
        geom = feat.get("geometry")
        if not geom:
            continue
        feature_count += 1
        # Optional header
        if header_key is not None:
            header_val = props.get(header_key, "")
            out_lines.append(f"# Feature {feature_count}: {header_key}={header_val}")

        rings = _extract_rings(geom)
        for r_i, ring in enumerate(rings, start=1):
            # Ensure closed ring if geometry is polygon-like & not already closed
            if geom.get("type", "").endswith("Polygon") and (
                len(ring) >= 2 and ring[0] != ring[-1]
            ):
                ring = ring + [ring[0]]

            for coord in ring:
                out_lines.append(_fmt_coord(coord, precision=precision, sep=sep))

            # ring separator
            if ring_sep == "blank":
                out_lines.append("")
            elif ring_sep == "nan":
                out_lines.append(_get_nan_sep_line(sep=sep))
            elif ring_sep == "end":
                out_lines.append("END")
            else:
                raise ValueError("ring_sep must be one of: blank, nan, end")

        # separate features with an extra blank line to be safe
        if out_lines and out_lines[-1] != "":
            out_lines.append("")

    # Tidy trailing separators
    while out_lines and out_lines[-1] == "":
        out_lines.pop()

    txt_path.write_text(
        "\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8"
    )
    print(f"Wrote {txt_path} with {feature_count} feature(s).")


@app.command(
    help="Convert GeoJSON (Feature/FeatureCollection/Geometry) to TXT outline format."
)
def main(
    geojson: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Input GeoJSON file"
    ),
    output: Path | None = typer.Option(
        None,
        dir_okay=False,
        help="Output TXT file path (defaults to input name with .txt)",
    ),
    sep: str = typer.Option(" ", help="Separator between numbers in output lines."),
    precision: int = typer.Option(8, min=0, help="Decimal places for coordinates."),
    ring_sep: str = typer.Option(
        "blank", metavar="[blank|nan|end]", help="Separator between rings."
    ),
    header_key: str | None = typer.Option(
        None, help="If set, write '# Feature: key=value' using this property"
    ),
    where: str | None = typer.Option(None, help="Filter features by 'key=value'."),
):
    """
    Convert GeoJSON to TXT outline format.

    Parameters
    ----------
    geojson : Path
        Input GeoJSON file.
    output : Path, optional
        Output TXT file path. If not provided, defaults to input name with .txt extension.
    sep : str, optional
        Separator between numbers in output lines. Default is space.
    precision : int, optional
        Decimal places for coordinates. Default is 8.
    ring_sep : str, optional
        Separator between rings. One of: blank, nan, end. Default is blank.
    header_key : str, optional
        If set, write a '# Feature: key=value' line using this property. Default is None.
    where : str, optional
        If set, filter to a single feature by property equality: key=value.
    """

    # Default output name if not provided
    if output is None:
        if geojson.suffix.lower() == ".geojson":
            output = geojson.with_suffix(".txt")
        else:
            output = geojson.with_name(geojson.stem + ".txt")

    # Validate enum-like options
    if ring_sep not in {"blank", "nan", "end"}:
        raise typer.BadParameter(
            "ring-sep must be one of: blank, nan, end", param_hint="--ring-sep"
        )

    convert(
        geojson_path=geojson,
        txt_path=output,
        sep=sep,
        precision=precision,
        ring_sep=ring_sep,
        header_key=header_key,
        where=where,
    )


if __name__ == "__main__":
    app()
