"""
Analyze and plot tomography data from TXT or HDF5 files.

This script provides functionality to analyze tomography data, generate spatial
distribution plots, check grid consistency, and create various visualizations.
"""

import os
from pathlib import Path
from typing import Annotated

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import typer

app = typer.Typer(pretty_exceptions_enable=False)


def load_txt_ep_format(txt_file: str) -> pd.DataFrame:
    """
    Load EP-style TXT tomography grid. Keeps longitudes as provided
    (may include values >180 or <0).
    """
    col_names = [
        "vp", "vp_o_vs", "vs", "rho", "sf_vp", "sf_vp_o_vs",
        "x", "y", "depth", "lat", "lon"
    ]
    df = pd.read_csv(
        txt_file,
        sep=r"\s+",
        skiprows=2,
        names=col_names,
        engine="python"
    )
    # NOTE: do NOT force-convert lon here; plotting handles 0–360 or -180..180
    return df


def load_hdf5_data(h5_file: str) -> pd.DataFrame:
    """
    Load a single depth slice from the HDF5 tomography file into a flat DataFrame.
    """
    with h5py.File(h5_file, "r") as f:
        depth_keys = sorted(f.keys(), key=lambda x: float(x))
        group = f[depth_keys[0]]

        lat = group["latitudes"][:]
        lon = group["longitudes"][:]
        vp = group["vp"][:]  # shape (nlat, nlon)
        lon_grid, lat_grid = np.meshgrid(lon, lat)

        df = pd.DataFrame({
            "lat": lat_grid.ravel().astype(np.float32),
            "lon": lon_grid.ravel().astype(np.float32),
            "vp": vp.ravel().astype(np.float32),
            "depth": float(depth_keys[0])
        })
    return df


def check_latlon_consistency(h5_file: str) -> None:
    """
    Verify that all depth groups share identical latitude/longitude arrays.
    """
    with h5py.File(h5_file, "r") as f:
        first_group = next(iter(f.keys()))
        lat_ref = f[first_group]["latitudes"][:]
        lon_ref = f[first_group]["longitudes"][:]

        all_good = True
        for depth in f.keys():
            lat = f[depth]["latitudes"][:]
            lon = f[depth]["longitudes"][:]

            if not (np.allclose(lat, lat_ref) and np.allclose(lon, lon_ref)):
                print(f"Mismatch in lat/lon at depth: {depth}")
                all_good = False

        if all_good:
            print("✅ All latitudes and longitudes are consistent across depths.")
        else:
            print("❌ Inconsistencies found in lat/lon arrays.")


def check_grid_spacing(lat: np.ndarray, lon: np.ndarray, tol: float = 1e-6) -> None:
    """
    Report unique spacings for lat/lon and whether they are regular.
    Prints approximate km for spacings.
    """
    lat_spacing = np.diff(lat)
    lon_spacing = np.diff(lon)

    unique_lat_spacings = np.unique(np.round(lat_spacing, decimals=5))
    unique_lon_spacings = np.unique(np.round(lon_spacing, decimals=5))

    is_lat_regular = len(unique_lat_spacings) == 1
    is_lon_regular = len(unique_lon_spacings) == 1

    # Latitude conversion (constant)
    lat_km_spacing = np.round(unique_lat_spacings * 111.32, 3)

    # Longitude spacing in km varies with latitude
    latitudes_for_conversion = np.linspace(lat.min(), lat.max(), num=1000)
    lon_km_spacings = unique_lon_spacings[:, np.newaxis] * 111.32 * np.cos(
        np.radians(latitudes_for_conversion)
    )
    lon_km_min = np.min(lon_km_spacings, axis=1)
    lon_km_max = np.max(lon_km_spacings, axis=1)

    print(
        f"Latitude spacings (unique): {unique_lat_spacings} deg ≈ {lat_km_spacing} km | "
        f"Regular: {is_lat_regular}"
    )
    print(
        f"Longitude spacings (unique): {unique_lon_spacings} deg ≈ "
        f"[{lon_km_min.min():.3f} – {lon_km_max.max():.3f}] km | Regular: {is_lon_regular}"
    )


def lons_centered_for_display(lon, center=180.0):
    """
    Shift longitudes into a continuous range [center-180, center+180)
    so there's a single seam at 'center' (default 180°).
    """
    lon = np.asarray(lon, dtype=float)
    # wrap to [-180, 180) after subtracting the center, then shift back
    return ((lon - center + 180.0) % 360.0) - 180.0 + center


def lons_centered_180(lon):
    """
    Convert arbitrary longitudes to the native range of
    PlateCarree(central_longitude=180), i.e. [-180, 180).
    """
    lon = np.asarray(lon, dtype=float)
    # shift by -180, wrap to [-180,180), done
    return ((lon - 180.0 + 180.0) % 360.0) - 180.0


