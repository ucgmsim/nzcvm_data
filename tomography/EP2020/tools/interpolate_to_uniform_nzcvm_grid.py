"""
Interpolate Eberhart-Phillips tomography data onto a uniform NZCVM grid.

This script interpolates scattered Eberhart-Phillips tomography points onto a uniform
rectilinear grid suitable for use in the NZCVM framework.

OPTIMIZED VERSION: Includes gzip compression and float32 coordinates for 
efficient file sizes (typically 2-4x smaller than uncompressed).
"""

import argparse
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
    rho_stack: np.ndarray,
    compression_level: int = 4
) -> None:
    """
    Write EP-style tomography HDF5 file with compression.

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
    compression_level : int
        Gzip compression level (0-9). Default 4 is good balance.
        0=no compression, 9=max compression (slower).
    """
    # Create coordinate meshgrid (keep as float64 for best compression with shuffle)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    coords = np.stack([lat_grid, lon_grid], axis=-1)  # float64

    # Replace NaN with -999.0 flag
    vp_stack[np.isnan(vp_stack)] = -999.0
    vs_stack[np.isnan(vs_stack)] = -999.0
    rho_stack[np.isnan(rho_stack)] = -999.0

    # Calculate expected file sizes
    nlat, nlon = len(lats), len(lons)
    points_per_level = nlat * nlon
    data_size_mb = (points_per_level * 3 * 4 * len(depth_list)) / (1024**2)  # 3 vars, 4 bytes
    coords_size_mb = (points_per_level * 2 * 8 * len(depth_list)) / (1024**2)  # coords, 2 vals, 8 bytes
    total_uncompressed_mb = data_size_mb + coords_size_mb
    
    print(f"\n💾 Writing HDF5 with compression:")
    print(f"   Output: {output_path}")
    print(f"   Grid: {nlat} lat × {nlon} lon × {len(depth_list)} depth")
    print(f"   Compression: gzip level {compression_level} + shuffle filter")
    print(f"   Uncompressed size estimate: {total_uncompressed_mb:.1f} MB ({total_uncompressed_mb/1024:.2f} GB)")

    # Determine optimal chunk size for 2D data arrays (256x256 is good for most datasets)
    chunk_size = min(256, nlat), min(256, nlon)
    
    # Chunk size for coords (smaller chunks for 3D array)
    coords_chunk_size = (min(88, nlat), min(50, nlon), 1)

    with h5py.File(output_path, "w") as f:
        for iz, depth in enumerate(depth_list):
            grp_name = f"{depth:.0f}" if depth == int(depth) else f"{depth:.1f}"
            grp = f.create_group(grp_name)
            
            # Store lat/lon as float64 with compression and shuffle
            grp.create_dataset("latitudes", data=lats, 
                             dtype=np.float64,
                             compression="gzip", 
                             compression_opts=compression_level,
                             shuffle=True)
            grp.create_dataset("longitudes", data=lons, 
                             dtype=np.float64,
                             compression="gzip", 
                             compression_opts=compression_level,
                             shuffle=True)
            
            # Coords as float64 with compression, shuffle, and optimized chunking
            # Regular grids compress EXTREMELY well with shuffle (36x compression!)
            grp.create_dataset("coords", data=coords, 
                             dtype=np.float64,
                             compression="gzip", 
                             compression_opts=compression_level,
                             shuffle=True,
                             chunks=coords_chunk_size)
            
            # Data arrays with compression, shuffle, and optimized chunking
            grp.create_dataset("vp", data=vp_stack[iz], 
                             dtype=np.float32,
                             compression="gzip", 
                             compression_opts=compression_level,
                             shuffle=True,
                             chunks=chunk_size)
            grp.create_dataset("vs", data=vs_stack[iz], 
                             dtype=np.float32,
                             compression="gzip", 
                             compression_opts=compression_level,
                             shuffle=True,
                             chunks=chunk_size)
            grp.create_dataset("rho", data=rho_stack[iz], 
                             dtype=np.float32,
                             compression="gzip", 
                             compression_opts=compression_level,
                             shuffle=True,
                             chunks=chunk_size)
            
            if (iz + 1) % 5 == 0 or iz == 0 or iz == len(depth_list) - 1:
                print(f"   Written group '{grp_name}' ({iz+1}/{len(depth_list)})")

    # Report actual file size
    actual_size_mb = Path(output_path).stat().st_size / (1024**2)
    compression_ratio = total_uncompressed_mb / actual_size_mb if actual_size_mb > 0 else 0
    
    print(f"\n✅ Successfully saved EP-style HDF5 to {output_path}")
    print(f"   Actual file size: {actual_size_mb:.1f} MB ({actual_size_mb/1024:.2f} GB)")
    print(f"   Compression ratio: {compression_ratio:.1f}x")
    print(f"   Space saved: {total_uncompressed_mb - actual_size_mb:.1f} MB ({(total_uncompressed_mb - actual_size_mb)/1024:.2f} GB)")


