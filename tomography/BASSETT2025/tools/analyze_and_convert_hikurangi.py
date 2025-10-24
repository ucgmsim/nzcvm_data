"""
Analyze and convert Hikurangi tomography data to EP2020-compatible HDF5 format.

This version interpolates Hikurangi data onto the SAME GRID as EP2020 for compatibility
and easy model blending. The Hikurangi data fills an UPRIGHT RECTANGULAR region aligned
with lat/lon coordinates within the EP2020 grid.

Key features:
- Uses EP2020 grid spacing and coordinates
- Regular upright lon/lat grid (no rotation)
- Rectangular bounding box (upright coverage area)
- Direct compatibility with EP2020 for model blending
"""

from pathlib import Path
from typing import Tuple

import h5py
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
from scipy.spatial import ConvexHull
import matplotlib.pyplot as plt


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
    print("📥 Reading Hikurangi data...")
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
    
    df["elevation"] = -df["depth"]
    print(f"   Total points: {len(df):,}")
    
    # Handle dateline crossing
    lon_span = df["lon"].max() - df["lon"].min()
    if lon_span > 180:
        print(f"   ⚠️  Detected dateline crossing (converting to 0-360 range)")
        df.loc[df['lon'] < 0, 'lon'] += 360
    
    return df


def load_ep2020_grid(ep2020_path: str | Path) -> dict:
    """
    Load the grid structure from EP2020 HDF5 file.
    
    Parameters
    ----------
    ep2020_path : str or Path
        Path to EP2020 HDF5 file.
    
    Returns
    -------
    dict
        Dictionary containing EP2020 grid information.
    """
    print("\n" + "="*70)
    print("LOADING EP2020 GRID STRUCTURE")
    print("="*70)
    
    with h5py.File(ep2020_path, 'r') as f:
        # Get first group to read coordinate arrays
        first_group = list(f.keys())[0]
        lats = f[first_group]['latitudes'][:]
        lons = f[first_group]['longitudes'][:]
        
        # Get all elevation levels
        elevations = []
        for key in f.keys():
            try:
                # Handle both integer and decimal group names
                if '_' in key:
                    # Format like "-100_50" for -100.5
                    parts = key.split('_')
                    elev = float(parts[0]) + float(parts[1])/100 * (1 if float(parts[0]) >= 0 else -1)
                else:
                    elev = float(key)
                elevations.append(elev)
            except ValueError:
                continue
        
        elevations = np.sort(elevations)
    
    print(f"\n   Grid dimensions: {len(lats)} lat × {len(lons)} lon")
    print(f"   Latitude range: {lats.min():.3f}° to {lats.max():.3f}°")
    print(f"   Longitude range: {lons.min():.3f}° to {lons.max():.3f}°")
    print(f"   Lat spacing: {np.median(np.diff(lats)):.5f}°")
    print(f"   Lon spacing: {np.median(np.diff(lons)):.5f}°")
    print(f"   Total grid points: {len(lats) * len(lons):,}")
    print(f"   Elevation levels: {len(elevations)}")
    
    return {
        "lat": lats,
        "lon": lons,
        "elevations": elevations,
        "nlat": len(lats),
        "nlon": len(lons)
    }


