#!/usr/bin/env python3
"""
Convert CSV data to GeoJSON format.

This script reads a CSV file with flexible column structure and creates a GeoJSON file
containing point features and optionally a boundary polygon.

Features:
- Flexible CSV column specification (like tomo_map.py)
- Creates GeoJSON Point features for each data point
- Optionally creates boundary polygon (convex hull or bounding box)
- Can include additional CSV columns as GeoJSON properties
- Supports various CSV separators and formats

Usage:
    csv_to_geojson.py data.csv output.geojson \
        --lon-col 5 --lat-col 6 \
        [--property-cols 7 8 9] [--property-names vp vs rho] \
        [--boundary-type {convex_hull,bbox,none}] \
        [--skip-rows 2] [--sep ,]
"""

import argparse
from pathlib import Path
from typing import List, Optional

import geojson
import numpy as np
import pandas as pd
from shapely.geometry import MultiPoint, Point, mapping


def read_csv_with_columns(
    csv_path: str | Path,
    lon_col: int,
    lat_col: int,
    property_cols: Optional[List[int]] = None,
    property_names: Optional[List[str]] = None,
    skip_rows: int = 0,
    sep: str = r"\s+",
    depth_col: Optional[int] = None,
    depth_filter: Optional[float] = None,
    depth_tolerance: Optional[float] = None
) -> pd.DataFrame:
    """
    Read CSV file with specified column indices.

    Parameters
    ----------
    csv_path : str or Path
        Path to CSV file.
    lon_col : int
        Column index for longitude (0-based).
    lat_col : int
        Column index for latitude (0-based).
    property_cols : list of int, optional
        Column indices for additional properties to include.
    property_names : list of str, optional
        Names for the property columns.
    skip_rows : int
        Number of rows to skip at the start.
    sep : str
        Column separator (default: whitespace).
    depth_col : int, optional
        Column index for depth/elevation (for filtering).
    depth_filter : float, optional
        Depth value to filter on.
    depth_tolerance : float, optional
        Tolerance for depth filtering.

    Returns
    -------
    pd.DataFrame
        DataFrame with 'lon', 'lat', and optionally 'depth' and property columns.
    """
    print(f"📥 Reading CSV file: {csv_path}")
    print(f"   Skip rows: {skip_rows}")
    print(f"   Separator: '{sep}'")
    print(f"   Longitude column: {lon_col}")
    print(f"   Latitude column: {lat_col}")

    # Read CSV without headers
    df = pd.read_csv(
        csv_path,
        sep=sep,
        skiprows=skip_rows,
        header=None,
        engine='python'
    )

    print(f"   Total rows read: {len(df):,}")
    print(f"   Total columns: {len(df.columns)}")

    # Extract lon/lat
    if lon_col >= len(df.columns) or lat_col >= len(df.columns):
        raise ValueError(
            f"Column indices out of range. File has {len(df.columns)} columns, "
            f"but lon_col={lon_col}, lat_col={lat_col}"
        )

    result = pd.DataFrame({
        'lon': df.iloc[:, lon_col],
        'lat': df.iloc[:, lat_col]
    })

    # Extract depth if specified
    if depth_col is not None:
        if depth_col >= len(df.columns):
            raise ValueError(f"Depth column {depth_col} out of range")
        result['depth'] = df.iloc[:, depth_col]
        print(f"   Depth column: {depth_col}")
        print(f"   Depth range: {result['depth'].min():.2f} to {result['depth'].max():.2f}")

    # Filter by depth if requested
    if depth_filter is not None and depth_col is not None:
        tolerance = depth_tolerance if depth_tolerance is not None else 0.1
        mask = np.abs(result['depth'] - depth_filter) <= tolerance
        result = result[mask].copy()
        print(f"   Filtered to depth {depth_filter} ± {tolerance}: {len(result):,} points")

    # Extract additional properties
    if property_cols:
        if property_names and len(property_names) != len(property_cols):
            raise ValueError(
                f"Number of property names ({len(property_names)}) must match "
                f"number of property columns ({len(property_cols)})"
            )

        for i, col_idx in enumerate(property_cols):
            if col_idx >= len(df.columns):
                raise ValueError(f"Property column {col_idx} out of range")

            col_name = property_names[i] if property_names else f"prop_{i}"
            result[col_name] = df.iloc[:, col_idx]

        print(f"   Property columns: {property_cols}")
        if property_names:
            print(f"   Property names: {property_names}")

    print(f"   Longitude range: {result['lon'].min():.3f}° to {result['lon'].max():.3f}°")
    print(f"   Latitude range: {result['lat'].min():.3f}° to {result['lat'].max():.3f}°")

    return result


