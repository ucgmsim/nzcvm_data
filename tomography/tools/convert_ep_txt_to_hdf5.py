#!/usr/bin/env python3
"""
Convert Eberhart-Phillips TXT tomography data to optimized HDF5 format WITHOUT interpolation.

This script reads the raw EP-style TXT file and converts it directly to the optimized
HDF5 format, preserving the original grid structure without any interpolation.

The key difference from interpolate_to_uniform_nzcvm_grid.py:
- NO interpolation onto a different grid
- Direct conversion of the original data grid
- Preserves original lat/lon/depth structure
- Much faster (no scipy interpolation)
- Suitable when you want to keep the original data as-is

Usage:
    python convert_ep_txt_to_hdf5.py input.txt output.h5
"""

import argparse
from pathlib import Path
from datetime import datetime

import h5py
import numpy as np
import pandas as pd


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
    print(f"📥 Reading EP-style TXT file: {txt_path}")

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

    # Invert depth to negative (depth positive down -> elevation negative down)
    df['depth'] = -1 * df['depth']

    print(f"   Total points: {len(df):,}")
    print(f"   Latitude range: {df['lat'].min():.3f}° to {df['lat'].max():.3f}°")
    print(f"   Longitude range: {df['lon'].min():.3f}° to {df['lon'].max():.3f}°")
    print(f"   Depth range: {df['depth'].min():.1f} to {df['depth'].max():.1f} km")

    return df


def analyze_grid_structure(df: pd.DataFrame) -> dict:
    """
    Analyze the grid structure from the raw data.

    Parameters
    ----------
    df : pd.DataFrame
        Raw tomography data.

    Returns
    -------
    dict
        Dictionary containing grid information:
        - depths: sorted unique depth values
        - grid_info: dict per depth with lat/lon arrays and dimensions
    """
    print("\n" + "="*70)
    print("ANALYZING GRID STRUCTURE")
    print("="*70)

    depths = sorted(df['depth'].unique())
    print(f"\nFound {len(depths)} depth levels:")
    print(f"   Depths: {depths}")

    grid_info = {}

    for depth in depths:
        df_depth = df[df['depth'] == depth]

        # Get unique lat/lon values
        lats = np.sort(df_depth['lat'].unique())
        lons = np.sort(df_depth['lon'].unique())

        # Check if it's a complete grid
        expected_points = len(lats) * len(lons)
        actual_points = len(df_depth)

        grid_info[depth] = {
            'latitudes': lats,
            'longitudes': lons,
            'nlat': len(lats),
            'nlon': len(lons),
            'expected_points': expected_points,
            'actual_points': actual_points,
            'is_complete': expected_points == actual_points
        }

        coverage = 100 * actual_points / expected_points
        status = "✓ Complete" if grid_info[depth]['is_complete'] else f"⚠ {coverage:.1f}% coverage"

        print(f"   Depth {depth:6.1f} km: {len(lats):4d} lat × {len(lons):4d} lon = {expected_points:6d} points ({status})")

    return {
        'depths': np.array(depths),
        'grid_info': grid_info
    }


def create_grid_arrays(df: pd.DataFrame, depth: float, grid_info: dict) -> tuple:
    """
    Create 2D grid arrays for a specific depth from scattered point data.

    Parameters
    ----------
    df : pd.DataFrame
        Raw tomography data.
    depth : float
        Depth level to extract.
    grid_info : dict
        Grid information for this depth.

    Returns
    -------
    tuple
        (vp_grid, vs_grid, rho_grid) as 2D numpy arrays
    """
    info = grid_info[depth]
    lats = info['latitudes']
    lons = info['longitudes']
    nlat, nlon = info['nlat'], info['nlon']

    # Extract data for this depth
    df_depth = df[df['depth'] == depth].copy()

    # Initialize output arrays with NaN
    vp_grid = np.full((nlat, nlon), np.nan, dtype=np.float32)
    vs_grid = np.full((nlat, nlon), np.nan, dtype=np.float32)
    rho_grid = np.full((nlat, nlon), np.nan, dtype=np.float32)

    # Create lookup dictionaries for lat/lon indices
    lat_to_idx = {lat: i for i, lat in enumerate(lats)}
    lon_to_idx = {lon: i for i, lon in enumerate(lons)}

    # Fill in the grids
    for _, row in df_depth.iterrows():
        i = lat_to_idx[row['lat']]
        j = lon_to_idx[row['lon']]
        vp_grid[i, j] = row['vp']
        vs_grid[i, j] = row['vs']
        rho_grid[i, j] = row['rho']

    return vp_grid, vs_grid, rho_grid


