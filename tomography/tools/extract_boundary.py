#!/usr/bin/env python3
"""
Unified boundary extraction tool for tomography data.

Automatically detects input format (HDF5 or CSV/TXT) and extracts boundary polygon
to GeoJSON format.

This is a convenience wrapper that:
- Auto-detects file format
- Uses appropriate extraction method
- Provides simplified interface

For HDF5: Reads from optimized or legacy format
For CSV/TXT: Requires column specification

Usage:
    # HDF5 file (automatic)
    extract_boundary.py model.h5 boundary.geojson

    # CSV/TXT file (specify columns)
    extract_boundary.py data.txt boundary.geojson --lon-col 10 --lat-col 9

    # With depth filtering
    extract_boundary.py data.txt boundary.geojson \
        --lon-col 10 --lat-col 9 --depth-col 8 --depth-filter -85
"""

import argparse
import sys
from pathlib import Path

import geojson
import h5py
import numpy as np
import pandas as pd
from shapely.geometry import MultiPoint, mapping


def detect_file_type(file_path: Path) -> str:
    """
    Detect if file is HDF5 or CSV/TXT.

    Parameters
    ----------
    file_path : Path
        Path to input file.

    Returns
    -------
    str
        'hdf5' or 'csv'
    """
    # Check extension first
    if file_path.suffix.lower() in ['.h5', '.hdf5']:
        return 'hdf5'

    # Try to open as HDF5
    try:
        with h5py.File(file_path, 'r'):
            return 'hdf5'
    except (OSError, IOError):
        return 'csv'


def extract_boundary_from_hdf5(h5_path: Path) -> np.ndarray:
    """
    Extract boundary points from HDF5 file.

    Supports both optimized (coordinates at root) and legacy formats.

    Parameters
    ----------
    h5_path : Path
        Path to HDF5 file.

    Returns
    -------
    np.ndarray
        Array of [lon, lat] edge points.
    """
    print(f"📥 Reading HDF5 file: {h5_path}")

    with h5py.File(h5_path, 'r') as f:
        # Try optimized format first (coordinates at root)
        if 'latitudes' in f and 'longitudes' in f:
            lats = f['latitudes'][:]
            lons = f['longitudes'][:]
            print("   ✓ Using optimized format (coordinates at root)")
        else:
            # Legacy format (coordinates in first group)
            groups = [k for k in f.keys() if isinstance(f[k], h5py.Group)]
            if not groups:
                raise ValueError("No groups found in HDF5 file")

            first_group = groups[0]
            lats = f[first_group]['latitudes'][:]
            lons = f[first_group]['longitudes'][:]
            print(f"   ✓ Using legacy format (coordinates in {first_group})")

    print(f"   Grid: {len(lats)} lat × {len(lons)} lon")
    print(f"   Latitude range: {lats.min():.3f}° to {lats.max():.3f}°")
    print(f"   Longitude range: {lons.min():.3f}° to {lons.max():.3f}°")

    # Create edge points only (not all grid points)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    edge_coords = []

    # Top and bottom rows
    edge_coords += list(zip(lon_grid[0, :], lat_grid[0, :]))
    edge_coords += list(zip(lon_grid[-1, :], lat_grid[-1, :]))

    # Left and right columns (excluding corners to avoid duplicates)
    edge_coords += list(zip(lon_grid[1:-1, 0], lat_grid[1:-1, 0]))
    edge_coords += list(zip(lon_grid[1:-1, -1], lat_grid[1:-1, -1]))

    print(f"   Extracted {len(edge_coords)} edge points")

    return np.array(edge_coords)


def extract_boundary_from_csv(
    csv_path: Path,
    lon_col: int,
    lat_col: int,
    skip_rows: int = 0,
    sep: str = r'\s+',
    depth_col: int = None,
    depth_filter: float = None,
    depth_tolerance: float = 0.1
) -> np.ndarray:
    """
    Extract boundary points from CSV/TXT file.

    Parameters
    ----------
    csv_path : Path
        Path to CSV file.
    lon_col : int
        Column index for longitude.
    lat_col : int
        Column index for latitude.
    skip_rows : int
        Number of rows to skip.
    sep : str
        Column separator.
    depth_col : int, optional
        Column index for depth (for filtering).
    depth_filter : float, optional
        Depth value to filter on.
    depth_tolerance : float
        Tolerance for depth filtering.

    Returns
    -------
    np.ndarray
        Array of [lon, lat] points.
    """
    print(f"📥 Reading CSV file: {csv_path}")
    print(f"   Columns: lon={lon_col}, lat={lat_col}")
    if depth_col is not None:
        print(f"   Depth column: {depth_col}")

    # Read CSV
    df = pd.read_csv(csv_path, sep=sep, skiprows=skip_rows, header=None, engine='python')

    # Validate columns
    if lon_col >= len(df.columns) or lat_col >= len(df.columns):
        raise ValueError(f"Column index out of range (file has {len(df.columns)} columns)")

    # Extract coordinates
    points = df.iloc[:, [lon_col, lat_col]].values

    # Filter by depth if specified
    if depth_filter is not None and depth_col is not None:
        if depth_col >= len(df.columns):
            raise ValueError(f"Depth column {depth_col} out of range")

        depths = df.iloc[:, depth_col].values
        mask = np.abs(depths - depth_filter) <= depth_tolerance
        points = points[mask]
        print(f"   Filtered to depth {depth_filter} ± {depth_tolerance}: {len(points)} points")

    print(f"   Total points: {len(points):,}")
    print(f"   Longitude range: {points[:, 0].min():.3f}° to {points[:, 0].max():.3f}°")
    print(f"   Latitude range: {points[:, 1].min():.3f}° to {points[:, 1].max():.3f}°")

    return points