def create_boundary_polygon(points: np.ndarray, boundary_type: str):
    """
    Create boundary polygon from points.

    Parameters
    ----------
    points : np.ndarray
        Array of [lon, lat] coordinates.
    boundary_type : str
        Type of boundary: 'convex_hull', 'bbox', or 'none'.

    Returns
    -------
    shapely geometry or None
        Boundary polygon or None if boundary_type='none'.
    """
    if boundary_type == 'none':
        return None

    multipoint = MultiPoint(points)

    if boundary_type == 'convex_hull':
        return multipoint.convex_hull
    elif boundary_type == 'bbox':
        # Create bounding box
        return multipoint.envelope
    else:
        raise ValueError(f"Unknown boundary type: {boundary_type}")


def create_geojson(
    df: pd.DataFrame,
    boundary_type: str = 'convex_hull',
    include_points: bool = True,
    point_limit: Optional[int] = None,
    property_cols: Optional[List[str]] = None
) -> geojson.FeatureCollection:
    """
    Create GeoJSON FeatureCollection from DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'lon', 'lat', and optional property columns.
    boundary_type : str
        Type of boundary polygon: 'convex_hull', 'bbox', or 'none'.
    include_points : bool
        Whether to include individual point features.
    point_limit : int, optional
        Maximum number of points to include (for large datasets).
    property_cols : list of str, optional
        Column names to include as properties in point features.

    Returns
    -------
    geojson.FeatureCollection
        GeoJSON feature collection.
    """
    features = []

    # Add boundary polygon if requested
    if boundary_type != 'none':
        print(f"\n📐 Creating boundary polygon ({boundary_type})...")
        points = df[['lon', 'lat']].values
        boundary = create_boundary_polygon(points, boundary_type)

        if boundary:
            boundary_feature = geojson.Feature(
                geometry=mapping(boundary),
                properties={
                    'type': 'boundary',
                    'boundary_method': boundary_type,
                    'num_points': len(df)
                }
            )
            features.append(boundary_feature)
            print(f"   ✓ Boundary polygon created")

    # Add point features if requested
    if include_points:
        print(f"\n📍 Creating point features...")

        # Apply point limit if specified
        if point_limit and len(df) > point_limit:
            print(f"   ⚠️  Dataset has {len(df):,} points, limiting to {point_limit:,}")
            df_points = df.sample(n=point_limit, random_state=42)
        else:
            df_points = df

        # Determine which properties to include
        prop_columns = []
        if property_cols:
            prop_columns = [col for col in property_cols if col in df_points.columns]

        for idx, row in df_points.iterrows():
            point = Point((row['lon'], row['lat']))

            # Build properties dictionary
            properties = {}
            for col in prop_columns:
                val = row[col]
                # Convert numpy types to native Python types for JSON serialization
                if isinstance(val, (np.integer, np.floating)):
                    val = float(val)
                properties[col] = val

            # Add depth if present
            if 'depth' in row and pd.notna(row['depth']):
                properties['depth'] = float(row['depth'])

            feature = geojson.Feature(
                geometry=mapping(point),
                properties=properties if properties else None
            )
            features.append(feature)

        print(f"   ✓ Created {len(df_points):,} point features")

    return geojson.FeatureCollection(features)


def write_geojson(feature_collection: geojson.FeatureCollection, output_path: str | Path):
    """
    Write GeoJSON to file.

    Parameters
    ----------
    feature_collection : geojson.FeatureCollection
        GeoJSON feature collection.
    output_path : str or Path
        Output file path.
    """
    print(f"\n💾 Writing GeoJSON to: {output_path}")

    with open(output_path, 'w') as f:
        geojson.dump(feature_collection, f, indent=2)

    file_size = Path(output_path).stat().st_size / 1024
    print(f"   File size: {file_size:.1f} KB ({file_size/1024:.2f} MB)")
    print(f"   Total features: {len(feature_collection['features'])}")