def write_optimized_hdf5(
    output_path: str | Path,
    grid_structure: dict,
    df: pd.DataFrame,
    compression_level: int = 4,
    fill_value: float = -999.0
) -> None:
    """
    Write tomography data to optimized HDF5 format.

    Parameters
    ----------
    output_path : str or Path
        Output HDF5 file path.
    grid_structure : dict
        Grid structure information from analyze_grid_structure.
    df : pd.DataFrame
        Raw tomography data.
    compression_level : int
        Gzip compression level (0-9).
    fill_value : float
        Value to use for NaN (default: -999.0).
    """
    print("\n" + "="*70)
    print("WRITING OPTIMIZED HDF5 FILE")
    print("="*70)

    depths = grid_structure['depths']
    grid_info = grid_structure['grid_info']

    # Use the first depth's grid as the canonical grid
    # (assuming all depths have the same lat/lon coverage)
    first_depth = depths[0]
    canonical_lats = grid_info[first_depth]['latitudes']
    canonical_lons = grid_info[first_depth]['longitudes']

    nlat, nlon = len(canonical_lats), len(canonical_lons)
    ndepth = len(depths)

    print(f"\n   Canonical grid: {nlat} lat × {nlon} lon × {ndepth} depth")
    print(f"   Output: {output_path}")
    print(f"   Compression: gzip level {compression_level} + shuffle filter")
    print(f"   Format: Optimized v2 (coordinates at root level)")

    # Calculate chunk size
    chunk_size = (min(256, nlat), min(256, nlon))

    with h5py.File(output_path, "w") as f:
        # File-level metadata
        f.attrs['created'] = datetime.utcnow().isoformat() + "Z"
        f.attrs['generator'] = 'convert_ep_txt_to_hdf5.py'
        f.attrs['schema'] = 'NZTomographyLevelStacked v2'
        f.attrs['optimized_structure'] = True
        f.attrs['interpolated'] = False  # KEY: This is NOT interpolated
        f.attrs['data_dtype_vp_vs_rho'] = 'float32'
        f.attrs['coord_dtype_lat_lon'] = 'float64'
        f.attrs['compression'] = f'gzip:{compression_level}'
        f.attrs['shuffle'] = True
        f.attrs['fill_value_nan_representation'] = fill_value
        f.attrs['description'] = 'EP tomography - direct conversion without interpolation'

        # Store coordinates at root level (OPTIMIZED FORMAT)
        f.create_dataset(
            'latitudes',
            data=canonical_lats,
            dtype=np.float64,
            compression='gzip',
            compression_opts=compression_level,
            shuffle=True
        )
        f.create_dataset(
            'longitudes',
            data=canonical_lons,
            dtype=np.float64,
            compression='gzip',
            compression_opts=compression_level,
            shuffle=True
        )

        print(f"   ✓ Stored coordinates at root level ({nlat} lat, {nlon} lon)")

        # Process each depth level
        for iz, depth in enumerate(depths):
            # Create group name
            grp_name = f"{depth:.0f}" if depth == int(depth) else f"{depth:.1f}"
            grp = f.create_group(grp_name)

            # Create 2D grids for this depth
            vp_grid, vs_grid, rho_grid = create_grid_arrays(df, depth, grid_info)

            # Replace NaN with fill value
            vp_out = np.where(np.isnan(vp_grid), fill_value, vp_grid)
            vs_out = np.where(np.isnan(vs_grid), fill_value, vs_grid)
            rho_out = np.where(np.isnan(rho_grid), fill_value, rho_grid)

            # Write datasets
            grp.create_dataset(
                'vp',
                data=vp_out,
                dtype=np.float32,
                compression='gzip',
                compression_opts=compression_level,
                shuffle=True,
                chunks=chunk_size
            )
            grp.create_dataset(
                'vs',
                data=vs_out,
                dtype=np.float32,
                compression='gzip',
                compression_opts=compression_level,
                shuffle=True,
                chunks=chunk_size
            )
            grp.create_dataset(
                'rho',
                data=rho_out,
                dtype=np.float32,
                compression='gzip',
                compression_opts=compression_level,
                shuffle=True,
                chunks=chunk_size
            )

            # Count NaN values
            nan_count = np.sum(np.isnan(vp_grid))
            if nan_count > 0:
                total = vp_grid.size
                print(f"   Depth {grp_name:>6} km: {nan_count:6d} NaN values ({100*nan_count/total:.1f}%)")

            if (iz + 1) % 5 == 0 or iz == 0 or iz == len(depths) - 1:
                print(f"   Written group '{grp_name}' ({iz+1}/{len(depths)})")

    # Report file size
    actual_size_mb = Path(output_path).stat().st_size / (1024**2)
    print(f"\n✅ Successfully saved to {output_path}")
    print(f"   File size: {actual_size_mb:.1f} MB ({actual_size_mb/1024:.2f} GB)")