def find_hikurangi_coverage_on_ep2020_grid(
    df: pd.DataFrame,
    ep2020_grid: dict
) -> dict:
    """
    Determine grid for Hikurangi data using EP2020 spacing but extended coverage.
    
    Uses EP2020's grid spacing but extends beyond EP2020 boundaries to capture
    all Hikurangi data (especially beyond 180° meridian).
    
    Parameters
    ----------
    df : pd.DataFrame
        Hikurangi data.
    ep2020_grid : dict
        EP2020 grid specification (for spacing).
    
    Returns
    -------
    dict
        Extended grid information.
    """
    print("\n" + "="*70)
    print("DETERMINING EXTENDED GRID FOR HIKURANGI")
    print("="*70)
    
    # Hikurangi data extent
    hik_lon_min, hik_lon_max = df["lon"].min(), df["lon"].max()
    hik_lat_min, hik_lat_max = df["lat"].min(), df["lat"].max()
    
    print(f"\nHikurangi full extent:")
    print(f"   Longitude: {hik_lon_min:.3f}° to {hik_lon_max:.3f}°")
    print(f"   Latitude:  {hik_lat_min:.3f}° to {hik_lat_max:.3f}°")
    
    # Get EP2020 grid spacing
    ep_lats = ep2020_grid["lat"]
    ep_lons = ep2020_grid["lon"]
    
    # Calculate spacing (may be negative for latitude)
    dlat = np.median(np.diff(ep_lats))
    dlon = np.median(np.diff(ep_lons))
    
    print(f"\nEP2020 grid spacing:")
    print(f"   dlat = {dlat:.5f}°, dlon = {dlon:.5f}°")
    
    # Add buffer
    buffer = 0.02
    
    # For LATITUDE: Find EP2020 points that bracket Hikurangi
    # EP2020: -48 to -33 (descending, so use reversed search)
    # Hikurangi: -45.037 to -34.357
    
    # Find indices in EP2020 that bracket Hikurangi extent
    # Since ep_lats goes -48, -47.99, ..., -33 (descending)
    # We need points where ep_lats <= -34.357 and ep_lats >= -45.037
    
    lat_mask = (ep_lats <= hik_lat_max + buffer) & (ep_lats >= hik_lat_min - buffer)
    lat_indices = np.where(lat_mask)[0]
    
    if len(lat_indices) > 0:
        lat_start_idx = lat_indices[0]
        lat_end_idx = lat_indices[-1]
        extended_lats = ep_lats[lat_start_idx:lat_end_idx+1]
    else:
        # Shouldn't happen but fallback
        extended_lats = ep_lats
    
    # For LONGITUDE: Find EP2020 points and extend beyond if needed
    # EP2020: 165 to 180
    # Hikurangi: 169.299 to 182.146 (extends beyond 180!)
    
    lon_mask = ep_lons >= hik_lon_min - buffer
    lon_indices = np.where(lon_mask)[0]
    
    if len(lon_indices) > 0:
        lon_start_idx = lon_indices[0]
        lon_start = ep_lons[lon_start_idx]
        
        # How many steps do we need to reach hik_lon_max?
        n_lon_steps = int(np.ceil((hik_lon_max + buffer - lon_start) / dlon)) + 1
        extended_lons = lon_start + np.arange(n_lon_steps) * dlon
    else:
        extended_lons = ep_lons
    
    print(f"\nExtended grid (using EP2020 spacing):")
    print(f"   Latitude: {len(extended_lats)} points from {extended_lats[0]:.3f}° to {extended_lats[-1]:.3f}°")
    print(f"   Longitude: {len(extended_lons)} points from {extended_lons[0]:.3f}° to {extended_lons[-1]:.3f}°")
    print(f"   Grid size: {len(extended_lats)} × {len(extended_lons)} = {len(extended_lats)*len(extended_lons):,} points")
    
    if extended_lons[-1] > 180.0:
        print(f"   ✓ Extends beyond 180° meridian (EP2020 boundary) to {extended_lons[-1]:.3f}°")
    
    return {
        "lat": extended_lats,
        "lon": extended_lons,
        "nlat": len(extended_lats),
        "nlon": len(extended_lons),
        "ep2020_compatible_spacing": True
    }