def main():
    """
    Main function.
    """
    parser = argparse.ArgumentParser(
        description="Convert CSV data to GeoJSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic: create points and convex hull boundary
  python csv_to_geojson.py data.csv output.geojson --lon-col 5 --lat-col 6

  # With properties (e.g., vp, vs, rho)
  python csv_to_geojson.py data.csv output.geojson \\
      --lon-col 10 --lat-col 9 \\
      --property-cols 7 8 11 --property-names vp vs rho

  # Only boundary polygon (no points)
  python csv_to_geojson.py data.csv boundary.geojson \\
      --lon-col 5 --lat-col 6 --no-points

  # With depth filtering
  python csv_to_geojson.py data.csv output.geojson \\
      --lon-col 5 --lat-col 6 --depth-col 8 \\
      --depth-filter -85 --depth-tolerance 5

  # Bounding box instead of convex hull
  python csv_to_geojson.py data.csv output.geojson \\
      --lon-col 5 --lat-col 6 --boundary-type bbox

  # Large dataset: sample 10000 points
  python csv_to_geojson.py data.csv output.geojson \\
      --lon-col 5 --lat-col 6 --point-limit 10000

  # CSV with comma separator, skip 1 header row
  python csv_to_geojson.py data.csv output.geojson \\
      --lon-col 2 --lat-col 1 --sep ',' --skip-rows 1
        """
    )

    # Input/output
    parser.add_argument(
        'input_csv',
        type=Path,
        help='Input CSV file'
    )
    parser.add_argument(
        'output_geojson',
        type=Path,
        help='Output GeoJSON file'
    )

    # Required column specification
    parser.add_argument(
        '--lon-col',
        type=int,
        required=True,
        help='Column index for longitude (0-based)'
    )
    parser.add_argument(
        '--lat-col',
        type=int,
        required=True,
        help='Column index for latitude (0-based)'
    )

    # Optional columns
    parser.add_argument(
        '--depth-col',
        type=int,
        help='Column index for depth/elevation (optional)'
    )
    parser.add_argument(
        '--property-cols',
        type=int,
        nargs='+',
        help='Column indices for additional properties (space-separated)'
    )
    parser.add_argument(
        '--property-names',
        type=str,
        nargs='+',
        help='Names for property columns (must match number of --property-cols)'
    )

    # CSV reading options
    parser.add_argument(
        '--skip-rows',
        type=int,
        default=0,
        help='Number of rows to skip at start of file (default: 0)'
    )
    parser.add_argument(
        '--sep',
        type=str,
        default=r'\s+',
        help='Column separator (default: whitespace). Use "," for comma-separated'
    )

    # Depth filtering
    parser.add_argument(
        '--depth-filter',
        type=float,
        help='Filter points to specific depth value (requires --depth-col)'
    )
    parser.add_argument(
        '--depth-tolerance',
        type=float,
        default=0.1,
        help='Tolerance for depth filtering (default: 0.1)'
    )

    # GeoJSON options
    parser.add_argument(
        '--boundary-type',
        type=str,
        choices=['convex_hull', 'bbox', 'none'],
        default='convex_hull',
        help='Type of boundary polygon to create (default: convex_hull)'
    )
    parser.add_argument(
        '--no-points',
        action='store_true',
        help='Do not include individual point features (only boundary)'
    )
    parser.add_argument(
        '--point-limit',
        type=int,
        help='Maximum number of points to include (for large datasets)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.depth_filter is not None and args.depth_col is None:
        parser.error("--depth-filter requires --depth-col")

    if args.property_names and not args.property_cols:
        parser.error("--property-names requires --property-cols")

    print("="*70)
    print("CSV → GeoJSON CONVERTER")
    print("="*70)

    # Read CSV
    df = read_csv_with_columns(
        args.input_csv,
        lon_col=args.lon_col,
        lat_col=args.lat_col,
        property_cols=args.property_cols,
        property_names=args.property_names,
        skip_rows=args.skip_rows,
        sep=args.sep,
        depth_col=args.depth_col,
        depth_filter=args.depth_filter,
        depth_tolerance=args.depth_tolerance
    )

    # Create GeoJSON
    feature_collection = create_geojson(
        df,
        boundary_type=args.boundary_type,
        include_points=not args.no_points,
        point_limit=args.point_limit,
        property_cols=args.property_names if args.property_names else None
    )

    # Write output
    write_geojson(feature_collection, args.output_geojson)

    print("\n" + "="*70)
    print("✅ CONVERSION COMPLETE!")
    print("="*70)
    print(f"\n   Summary:")
    print(f"   Input:  {args.input_csv}")
    print(f"   Output: {args.output_geojson}")
    print(f"   Points: {len(df):,}")
    print(f"   Boundary: {args.boundary_type}")


if __name__ == '__main__':
    main()
