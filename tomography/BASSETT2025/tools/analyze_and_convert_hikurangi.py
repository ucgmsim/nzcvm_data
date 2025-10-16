"""
Analyze and convert Hikurangi tomography data to NZCVM-compatible HDF5 format.

This script:
1. Analyzes the spatial structure and resolution of Hikurangi data
2. Compares with EP2020 reference grid
3. Interpolates to an appropriate regular grid
4. Saves in HDF5 format consistent with EP2020
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
    
    # Read with chunking for large file
    df = pd.read_csv(
        txt_path,
        sep=r"\s+",
        skiprows=2,
        names=col_names,
        engine="python"
    )
    
    print(f"   Total points: {len(df):,}")
    return df


def detect_units(df: pd.DataFrame) -> dict:
    """
    Detect and verify units of velocity and density data.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    
    Returns
    -------
    dict
        Dictionary with unit detection results and conversion factors if needed.
    """
    print("\n" + "="*70)
    print("UNIT DETECTION AND VERIFICATION")
    print("="*70)
    
    # Get statistics excluding zeros and extreme outliers
    vp_nonzero = df[df['vp'] > 0.01]['vp']
    vs_nonzero = df[df['vs'] > 0.01]['vs']
    rho_nonzero = df[df['rho'] > 0.1]['rho']
    
    vp_min, vp_max, vp_median = vp_nonzero.min(), vp_nonzero.max(), vp_nonzero.median()
    vs_min, vs_max, vs_median = vs_nonzero.min(), vs_nonzero.max(), vs_nonzero.median()
    rho_min, rho_max, rho_median = rho_nonzero.min(), rho_nonzero.max(), rho_nonzero.median()
    
    print(f"\nRaw value ranges (excluding near-zero values):")
    print(f"   Vp:  min={vp_min:.3f}, max={vp_max:.3f}, median={vp_median:.3f}")
    print(f"   Vs:  min={vs_min:.3f}, max={vs_max:.3f}, median={vs_median:.3f}")
    print(f"   Rho: min={rho_min:.3f}, max={rho_max:.3f}, median={rho_median:.3f}")
    
    # Expected ranges for different unit systems
    # Velocities
    vp_range_kms = (1.4, 9.0)      # km/s: typical crustal range
    vp_range_ms = (1400, 9000)     # m/s
    vs_range_kms = (0.5, 5.5)      # km/s
    vs_range_ms = (500, 5500)      # m/s
    
    # Density
    rho_range_gcc = (1.5, 3.6)     # g/cm³: typical crustal range
    rho_range_kgm3 = (1500, 3600)  # kg/m³
    
    # Detect units
    results = {
        'vp_likely_kms': vp_range_kms[0] <= vp_median <= vp_range_kms[1],
        'vp_likely_ms': vp_range_ms[0] <= vp_median <= vp_range_ms[1],
        'vs_likely_kms': vs_range_kms[0] <= vs_median <= vs_range_kms[1],
        'vs_likely_ms': vs_range_ms[0] <= vs_median <= vs_range_ms[1],
        'rho_likely_gcc': rho_range_gcc[0] <= rho_median <= rho_range_gcc[1],
        'rho_likely_kgm3': rho_range_kgm3[0] <= rho_median <= rho_range_kgm3[1],
        'vp_conversion': 1.0,
        'vs_conversion': 1.0,
        'rho_conversion': 1.0,
        'needs_conversion': False
    }
    
    print(f"\n" + "="*70)
    print("UNIT DETECTION RESULTS:")
    print("="*70)
    
    # Velocity unit detection
    print(f"\nVELOCITY UNITS:")
    if results['vp_likely_kms'] and results['vs_likely_kms']:
        print(f"   ✅ Vp and Vs appear to be in km/s")
        print(f"      (Vp median {vp_median:.2f} km/s, Vs median {vs_median:.2f} km/s)")
    elif results['vp_likely_ms'] and results['vs_likely_ms']:
        print(f"   ⚠️  Vp and Vs appear to be in m/s (NOT km/s!)")
        print(f"      (Vp median {vp_median:.0f} m/s, Vs median {vs_median:.0f} m/s)")
        print(f"   🔄 Will convert to km/s by dividing by 1000")
        results['vp_conversion'] = 0.001
        results['vs_conversion'] = 0.001
        results['needs_conversion'] = True
    else:
        print(f"   ❌ WARNING: Velocity units are UNCLEAR or UNUSUAL!")
        print(f"      Vp median: {vp_median:.3f}")
        print(f"      Vs median: {vs_median:.3f}")
        print(f"      Expected km/s: Vp ~2-7, Vs ~1-4")
        print(f"      Expected m/s: Vp ~2000-7000, Vs ~1000-4000")
        print(f"   ⚠️  MANUAL VERIFICATION REQUIRED!")
    
    # Density unit detection
    print(f"\nDENSITY UNITS:")
    if results['rho_likely_gcc']:
        print(f"   ✅ Density appears to be in g/cm³")
        print(f"      (median {rho_median:.2f} g/cm³)")
    elif results['rho_likely_kgm3']:
        print(f"   ⚠️  Density appears to be in kg/m³ (NOT g/cm³!)")
        print(f"      (median {rho_median:.0f} kg/m³)")
        print(f"   🔄 Will convert to g/cm³ by dividing by 1000")
        results['rho_conversion'] = 0.001
        results['needs_conversion'] = True
    else:
        print(f"   ❌ WARNING: Density units are UNCLEAR or UNUSUAL!")
        print(f"      Median: {rho_median:.3f}")
        print(f"      Expected g/cm³: ~2.0-3.0")
        print(f"      Expected kg/m³: ~2000-3000")
        print(f"   ⚠️  MANUAL VERIFICATION REQUIRED!")
    
    # Check for suspicious low values that might be water or flag values
    print(f"\nDATA QUALITY CHECKS:")
    very_low_vp = (df['vp'] < 1.0).sum()
    very_low_vs = (df['vs'] < 0.3).sum()
    print(f"   Very low Vp (<1.0): {very_low_vp:,} points ({100*very_low_vp/len(df):.1f}%)")
    print(f"   Very low Vs (<0.3): {very_low_vs:,} points ({100*very_low_vs/len(df):.1f}%)")
    
    if very_low_vp > len(df) * 0.01:  # More than 1% of points
        print(f"   ℹ️  Note: Many low velocity values detected.")
        print(f"      These might be:")
        print(f"      - Water layer (Vp~1.5 km/s, Vs~0)")
        print(f"      - Very soft sediments")
        print(f"      - Flag/placeholder values")
        print(f"      - Incorrect units")
    
    print(f"\n" + "="*70)
    
    if results['needs_conversion']:
        print(f"⚠️  CONVERSION WILL BE APPLIED:")
        print(f"   Vp: multiply by {results['vp_conversion']}")
        print(f"   Vs: multiply by {results['vs_conversion']}")
        print(f"   Rho: multiply by {results['rho_conversion']}")
        print(f"="*70)
    
    return results


def analyze_grid_structure(df: pd.DataFrame) -> dict:
    """
    Analyze the grid structure of the Hikurangi data.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    
    Returns
    -------
    dict
        Dictionary containing grid analysis results.
    """
    print("\n" + "="*70)
    print("GRID STRUCTURE ANALYSIS")
    print("="*70)
    
    # 1. Check orientation (via model_x, model_y)
    unique_model_x = np.unique(df["model_x"])
    unique_model_y = np.unique(df["model_y"])
    unique_depths = np.unique(df["depth"])
    
    print(f"\n1. ORIENTATION & COORDINATE SYSTEM:")
    print(f"   Model X range: {unique_model_x.min():.1f} to {unique_model_x.max():.1f} km")
    print(f"   Model Y range: {unique_model_y.min():.1f} to {unique_model_y.max():.1f} km")
    print(f"   Number of unique X values: {len(unique_model_x)}")
    print(f"   Number of unique Y values: {len(unique_model_y)}")
    
    # Check if grid is regular
    if len(unique_model_x) > 1:
        dx = np.diff(unique_model_x)
        dx_regular = np.allclose(dx, dx[0], rtol=1e-3)
        print(f"   X spacing regular: {dx_regular}")
        if dx_regular:
            print(f"   X spacing: {dx[0]:.3f} km")
        else:
            print(f"   X spacing: min={dx.min():.3f}, max={dx.max():.3f}, mean={dx.mean():.3f} km")
    
    if len(unique_model_y) > 1:
        dy = np.diff(unique_model_y)
        dy_regular = np.allclose(dy, dy[0], rtol=1e-3)
        print(f"   Y spacing regular: {dy_regular}")
        if dy_regular:
            print(f"   Y spacing: {dy[0]:.3f} km")
        else:
            print(f"   Y spacing: min={dy.min():.3f}, max={dy.max():.3f}, mean={dy.mean():.3f} km")
    
    # 2. Domain in lat/lon (handle dateline crossing)
    print(f"\n2. GEOGRAPHIC DOMAIN:")
    lon_min_raw, lon_max_raw = df['lon'].min(), df['lon'].max()
    
    # Check if data crosses the dateline (180° meridian)
    lon_span_raw = lon_max_raw - lon_min_raw
    crosses_dateline = lon_span_raw > 180
    
    if crosses_dateline:
        # Convert negative longitudes to 0-360 range
        lon_adjusted = df['lon'].copy()
        lon_adjusted[lon_adjusted < 0] += 360
        lon_min, lon_max = lon_adjusted.min(), lon_adjusted.max()
        print(f"   ⚠️  Data crosses 180° dateline!")
        print(f"   Raw longitude: {lon_min_raw:.3f}°E to {lon_max_raw:.3f}°E (spans {lon_span_raw:.1f}°)")
        print(f"   Adjusted to: {lon_min:.3f}°E to {lon_max:.3f}°E (0-360 range)")
    else:
        lon_min, lon_max = lon_min_raw, lon_max_raw
        print(f"   Longitude: {lon_min:.3f}°E to {lon_max:.3f}°E")
    
    print(f"   Latitude: {df['lat'].min():.3f}°S to {df['lat'].max():.3f}°S")
    print(f"   Span: {lon_max-lon_min:.3f}° lon × {df['lat'].max()-df['lat'].min():.3f}° lat")
    
    # 3. Depth levels
    print(f"\n3. DEPTH LEVELS:")
    print(f"   Number of depth levels: {len(unique_depths)}")
    print(f"   Depth range: {unique_depths.min():.2f} to {unique_depths.max():.2f} km")
    if len(unique_depths) > 1:
        dz = np.diff(unique_depths)
        dz_regular = np.allclose(dz, dz[0], rtol=1e-3)
        print(f"   Depth spacing regular: {dz_regular}")
        if dz_regular:
            print(f"   Depth spacing: {dz[0]:.3f} km")
        else:
            print(f"   Depth spacing: min={dz.min():.3f}, max={dz.max():.3f}, mean={dz.mean():.3f} km")
    
    # Sample depths to show
    if len(unique_depths) <= 20:
        print(f"   All depths: {unique_depths}")
    else:
        print(f"   First 10 depths: {unique_depths[:10]}")
        print(f"   Last 10 depths: {unique_depths[-10:]}")
    
    # 4. Points per depth level
    points_per_depth = df.groupby("depth").size()
    print(f"\n4. POINTS PER DEPTH LEVEL:")
    print(f"   Min points: {points_per_depth.min():,}")
    print(f"   Max points: {points_per_depth.max():,}")
    print(f"   Mean points: {points_per_depth.mean():,.0f}")
    print(f"   Consistent: {points_per_depth.nunique() == 1}")
    
    # 5. Check for rotation angle
    print(f"\n5. ROTATION ANALYSIS:")
    # Calculate angle between model coords and geographic coords
    # Sample a few points to check
    sample = df.sample(min(1000, len(df)), random_state=42)
    
    # Convert lat/lon differences to approximate km (rough estimate)
    mean_lat = sample["lat"].mean()
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * np.cos(np.radians(mean_lat))
    
    # Calculate vectors in both coordinate systems
    if len(sample) > 1:
        # Take differences between consecutive points
        sample_sorted = sample.sort_values(["model_y", "model_x"])
        dx_model = sample_sorted["model_x"].diff().dropna()
        dy_model = sample_sorted["model_y"].diff().dropna()
        dlon = sample_sorted["lon"].diff().dropna() * km_per_deg_lon
        dlat = sample_sorted["lat"].diff().dropna() * km_per_deg_lat
        
        # Find points with significant model_x displacement
        sig_points = (np.abs(dx_model) > 0.1) & (np.abs(dy_model) < 0.1)
        if sig_points.any():
            angles = np.arctan2(dlat[sig_points].values, dlon[sig_points].values) - \
                     np.arctan2(dy_model[sig_points].values, dx_model[sig_points].values)
            mean_angle = np.degrees(np.angle(np.exp(1j * angles).mean()))
            print(f"   Estimated rotation: {mean_angle:.1f}° (approximate)")
        else:
            print(f"   Cannot estimate rotation from sample")
    
    # 6. Velocity and density summary (unit conversion already applied if needed)
    print(f"\n6. PARAMETER SUMMARY:")
    print(f"   Vp: {df['vp'].min():.3f} to {df['vp'].max():.3f} km/s")
    print(f"   Vs: {df['vs'].min():.3f} to {df['vs'].max():.3f} km/s")
    print(f"   Vp/Vs: {df['vp_o_vs'].min():.3f} to {df['vp_o_vs'].max():.3f}")
    print(f"   Density: {df['rho'].min():.3f} to {df['rho'].max():.3f} g/cm³")
    
    # Constraint flag statistics
    print(f"\n7. DATA CONSTRAINT:")
    print(f"   Constrained points (flag=1): {(df['constraint']==1).sum():,} ({100*(df['constraint']==1).mean():.1f}%)")
    print(f"   Unconstrained points (flag=0): {(df['constraint']==0).sum():,} ({100*(df['constraint']==0).mean():.1f}%)")
    
    # Determine final longitude range to use
    if crosses_dateline:
        final_lon_range = (lon_min, lon_max)  # Adjusted 0-360 range
    else:
        final_lon_range = (lon_min_raw, lon_max_raw)
    
    return {
        "model_x": unique_model_x,
        "model_y": unique_model_y,
        "depths": unique_depths,
        "lon_range": final_lon_range,
        "lat_range": (df['lat'].min(), df['lat'].max()),
        "points_per_depth": points_per_depth.values[0] if points_per_depth.nunique() == 1 else None,
        "crosses_dateline": crosses_dateline
    }


def load_ep2020_grid_info(h5_path: str | Path) -> dict:
    """
    Load EP2020 grid information for comparison.
    
    Parameters
    ----------
    h5_path : str or Path
        Path to EP2020 HDF5 file.
    
    Returns
    -------
    dict
        Dictionary with EP2020 grid info.
    """
    print("\n" + "="*70)
    print("EP2020 REFERENCE GRID")
    print("="*70)
    
    with h5py.File(h5_path, "r") as f:
        # Get first group to extract grid
        first_group = list(f.keys())[0]
        grp = f[first_group]
        
        lat = grp["latitudes"][:]
        lon = grp["longitudes"][:]
        depths = sorted([float(k) for k in f.keys()])
        
        print(f"\nGrid dimensions: {len(lat)} × {len(lon)} × {len(depths)}")
        print(f"Latitude: {lat.min():.3f}°S to {lat.max():.3f}°S")
        print(f"Longitude: {lon.min():.3f}°E to {lon.max():.3f}°E")
        print(f"Depths: {len(depths)} levels from {min(depths):.0f} to {max(depths):.0f} km")
        
        dlat = np.diff(lat)
        dlon = np.diff(lon)
        print(f"Latitude spacing: {dlat.mean():.4f}° ({dlat.mean()*111:.2f} km)")
        print(f"Longitude spacing: {dlon.mean():.4f}° ({dlon.mean()*111*np.cos(np.radians(lat.mean())):.2f} km)")
        
        return {
            "lat": lat,
            "lon": lon,
            "depths": np.array(depths),
            "dlat": dlat.mean(),
            "dlon": dlon.mean()
        }


def determine_target_grid(hik_info: dict, ep_info: dict = None, use_ep_spacing: bool = True) -> dict:
    """
    Determine appropriate target grid for Hikurangi data.
    
    Parameters
    ----------
    hik_info : dict
        Hikurangi grid information.
    ep_info : dict, optional
        EP2020 grid information for reference.
    use_ep_spacing : bool
        If True and ep_info is provided, use EP2020 grid spacing for compatibility.
    
    Returns
    -------
    dict
        Target grid specification.
    """
    print("\n" + "="*70)
    print("TARGET GRID DETERMINATION")
    print("="*70)
    
    lon_min, lon_max = hik_info["lon_range"]
    lat_min, lat_max = hik_info["lat_range"]
    
    # Estimate current resolution
    model_x = hik_info["model_x"]
    model_y = hik_info["model_y"]
    
    if len(model_x) > 1 and len(model_y) > 1:
        dx_km = np.median(np.diff(model_x))
        dy_km = np.median(np.diff(model_y))
        mean_lat = (lat_min + lat_max) / 2
        
        # Convert to degrees (approximate)
        dlat_deg = dy_km / 111.0
        dlon_deg = dx_km / (111.0 * np.cos(np.radians(mean_lat)))
        
        print(f"\nOriginal grid spacing:")
        print(f"   Model space: {dx_km:.3f} km × {dy_km:.3f} km")
        print(f"   Geographic: ~{dlon_deg:.4f}° × {dlat_deg:.4f}°")
        
        # Determine target spacing
        if use_ep_spacing and ep_info is not None:
            # Use EP2020 spacing for compatibility
            target_dlat = abs(ep_info["dlat"])  # Use absolute value
            target_dlon = abs(ep_info["dlon"])
            print(f"\nUsing EP2020 grid spacing for compatibility:")
            print(f"   {target_dlon:.4f}° × {target_dlat:.4f}°")
        else:
            # Use Hikurangi's native resolution
            target_dlat = dlat_deg
            target_dlon = dlon_deg
            print(f"\nUsing Hikurangi native resolution:")
            print(f"   {target_dlon:.4f}° × {target_dlat:.4f}°")
    else:
        # Default spacing if can't determine from data
        if ep_info is not None:
            target_dlat = abs(ep_info["dlat"])
            target_dlon = abs(ep_info["dlon"])
        else:
            target_dlat = 0.01  # ~1.1 km
            target_dlon = 0.01  # ~0.8-1.0 km depending on latitude
        print(f"\nUsing default grid spacing: {target_dlon:.4f}° × {target_dlat:.4f}°")
    
    # Generate grid with proper handling
    # Add small buffer
    lon_buffer = target_dlon * 2
    lat_buffer = target_dlat * 2
    
    # Create latitude array (always works normally)
    target_lat = np.arange(lat_min - lat_buffer, lat_max + lat_buffer + target_dlat/2, target_dlat)
    
    # Create longitude array (handle potential dateline crossing)
    if lon_min < 0 and lon_max > 180:  # Crosses dateline in adjusted coords
        # This shouldn't happen with adjusted coords, but handle it
        target_lon = np.arange(lon_min - lon_buffer, lon_max + lon_buffer + target_dlon/2, target_dlon)
    else:
        target_lon = np.arange(lon_min - lon_buffer, lon_max + lon_buffer + target_dlon/2, target_dlon)
    
    target_depths = hik_info["depths"]
    
    print(f"\nTarget grid dimensions: {len(target_lat)} × {len(target_lon)} × {len(target_depths)}")
    print(f"Target points per level: {len(target_lat) * len(target_lon):,}")
    print(f"Target total points: {len(target_lat) * len(target_lon) * len(target_depths):,}")
    
    # Convert longitudes back to -180 to 180 range if needed
    if (target_lon > 180).any():
        print(f"\nConverting longitudes back to -180 to 180 range...")
        target_lon_wrapped = target_lon.copy()
        target_lon_wrapped[target_lon_wrapped > 180] -= 360
        print(f"   Longitude range: {target_lon_wrapped.min():.3f}°E to {target_lon_wrapped.max():.3f}°E")
        use_wrapped = True
    else:
        target_lon_wrapped = target_lon
        use_wrapped = False
    
    return {
        "lat": target_lat,
        "lon": target_lon_wrapped,
        "lon_original": target_lon,  # Keep for reference
        "depths": target_depths,
        "dlat": target_dlat,
        "dlon": target_dlon,
        "crosses_dateline": use_wrapped
    }


def interpolate_hikurangi_to_grid(
    df: pd.DataFrame,
    target_grid: dict,
    use_constrained_only: bool = False
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Interpolate Hikurangi data to regular grid.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input Hikurangi data.
    target_grid : dict
        Target grid specification.
    use_constrained_only : bool
        If True, only use constrained points (constraint=1) for interpolation.
    
    Returns
    -------
    tuple
        (vp_stack, vs_stack, rho_stack) as 3D arrays (nz, nlat, nlon).
    """
    print("\n" + "="*70)
    print("INTERPOLATION")
    print("="*70)
    
    if use_constrained_only:
        print("\nUsing only constrained points (constraint=1)")
        df = df[df["constraint"] == 1].copy()
        print(f"Points remaining: {len(df):,}")
    
    lat = target_grid["lat"]
    lon = target_grid["lon"]
    depths = target_grid["depths"]
    
    nlat, nlon, ndepth = len(lat), len(lon), len(depths)
    
    vp_stack = np.full((ndepth, nlat, nlon), np.nan, dtype=np.float32)
    vs_stack = np.full((ndepth, nlat, nlon), np.nan, dtype=np.float32)
    rho_stack = np.full((ndepth, nlat, nlon), np.nan, dtype=np.float32)
    
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    
    print(f"\nInterpolating {len(depths)} depth levels...")
    for iz, d in enumerate(depths):
        if (iz + 1) % 10 == 0 or iz == 0 or iz == len(depths) - 1:
            print(f"   Level {iz+1}/{len(depths)}: depth = {d:.2f} km")
        
        # Get data at this depth
        df_d = df[np.isclose(df["depth"], d, atol=1e-3)]
        
        if df_d.empty:
            print(f"      ⚠️  No data at depth={d:.2f} km")
            continue
        
        if len(df_d) < 4:
            print(f"      ⚠️  Insufficient points ({len(df_d)}) at depth={d:.2f} km")
            continue
        
        # Prepare data
        points = df_d[["lon", "lat"]].values
        vp_vals = df_d["vp"].values
        vs_vals = df_d["vs"].values
        rho_vals = df_d["rho"].values
        
        # Interpolate
        try:
            vp_interp = griddata(points, vp_vals, (lon_grid, lat_grid), 
                               method="linear", fill_value=np.nan)
            vs_interp = griddata(points, vs_vals, (lon_grid, lat_grid), 
                               method="linear", fill_value=np.nan)
            rho_interp = griddata(points, rho_vals, (lon_grid, lat_grid), 
                                method="linear", fill_value=np.nan)
            
            vp_stack[iz] = vp_interp
            vs_stack[iz] = vs_interp
            rho_stack[iz] = rho_interp
            
            # Report coverage
            coverage = 100 * (~np.isnan(vp_interp)).sum() / vp_interp.size
            if (iz + 1) % 10 == 0 or iz == 0 or iz == len(depths) - 1:
                print(f"      Coverage: {coverage:.1f}%")
        
        except Exception as e:
            print(f"      ❌ Error: {e}")
    
    # Summary statistics
    print(f"\nInterpolation complete:")
    print(f"   Vp coverage: {100*(~np.isnan(vp_stack)).sum()/vp_stack.size:.1f}%")
    print(f"   Vs coverage: {100*(~np.isnan(vs_stack)).sum()/vs_stack.size:.1f}%")
    print(f"   Rho coverage: {100*(~np.isnan(rho_stack)).sum()/rho_stack.size:.1f}%")
    
    return vp_stack, vs_stack, rho_stack