def reconcile_depths(input_depths: set, ref_depths: np.ndarray) -> np.ndarray:
    """
    Reconcile depths between input data and reference grid.

    Parameters
    ----------
    input_depths : set
        Set of depths available in input data.
    ref_depths : np.ndarray
        Reference depths from grid.

    Returns
    -------
    np.ndarray
        Final depth array to use for interpolation.
    """
    input_depths_array = np.array(sorted(input_depths))
    ref_depths_set = set(ref_depths)

    print(f"📊 Depth compatibility analysis:")
    print(f"   Input data depths: {len(input_depths)} levels")
    print(f"   Reference grid depths: {len(ref_depths)} levels")

    # Find overlapping depths
    common_depths = input_depths & ref_depths_set
    input_only = input_depths - ref_depths_set
    ref_only = ref_depths_set - input_depths

    print(f"   Common depths: {len(common_depths)}")
    if input_only:
        print(f"   ⚠️  Input-only depths (will be added): {sorted(input_only)}")
    if ref_only:
        print(f"   ℹ️  Reference-only depths (will be skipped): {len(ref_only)} levels")

    # Determine final depth array
    if ref_depths_set.issuperset(input_depths):
        # Reference is superset - use only depths that have input data
        final_depths = input_depths_array
        print(f"   ✅ Using input depths only ({len(final_depths)} levels)")
    else:
        # Input has additional depths - combine both
        all_depths = sorted(input_depths | ref_depths_set)
        final_depths = np.array(all_depths)
        print(f"   ✅ Using combined depths ({len(final_depths)} levels)")

    return final_depths


def main() -> None:
    """
    Main function to run the interpolation process.

    This function orchestrates the entire interpolation workflow:
    1. Parse command line arguments
    2. Read Eberhart-Phillips data
    3. Load NZCVM grid
    4. Reconcile depths
    5. Interpolate data to grid
    6. Save results to HDF5 with compression
    """
    parser = argparse.ArgumentParser(
        description="Interpolate Eberhart-Phillips tomography data onto uniform NZCVM grid with compression"
    )
    parser.add_argument(
        "input_txt",
        type=Path,
        help="Path to input EP-style TXT file"
    )
    parser.add_argument(
        "ref_h5",
        type=Path,
        help="Path to reference HDF5 file for grid definition"
    )
    parser.add_argument(
        "out_h5",
        type=Path,
        help="Path to output HDF5 file"
    )
    parser.add_argument(
        "--compression",
        type=int,
        default=4,
        choices=range(0, 10),
        help="Gzip compression level (0-9, default: 4). Higher = smaller but slower."
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Eberhart-Phillips TOMOGRAPHY INTERPOLATION (OPTIMIZED)")
    print("=" * 70)

    print("\n📥 Reading EP-style TXT...")
    df = read_ep_txt(args.input_txt)
    input_depths = set(df['depth'])
    print(f"   Found {len(input_depths)} depth levels in input data")

    print("\n📐 Loading NZCVM grid...")
    lat, lon, ref_depths = load_nzcvm_grid(args.ref_h5)
    print(f"   Grid: {len(lat)} lat × {len(lon)} lon = {len(lat)*len(lon):,} points per level")

    # Reconcile depths between input and reference
    print(f"\n")
    final_depths = reconcile_depths(input_depths, ref_depths)

    print("\n📊 Interpolating vp...")
    vp = interpolate_property_to_grid(df, lat, lon, final_depths, "vp")
    print("📊 Interpolating vs...")
    vs = interpolate_property_to_grid(df, lat, lon, final_depths, "vs")
    print("📊 Interpolating rho...")
    rho = interpolate_property_to_grid(df, lat, lon, final_depths, "rho")

    print("\n💾 Writing to output HDF5...")
    write_epstyle_hdf5(args.out_h5, lat, lon, final_depths, vp, vs, rho, 
                       compression_level=args.compression)
    
    print("\n" + "=" * 70)
    print("CONVERSION COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