def choose_projection_and_extent(lats: np.ndarray, lons: np.ndarray):
    """
    Decide projection and compute a tight extent.

    Returns
    -------
    ax_crs : axes projection
    data_crs : CRS of input data (always standard PlateCarree lon/lat)
    extent : (minlon, maxlon, minlat, maxlat) in the CRS given by extent_crs
    extent_crs : CRS that 'extent' is expressed in
    """
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)

    data_crs = ccrs.PlateCarree()  # input data CRS

    pad_lon = 0.5
    pad_lat = 0.5
    minlat = max(-90.0, float(lats.min()) - pad_lat)
    maxlat = min( 90.0, float(lats.max()) + pad_lat)

    has_over_180   = np.nanmax(lons) > 180.0
    has_negative   = np.nanmin(lons) < 0.0
    crosses_dl     = has_over_180 or has_negative

    if crosses_dl:
        # Use 180-centered axes; compute extent in that axes' native range [-180,180)
        ax_crs = ccrs.PlateCarree(central_longitude=180)
        lons_c = lons_centered_180(lons)                # <<< key fix (NOT 0..360)
        minlon = max(-180.0, float(lons_c.min()) - pad_lon)
        maxlon = min( 180.0, float(lons_c.max()) + pad_lon)
        extent = (minlon, maxlon, minlat, maxlat)
        extent_crs = ax_crs                              # extent expressed in axes CRS
    else:
        # Standard case: compute extent in data CRS and pass with data_crs
        ax_crs = ccrs.PlateCarree()
        minlon = max(-180.0, float(lons.min()) - pad_lon)
        maxlon = min( 180.0, float(lons.max()) + pad_lon)
        extent = (minlon, maxlon, minlat, maxlat)
        extent_crs = data_crs

    return ax_crs, data_crs, extent, extent_crs


def plot_spatial_distribution(df: pd.DataFrame, title_suffix: str = "") -> None:
    """
    Map the grid points without clipping across the dateline.
    Uses a 180°-centered axes when needed and sets extent in the matching CRS.
    """
    lats = df["lat"].values
    lons = df["lon"].values

    ax_crs, data_crs, extent, extent_crs = choose_projection_and_extent(lats, lons)

    fig = plt.figure(figsize=(10, 8))
    ax = plt.axes(projection=ax_crs)

    # Set extent in the CRS it was computed in
    ax.set_extent(extent, crs=extent_crs)

    ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
    ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.6)
    ax.add_feature(cfeature.LAND, facecolor="lightgray", edgecolor="none")
    ax.add_feature(cfeature.OCEAN, facecolor="lightsteelblue", edgecolor="none")
    ax.add_feature(cfeature.LAKES, alpha=0.5)
    ax.add_feature(cfeature.RIVERS, linewidth=0.5)

    ax.scatter(
        df["lon"], df["lat"],
        s=1, c="red", alpha=0.5,
        transform=data_crs,   # input data CRS is always standard lon/lat
        label="Model Grid"
    )
    gl = ax.gridlines(draw_labels=True, linestyle="--", linewidth=0.5)
    try:
        gl.right_labels = False
        gl.top_labels = False
    except Exception:
        pass

    plt.title(f"Spatial Domain of Tomography Model {title_suffix}")
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_spacing_histograms(df: pd.DataFrame) -> None:
    """
    Plot histograms of latitude and longitude spacing and density map.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing lat/lon data.
    """
    lat_spacing = np.diff(np.sort(np.unique(df["lat"])))
    lon_spacing = np.diff(np.sort(np.unique(df["lon"])))

    # Histogram: latitude spacing
    plt.figure(figsize=(10, 4))
    sns.histplot(lat_spacing, bins=100, kde=True)
    plt.title("Latitude Spacing Distribution")
    plt.xlabel("Δlat (degrees)")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.show()

    # Histogram: longitude spacing
    plt.figure(figsize=(10, 4))
    sns.histplot(lon_spacing, bins=100, kde=True)
    plt.title("Longitude Spacing Distribution")
    plt.xlabel("Δlon (degrees)")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.show()

    # Density map (data space) — shift longitudes so the seam is at 180°
    lon_disp = lons_centered_for_display(df["lon"].values, center=180.0)
    plt.figure(figsize=(8, 6))
    plt.hexbin(lon_disp, df["lat"], gridsize=100, cmap="Reds", mincnt=1)
    plt.colorbar(label="Number of Points")
    plt.title("Grid Point Density (centered at 180°)")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.tight_layout()
    plt.show()


def plot_density_map(df: pd.DataFrame) -> None:
    """
    Plot a density map of grid points.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing lat/lon data.
    """
    lon_disp = lons_centered_for_display(df["lon"].values, center=180.0)
    plt.figure(figsize=(10, 6))
    plt.hexbin(lon_disp, df["lat"], gridsize=100, cmap="Reds", mincnt=1)
    plt.colorbar(label="Number of Points")
    plt.title("Grid Point Density (centered at 180°)")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.tight_layout()
    plt.show()


@app.command()
def analyze(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="Input tomography file (.txt or .h5)"
        ),
    ],
) -> None:
    """
    Analyze and plot tomography data from TXT or HDF5.

    Parameters
    ----------
    input_file : Path
        Input tomography file (.txt or .h5).
    """
    ext = input_file.suffix.lower()
    if ext == ".h5":
        df = load_hdf5_data(str(input_file))
        check_latlon_consistency(str(input_file))
        suffix = "(HDF5)"
    elif ext == ".txt":
        df = load_txt_ep_format(str(input_file))
        suffix = "(TXT)"
    else:
        raise typer.BadParameter("Unsupported file type. Use .txt or .h5")

    print(f"Loaded {len(df)} points.")
    print("Unique latitudes:", len(np.unique(df["lat"])))
    print("Unique longitudes:", len(np.unique(df["lon"])))

    lat_vals = np.sort(np.unique(df["lat"]))
    lon_vals = np.sort(np.unique(df["lon"]))

    print(f"Lat range: {df['lat'].min()} {df['lat'].max()}")
    print(f"Lon range: {df['lon'].min()} {df['lon'].max()}")

    check_grid_spacing(lat_vals, lon_vals)

    # Map view that handles dateline properly
    plot_spatial_distribution(df, suffix)

    # Spacing + data-space density
    plot_spacing_histograms(df)

    # If a depth column exists, show surface slice density
    if "depth" in df.columns:
        df_surface = df[df["depth"] == df["depth"].min()]
        if not df_surface.empty:
            plot_density_map(df_surface)


if __name__ == "__main__":
    app()
