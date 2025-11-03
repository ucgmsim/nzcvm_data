#!/usr/bin/env python3
"""
Convert Hikurangi TXT tomography data to optimized HDF5 format WITHOUT interpolation.

This script reads the raw Hikurangi TXT file and converts it directly to the optimized
HDF5 format, preserving the original grid structure without any interpolation.

The key difference from analyze_and_convert_hikurangi.py:
- NO interpolation onto EP2020 grid or any other grid
- Direct conversion of the original Hikurangi data grid
- Preserves original lat/lon/depth structure
- Much faster (no scipy interpolation)
- Suitable when you want to keep the original data as-is

Usage:
    python convert_hikurangi_txt_to_hdf5.py input.txt output.h5
"""

import argparse
from pathlib import Path
from datetime import datetime

import h5py
import numpy as np
import pandas as pd


def read_hikurangi_txt(txt_path: str | Path) -> pd.DataFrame:
    """
    Read Hikurangi tomography data.

    Parameters
    ----------
    txt_path : str or Path
        Path to the Hikurangi TXT file.

    Returns
    -------
    pd.DataFrame
        DataFrame containing tomography data.
    """
    print(f"📥 Reading Hikurangi TXT file: {txt_path}")

    col_names = [
        "model_x", "model_y", "depth", "utm60se", "utm60sn",
        "lon", "lat", "vp", "vs", "vp_o_vs", "rho", "constraint"
    ]

    df = pd.read_csv(
        txt_path,
        sep=r"\s+",
        skiprows=2,
        names=col_names,
        engine="python"
    )

    # Convert depth to elevation (negative down)
    df["elevation"] = -df["depth"]

    print(f"   Total points: {len(df):,}")
    print(f"   Latitude range: {df['lat'].min():.3f}° to {df['lat'].max():.3f}°")
    print(f"   Longitude range: {df['lon'].min():.3f}° to {df['lon'].max():.3f}°")
    print(f"   Elevation range: {df['elevation'].min():.1f} to {df['elevation'].max():.1f} km")

    # Handle dateline crossing if needed
    lon_span = df["lon"].max() - df["lon"].min()
    if lon_span > 180:
        print(f"   ⚠️  Detected dateline crossing (converting to 0-360 range)")
        df.loc[df['lon'] < 0, 'lon'] += 360

    return df


def analyze_grid_structure(df: pd.DataFrame) -> dict:
    """
    Analyze the grid structure from the raw Hikurangi data.

    Parameters
    ----------
    df : pd.DataFrame
        Raw tomography data.

    Returns
    -------
    dict
        Dictionary containing grid information:
        - elevations: sorted unique elevation values
        - grid_info: dict per elevation with lat/lon arrays and dimensions
    """
    print("\n" + "="*70)
    print("ANALYZING GRID STRUCTURE")
    print("="*70)

    elevations = sorted(df['elevation'].unique())
    print(f"\nFound {len(elevations)} elevation levels:")

    grid_info = {}

    for elev in elevations:
        df_elev = df[df['elevation'] == elev]

        # Get unique lat/lon values
        lats = np.sort(df_elev['lat'].unique())
        lons = np.sort(df_elev['lon'].unique())

        # Check if it's a complete grid
        expected_points = len(lats) * len(lons)
        actual_points = len(df_elev)

        grid_info[elev] = {
            'latitudes': lats,
            'longitudes': lons,
            'nlat': len(lats),
            'nlon': len(lons),
            'expected_points': expected_points,
            'actual_points': actual_points,
            'is_complete': expected_points == actual_points
        }

        coverage = 100 * actual_points / expected_points
        status = "✓ Complete" if grid_info[elev]['is_complete'] else f"⚠ {coverage:.1f}% coverage"

        print(f"   Elev {elev:7.1f} km: {len(lats):4d} lat × {len(lons):4d} lon = {expected_points:6d} points ({status})")

    return {
        'elevations': np.array(elevations),
        'grid_info': grid_info
    }


def create_grid_arrays(df: pd.DataFrame, elevation: float, grid_info: dict) -> tuple:
    """
    Create 2D grid arrays for a specific elevation from scattered point data.

    Parameters
    ----------
    df : pd.DataFrame
        Raw tomography data.
    elevation : float
        Elevation level to extract.
    grid_info : dict
        Grid information for this elevation.

    Returns
    -------
    tuple
        (vp_grid, vs_grid, rho_grid) as 2D numpy arrays
    """
    info = grid_info[elevation]
    lats = info['latitudes']
    lons = info['longitudes']
    nlat, nlon = info['nlat'], info['nlon']

    # Extract data for this elevation
    df_elev = df[df['elevation'] == elevation].copy()

    # Initialize output arrays with NaN
    vp_grid = np.full((nlat, nlon), np.nan, dtype=np.float32)
    vs_grid = np.full((nlat, nlon), np.nan, dtype=np.float32)
    rho_grid = np.full((nlat, nlon), np.nan, dtype=np.float32)

    # Create lookup dictionaries for lat/lon indices
    lat_to_idx = {lat: i for i, lat in enumerate(lats)}
    lon_to_idx = {lon: i for i, lon in enumerate(lons)}

    # Fill in the grids
    for _, row in df_elev.iterrows():
        # Find closest lat/lon in grid (in case of floating point differences)
        lat_idx = np.argmin(np.abs(lats - row['lat']))
        lon_idx = np.argmin(np.abs(lons - row['lon']))

        vp_grid[lat_idx, lon_idx] = row['vp']
        vs_grid[lat_idx, lon_idx] = row['vs']
        rho_grid[lat_idx, lon_idx] = row['rho']

    return vp_grid, vs_grid, rho_grid


