"""
Inspect HDF5 file compression settings and data types.

This script examines the compression, chunking, and dtype settings
of all datasets in an HDF5 file.
"""

import sys
from pathlib import Path
import h5py
import numpy as np


def inspect_hdf5_compression(h5_path: str | Path):
    """
    Inspect compression settings of an HDF5 file.
    
    Parameters
    ----------
    h5_path : str or Path
        Path to HDF5 file to inspect.
    """
    print("=" * 70)
    print(f"HDF5 COMPRESSION INSPECTION: {h5_path}")
    print("=" * 70)
    
    file_size_mb = Path(h5_path).stat().st_size / (1024**2)
    print(f"\nFile size: {file_size_mb:.1f} MB ({file_size_mb/1024:.2f} GB)")
    
    with h5py.File(h5_path, "r") as f:
        depth_keys = list(f.keys())
        print(f"Number of groups (depth levels): {len(depth_keys)}")
        
        # Examine first group in detail
        first_key = depth_keys[0]
        print(f"\nDetailed inspection of group '{first_key}':")
        print("-" * 70)
        
        grp = f[first_key]
        
        for dataset_name in grp.keys():
            ds = grp[dataset_name]
            
            print(f"\nDataset: {dataset_name}")
            print(f"  Shape: {ds.shape}")
            print(f"  Dtype: {ds.dtype}")
            print(f"  Size: {ds.size * ds.dtype.itemsize / (1024**2):.2f} MB (uncompressed)")
            
            # Compression info
            compression = ds.compression
            if compression:
                print(f"  Compression: {compression}")
                if compression == 'gzip':
                    print(f"  Compression level: {ds.compression_opts}")
            else:
                print(f"  Compression: None")
            
            # Chunking info
            chunks = ds.chunks
            if chunks:
                print(f"  Chunking: {chunks}")
            else:
                print(f"  Chunking: None (contiguous)")
            
            # Shuffle filter
            shuffle = ds.shuffle
            print(f"  Shuffle filter: {shuffle}")
            
            # Fletcher32 checksum
            fletcher32 = ds.fletcher32
            print(f"  Fletcher32 checksum: {fletcher32}")
            
            # Actual size on disk (approximation)
            if hasattr(ds.id, 'get_storage_size'):
                storage_size = ds.id.get_storage_size()
                if storage_size > 0:
                    compression_ratio = (ds.size * ds.dtype.itemsize) / storage_size
                    print(f"  Storage size: {storage_size / (1024**2):.2f} MB")
                    print(f"  Compression ratio: {compression_ratio:.1f}x")
        
        # Check if all groups have same settings
        print("\n" + "=" * 70)
        print("CHECKING CONSISTENCY ACROSS ALL GROUPS")
        print("=" * 70)
        
        compressions = set()
        dtypes = {}
        
        for key in depth_keys:
            grp = f[key]
            for ds_name in grp.keys():
                ds = grp[ds_name]
                compressions.add(ds.compression)
                
                if ds_name not in dtypes:
                    dtypes[ds_name] = set()
                dtypes[ds_name].add(str(ds.dtype))
        
        print(f"\nCompression methods used: {compressions}")
        print(f"\nData types by dataset:")
        for ds_name, dtype_set in sorted(dtypes.items()):
            print(f"  {ds_name}: {dtype_set}")
        
        # Estimate total uncompressed size
        first_grp = f[depth_keys[0]]
        total_uncompressed = 0
        for ds_name in first_grp.keys():
            ds = first_grp[ds_name]
            size_per_group = ds.size * ds.dtype.itemsize
            total_size = size_per_group * len(depth_keys)
            total_uncompressed += total_size
        
        total_uncompressed_mb = total_uncompressed / (1024**2)
        actual_compression = total_uncompressed_mb / file_size_mb
        
        print(f"\n" + "=" * 70)
        print("OVERALL STATISTICS")
        print("=" * 70)
        print(f"Total uncompressed size estimate: {total_uncompressed_mb:.1f} MB ({total_uncompressed_mb/1024:.2f} GB)")
        print(f"Actual file size: {file_size_mb:.1f} MB ({file_size_mb/1024:.2f} GB)")
        print(f"Overall compression ratio: {actual_compression:.1f}x")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_hdf5_compression.py <file.h5>")
        sys.exit(1)
    
    h5_file = Path(sys.argv[1])
    if not h5_file.exists():
        print(f"Error: File not found: {h5_file}")
        sys.exit(1)
    
    inspect_hdf5_compression(h5_file)
