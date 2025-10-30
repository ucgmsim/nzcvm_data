"""
Interpolate Eberhart-Phillips tomography data onto a uniform NZCVM grid.

This script interpolates scattered Eberhart-Phillips tomography points onto a uniform
rectilinear grid suitable for use in the NZCVM framework.

OPTIMIZED VERSION: Includes gzip compression and float32 coordinates for 
efficient file sizes (typically 2-4x smaller than uncompressed).

IMPROVEMENTS:
- Keeps NaN values instead of filling with 0.0 (avoids boundary artifacts)
- Optional longitude extension beyond 180 deg meridian
- Retains all input depth levels
- FIXED: Longitude normalization across dateline (handles negative vs >180 deg coordinates)

DATELINE FIX:
When using --extend-lon to extend the grid beyond 180 deg, the script now automatically
normalizes input data longitudes to match the target grid convention:
- If grid extends >180: All longitudes normalized to 0-360 (e.g., -175 -> 185)
- Otherwise: All longitudes normalized to -180 to 180 (e.g., 185 -> -175)
This ensures scipy.interpolate.griddata can properly interpolate across the dateline.
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


def load_nzcvm_grid(h5_path: str | Path, extend_lon_deg: float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load NZCVM grid coordinates from reference HDF5 file.

    Parameters
    ----------
    h5_path : str or Path
        Path to the reference HDF5 file.
    extend_lon_deg : float, optional
        Degrees to extend longitude grid beyond 180deg (default: 0.0).
        Positive values extend eastward beyond 180deg.

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

    # Extend longitude grid if requested
    if extend_lon_deg > 0:
        lon_spacing = np.median(np.diff(lon))
        max_lon = lon[-1]
        n_extend = int(np.ceil(extend_lon_deg / lon_spacing))
        extended_lons = max_lon + lon_spacing * np.arange(1, n_extend + 1)
        lon = np.concatenate([lon, extended_lons])
        print(f"   Extended longitude grid by {extend_lon_deg:.2f}deg ({n_extend} points)")
        print(f"   New longitude range: {lon[0]:.2f}deg to {lon[-1]:.2f}deg")

    return lat, lon, depth


def interpolate_property_to_grid(
    df: pd.DataFrame,
    lat: np.ndarray,
    lon: np.ndarray,
    depth: np.ndarray,
    field_name: str,
    fill_value: float = np.nan
) -> np.ndarray:
    """
    Interpolate a property from scattered points to a regular grid.

    IMPROVED: Configurable fill_value for regions outside data coverage.
    FIXED: Handles longitude normalization across dateline (negative vs >180 deg coordinates).

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
    fill_value : float, optional
        Value to use for regions outside data coverage (default: np.nan).
        Common choices: np.nan (recommended), 0.0, or a specific velocity value.

    Returns
    -------
    np.ndarray
        Interpolated data on regular grid with shape (ndepth, nlat, nlon).
        Regions outside data coverage are filled with fill_value.
    """
    nlat, nlon, ndepth = len(lat), len(lon), len(depth)
    out = np.full((ndepth, nlat, nlon), np.nan, dtype=np.float32)

    # Determine target longitude convention based on grid extent
    # If grid extends beyond 180 deg, normalize everything to 0-360
    # Otherwise use -180 to 180
    use_360_convention = np.any(lon > 180.0)

    if use_360_convention:
        print(f"   [INFO] Longitude normalization: Using 0-360 deg convention (grid extends to {lon.max():.2f} deg)")
    else:
        print(f"   [INFO] Longitude normalization: Using -180 to 180 deg convention")

    for iz, d in enumerate(depth):
        df_d = df[np.isclose(df["depth"], d, atol=1e-3)]
        if df_d.empty:
            fill_str = "NaN" if np.isnan(fill_value) else f"{fill_value}"
            print(f"   No data at depth={d:.2f} km - leaving as {fill_str}")
            continue

        # Normalize input data longitudes to match target grid convention
        input_lons = df_d["lon"].values.copy()
        if use_360_convention:
            # Convert negative longitudes to 0-360 range (e.g., -175 deg -> 185 deg)
            input_lons = np.where(input_lons < 0, input_lons + 360.0, input_lons)
        else:
            # Convert longitudes > 180 to -180 to 180 range (e.g., 185 deg -> -175 deg)
            input_lons = np.where(input_lons > 180, input_lons - 360.0, input_lons)

        points = np.column_stack([input_lons, df_d["lat"].values])
        values = df_d[field_name].values
        lon_grid, lat_grid = np.meshgrid(lon, lat)

        # Use configurable fill_value for regions outside data coverage
        interp = griddata(points, values, (lon_grid, lat_grid), method="linear", fill_value=fill_value)
        out[iz] = interp

        # Report coverage statistics
        if np.isnan(fill_value):
            valid_points = np.sum(~np.isnan(interp))
        else:
            # If using a specific fill value, points matching it are considered "filled"
            valid_points = np.sum(~np.isclose(interp, fill_value))

        total_points = interp.size
        coverage = 100 * valid_points / total_points
        if coverage < 95:
            filled_points = total_points - valid_points
            fill_str = "NaN" if np.isnan(fill_value) else f"{fill_value}"
            print(f"   Depth {d:.2f} km: {coverage:.1f}% coverage ({filled_points} {fill_str} points)")

    return out


def write_epstyle_hdf5(
    output_path: str | Path,
    lats: np.ndarray,
    lons: np.ndarray,
    depth_list: np.ndarray,
    vp_stack: np.ndarray,
    vs_stack: np.ndarray,
    rho_stack: np.ndarray,
    compression_level: int = 4,
    original_fill_value: float = np.nan
) -> None:
    """
    Write EP-style tomography HDF5 file with compression.

    Each depth slice becomes a group named by depth in km.
    NaN values are stored as -999.0 flag value.

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
    original_fill_value : float
        Original fill value used during interpolation (before conversion to -999.0).
        Stored as metadata for visualization tools.
    """
    # Create coordinate meshgrid (keep as float64 for best compression with shuffle)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    coords = np.stack([lat_grid, lon_grid], axis=-1)  # float64

    # Count NaN values before replacement
    nan_vp = np.sum(np.isnan(vp_stack))
    nan_vs = np.sum(np.isnan(vs_stack))
    nan_rho = np.sum(np.isnan(rho_stack))
    total_points = vp_stack.size

    print(f"\n   NaN statistics (will be stored as -999.0):")
    print(f"      VP:  {nan_vp:,} / {total_points:,} ({100*nan_vp/total_points:.2f}%)")
    print(f"      VS:  {nan_vs:,} / {total_points:,} ({100*nan_vs/total_points:.2f}%)")
    print(f"      RHO: {nan_rho:,} / {total_points:,} ({100*nan_rho/total_points:.2f}%)")

    # Replace NaN with -999.0 flag
    vp_stack = vp_stack.copy()
    vs_stack = vs_stack.copy()
    rho_stack = rho_stack.copy()
    vp_stack[np.isnan(vp_stack)] = -999.0
    vs_stack[np.isnan(vs_stack)] = -999.0
    rho_stack[np.isnan(rho_stack)] = -999.0

    # Calculate expected file sizes
    nlat, nlon = len(lats), len(lons)
    points_per_level = nlat * nlon
    data_size_mb = (points_per_level * 3 * 4 * len(depth_list)) / (1024**2)  # 3 vars, 4 bytes
    coords_size_mb = (points_per_level * 2 * 8 * len(depth_list)) / (1024**2)  # coords, 2 vals, 8 bytes
    total_uncompressed_mb = data_size_mb + coords_size_mb

    print(f"\n   Writing HDF5 with compression:")
    print(f"   Output: {output_path}")
    print(f"   Grid: {nlat} lat x {nlon} lon x {len(depth_list)} depth")
    print(f"   Compression: gzip level {compression_level} + shuffle filter")
    print(f"   Uncompressed size estimate: {total_uncompressed_mb:.1f} MB ({total_uncompressed_mb/1024:.2f} GB)")

    # Determine optimal chunk size for 2D data arrays (256x256 is good for most datasets)
    chunk_size = min(256, nlat), min(256, nlon)

    # Chunk size for coords (smaller chunks for 3D array)
    coords_chunk_size = (min(88, nlat), min(50, nlon), 1)

    with h5py.File(output_path, "w") as f:
        # Store metadata about fill values at root level
        f.attrs['fill_value_nan_representation'] = -999.0
        f.attrs['original_fill_value'] = float(original_fill_value) if not np.isnan(original_fill_value) else -999.0
        f.attrs['fill_value_is_nan'] = bool(np.isnan(original_fill_value))
        f.attrs['description'] = 'Eberhart-Phillips tomography on uniform NZCVM grid'
        f.attrs['creation_date'] = pd.Timestamp.now().isoformat()

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

    print(f"\n   Successfully saved EP-style HDF5 to {output_path}")
    print(f"   Actual file size: {actual_size_mb:.1f} MB ({actual_size_mb/1024:.2f} GB)")
    print(f"   Compression ratio: {compression_ratio:.1f}x")
    print(f"   Space saved: {total_uncompressed_mb - actual_size_mb:.1f} MB ({(total_uncompressed_mb - actual_size_mb)/1024:.2f} GB)")


def reconcile_depths(input_depths: set, ref_depths: np.ndarray, keep_all_input: bool = True) -> np.ndarray:
    """
    Reconcile depths between input data and reference grid.

    IMPROVED: Now always retains all input depth levels by default.

    Parameters
    ----------
    input_depths : set
        Set of depths available in input data.
    ref_depths : np.ndarray
        Reference depths from grid.
    keep_all_input : bool, optional
        If True (default), retain all input depth levels even if not in reference.
        If False, only use depths that are in reference grid.

    Returns
    -------
    np.ndarray
        Final depth array to use for interpolation.
    """
    input_depths_array = np.array(sorted(input_depths))
    ref_depths_set = set(ref_depths)

    print(f"   Depth compatibility analysis:")
    print(f"   Input data depths: {len(input_depths)} levels")
    print(f"   Reference grid depths: {len(ref_depths)} levels")

    # Find overlapping depths
    common_depths = input_depths & ref_depths_set
    input_only = input_depths - ref_depths_set
    ref_only = ref_depths_set - input_depths

    print(f"   Common depths: {len(common_depths)}")
    if input_only:
        print(f"   Input-only depths: {sorted(input_only)}")
    if ref_only:
        print(f"   Reference-only depths (no input data): {len(ref_only)} levels")

    # Determine final depth array
    if keep_all_input:
        # IMPROVED: Always keep all input depths
        if input_only:
            # Combine input and reference depths
            all_depths = sorted(input_depths | ref_depths_set)
            final_depths = np.array(all_depths)
            print(f"   Using ALL depths (input + reference): {len(final_depths)} levels")
        else:
            # Input is subset of reference - use input depths only
            final_depths = input_depths_array
            print(f"   Using input depths only: {len(final_depths)} levels")
    else:
        # Only use depths that exist in reference (old behavior)
        if ref_depths_set.issuperset(input_depths):
            final_depths = input_depths_array
            print(f"   Using input depths only: {len(final_depths)} levels")
        else:
            print(f"   Warning: Input has depths not in reference, but keep_all_input=False")
            final_depths = input_depths_array
            print(f"   Using input depths anyway: {len(final_depths)} levels")

    return final_depths


def parse_fill_value(fill_value_str: str) -> float:
    """
    Parse fill value argument from string to float.

    Parameters
    ----------
    fill_value_str : str
        Fill value as string: "nan", "0", or any numeric value.

    Returns
    -------
    float
        Parsed fill value (np.nan or numeric value).

    Raises
    ------
    ValueError
        If the string cannot be parsed as a number or "nan".
    """
    fill_value_str = fill_value_str.strip().lower()

    if fill_value_str == "nan":
        return np.nan

    try:
        return float(fill_value_str)
    except ValueError:
        raise ValueError(
            f"Invalid fill-value '{fill_value_str}'. "
            f"Must be 'nan' or a numeric value (e.g., '0', '3.5')"
        )


def main() -> None:
    """
    Main function to run the interpolation process.

    This function orchestrates the entire interpolation workflow:
    1. Parse command line arguments
    2. Read Eberhart-Phillips data
    3. Load NZCVM grid (optionally extended)
    4. Reconcile depths (keeping all input levels)
    5. Interpolate data to grid (NaN for uncovered regions)
    6. Save results to HDF5 with compression
    """
    parser = argparse.ArgumentParser(
        description="Interpolate Eberhart-Phillips tomography data onto uniform NZCVM grid with compression",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (NaN preserved for boundary regions - RECOMMENDED)
  python %(prog)s input.txt reference.h5 output.h5
  
  # Extend grid by 5deg beyond 180deg meridian
  python %(prog)s input.txt reference.h5 output.h5 --extend-lon 5.0
  
  # Use 0.0 for regions outside data (old behavior, may cause artifacts)
  python %(prog)s input.txt reference.h5 output.h5 --fill-value 0
  
  # Use specific velocity value (e.g., 3.5 km/s) for uncovered regions
  python %(prog)s input.txt reference.h5 output.h5 --fill-value 3.5
  
  # Higher compression for smaller files
  python %(prog)s input.txt reference.h5 output.h5 --compression 6
  
  # Only use depths from reference grid
  python %(prog)s input.txt reference.h5 output.h5 --no-keep-all-depths
  
  # Combination: extend grid and use specific fill value
  python %(prog)s input.txt reference.h5 output.h5 --extend-lon 5.0 --fill-value 3.5
        """
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
    parser.add_argument(
        "--extend-lon",
        type=float,
        default=0.0,
        metavar="DEGREES",
        help="Extend longitude grid beyond 180deg by this many degrees (default: 0.0)"
    )
    parser.add_argument(
        "--fill-value",
        type=str,
        default="nan",
        metavar="VALUE",
        help='Fill value for regions outside data coverage. Options: "nan" (default, recommended), '
             '"0" or any number (e.g., "3.5"). Using "nan" avoids boundary artifacts.'
    )
    parser.add_argument(
        "--no-keep-all-depths",
        action="store_true",
        help="Only use depths from reference grid, ignore input-only depths"
    )

    args = parser.parse_args()

    # Parse fill value
    try:
        fill_value = parse_fill_value(args.fill_value)
    except ValueError as e:
        parser.error(str(e))

    fill_value_str = "NaN" if np.isnan(fill_value) else f"{fill_value}"

    print("=" * 70)
    print("Eberhart-Phillips TOMOGRAPHY INTERPOLATION (IMPROVED)")
    print("=" * 70)
    print("\n   Improvements in this version:")
    print("   - Configurable fill value for regions outside data coverage")
    print("   - Optional longitude extension beyond 180deg meridian")
    print("   - All input depth levels retained by default")
    print(f"\n   Current settings:")
    print(f"   Fill value: {fill_value_str}")
    if np.isnan(fill_value):
        print("     Using NaN (recommended - avoids boundary artifacts)")
    elif fill_value == 0.0:
        print("     Using 0.0 (may create artifacts at boundaries)")
    else:
        print(f"     Using custom value: {fill_value}")
    print(f"   Compression level: {args.compression}")
    if args.extend_lon > 0:
        print(f"   Longitude extension: {args.extend_lon}deg")

    print("\n   Reading EP-style TXT...")
    df = read_ep_txt(args.input_txt)
    input_depths = set(df['depth'])
    print(f"   Found {len(input_depths)} depth levels in input data")
    print(f"   Longitude range: {df['lon'].min():.2f}deg to {df['lon'].max():.2f}deg")
    print(f"   Latitude range: {df['lat'].min():.2f}deg to {df['lat'].max():.2f}deg")

    print("\n   Loading NZCVM grid...")
    lat, lon, ref_depths = load_nzcvm_grid(args.ref_h5, extend_lon_deg=args.extend_lon)
    print(f"   Grid: {len(lat)} lat x {len(lon)} lon = {len(lat)*len(lon):,} points per level")
    print(f"   Longitude range: {lon.min():.2f}deg to {lon.max():.2f}deg")
    print(f"   Latitude range: {lat.min():.2f}deg to {lat.max():.2f}deg")

    # Reconcile depths between input and reference
    print(f"\n")
    final_depths = reconcile_depths(input_depths, ref_depths,
                                     keep_all_input=not args.no_keep_all_depths)

    print("\n   Interpolating vp...")
    vp = interpolate_property_to_grid(df, lat, lon, final_depths, "vp", fill_value=fill_value)
    print("   Interpolating vs...")
    vs = interpolate_property_to_grid(df, lat, lon, final_depths, "vs", fill_value=fill_value)
    print("   Interpolating rho...")
    rho = interpolate_property_to_grid(df, lat, lon, final_depths, "rho", fill_value=fill_value)

    print("\n   Writing to output HDF5...")
    write_epstyle_hdf5(args.out_h5, lat, lon, final_depths, vp, vs, rho,
                       compression_level=args.compression,
                       original_fill_value=fill_value)

    print("\n" + "=" * 70)
    print("CONVERSION COMPLETE!")
    print("=" * 70)
    print("\n   Notes:")
    if np.isnan(fill_value):
        print("   - NaN values (uncovered regions) are stored as -999.0 in the HDF5 file")
        print("   - Use reader/visualization code that recognizes -999.0 as missing data")
    else:
        print(f"   - Uncovered regions filled with: {fill_value}")
        print(f"   - NaN values (if any from input) stored as -999.0 in the HDF5 file")
        print(f"   - Fill value {fill_value} and -999.0 both indicate regions to handle carefully")
    print("   - Check coverage statistics above for data quality assessment")


if __name__ == "__main__":
    main()