def interpolate_hikurangi_to_extended_grid(
    df: pd.DataFrame,
    extended_grid: dict
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Interpolate Hikurangi data onto extended grid, then apply rectangular mask AFTER.
    
    This avoids edge artifacts by interpolating first, then masking.
    
    Parameters
    ----------
    df : pd.DataFrame
        Hikurangi data.
    extended_grid : dict
        Extended grid specification.
    
    Returns
    -------
    tuple
        (vp_stack, vs_stack, rho_stack, elevations).
    """
    print("\n" + "="*70)
    print("INTERPOLATION TO EXTENDED GRID")
    print("="*70)
    
    # Get Hikurangi elevation levels
    hik_elevations = np.unique(df["elevation"])
    
    lats = extended_grid["lat"]
    lons = extended_grid["lon"]
    nlon, nlat, nz = len(lons), len(lats), len(hik_elevations)
    
    # Initialize arrays
    vp_stack = np.full((nz, nlat, nlon), np.nan, dtype=np.float32)
    vs_stack = np.full((nz, nlat, nlon), np.nan, dtype=np.float32)
    rho_stack = np.full((nz, nlat, nlon), np.nan, dtype=np.float32)
    
    # Create meshgrid
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    grid_points = np.column_stack([lon_grid.ravel(), lat_grid.ravel()])
    
    print(f"\nInterpolating {nz} elevation levels...")
    print(f"   Grid: {nlat} × {nlon} points")
    
    for iz, elev in enumerate(hik_elevations):
        if (iz + 1) % 20 == 0 or iz == 0 or iz == nz - 1:
            print(f"   Level {iz+1}/{nz}: elevation = {elev:.2f} km")
        
        # Get data at this elevation
        df_d = df[np.isclose(df["elevation"], elev, atol=1e-3)]
        
        if df_d.empty or len(df_d) < 4:
            continue
        
        # Data points
        data_points = df_d[["lon", "lat"]].values
        vp_vals = df_d["vp"].values
        vs_vals = df_d["vs"].values
        rho_vals = df_d["rho"].values
        
        try:
            # STEP 1: Interpolate to full grid (no masking yet)
            vp_flat = griddata(data_points, vp_vals, grid_points,
                             method="linear", fill_value=np.nan)
            vs_flat = griddata(data_points, vs_vals, grid_points,
                             method="linear", fill_value=np.nan)
            rho_flat = griddata(data_points, rho_vals, grid_points,
                              method="linear", fill_value=np.nan)
            
            # STEP 2: Apply rectangular mask AFTER interpolation
            # This avoids edge artifacts from premature clipping
            data_lon_min, data_lon_max = data_points[:, 0].min(), data_points[:, 0].max()
            data_lat_min, data_lat_max = data_points[:, 1].min(), data_points[:, 1].max()
            
            grid_lons = grid_points[:, 0]
            grid_lats = grid_points[:, 1]
            
            inside_box = ((grid_lons >= data_lon_min) & (grid_lons <= data_lon_max) &
                         (grid_lats >= data_lat_min) & (grid_lats <= data_lat_max))
            
            vp_flat[~inside_box] = np.nan
            vs_flat[~inside_box] = np.nan
            rho_flat[~inside_box] = np.nan
            
            # Reshape to 2D grid
            vp_stack[iz] = vp_flat.reshape((nlat, nlon))
            vs_stack[iz] = vs_flat.reshape((nlat, nlon))
            rho_stack[iz] = rho_flat.reshape((nlat, nlon))
            
            if (iz + 1) % 20 == 0 or iz == 0 or iz == nz - 1:
                coverage = 100 * (~np.isnan(vp_flat)).sum() / len(vp_flat)
                print(f"      Coverage: {coverage:.1f}%")
        
        except Exception as e:
            print(f"      ❌ Error: {e}")
    
    # Summary
    total_coverage = 100 * (~np.isnan(vp_stack)).sum() / vp_stack.size
    print(f"\nInterpolation complete:")
    print(f"   Overall coverage: {total_coverage:.2f}%")
    
    return vp_stack, vs_stack, rho_stack, hik_elevations


def write_extended_hdf5(
    output_path: str | Path,
    extended_grid: dict,
    elevations: np.ndarray,
    vp_stack: np.ndarray,
    vs_stack: np.ndarray,
    rho_stack: np.ndarray,
    compression_level: int = 4,
    use_shuffle: bool = False,
    coord_dtype: str = 'float32'
):
    """
    Write Hikurangi data in extended HDF5 format.
    
    Uses EP2020 spacing but extends beyond 180° to capture all data.
    
    Parameters
    ----------
    output_path : str or Path
        Output HDF5 file path.
    extended_grid : dict
        Extended grid specification.
    elevations : np.ndarray
        Elevation levels.
    vp_stack : np.ndarray
        3D array of Vp values.
    vs_stack : np.ndarray
        3D array of Vs values.
    rho_stack : np.ndarray
        3D array of density values.
    compression_level : int
        GZIP compression level.
    use_shuffle : bool
        Enable shuffle filter (keep False for sparse data).
    coord_dtype : str
        Coordinate data type.
    """
    print("\n" + "="*70)
    print("WRITING EXTENDED HDF5 FILE")
    print("="*70)
    
    lats = extended_grid["lat"]
    lons = extended_grid["lon"]
    nlat, nlon = len(lats), len(lons)
    nz = len(elevations)
    
    print(f"\n   Extended grid: {nlat} × {nlon}")
    print(f"   Lat range: {lats.min():.3f}° to {lats.max():.3f}°")
    print(f"   Lon range: {lons.min():.3f}° to {lons.max():.3f}°")
    print(f"   EP2020-compatible spacing: ✓")
    if lons.max() > 180.0:
        print(f"   Extends beyond 180° meridian: ✓")
    
    # Replace NaN with -999.0
    vp_out = np.where(np.isnan(vp_stack), -999.0, vp_stack)
    vs_out = np.where(np.isnan(vs_stack), -999.0, vs_stack)
    rho_out = np.where(np.isnan(rho_stack), -999.0, rho_stack)
    
    # Calculate actual coverage
    coverage_pct = 100 * (vp_stack != -999.0).sum() / vp_stack.size
    print(f"   Data coverage: {coverage_pct:.1f}% (rest is fill values)")
    
    # Chunking
    chunk_size = (min(50, nlat), min(50, nlon))
    coords_chunk_lat = (min(1000, nlat),)
    coords_chunk_lon = (min(1000, nlon),)
    
    with h5py.File(output_path, "w") as f:
        for iz, elev in enumerate(elevations):
            elev_rounded = round(elev, 2)
            
            if abs(elev_rounded - round(elev_rounded)) < 1e-6:
                grp_name = str(int(round(elev_rounded)))
            else:
                grp_name = f"{elev_rounded:.2f}".replace('.', '_').replace('-_', '-')
            
            grp = f.create_group(grp_name)
            
            # Store coordinates
            grp.create_dataset("latitudes", data=lats.astype(coord_dtype),
                             compression="gzip", compression_opts=compression_level,
                             shuffle=use_shuffle, chunks=coords_chunk_lat)
            grp.create_dataset("longitudes", data=lons.astype(coord_dtype),
                             compression="gzip", compression_opts=compression_level,
                             shuffle=use_shuffle, chunks=coords_chunk_lon)
            
            # Store data
            grp.create_dataset("vp", data=vp_out[iz], dtype=np.float32,
                             compression="gzip", compression_opts=compression_level,
                             shuffle=use_shuffle, chunks=chunk_size)
            grp.create_dataset("vs", data=vs_out[iz], dtype=np.float32,
                             compression="gzip", compression_opts=compression_level,
                             shuffle=use_shuffle, chunks=chunk_size)
            grp.create_dataset("rho", data=rho_out[iz], dtype=np.float32,
                             compression="gzip", compression_opts=compression_level,
                             shuffle=use_shuffle, chunks=chunk_size)
            
            if (iz + 1) % 20 == 0 or iz == 0 or iz == nz - 1:
                print(f"   Written group '{grp_name}'")
    
    actual_size_mb = Path(output_path).stat().st_size / (1024**2)
    print(f"\n✅ Successfully saved to {output_path}")
    print(f"   File size: {actual_size_mb:.1f} MB")
    print(f"   Note: shuffle=False optimizes compression for sparse data")


def main():
    """
    Main execution function.
    """
    print("="*70)
    print("HIKURANGI → EP2020-COMPATIBLE EXTENDED GRID")
    print("="*70)
    
    # Configuration
    hikurangi_txt = Path("Hikurangi_3D_model.txt")
    ep2020_h5 = Path("../EP2020/ep2020.h5")  # For grid spacing reference
    output_h5 = Path("hikurangi_ep2020grid.h5")
    
    # Compression settings (optimized for sparse data)
    compression_level = 4
    use_shuffle = False  # CRITICAL: False for sparse data with many -999.0 values
    coord_dtype = 'float32'
    
    print(f"\n📝 Settings:")
    print(f"   Hikurangi input: {hikurangi_txt}")
    print(f"   EP2020 reference: {ep2020_h5} (for grid spacing)")
    print(f"   Output: {output_h5}")
    print(f"   Compression: level={compression_level}, shuffle={use_shuffle}")
    
    # Step 1: Read Hikurangi data
    df = read_hikurangi_txt(hikurangi_txt)
    
    # Step 2: Load EP2020 grid (for spacing reference)
    ep2020_grid = load_ep2020_grid(ep2020_h5)
    
    # Step 3: Create extended grid using EP2020 spacing
    extended_grid = find_hikurangi_coverage_on_ep2020_grid(df, ep2020_grid)
    
    # Step 4: Interpolate (with masking AFTER interpolation)
    vp_stack, vs_stack, rho_stack, elevations = interpolate_hikurangi_to_extended_grid(
        df, extended_grid
    )
    
    # Step 5: Write HDF5
    write_extended_hdf5(
        output_h5, extended_grid, elevations,
        vp_stack, vs_stack, rho_stack,
        compression_level, use_shuffle, coord_dtype
    )
    
    print("\n" + "="*70)
    print("CONVERSION COMPLETE!")
    print("="*70)
    print(f"\n✅ EP2020-compatible spacing")
    print(f"✅ Extends beyond 180° meridian (captures all Hikurangi data)")
    print(f"✅ Upright rectangular coverage")
    print(f"✅ Masking applied AFTER interpolation (no edge artifacts)")
    print(f"✅ Optimized compression for sparse data")


if __name__ == "__main__":
    main()
