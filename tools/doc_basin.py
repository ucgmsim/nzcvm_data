import json
import re
from pathlib import Path
from typing import Annotated

import geopandas as gpd
import h5py
import matplotlib.pyplot as plt
import numpy as np
import typer
import yaml

app = typer.Typer()

with open("nzcvm_registry.yaml") as f:
    registry = yaml.safe_load(f)

basins = registry["basin"]

basin_map = {}
for b in basins:
    m = re.match(r"(.+)_v(\d+p\d+)", b["name"])
    if m:
        base, ver = m.groups()
        basin_map.setdefault(base, []).append((ver, b))

for base in basin_map:
    basin_map[base].sort(
        key=lambda x: [
            int(n) if n.isdigit() else n for n in x[0].replace("p", ".").split(".")
        ],
        reverse=True,
    )


def surface_ascii2h5(ascii_path):
    txt_path = Path(ascii_path)
    arr = np.loadtxt(txt_path)
    ny, nx = arr.shape
    lon = np.linspace(0, 1, nx)  # dummy
    lat = np.linspace(0, 1, ny)  # dummy
    outpath = txt_path.with_suffix(".h5")
    with h5py.File(outpath, "w") as f:
        f.create_dataset("elevation", data=arr)
        f.create_dataset("longitude", data=lon)
        f.create_dataset("latitude", data=lat)


def boundary_txt_to_geojson(txt_path):
    coords = np.loadtxt(txt_path)
    polygon = {"type": "Polygon", "coordinates": [coords.tolist()]}
    outpath = Path(txt_path).with_suffix(".geojson")
    with open(outpath, "w") as f:
        json.dump({"type": "Feature", "geometry": polygon, "properties": {}}, f)


def map_one_basin(basin_name: str, registry_path: str, outdir: Path):
    with open(registry_path) as f:
        registry = yaml.safe_load(f)

    basin_entry = next(b for b in registry["basin"] if b["name"] == basin_name)
    boundaries = basin_entry.get("boundaries", [])
    gdfs = [
        gpd.read_file(Path(b).with_suffix(".geojson"))
        for b in boundaries
        if Path(b).with_suffix(".geojson").exists()
    ]
    if not gdfs:
        return

    gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
    fig, ax = plt.subplots(figsize=(6, 6))
    gdf.plot(ax=ax, edgecolor="black", facecolor="lightblue")
    ax.set_title(f"{basin_name} basin map")
    outdir.mkdir(parents=True, exist_ok=True)
    plt.savefig(outdir / f"{basin_name}.png")
    plt.close()


def generate_basin_wiki(basin_name: str, registry_path: str, outdir: Path):
    with open(registry_path) as f:
        registry = yaml.safe_load(f)

    basin_entry = next(b for b in registry["basin"] if b["name"] == basin_name)
    lines = [f"# {basin_name}", ""]
    if "notes" in basin_entry:
        lines += basin_entry["notes"] + [""]
    if "wiki_images" in basin_entry:
        for img in basin_entry["wiki_images"]:
            lines.append(f"![{basin_name}]({img})")
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / f"{basin_name}.md", "w") as f:
        f.write("\n".join(lines))


@app.command()
def process(
    basin: Annotated[str, typer.Argument(help="Basin name or 'all'")],
    project_root: Annotated[Path, typer.Option(help="Path to the project root")],
):
    targets = []
    if basin == "all":
        targets = [b[1] for blist in basin_map.values() for b in [blist[0]]]
    else:
        if basin not in basin_map:
            typer.echo(f"Unknown basin base name: {basin}", err=True)
            raise typer.Exit(1)
        targets = [basin_map[basin][0][1]]

    for b in targets:
        name = b["name"]
        typer.echo(f"Processing: {name}")
        bdir = Path("regional") / name.split("_")[0]

        for surface in b.get("surfaces", []):
            if surface["path"].endswith(".in"):
                surface_ascii2h5(bdir / surface["path"])

        for boundary in b.get("boundaries", []):
            boundary_txt_to_geojson(boundary)

        smoothing = b.get("smoothing")
        map_out = project_root / "wiki" / "images" / "regional"
        map_one_basin(name, "nzcvm_registry.yaml", map_out)

        wiki_out = project_root / "wiki" / "basins"
        generate_basin_wiki(name, "nzcvm_registry.yaml", wiki_out)


if __name__ == "__main__":
    app()
