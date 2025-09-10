"""
Interpolate EP2020 tomography data onto a uniform NZCVM grid.

This script interpolates scattered EP2020 tomography points onto a uniform
rectilinear grid suitable for use in the NZCVM framework.
"""

from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy.interpolate import griddata


def read_ep_txt(txt_path: str | Path) -> pd.DataFrame:
    """
    Read EP-style TXT tomography data.

    Parameters
    ----------
    txt_path : str or Path
        Path to the EP TXT file.

    Returns
    -------
    pd.DataFrame
        DataFrame containing tomography data with depth inverted to negative values.
    """
    col_names = [
        "vp", "vp_o_vs", "vs", "rho", "sf_vp", "sf_vp_o_vs",
        "x", "y", "depth", "lat", "lon"
    ]
    df = pd.read_csv(
        txt_path,
        sep=r"\s+",
        skiprows=2,
        names=col_names,
        engine="python"
    )
    df['depth']=-1*df['depth']

    return df


def load_nzcvm_grid(h5_path: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load NZCVM grid coordinates from reference HDF5 file.

    Parameters
    ----------
    h5_path : str or Path
        Path to the reference HDF5 file.

    Returns
    -------
    tuple[np.ndarray, np.ndarray, np.ndarray]
        Tuple containing (latitudes, longitudes, depths).
    """
    with h5py.File(h5_path, "r") as f:
        depth_keys = sorted(f.keys(), key=lambda x: float(x))
        depth = np.array([float(k) for k in depth_keys])
        group0 = f[depth_keys[0]]
        lat = group0["latitudes"][:]
        lon = group0["longitudes"][:]
    return lat, lon, depth


def interpolate_property_to_grid(
    df: pd.DataFrame,
    lat: np.ndarray,
    lon: np.ndarray,
    depth: np.ndarray,
    field_name: str
) -> np.ndarray:
    """
    Interpolate a property from scattered points to a regular grid.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame containing scattered data points.
    lat : np.ndarray
        Target latitude grid points.
    lon : np.ndarray
        Target longitude grid points.
    depth : np.ndarray
        Target depth levels.
    field_name : str
        Name of the field to interpolate.

    Returns
    -------
    np.ndarray
        Interpolated data on regular grid with shape (ndepth, nlat, nlon).
    """
    nlat, nlon, ndepth = len(lat), len(lon), len(depth)
    out = np.full((ndepth, nlat, nlon), np.nan, dtype=np.float32)

    for iz, d in enumerate(depth):
        df_d = df[np.isclose(df["depth"], d, atol=1e-3)]
        if df_d.empty:
            print(f"⚠️ No data at depth={d:.2f} km")
            continue

        points = df_d[["lon", "lat"]].values
        values = df_d[field_name].values
        lon_grid, lat_grid = np.meshgrid(lon, lat)

        interp = griddata(points, values, (lon_grid, lat_grid), method="linear", fill_value=0.0)
        out[iz] = interp

    return out


def write_epstyle_hdf5(
    output_path: str | Path,
    lats: np.ndarray,
    lons: np.ndarray,
    depth_list: np.ndarray,
    vp_stack: np.ndarray,
    vs_stack: np.ndarray,
    rho_stack: np.ndarray
) -> None:
    """
    Write EP-style tomography HDF5 file.

    Each depth slice becomes a group named by depth in km.
    
    Parameters
    ----------
    output_path : str or Path
        Output HDF5 file path.
    lats : np.ndarray
        Latitude values (nlat,).
    lons : np.ndarray
        Longitude values (nlon,).
    depth_list : np.ndarray
        Depths in km (nz,).
    vp_stack : np.ndarray
        P-wave velocity data (nz, nlat, nlon).
    vs_stack : np.ndarray
        S-wave velocity data (nz, nlat, nlon).
    rho_stack : np.ndarray
        Density data (nz, nlat, nlon).
    """
    nlat, nlon = len(lats), len(lons)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    coords = np.stack([lat_grid, lon_grid], axis=-1)  # shape: (nlat, nlon, 2)

    vp_stack[np.isnan(vp_stack)]=-999.0
    vs_stack[np.isnan(vs_stack)]=-999.0
    rho_stack[np.isnan(rho_stack)]=-999.0

    with h5py.File(output_path, "w") as f:
        for iz, depth in enumerate(depth_list):
            grp = f.create_group(f"{depth:.0f}")
            grp.create_dataset("latitudes", data=lats)
            grp.create_dataset("longitudes", data=lons)
            grp.create_dataset("coords", data=coords)
            grp.create_dataset("vp", data=vp_stack[iz])
            grp.create_dataset("vs", data=vs_stack[iz])
            grp.create_dataset("rho", data=rho_stack[iz])

    print(f"✅ Saved EP-style HDF5 to {output_path}")


def main() -> None:
    """
    Main function to run the interpolation process.

    This function orchestrates the entire interpolation workflow:
    1. Read EP2020 data
    2. Load NZCVM grid
    3. Interpolate data to grid
    4. Save results to HDF5
    """
    input_txt = Path("vlnzw2p2dnxyzltln.tbl.txt")
    ref_h5 = Path("../../EP2010/ep2010.h5")
    out_h5 = Path("../ep2020_uniform.h5")

    print("📥 Reading EP-style TXT...")
    df = read_ep_txt(input_txt)
    print(set(df['depth']))

    print("📐 Loading NZCVM grid...")
    lat, lon, depth = load_nzcvm_grid(ref_h5)

    print("📊 Interpolating vp...")
    vp = interpolate_property_to_grid(df, lat, lon, depth, "vp")
    print("📊 Interpolating vs...")
    vs = interpolate_property_to_grid(df, lat, lon, depth, "vs")
    print("📊 Interpolating rho...")
    rho = interpolate_property_to_grid(df, lat, lon, depth, "rho")

    print("💾 Writing to output HDF5...")
    write_epstyle_hdf5(out_h5, lat, lon, depth, vp, vs, rho)


if __name__ == "__main__":
    main()