def write_hikurangi_hdf5(
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
    Write Hikurangi tomography data to HDF5 in EP2020-compatible format with compression.
    
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
        P-wave velocity in km/s (nz, nlat, nlon).
    vs_stack : np.ndarray
        S-wave velocity in km/s (nz, nlat, nlon).
    rho_stack : np.ndarray
        Density in g/cm³ (nz, nlat, nlon).
    compression_level : int
        Gzip compression level (0-9). Default 4 is good balance.
        0=no compression, 9=max compression (slower).
    """
    print("\n" + "="*70)
    print("WRITING HDF5")
    print("="*70)
    
    # Create coordinate meshgrid (keep as float64 for best compression with shuffle)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    coords = np.stack([lat_grid, lon_grid], axis=-1)  # float64
    
    # Replace NaN with -999.0 flag
    vp_stack = vp_stack.copy()
    vs_stack = vs_stack.copy()
    rho_stack = rho_stack.copy()
    
    vp_stack[np.isnan(vp_stack)] = -999.0
    vs_stack[np.isnan(vs_stack)] = -999.0
    rho_stack[np.isnan(rho_stack)] = -999.0
    
    print(f"\nWriting to: {output_path}")
    print(f"Grid: {len(lats)} lat × {len(lons)} lon × {len(depth_list)} depth")
    print(f"Compression: gzip level {compression_level} + shuffle filter")
    
    # Calculate expected file size
    points_per_level = len(lats) * len(lons)
    data_size_mb = (points_per_level * 3 * 4 * len(depth_list)) / (1024**2)  # 3 vars, 4 bytes each
    coords_size_mb = (points_per_level * 2 * 8 * len(depth_list)) / (1024**2)  # coords, 2 values, 8 bytes
    print(f"Uncompressed size estimate: {(data_size_mb + coords_size_mb):.1f} MB")
    
    # Determine optimal chunk size
    chunk_size = min(256, len(lats)), min(256, len(lons))
    coords_chunk_size = (min(88, len(lats)), min(50, len(lons)), 1)
    
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
            # Regular grids compress EXTREMELY well with shuffle filter
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
            
            if (iz + 1) % 20 == 0 or iz == 0 or iz == len(depth_list) - 1:
                print(f"   Written group '{grp_name}'")
    
    # Report actual file size
    actual_size_mb = Path(output_path).stat().st_size / (1024**2)
    compression_ratio = (data_size_mb + coords_size_mb) / actual_size_mb if actual_size_mb > 0 else 0
    
    print(f"\n✅ Successfully saved Hikurangi HDF5 to {output_path}")
    print(f"   Actual file size: {actual_size_mb:.1f} MB")
    print(f"   Compression ratio: {compression_ratio:.1f}x")


def create_comparison_plot(df: pd.DataFrame, output_path: str = "hikurangi_coverage.png"):
    """
    Create a visualization of the Hikurangi data coverage.
    
    Parameters
    ----------
    df : pd.DataFrame
        Hikurangi data.
    output_path : str
        Output file path for the plot.
    """
    print(f"\n📊 Creating coverage visualization...")
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: All points at surface level
    surface_data = df[df["depth"] == df["depth"].min()]
    axes[0].scatter(surface_data["lon"], surface_data["lat"], 
                    s=1, alpha=0.5, c='red')
    axes[0].set_xlabel("Longitude (°E)")
    axes[0].set_ylabel("Latitude (°S)")
    axes[0].set_title(f"Hikurangi Data Coverage (depth={surface_data['depth'].iloc[0]:.1f} km)")
    axes[0].grid(True, alpha=0.3)
    
    # Plot 2: Constrained vs unconstrained
    constrained = df[(df["depth"] == df["depth"].min()) & (df["constraint"] == 1)]
    unconstrained = df[(df["depth"] == df["depth"].min()) & (df["constraint"] == 0)]
    
    axes[1].scatter(unconstrained["lon"], unconstrained["lat"], 
                   s=1, alpha=0.3, c='lightgray', label='Unconstrained')
    axes[1].scatter(constrained["lon"], constrained["lat"], 
                   s=1, alpha=0.5, c='red', label='Constrained')
    axes[1].set_xlabel("Longitude (°E)")
    axes[1].set_ylabel("Latitude (°S)")
    axes[1].set_title("Data Constraint Status")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"   Saved to {output_path}")
    plt.close()


def main():
    """
    Main execution function.
    """
    # File paths - ADJUST THESE
    hikurangi_txt = Path("Hikurangi_3D_model.txt")
    ep2020_h5 = Path("ep2020.h5")  # Optional, for comparison
    output_h5 = Path("hikurangi_uniform.h5")
    
    print("="*70)
    print("HIKURANGI TOMOGRAPHY CONVERSION")
    print("="*70)
    
    # Step 1: Read Hikurangi data
    df = read_hikurangi_txt(hikurangi_txt)
    
    # Step 2: Detect and verify units
    unit_info = detect_units(df)
    
    # Apply unit conversions if needed
    if unit_info['needs_conversion']:
        print(f"\n🔄 Applying unit conversions...")
        df['vp'] = df['vp'] * unit_info['vp_conversion']
        df['vs'] = df['vs'] * unit_info['vs_conversion']
        df['rho'] = df['rho'] * unit_info['rho_conversion']
        print(f"   ✅ Conversions applied")
        print(f"   New Vp range: {df['vp'].min():.3f} to {df['vp'].max():.3f} km/s")
        print(f"   New Vs range: {df['vs'].min():.3f} to {df['vs'].max():.3f} km/s")
        print(f"   New Rho range: {df['rho'].min():.3f} to {df['rho'].max():.3f} g/cm³")
    
    # Step 3: Analyze grid structure
    hik_info = analyze_grid_structure(df)
    
    # If data crosses dateline, adjust longitudes in dataframe
    if hik_info.get("crosses_dateline", False):
        print(f"\n🔄 Adjusting longitude values in dataframe...")
        df.loc[df['lon'] < 0, 'lon'] += 360
        print(f"   ✅ Longitudes adjusted to 0-360 range for interpolation")
    
    # Step 4: Load EP2020 for comparison (if available)
    ep_info = None
    if ep2020_h5.exists():
        ep_info = load_ep2020_grid_info(ep2020_h5)
    else:
        print(f"\n⚠️  EP2020 file not found at {ep2020_h5}")
        print("   Proceeding without comparison...")
    
    # Step 5: Determine target grid (use EP2020 spacing for compatibility)
    target_grid = determine_target_grid(hik_info, ep_info, use_ep_spacing=True)
    
    # Step 6: Create visualization
    create_comparison_plot(df, "hikurangi_coverage.png")
    
    # Step 7: Interpolate to regular grid
    print("\n" + "="*70)
    print("INTERPOLATION OPTIONS")
    print("="*70)
    print("\nYou can interpolate using:")
    print("   1. All points (default)")
    print("   2. Only constrained points (constraint=1)")
    
    # For now, use all points
    use_constrained_only = False
    
    vp_stack, vs_stack, rho_stack = interpolate_hikurangi_to_grid(
        df, target_grid, use_constrained_only
    )
    
    # Step 8: Write HDF5
    write_hikurangi_hdf5(
        output_h5,
        target_grid["lat"],
        target_grid["lon"],
        target_grid["depths"],
        vp_stack,
        vs_stack,
        rho_stack
    )
    
    print("\n" + "="*70)
    print("CONVERSION COMPLETE!")
    print("="*70)
    print(f"\nOutput file: {output_h5}")
    print(f"Visualization: hikurangi_coverage.png")


if __name__ == "__main__":
    main()