def create_boundary_geojson(points: np.ndarray, boundary_type: str = 'convex_hull') -> dict:
    """
    Create GeoJSON boundary from points.

    Parameters
    ----------
    points : np.ndarray
        Array of [lon, lat] coordinates.
    boundary_type : str
        'convex_hull' or 'bbox'.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    print(f"\n📐 Creating {boundary_type} boundary...")

    multipoint = MultiPoint(points)

    if boundary_type == 'convex_hull':
        boundary = multipoint.convex_hull
    elif boundary_type == 'bbox':
        boundary = multipoint.envelope
    else:
        raise ValueError(f"Unknown boundary type: {boundary_type}")

    feature = geojson.Feature(
        geometry=mapping(boundary),
        properties={
            'type': 'boundary',
            'boundary_method': boundary_type,
            'num_points': len(points),
            'lon_min': float(points[:, 0].min()),
            'lon_max': float(points[:, 0].max()),
            'lat_min': float(points[:, 1].min()),
            'lat_max': float(points[:, 1].max())
        }
    )

    print(f"   ✓ Boundary created from {len(points):,} points")

    return geojson.FeatureCollection([feature])


def main():
    """
    Main function.
    """
    parser = argparse.ArgumentParser(
        description="Extract boundary polygon from tomography data (HDF5 or CSV/TXT)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # HDF5 file (automatic detection)
  python extract_boundary.py model.h5 boundary.geojson

  # CSV/TXT file (requires column specification)
  python extract_boundary.py data.txt boundary.geojson --lon-col 10 --lat-col 9

  # With depth filtering
  python extract_boundary.py data.txt boundary.geojson \\
      --lon-col 10 --lat-col 9 --depth-col 8 --depth-filter -85

  # Bounding box instead of convex hull
  python extract_boundary.py model.h5 bbox.geojson --boundary-type bbox

  # EP-style TXT file
  python extract_boundary.py ep2020.txt boundary.geojson \\
      --skip-rows 2 --lon-col 10 --lat-col 9

  # Hikurangi TXT file
  python extract_boundary.py hikurangi.txt boundary.geojson \\
      --skip-rows 2 --lon-col 5 --lat-col 6
        """
    )

    parser.add_argument(
        'input_file',
        type=Path,
        help='Input file (HDF5 or CSV/TXT)'
    )
    parser.add_argument(
        'output_geojson',
        type=Path,
        help='Output GeoJSON file'
    )

    # CSV-specific options
    parser.add_argument(
        '--lon-col',
        type=int,
        help='Longitude column index (required for CSV/TXT)'
    )
    parser.add_argument(
        '--lat-col',
        type=int,
        help='Latitude column index (required for CSV/TXT)'
    )
    parser.add_argument(
        '--depth-col',
        type=int,
        help='Depth column index (optional, for filtering)'
    )
    parser.add_argument(
        '--depth-filter',
        type=float,
        help='Extract boundary for specific depth'
    )
    parser.add_argument(
        '--depth-tolerance',
        type=float,
        default=0.1,
        help='Tolerance for depth filtering (default: 0.1)'
    )
    parser.add_argument(
        '--skip-rows',
        type=int,
        default=0,
        help='Number of rows to skip (CSV/TXT only)'
    )
    parser.add_argument(
        '--sep',
        type=str,
        default=r'\s+',
        help='Column separator (CSV/TXT only, default: whitespace)'
    )

    # General options
    parser.add_argument(
        '--boundary-type',
        type=str,
        choices=['convex_hull', 'bbox'],
        default='convex_hull',
        help='Type of boundary polygon (default: convex_hull)'
    )

    args = parser.parse_args()

    # Detect file type
    file_type = detect_file_type(args.input_file)

    print("="*70)
    print("BOUNDARY EXTRACTION")
    print("="*70)
    print(f"\nInput:  {args.input_file}")
    print(f"Output: {args.output_geojson}")
    print(f"Format: {file_type.upper()}")
    print(f"Boundary type: {args.boundary_type}")

    # Extract boundary points
    if file_type == 'hdf5':
        points = extract_boundary_from_hdf5(args.input_file)
    else:  # CSV
        if args.lon_col is None or args.lat_col is None:
            print("\n❌ ERROR: CSV/TXT files require --lon-col and --lat-col", file=sys.stderr)
            sys.exit(1)

        points = extract_boundary_from_csv(
            args.input_file,
            lon_col=args.lon_col,
            lat_col=args.lat_col,
            skip_rows=args.skip_rows,
            sep=args.sep,
            depth_col=args.depth_col,
            depth_filter=args.depth_filter,
            depth_tolerance=args.depth_tolerance
        )

    # Create GeoJSON
    feature_collection = create_boundary_geojson(points, args.boundary_type)

    # Write output
    print(f"\n💾 Writing GeoJSON to: {args.output_geojson}")
    with open(args.output_geojson, 'w') as f:
        geojson.dump(feature_collection, f, indent=2)

    file_size = args.output_geojson.stat().st_size / 1024
    print(f"   File size: {file_size:.1f} KB")

    print("\n" + "="*70)
    print("✅ EXTRACTION COMPLETE!")
    print("="*70)
    print(f"\n   Summary:")
    print(f"   Input:  {args.input_file} ({file_type.upper()})")
    print(f"   Output: {args.output_geojson}")
    print(f"   Method: {args.boundary_type}")
    print(f"   Points: {len(points):,}")


if __name__ == '__main__':
    main()
