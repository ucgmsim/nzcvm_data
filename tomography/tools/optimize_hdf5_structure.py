#!/usr/bin/env python3
"""
Optimize HDF5 tomography file structure by storing coordinates once at root level.

This script converts the old format where coordinates are duplicated in each depth
group to a new format where coordinates are stored once at the root level.

Old format:
    /depth_group/latitudes, longitudes, coords, vp, vs, rho

New format:
    /latitudes, longitudes  (stored once)
    /depth_group/vp, vs, rho

This saves ~400+ MB per file by eliminating redundant coordinate data.
"""

import argparse
import h5py
import numpy as np
from pathlib import Path
import sys
from datetime import datetime


def optimize_hdf5_structure(
    input_file: Path,
    output_file: Path,
    remove_coords: bool = True,
    gzip_level: int = 4,
    shuffle: bool = True,
    verbose: bool = True
) -> None:
    """
    Convert HDF5 tomography file to optimized structure.

    Parameters
    ----------
    input_file : Path
        Input HDF5 file with old structure
    output_file : Path
        Output HDF5 file with optimized structure
    remove_coords : bool
        If True, don't copy 'coords' dataset (can be generated on-the-fly)
    gzip_level : int
        Gzip compression level (1-9)
    shuffle : bool
        Enable shuffle filter for better compression
    verbose : bool
        Print progress information
    """
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    if output_file.exists():
        raise FileExistsError(f"Output file already exists: {output_file}")

    if verbose:
        print(f"Optimizing: {input_file}")
        print(f"Output to:  {output_file}")
        print(f"Compression: gzip level {gzip_level}, shuffle={shuffle}")
        print(f"Remove coords dataset: {remove_coords}\n")

    with h5py.File(input_file, 'r') as f_in, h5py.File(output_file, 'w') as f_out:
        # Get all depth groups
        groups = list(f_in.keys())
        if verbose:
            print(f"Found {len(groups)} depth groups: {sorted(groups, key=lambda x: float(x))}")

        if not groups:
            raise ValueError("No groups found in input file")

        # Get reference coordinates from first group
        ref_group = f_in[groups[0]]
        ref_lat = ref_group['latitudes'][:]
        ref_lon = ref_group['longitudes'][:]

        if verbose:
            print(f"\nStoring coordinates at root level:")
            print(f"  latitudes:  {ref_lat.shape} ({ref_lat.nbytes / 1024:.2f} KB)")
            print(f"  longitudes: {ref_lon.shape} ({ref_lon.nbytes / 1024:.2f} KB)")

        # Verify all groups have identical coordinates
        if verbose:
            print("\nVerifying coordinate consistency across all groups...")

        for group_name in groups:
            lat = f_in[group_name]['latitudes'][:]
            lon = f_in[group_name]['longitudes'][:]

            if not np.array_equal(lat, ref_lat):
                raise ValueError(f"Latitudes in group '{group_name}' differ from reference")
            if not np.array_equal(lon, ref_lon):
                raise ValueError(f"Longitudes in group '{group_name}' differ from reference")

        if verbose:
            print("✓ All coordinates are identical")

        # Store coordinates once at root level
        f_out.create_dataset(
            'latitudes',
            data=ref_lat,
            compression='gzip',
            compression_opts=gzip_level,
            shuffle=shuffle
        )
        f_out.create_dataset(
            'longitudes',
            data=ref_lon,
            compression='gzip',
            compression_opts=gzip_level,
            shuffle=shuffle
        )

        # Copy root-level attributes if they exist
        for attr_name, attr_value in f_in.attrs.items():
            f_out.attrs[attr_name] = attr_value

        # Add optimization metadata
        f_out.attrs['optimized_structure'] = True
        f_out.attrs['optimization_date'] = datetime.now().isoformat()
        f_out.attrs['coordinates_stored_at_root'] = True

        # Process each depth group
        if verbose:
            print(f"\nProcessing {len(groups)} depth groups...")

        total_saved = 0
        for i, group_name in enumerate(sorted(groups, key=lambda x: float(x)), 1):
            if verbose:
                print(f"  [{i}/{len(groups)}] {group_name} km...", end=' ', flush=True)

            in_group = f_in[group_name]
            out_group = f_out.create_group(group_name)

            # Calculate space saved
            saved = in_group['latitudes'].nbytes + in_group['longitudes'].nbytes
            if remove_coords and 'coords' in in_group:
                saved += in_group['coords'].nbytes
            total_saved += saved

            # Copy velocity and density datasets (but not coordinates)
            for dataset_name in ['vp', 'vs', 'rho']:
                if dataset_name not in in_group:
                    if verbose:
                        print(f"\n    Warning: '{dataset_name}' not found in group '{group_name}'")
                    continue

                in_dataset = in_group[dataset_name]

                # Get original compression settings
                compression = in_dataset.compression
                compression_opts = in_dataset.compression_opts
                chunks = in_dataset.chunks

                # Use specified compression settings
                out_group.create_dataset(
                    dataset_name,
                    data=in_dataset[:],
                    compression='gzip',
                    compression_opts=gzip_level,
                    shuffle=shuffle,
                    chunks=chunks
                )

                # Copy dataset attributes
                for attr_name, attr_value in in_dataset.attrs.items():
                    out_group[dataset_name].attrs[attr_name] = attr_value

            # Copy group attributes
            for attr_name, attr_value in in_group.attrs.items():
                out_group.attrs[attr_name] = attr_value

            if verbose:
                print(f"saved {saved / 1024 / 1024:.2f} MB")

        if verbose:
            print(f"\n✓ Optimization complete!")
            print(f"  Total space saved (uncompressed): {total_saved / 1024 / 1024:.2f} MB")

            # Compare file sizes
            input_size = input_file.stat().st_size
            output_size = output_file.stat().st_size
            print(f"  Input file size:  {input_size / 1024 / 1024:.2f} MB")
            print(f"  Output file size: {output_size / 1024 / 1024:.2f} MB")
            print(f"  File size reduction: {(input_size - output_size) / 1024 / 1024:.2f} MB ({(1 - output_size/input_size)*100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Optimize HDF5 tomography file by storing coordinates once at root level",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Optimize a single file
  python optimize_hdf5_structure.py ep2020.h5 ep2020_optimized.h5

  # Keep coords dataset (not recommended)
  python optimize_hdf5_structure.py ep2020.h5 ep2020_opt.h5 --keep-coords

  # Use different compression
  python optimize_hdf5_structure.py ep2020.h5 ep2020_opt.h5 --gzip-level 9
        """
    )

    parser.add_argument(
        'input_file',
        type=Path,
        help='Input HDF5 file with old structure'
    )
    parser.add_argument(
        'output_file',
        type=Path,
        help='Output HDF5 file with optimized structure'
    )
    parser.add_argument(
        '--keep-coords',
        action='store_true',
        help='Keep the coords dataset (not recommended, saves ~400MB if removed)'
    )
    parser.add_argument(
        '--gzip-level',
        type=int,
        default=4,
        choices=range(1, 10),
        help='Gzip compression level (1-9, default: 4)'
    )
    parser.add_argument(
        '--no-shuffle',
        action='store_true',
        help='Disable shuffle filter'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    try:
        optimize_hdf5_structure(
            input_file=args.input_file,
            output_file=args.output_file,
            remove_coords=not args.keep_coords,
            gzip_level=args.gzip_level,
            shuffle=not args.no_shuffle,
            verbose=not args.quiet
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