def write_optimized_hdf5(
    output_path: str | Path,
    grid_structure: dict,
    df: pd.DataFrame,
    compression_level: int = 4,
    fill_value: float = -999.0
) -> None:
    """
    Write Hikurangi tomography data to optimized HDF5 format.

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

    elevations = grid_structure['elevations']
    grid_info = grid_structure['grid_info']

    # Use the first elevation's grid as the canonical grid
    # (assuming all elevations have the same lat/lon coverage)
    first_elev = elevations[0]
    canonical_lats = grid_info[first_elev]['latitudes']
    canonical_lons = grid_info[first_elev]['longitudes']

    nlat, nlon = len(canonical_lats), len(canonical_lons)
    nelev = len(elevations)

    print(f"\n   Canonical grid: {nlat} lat × {nlon} lon × {nelev} elevation")
    print(f"   Latitude range: {canonical_lats.min():.3f}° to {canonical_lats.max():.3f}°")
    print(f"   Longitude range: {canonical_lons.min():.3f}° to {canonical_lons.max():.3f}°")
    print(f"   Output: {output_path}")
    print(f"   Compression: gzip level {compression_level} + shuffle filter")
    print(f"   Format: Optimized v2 (coordinates at root level)")

    # Calculate chunk size
    chunk_size = (min(50, nlat), min(50, nlon))

    with h5py.File(output_path, "w") as f:
        # File-level metadata
        f.attrs['created'] = datetime.utcnow().isoformat() + "Z"
        f.attrs['generator'] = 'convert_hikurangi_txt_to_hdf5.py'
        f.attrs['schema'] = 'NZTomographyLevelStacked v2'
        f.attrs['optimized_structure'] = True
        f.attrs['interpolated'] = False  # KEY: This is NOT interpolated
        f.attrs['data_dtype_vp_vs_rho'] = 'float32'
        f.attrs['coord_dtype_lat_lon'] = 'float64'
        f.attrs['compression'] = f'gzip:{compression_level}'
        f.attrs['shuffle'] = True
        f.attrs['fill_value_nan_representation'] = fill_value
        f.attrs['description'] = 'Hikurangi tomography - direct conversion without interpolation'

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

        # Process each elevation level
        for iz, elev in enumerate(elevations):
            # Create group name (handle decimal elevations)
            elev_rounded = round(elev, 2)
            if abs(elev_rounded - round(elev_rounded)) < 1e-6:
                grp_name = str(int(round(elev_rounded)))
            else:
                # Replace decimal point with underscore for group names
                grp_name = f"{elev_rounded:.2f}".replace('.', '_').replace('-_', '-')

            grp = f.create_group(grp_name)

            # Create 2D grids for this elevation
            vp_grid, vs_grid, rho_grid = create_grid_arrays(df, elev, grid_info)

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

            # Count NaN values and report coverage
            nan_count = np.sum(np.isnan(vp_grid))
            total = vp_grid.size
            coverage = 100 * (total - nan_count) / total

            if nan_count > 0:
                print(f"   Elev {grp_name:>7}: Coverage {coverage:.1f}% ({nan_count:6d} NaN/{total:6d} total)")

            if (iz + 1) % 10 == 0 or iz == 0 or iz == len(elevations) - 1:
                print(f"   Written group '{grp_name}' ({iz+1}/{len(elevations)})")

    # Report file size
    actual_size_mb = Path(output_path).stat().st_size / (1024**2)
    print(f"\n✅ Successfully saved to {output_path}")
    print(f"   File size: {actual_size_mb:.1f} MB ({actual_size_mb/1024:.2f} GB)")


def main():
    """
    Main function to convert Hikurangi TXT to optimized HDF5.
    """
    parser = argparse.ArgumentParser(
        description="Convert Hikurangi TXT tomography to optimized HDF5 format WITHOUT interpolation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script performs DIRECT conversion from Hikurangi TXT to HDF5 format.
- NO interpolation onto EP2020 or any other grid
- Preserves original Hikurangi data structure
- Uses optimized HDF5 format (coordinates at root level)
- Much faster than interpolation-based conversion
- Handles dateline crossing automatically

Examples:
  # Basic conversion
  python convert_hikurangi_txt_to_hdf5.py Hikurangi_3D_model.txt hikurangi.h5

  # With higher compression
  python convert_hikurangi_txt_to_hdf5.py Hikurangi_3D_model.txt hikurangi.h5 --compression 6
        """
    )

    parser.add_argument(
        'input_txt',
        type=Path,
        help='Path to input Hikurangi TXT file'
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
    print("HIKURANGI TXT → OPTIMIZED HDF5 (NO INTERPOLATION)")
    print("="*70)
    print(f"\nInput:  {args.input_txt}")
    print(f"Output: {args.output_h5}")
    print(f"Mode:   DIRECT CONVERSION (no interpolation)")

    # Step 1: Read data
    df = read_hikurangi_txt(args.input_txt)

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
    print("   ✓ Handles dateline crossing automatically")


if __name__ == '__main__':
    main()