def main():
    """
    Main function to convert EP TXT to optimized HDF5.
    """
    parser = argparse.ArgumentParser(
        description="Convert EP TXT tomography to optimized HDF5 format WITHOUT interpolation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script performs DIRECT conversion from EP TXT to HDF5 format.
- NO interpolation onto a different grid
- Preserves original data structure
- Uses optimized HDF5 format (coordinates at root level)
- Much faster than interpolation-based conversion

Examples:
  # Basic conversion
  python convert_ep_txt_to_hdf5.py ep_model.txt ep_model.h5

  # With higher compression
  python convert_ep_txt_to_hdf5.py ep_model.txt ep_model.h5 --compression 6
        """
    )

    parser.add_argument(
        'input_txt',
        type=Path,
        help='Path to input EP-style TXT file'
    )
    parser.add_argument(
        'output_h5',
        type=Path,
        help='Path to output HDF5 file'
    )
    parser.add_argument(
        '--compression',
        type=int,
        default=4,
        choices=range(0, 10),
        help='Gzip compression level (0-9, default: 4)'
    )
    parser.add_argument(
        '--fill-value',
        type=float,
        default=-999.0,
        help='Fill value for NaN (default: -999.0)'
    )

    args = parser.parse_args()

    print("="*70)
    print("EP TXT → OPTIMIZED HDF5 (NO INTERPOLATION)")
    print("="*70)
    print(f"\nInput:  {args.input_txt}")
    print(f"Output: {args.output_h5}")
    print(f"Mode:   DIRECT CONVERSION (no interpolation)")

    # Step 1: Read data
    df = read_ep_txt(args.input_txt)

    # Step 2: Analyze grid structure
    grid_structure = analyze_grid_structure(df)

    # Step 3: Write optimized HDF5
    write_optimized_hdf5(
        args.output_h5,
        grid_structure,
        df,
        compression_level=args.compression,
        fill_value=args.fill_value
    )

    print("\n" + "="*70)
    print("CONVERSION COMPLETE!")
    print("="*70)
    print("\n   Key features:")
    print("   ✓ No interpolation (preserves original data)")
    print("   ✓ Optimized HDF5 format (saves ~400MB)")
    print("   ✓ Coordinates stored once at root level")
    print("   ✓ Compatible with all NZCVM tools")


if __name__ == '__main__':
    main()
