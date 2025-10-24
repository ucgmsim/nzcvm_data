#!/usr/bin/env python3
"""
2D Map Viewer for Tomography Data with Ratio and CSV Overlay Capabilities

- View scalar data (vp, vs, rho) from an HDF5 tomography file.
- Optionally compare with a second HDF5 file by plotting the natural logarithm ratio (compared_file / base_file).
- Optionally overlay point data from a CSV file, loading only points near the specified HDF5 elevation slice.

Usage:
    tomo_map.py h5file1 [--compared h5file2] \\
                            [--csv-data csvfile --lon-col LON_COL --lat-col LAT_COL --depth-col DEPTH_COL [--depth-is-elevation] --scalar-col SCALAR_COL [--depth-tolerance TOLERANCE] [--skip-rows N] [--sep SEP]] \\
                            [--scalar {vp,vs,rho}] [--vmin VMIN] [--vmax VMAX] \\
                            [--cmap CMAP] [--elevations ELEVATIONS [ELEVATIONS ...]] \\
                            [--output-dir OUTPUT_DIR] [--no-cartopy] [--dpi DPI]

Modes:
  1. Standard Plot: Provide only h5file1. Plots scalar data from h5file1.
  2. Ratio Plot: Provide h5file1 and --compared h5file2. Plots ln(h5file2 / h5file1) with a globally symmetric colormap. Prints comparison details.
  3. CSV Overlay: Provide h5file1, --csv-data, and column info. Plots scalar data from h5file1 (for specified elevations)
     and overlays points from the CSV that are within the depth tolerance of each HDF5 elevation slice.

Arguments & Options:
  h5file1               Path to the primary (base) HDF5 tomography file.
  --compared h5file2    Path to the second HDF5 file for ratio comparison. Enables ratio plot mode automatically. Cannot be used with --csv-data.
  --csv-data csvfile    Path to the CSV file containing point data. Enables CSV overlay mode automatically. Cannot be used with --compared.
  --lon-col LON_COL     Column name or index for longitude in the CSV file (required if --csv-data).
  --lat-col LAT_COL     Column name or index for latitude in the CSV file (required if --csv-data).
  --depth-col DEPTH_COL Column name or index for depth/elevation in the CSV file (required if --csv-data).
  --depth-is-elevation  Flag if the depth column in CSV actually represents elevation (positive up). Default is depth (positive down).
  --scalar-col SCALAR_COL Column name or index for the scalar value (matching --scalar) in the CSV file (required if --csv-data).
  --depth-tolerance TOLERANCE
                        Tolerance (in km) for matching CSV points to H5 elevations (default: 0.1 km).
  --skip-rows N         Number of rows to skip at the beginning of the CSV file (default: 0).
  --sep SEP             Delimiter used in the CSV file (default: ',').
  --scalar              Scalar field to plot (vp, vs, rho). Default: vp.
  --vmin, --vmax        Min/Max for color scale (auto if not set). Ignored for ratio plots (uses symmetric range).
  --cmap                Matplotlib colormap name. Default: RdYlBu_r (seismic for ratio).
  --elevations          Specific elevations (km) to plot from the HDF5 file. Plots all found if not specified.
  --output-dir          Output directory. Default: <h5file1_dir>/tomo_maps[_ln_ratio/_overlay].
  --no-cartopy          Disable cartopy (use plain matplotlib).
  --dpi                 DPI for saved figures. Default: 150.
"""

import argparse
import warnings
from pathlib import Path
from typing import List, Optional, Tuple, Union

import pandas as pd
import h5py
import matplotlib.pyplot as plt
import numpy as np

# Suppress specific pandas warning about dtype_backend
warnings.filterwarnings(
    "ignore", message="The behavior of DatetimeProperties.to_pydatetime is deprecated", category=FutureWarning
)


# Optional Cartopy
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAS_CARTOPY = True
except ImportError:
    HAS_CARTOPY = False
    print("⚠️  Cartopy not found. Install with: pip install cartopy")
    print("   Falling back to basic matplotlib plots without geographic features.")


# ----------------------------
# Longitude helpers / extents
# ----------------------------
def lons_centered_180(lon: np.ndarray) -> np.ndarray:
    """Convert longitudes to the native range of PlateCarree(lon_0=180): [-180, 180)."""
    lon = np.asarray(lon, dtype=float)
    return ((lon - 180.0 + 180.0) % 360.0) - 180.0

def choose_projection_and_extent(lats: np.ndarray, lons: np.ndarray) -> Tuple[object, object, Tuple[float, float, float, float], object]:
    """
    Decide projection and compute a *tight*, seam-safe extent.
    Returns (ax_crs, data_crs, extent, extent_crs).
    """
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)

    data_crs = ccrs.PlateCarree() if HAS_CARTOPY else None

    pad_lon = 2.0
    pad_lat = 2.0
    minlat = max(-90.0, float(np.nanmin(lats)) - pad_lat)
    maxlat = min( 90.0, float(np.nanmax(lats)) + pad_lat)

    lon_min = float(np.nanmin(lons))
    lon_max = float(np.nanmax(lons))
    has_over_180 = lon_max > 180.0
    has_negative = lon_min < 0.0
    # Check if the range crosses *either* 0/360 or +/-180
    crosses_seam = (lon_max - lon_min) > 180.0 or has_over_180 or has_negative

    # Critical: never let extent hit the seam exactly
    eps = 1e-6

    if crosses_seam and HAS_CARTOPY:
        # If data seems to cross the dateline, center projection on 180
        ax_crs = ccrs.PlateCarree(central_longitude=180)
        lons_ax = lons_centered_180(lons) # Convert data lons to projection's coordinates
        minlon_ax = float(np.nanmin(lons_ax))
        maxlon_ax = float(np.nanmax(lons_ax))
        # Pad in the projection's coordinates
        minlon = max(-180.0 + eps, minlon_ax - pad_lon)
        maxlon = min( 180.0 - eps, maxlon_ax + pad_lon)
        extent = (minlon, maxlon, minlat, maxlat)
        extent_crs = ax_crs # Extent is defined in the axes coordinates
    else:
        # Otherwise, use standard PlateCarree centered at 0
        ax_crs = ccrs.PlateCarree() if HAS_CARTOPY else None
        minlon_data = lon_min
        maxlon_data = lon_max
        # Pad in the data's coordinates
        minlon = max(-180.0 + eps, minlon_data - pad_lon)
        maxlon = min( 180.0 - eps, maxlon_data + pad_lon)
        extent = (minlon, maxlon, minlat, maxlat)
        extent_crs = data_crs # Extent is defined in the data coordinates

    return ax_crs, data_crs, extent, extent_crs

# ----------------------------
# HDF5 utilities
# ----------------------------
def load_hdf5_slice(h5_path: Path, elevation_key: str, scalar: str = "vp") -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load a single elevation slice; mask known fill values."""
    try:
        with h5py.File(h5_path, "r") as f:
            if elevation_key not in f:
                raise KeyError(f"Elevation key '{elevation_key}' not found in {h5_path}")
            grp = f[elevation_key]
            # Load lat/lon only if needed later, handle potential absence
            lat = grp.get("latitudes", None)
            lon = grp.get("longitudes", None)
            if lat is None or lon is None:
                 # Attempt to load from root if missing in group (less common structure)
                 lat = f.get("latitudes", None) if lat is None else lat
                 lon = f.get("longitudes", None) if lon is None else lon
                 if lat is None or lon is None:
                     raise KeyError(f"Latitude or Longitude dataset not found in group '{elevation_key}' or root of {h5_path}")
            lat = lat[:] # Load into memory
            lon = lon[:]

            if scalar not in grp:
                 raise KeyError(f"Scalar '{scalar}' not found in group '{elevation_key}' in {h5_path}")
            data = grp[scalar][:]
    except Exception as e:
        print(f"❌ Error loading HDF5 slice: {h5_path} [{elevation_key}/{scalar}]")
        raise e

    # Always mask standard fill values
    data = np.where(data == -999.0, np.nan, data)

    return lat, lon, data

def get_common_elevations(h5_path1: Path, h5_path2: Path) -> List[str]:
    """Find elevation keys present in both HDF5 files."""
    keys1 = set(get_all_elevations(h5_path1))
    keys2 = set(get_all_elevations(h5_path2))
    common = sorted(list(keys1.intersection(keys2)), key=lambda k: float(k.replace('_','.')), reverse=True)
    if not common:
        warnings.warn(f"⚠️ No common elevation keys found between {h5_path1.name} and {h5_path2.name}")
    return common

def get_all_elevations(h5_path: Path) -> List[str]:
    """Return all numeric group keys sorted by float value (highest first)."""
    try:
        with h5py.File(h5_path, "r") as f:
            # Attempt to convert keys to float, filter out non-numeric keys
            numeric_keys = []
            for k in f.keys():
                try:
                    # Allow underscore for negative decimals e.g., -0_50 -> -0.50
                    float(k.replace('_','.'))
                    numeric_keys.append(k)
                except ValueError:
                    continue # Skip non-numeric keys
        # Sort the valid numeric keys numerically (descending)
        return sorted(numeric_keys, key=lambda k: float(k.replace('_','.')), reverse=True)
    except Exception as e:
        print(f"❌ Error reading keys from HDF5 file: {h5_path}")
        raise e

def detect_elevations_from_csv(
    csv_path: Path,
    depth_col: Union[str, int],
    depth_is_elevation: bool = False,
    skip_rows: int = 0,
    separator: str = ',',
    chunksize: int = 100000,
) -> List[str]:
    """
    Detect unique elevation values from CSV file.
    Returns sorted list of elevation strings (highest first).
    """
    print(f"🔍 Detecting elevations from CSV file: {csv_path.name}...")
    
    try:
        # Read header
        header_df = pd.read_csv(csv_path, nrows=0, skiprows=skip_rows, sep=separator)
        
        # Determine column name
        if isinstance(depth_col, int):
            if depth_col >= len(header_df.columns):
                raise ValueError(f"Column index {depth_col} is out of bounds")
            col_name = header_df.columns[depth_col]
        else:
            col_name = depth_col
        
        # Read depth/elevation column in chunks
        unique_values = set()
        iterator = pd.read_csv(
            csv_path,
            chunksize=chunksize,
            usecols=[col_name],
            skiprows=skip_rows + 1,
            sep=separator,
            header=None,
            names=header_df.columns,
            low_memory=True,
        )
        
        for chunk in iterator:
            # Convert to numeric
            chunk[col_name] = pd.to_numeric(chunk[col_name], errors='coerce')
            chunk.dropna(subset=[col_name], inplace=True)
            
            # Convert to elevation (positive up)
            if depth_is_elevation:
                elevations = chunk[col_name].values
            else:
                elevations = -chunk[col_name].values
            
            # Add unique rounded values (to nearest 0.01)
            unique_values.update(np.round(elevations, 2))
        
        # Sort and format as strings
        sorted_elevations = sorted(list(unique_values), reverse=True)
        elevation_strings = [str(e).replace('.', '_') if e < 0 else str(e) for e in sorted_elevations]
        
        print(f"   Found {len(elevation_strings)} unique elevations: {sorted_elevations[:10]}{'...' if len(sorted_elevations) > 10 else ''}")
        
        return elevation_strings
        
    except Exception as e:
        print(f"❌ Error detecting elevations from CSV: {e}")
        raise e


def calculate_global_ln_ratio_limits(
    h5_path1: Path, h5_path2: Path, scalar: str, elevations: List[str]
) -> Tuple[float, float]:
    """Calculate symmetric natural log ratio limits across specified elevations."""
    print(f"📊 Calculating global symmetric Ln Ratio limits for {scalar}...")
    max_abs_ln_ratio = 0.0
    found_valid_ratio = False

    for elev in elevations:
        try:
            _, _, data1 = load_hdf5_slice(h5_path1, elev, scalar)
            _, _, data2 = load_hdf5_slice(h5_path2, elev, scalar)

            if data1.shape != data2.shape:
                print(f"   Skipping elevation {elev}: Shape mismatch {data1.shape} vs {data2.shape}")
                continue

            with np.errstate(divide='ignore', invalid='ignore'):
                valid_mask = (data1 > 0) & (data2 > 0) & ~np.isnan(data1) & ~np.isnan(data2)
                if np.any(valid_mask):
                    # Use natural log
                    ln_ratios = np.log(data2[valid_mask] / data1[valid_mask])
                    current_max = np.nanmax(np.abs(ln_ratios))
                    if np.isfinite(current_max): # Ensure we don't get inf/nan
                        max_abs_ln_ratio = max(max_abs_ln_ratio, current_max)
                        found_valid_ratio = True
                else:
                    print(f"   Skipping elevation {elev}: No valid data points for ratio calculation.")

        except KeyError as e:
             print(f"   Skipping elevation {elev}: Missing data - {e}")
        except Exception as e:
            print(f"   Skipping elevation {elev}: Error calculating ratio - {e}")

    if not found_valid_ratio:
         print("   No valid ratios found across any elevation. Using default limits [-1, 1].")
         return -1.0, 1.0

    # Ensure a minimum range if max_abs_ln_ratio is very small
    limit = max(max_abs_ln_ratio, 0.1) # Set a minimum half-range of 0.1
    vmin, vmax = -limit, limit
    print(f"   Global symmetric range: [{vmin:.3f} .. {vmax:.3f}]")
    return vmin, vmax


def determine_global_limits(
    h5_path: Path,
    scalar: str,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    percentile: float = 2.0,
) -> Tuple[float, float]:
    """Percentile-based global color limits unless user overrides."""
    if vmin is not None and vmax is not None:
        # If user provides limits, validate them
        if vmin >= vmax:
             warnings.warn(f"User specified vmin ({vmin}) >= vmax ({vmax}). Swapping them.", UserWarning)
             vmin, vmax = vmax, vmin
        return vmin, vmax

    print(f"📊 Calculating global {scalar} limits...")
    vals = []
    elevations = get_all_elevations(h5_path)
    if not elevations:
         print("   No numeric elevation groups found. Using default limits [0, 1].")
         return (0.0, 1.0)

    try:
        with h5py.File(h5_path, "r") as f:
            for k in elevations:
                if k in f and scalar in f[k]:
                    arr = f[k][scalar][:]
                    # Mask fill values before calculating percentiles
                    mask = (arr != -999.0) & ~np.isnan(arr)
                    arr = arr[mask]
                    if arr.size > 0:
                        vals.append(arr.ravel())
                else:
                    print(f"   Skipping group/scalar: {k}/{scalar}")

        if not vals:
            print("   No valid data found across elevations. Using default limits [0, 1].")
            return (0.0, 1.0)

        vals = np.concatenate(vals)
        if vals.size == 0:
             print("   No valid numeric data found. Using default limits [0, 1].")
             return (0.0, 1.0)

        # Calculate percentile limits
        calc_vmin = float(np.percentile(vals, percentile))
        calc_vmax = float(np.percentile(vals, 100 - percentile))

        # If limits are identical or inverted, use min/max
        if calc_vmin >= calc_vmax:
            calc_vmin = float(np.min(vals))
            calc_vmax = float(np.max(vals))
        # If still identical (e.g., constant value), add a small buffer
        if np.isclose(calc_vmin, calc_vmax):
            calc_vmin -= 0.1
            calc_vmax += 0.1

        # Assign final limits (respecting user input from the start)
        final_vmin = vmin if vmin is not None else calc_vmin
        final_vmax = vmax if vmax is not None else calc_vmax

        # Ensure vmin < vmax (final check after calculation)
        if final_vmin >= final_vmax:
             print(f"   Warning: Calculated limits are invalid ({final_vmin:.3f} >= {final_vmax:.3f}). Adjusting.")
             mid = (final_vmin + final_vmax) / 2.0
             final_vmin = mid - 0.5
             final_vmax = mid + 0.5

        print(f"   Global range: {final_vmin:.3f} .. {final_vmax:.3f}")
        return final_vmin, final_vmax

    except Exception as e:
        print(f"❌ Error calculating global limits for {h5_path}: {e}")
        # Fallback to defaults in case of error
        return (0.0, 1.0)

# ----------------------------
# CSV Data Loading (Fixed for dateline crossing)
# ----------------------------
def load_csv_data_for_elevation(
    csv_path: Path,
    target_elevation_km: float,
    lon_col: Union[str, int],
    lat_col: Union[str, int],
    depth_col: Union[str, int],
    scalar_col: Union[str, int],
    depth_is_elevation: bool = False,
    depth_tolerance_km: float = 0.1,
    skip_rows: int = 0,
    separator: str = ',',
    chunksize: int = 50000,
) -> Optional[pd.DataFrame]:
    """
    Efficiently load relevant points from a large CSV for a specific elevation slice.
    FIXED: Keeps longitudes in their original range (including negative values)
    instead of converting to 0-360. The projection system will handle the transformation.
    """
    print(f"   Loading CSV data near elevation {target_elevation_km:.2f} km from {csv_path.name}...")
    
    required_cols_indices = []
    required_cols_names = []
    use_cols = []
    rename_map = {}

    # Determine column identifiers and final names
    col_map = {
        'lon': lon_col, 'lat': lat_col, 'depth_or_elev': depth_col, 'scalar': scalar_col
    }
    try:
        # Read header potentially skipping rows
        header_df = pd.read_csv(csv_path, nrows=0, skiprows=skip_rows, sep=separator)
    except Exception as e:
        print(f"❌ Error reading CSV header: {csv_path} (skip_rows={skip_rows}, sep='{separator}')")
        raise e


    for name, identifier in col_map.items():
        col_label = {
            'lon': 'Longitude',
            'lat': 'Latitude', 
            'depth_or_elev': 'Depth/Elevation',
            'scalar': 'Scalar Value'
        }[name]
        if isinstance(identifier, int):
            if identifier >= len(header_df.columns):
                 raise ValueError(f"Column index {identifier} is out of bounds for CSV file (has {len(header_df.columns)} columns).")
            col_name = header_df.columns[identifier]
            print(f"      {col_label:20s} (--{name.replace('_', '-'):15s} {identifier}): found column '{col_name}'")
            required_cols_indices.append(identifier)
            required_cols_names.append(col_name)
            use_cols.append(col_name) # Use name for reading chunks
            rename_map[col_name] = name
        elif isinstance(identifier, str):
            if identifier not in header_df.columns:
                 raise ValueError(f"Column name '{identifier}' not found in CSV file header: {list(header_df.columns)}")
            print(f"      {col_label:20s} (--{name.replace('_', '-'):15s} '{identifier}'): found in CSV")
            required_cols_names.append(identifier)
            use_cols.append(identifier)
            rename_map[identifier] = name
        else:
             raise TypeError(f"Invalid column identifier type: {type(identifier)}")

    print(f"   📋 CSV Parsing Debug Info:")
    print(f"      Separator: '{separator}' (use --sep to change)")
    
    # Try to read first data row to show how it's being parsed
    try:
        first_row_df = pd.read_csv(csv_path, nrows=1, skiprows=skip_rows, sep=separator)
        if not first_row_df.empty:
            print(f"      First row parsed as: {first_row_df.columns.tolist()}")
            print(f"      First row values: {first_row_df.iloc[0].tolist()}")
    except:
        pass  # If we can't read first row, just continue
    
    print(f"   📊 Column Mapping:")
    for name, identifier in col_map.items():
        col_label = {
            'lon': 'Longitude',
            'lat': 'Latitude', 
            'depth_or_elev': 'Depth/Elevation',
            'scalar': 'Scalar Value'
        }[name]


    filtered_chunks = []
    # Define elevation range for filtering
    min_elev_km = target_elevation_km - depth_tolerance_km
    max_elev_km = target_elevation_km + depth_tolerance_km
    total_rows_processed = 0

    try:
        iterator = pd.read_csv(
            csv_path,
            chunksize=chunksize,
            usecols=use_cols, # Read only necessary columns
            skiprows=skip_rows + 1, # Skip specified rows + the header row
            sep=separator,
            header=None, # Already read header, prevent reading data rows as header
            names=header_df.columns, # Assign column names manually
            low_memory=True, # Aids memory efficiency
        )

        for chunk in iterator:
            total_rows_processed += len(chunk)
            # Rename columns to standard names
            chunk.rename(columns=rename_map, inplace=True)

            # Convert depth/elevation column to numeric, coercing errors
            chunk['depth_or_elev'] = pd.to_numeric(chunk['depth_or_elev'], errors='coerce')
            chunk.dropna(subset=['depth_or_elev'], inplace=True) # Drop rows where conversion failed

             # Convert CSV value to ELEVATION (km, positive up) for consistent comparison
            if depth_is_elevation:
                chunk['elevation_km'] = chunk['depth_or_elev']
            else: # CSV has depth (positive down)
                chunk['elevation_km'] = -chunk['depth_or_elev']

            # Filter by elevation range (use .copy() to avoid SettingWithCopyWarning)
            chunk_filtered = chunk[
                (chunk['elevation_km'] >= min_elev_km) & (chunk['elevation_km'] <= max_elev_km)
            ].copy()

            if not chunk_filtered.empty:
                 # --- Convert lon/lat/scalar columns, coerce errors ---
                 chunk_filtered.loc[:, 'lon'] = pd.to_numeric(chunk_filtered['lon'], errors='coerce')
                 chunk_filtered.loc[:, 'lat'] = pd.to_numeric(chunk_filtered['lat'], errors='coerce')
                 chunk_filtered.loc[:, 'scalar'] = pd.to_numeric(chunk_filtered['scalar'], errors='coerce')

                 # --- FIXED: Keep longitudes as-is ---
                 # DO NOT convert negative longitudes to 0-360 range
                 # The projection system (choose_projection_and_extent and plotting code)
                 # will handle coordinate transformation properly
                 # --- End longitude handling ---

                 # Drop rows where essential conversions failed
                 chunk_filtered.dropna(subset=['lon', 'lat', 'scalar'], inplace=True)


                 if not chunk_filtered.empty:
                    # Select only needed final columns
                    filtered_chunks.append(chunk_filtered[['lon', 'lat', 'scalar']])
            # Simple progress update (less frequent)
            if total_rows_processed % (chunksize * 50) == 0:
                 print(f"     Processed {total_rows_processed} rows...")


    except FileNotFoundError:
        print(f"❌ Error: CSV file not found: {csv_path}")
        return None
    except Exception as e:
        print(f"❌ Error processing CSV file {csv_path}: {e}")
        return None

    if not filtered_chunks:
        print(f"   No data found within elevation tolerance [{min_elev_km:.2f} - {max_elev_km:.2f} km]")
        return None

    result_df = pd.concat(filtered_chunks, ignore_index=True)
    print(f"   Loaded {len(result_df)} points from CSV near elevation {target_elevation_km:.2f} km.")

    # --- Data Validation ---
    valid_range = (0, 10) # Typical range for vp, vs (km/s), rho (g/cm^3)
    scalar_min, scalar_max = result_df['scalar'].min(), result_df['scalar'].max()
    if not (valid_range[0] <= scalar_min <= valid_range[1] and valid_range[0] <= scalar_max <= valid_range[1]):
         warnings.warn(
             f"CSV scalar values range [{scalar_min:.2f}, {scalar_max:.2f}] seems unusual for vp/vs/rho. "
             f"Expected range ~[0, 10]. Check units and column '{scalar_col}'.", UserWarning
        )
    lat_min, lat_max = result_df['lat'].min(), result_df['lat'].max()
    lon_min, lon_max = result_df['lon'].min(), result_df['lon'].max()
    if not (-90 <= lat_min <= 90 and -90 <= lat_max <= 90):
        warnings.warn(f"CSV latitude values range [{lat_min:.2f}, {lat_max:.2f}] is outside [-90, 90]. Check column '{lat_col}'.", UserWarning)
    # Updated lon validation - accept any range including negative values
    if not (-180 <= lon_min <= 360 and -180 <= lon_max <= 360):
         warnings.warn(f"CSV longitude values range [{lon_min:.2f}, {lon_max:.2f}] seems unusual. Check column '{lon_col}'.", UserWarning)


    return result_df


# ----------------------------
# Plotting
# ----------------------------
def create_map_plot(
    lat: np.ndarray, # HDF5 lat grid
    lon: np.ndarray, # HDF5 lon grid
    data: np.ndarray, # HDF5 data slice
    elevation: str,
    scalar: str,
    vmin: float,
    vmax: float,
    cmap: str = "RdYlBu_r",
    figsize: tuple = (10, 8),
    use_cartopy: bool = True,
    add_cities: bool = True,
    is_ratio: bool = False,
    csv_overlay_data: Optional[pd.DataFrame] = None,
    base_filename: str = "",
    compared_filename: str = "",
    csv_only: bool = False,
    no_outline_marker: bool = False,
):
    """Create a single map plot with optional CSV overlay, ensuring extent covers both datasets.
    
    If csv_only=True, only CSV scatter points are plotted without HDF5 background.
    """
    lon_grid, lat_grid = np.meshgrid(lon, lat) # Create 2D grids for HDF5 data

    if use_cartopy and HAS_CARTOPY:
        # --- Combine HDF5 and CSV coordinates BEFORE choosing projection ---
        # In csv-only mode, prioritize CSV data for projection/extent decision
        if csv_only and csv_overlay_data is not None and not csv_overlay_data.empty:
            # Use only CSV data for projection decision in csv-only mode
            all_lons_combined = csv_overlay_data['lon'].values
            all_lats_combined = csv_overlay_data['lat'].values
        else:
            # Normal mode: combine HDF5 and CSV data
            all_lons_combined = lon_grid.ravel()
            all_lats_combined = lat_grid.ravel()
            
            if csv_overlay_data is not None and not csv_overlay_data.empty:
                csv_lons = csv_overlay_data['lon'].values
                csv_lats = csv_overlay_data['lat'].values
                # Combine all coordinates for projection decision
                all_lons_combined = np.concatenate([all_lons_combined, csv_lons])
                all_lats_combined = np.concatenate([all_lats_combined, csv_lats])
        
        # Choose projection based on COMBINED dataset
        ax_crs, data_crs, extent, extent_crs = choose_projection_and_extent(all_lats_combined, all_lons_combined)

        # --- Setup Plot ---
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(1, 1, 1, projection=ax_crs)

        # --- Set map extent ---
        ax.set_extent(extent, crs=extent_crs)

        # --- Transform HDF5 grid coordinates ---
        if getattr(ax_crs, 'central_longitude', 0) == 180:
            lon_plot_h5 = lons_centered_180(lon_grid)
            plot_crs_h5 = ax_crs
        else:
            lon_plot_h5 = lon_grid
            plot_crs_h5 = data_crs

        # --- Base map features ---
        ax.coastlines(resolution="10m", linewidth=0.5, color="black", zorder=3)
        ax.add_feature(cfeature.BORDERS, linewidth=0.3, edgecolor="gray", zorder=3)
        ax.add_feature(cfeature.LAND, facecolor="whitesmoke", zorder=0)
        ax.add_feature(cfeature.OCEAN, facecolor="aliceblue", zorder=0)

        # --- HDF5 Data (Pcolormesh) ---
        if not csv_only:
            valid_data_mask = ~np.isnan(data)
            im = ax.pcolormesh(
                lon_plot_h5, lat_grid, np.where(valid_data_mask, data, np.nan),
                transform=plot_crs_h5,
                cmap=cmap, vmin=vmin, vmax=vmax,
                shading="auto", zorder=1
            )
        else:
            # For csv_only mode, create a dummy mappable for colorbar
            import matplotlib.cm as cm
            norm = plt.Normalize(vmin=vmin, vmax=vmax)
            im = cm.ScalarMappable(norm=norm, cmap=cmap)


        # --- CSV Overlay Data (Scatter) ---
        if csv_overlay_data is not None and not csv_overlay_data.empty:
            csv_lons_raw = csv_overlay_data['lon'].values
            csv_lats = csv_overlay_data['lat'].values
            
            # Transform CSV points to match the axes projection
            if getattr(ax_crs, 'central_longitude', 0) == 180:
                csv_lons_plot = lons_centered_180(csv_lons_raw)
                csv_crs_transform = ax_crs
            else:
                csv_lons_plot = csv_lons_raw
                csv_crs_transform = data_crs

            csv_vals_clipped = np.clip(csv_overlay_data['scalar'].values, vmin, vmax)

            # Set marker properties based on no_outline_marker flag
            if no_outline_marker:
                edge_color = 'none'
                edge_width = 0
            else:
                edge_color = 'black'
                edge_width = 0.25

            scatter = ax.scatter(
                csv_lons_plot, csv_lats, c=csv_vals_clipped,
                cmap=cmap, vmin=vmin, vmax=vmax,
                s=5, edgecolor=edge_color, linewidth=edge_width, alpha=0.7,
                transform=csv_crs_transform,
                zorder=2
            )


        # --- Gridlines ---
        gl = ax.gridlines(draw_labels=True, linewidth=0.5, color="gray", alpha=0.5, linestyle="--")
        gl.top_labels = False
        gl.right_labels = False

        # --- Optional Cities ---
        if add_cities and extent is not None and -48 < extent[2] < -34:
            cities = {
                "Wellington": (174.776, -41.287), "Auckland": (174.763, -36.848),
                "Christchurch": (172.636, -43.532), "Dunedin": (170.503, -45.879),
            }
            city_lons = np.array([c[0] for c in cities.values()])
            city_lats = np.array([c[1] for c in cities.values()])

            if getattr(ax_crs, 'central_longitude', 0) == 180:
                city_lons_plot = lons_centered_180(city_lons)
                city_crs = ax_crs
            else:
                city_lons_plot = city_lons
                city_crs = data_crs

            ax.plot(city_lons_plot, city_lats, 'ko', ms=3, transform=city_crs, zorder=4)
            for i, name in enumerate(cities.keys()):
                 if extent[0] <= city_lons_plot[i] <= extent[1] and \
                    extent[2] <= city_lats[i] <= extent[3]:
                    ax.text(city_lons_plot[i] + 0.1, city_lats[i], name, fontsize=8, transform=city_crs, zorder=4)


    else:
        # --- Non-cartopy fallback ---
        fig, ax = plt.subplots(figsize=figsize)

        # Calculate extent
        min_lon_h5, max_lon_h5 = np.nanmin(lon_grid), np.nanmax(lon_grid)
        min_lat_h5, max_lat_h5 = np.nanmin(lat_grid), np.nanmax(lat_grid)
        min_lon_final, max_lon_final = min_lon_h5, max_lon_h5
        min_lat_final, max_lat_final = min_lat_h5, max_lat_h5

        if csv_overlay_data is not None and not csv_overlay_data.empty:
             min_lon_final = min(min_lon_final, csv_overlay_data['lon'].min())
             max_lon_final = max(max_lon_final, csv_overlay_data['lon'].max())
             min_lat_final = min(min_lat_final, csv_overlay_data['lat'].min())
             max_lat_final = max(max_lat_final, csv_overlay_data['lat'].max())

        if not csv_only:
            valid_data_mask = ~np.isnan(data)
            im = ax.pcolormesh(
                lon_grid, lat_grid, np.where(valid_data_mask, data, np.nan),
                cmap=cmap, vmin=vmin, vmax=vmax, shading="auto"
            )
        else:
            # For csv_only mode, create a dummy mappable for colorbar
            import matplotlib.cm as cm
            norm = plt.Normalize(vmin=vmin, vmax=vmax)
            im = cm.ScalarMappable(norm=norm, cmap=cmap)

        if csv_overlay_data is not None and not csv_overlay_data.empty:
            csv_vals_clipped = np.clip(csv_overlay_data['scalar'].values, vmin, vmax)
            
            # Set marker properties based on no_outline_marker flag
            if no_outline_marker:
                edge_color = 'none'
                edge_width = 0
            else:
                edge_color = 'black'
                edge_width = 0.25
            
            scatter = ax.scatter(
                csv_overlay_data['lon'], csv_overlay_data['lat'], c=csv_vals_clipped,
                cmap=cmap, vmin=vmin, vmax=vmax,
                s=5, edgecolor=edge_color, linewidth=edge_width, alpha=0.7
            )

        ax.set_xlim(min_lon_final, max_lon_final)
        ax.set_ylim(min_lat_final, max_lat_final)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
        ax.set_aspect("equal", adjustable="box")


    # --- Colorbar ---
    cbar = plt.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    if is_ratio:
        cbar.set_label(f"ln({compared_filename} / {base_filename}) {scalar}", fontsize=10)
    else:
        cbar.set_label(f"{scalar.upper()} (km/s)" if scalar in ["vp", "vs"] else f"{scalar.upper()}", fontsize=10)

    # --- Title ---
    elev_float_str = f"{float(elevation.replace('_','.')):.2f}"
    n_csv = len(csv_overlay_data) if csv_overlay_data is not None and not csv_overlay_data.empty else 0
    if is_ratio:
        title = f"Ln Ratio of {scalar.upper()} at {elev_float_str} km elevation"
    elif csv_only:
        title = f"{scalar.upper()} from CSV data at {elev_float_str} km elevation ({n_csv} points)"
    elif csv_overlay_data is not None:
        title = f"{scalar.upper()} (km/s) at {elev_float_str} km elevation (with {n_csv} CSV points overlay)"
    else:
        title = f"{scalar.upper()} (km/s) at {elev_float_str} km elevation"
    
    ax.set_title(title, fontsize=12, pad=10)

    return fig, ax


# ----------------------------
# Main
# ----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="2D Map Viewer for Tomography Data with Ratio and CSV Overlay Capabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("h5file1", type=Path, nargs='?', help="Path to the primary (base) HDF5 tomography file (optional when using --csv-only).")
    parser.add_argument("--compared", type=Path, help="Path to the second HDF5 file for ratio comparison.")
    parser.add_argument("--with-csv", type=Path, dest="csv_data", help="Path to CSV file to overlay on HDF5 data.")
    parser.add_argument("--csv-only", type=Path, dest="csv_only_file", help="Path to CSV file to plot without HDF5 background (HDF5 file not required).")
    parser.add_argument("--lon-col", help="Column name or index for longitude in the CSV file.")
    parser.add_argument("--lat-col", help="Column name or index for latitude in the CSV file.")
    parser.add_argument("--depth-col", help="Column name or index for depth/elevation in the CSV file.")
    parser.add_argument("--depth-is-elevation", action="store_true",
                        help="Flag if the depth column in CSV represents elevation (positive up).")
    parser.add_argument("--scalar-col", help="Column name or index for the scalar value in the CSV file.")
    parser.add_argument("--depth-tolerance", type=float, default=0.1,
                        help="Tolerance (in km) for matching CSV points to H5 elevations (default: 0.1).")
    parser.add_argument("--skip-rows", type=int, default=0,
                        help="Number of rows to skip at the beginning of the CSV file (default: 0).")
    parser.add_argument("--sep", type=str, default=',',
                        help="Delimiter used in the CSV file (default: ',').")
    parser.add_argument("--scalar", type=str, default="vp", choices=["vp", "vs", "rho"],
                        help="Scalar field to plot (default: vp).")
    parser.add_argument("--vmin", type=float, help="Minimum for color scale.")
    parser.add_argument("--vmax", type=float, help="Maximum for color scale.")
    parser.add_argument("--cmap", type=str, help="Matplotlib colormap name.")
    parser.add_argument("--elevations", type=str, nargs="+",
                        help="Specific elevations (km) to plot from the HDF5 file.")
    parser.add_argument("--auto-elevations", action="store_true",
                        help="Automatically detect elevations from CSV data (for --csv-only mode).")
    parser.add_argument("--output-dir", type=Path, help="Output directory for saved plots.")
    parser.add_argument("--no-cartopy", action="store_true", help="Disable cartopy.")
    parser.add_argument("--no-outline-marker", action="store_true", help="Remove black outline from CSV scatter points (use when data is very dense).")
    parser.add_argument("--dpi", type=int, default=150, help="DPI for saved figures (default: 150).")

    args = parser.parse_args()

    # --- Validate h5file1 requirement ---
    csv_only_mode = args.csv_only_file is not None
    
    # Check for conflicting CSV options first
    if args.csv_data and args.csv_only_file:
        raise SystemExit("❌ Cannot use both --with-csv and --csv-only. Choose one.")
    
    if args.h5file1 is None and not csv_only_mode:
        raise SystemExit("❌ HDF5 file (h5file1) is required unless using --csv-only mode.")
    
    if args.h5file1 is not None and not args.h5file1.exists():
        raise SystemExit(f"❌ HDF5 file not found: {args.h5file1}")

    # --- Mode Detection and Validation ---
    is_ratio_mode = args.compared is not None
    is_overlay_mode = args.csv_data is not None
    
    # Handle --csv-only: it sets csv_data internally and enables csv-only mode
    if csv_only_mode:
        args.csv_data = args.csv_only_file
        is_overlay_mode = True  # Treat as overlay mode internally

    if is_ratio_mode and is_overlay_mode:
        raise SystemExit("❌ Cannot use --compared with --with-csv or --csv-only simultaneously. Choose one mode.")

    if is_ratio_mode:
        if not args.compared.exists():
            raise SystemExit(f"❌ Compared HDF5 file not found: {args.compared}")
        print("📊 Ratio Mode Enabled (ln(compared / base))")
        default_cmap = "seismic"
        output_suffix = "_ln_ratio"
        common_elevations = get_common_elevations(args.h5file1, args.compared)
        if not common_elevations:
            raise SystemExit("❌ No common elevations found between HDF5 files for ratio plot.")
        print(f"   Found {len(common_elevations)} common elevations.")

    elif is_overlay_mode:
        if not args.csv_data.exists():
            raise SystemExit(f"❌ CSV data file not found: {args.csv_data}")
        required_csv_cols = [args.lon_col, args.lat_col, args.depth_col, args.scalar_col]
        if any(c is None for c in required_csv_cols):
             raise SystemExit("❌ For CSV overlay (--with-csv or --csv-only), you must specify --lon-col, --lat-col, --depth-col, and --scalar-col.")
        if csv_only_mode:
            print("📍 CSV-Only Mode Enabled (plotting CSV data without HDF5 background)")
        else:
            print("📍 CSV Overlay Mode Enabled (overlaying CSV on HDF5 data)")
        default_cmap = "RdYlBu_r"
        output_suffix = "_csv_only" if csv_only_mode else "_overlay"

        # Parse column specs
        def parse_col_spec(spec):
            if spec is None: return None
            try: return int(spec)
            except ValueError: return spec
        args.lon_col = parse_col_spec(args.lon_col)
        args.lat_col = parse_col_spec(args.lat_col)
        args.depth_col = parse_col_spec(args.depth_col)
        args.scalar_col = parse_col_spec(args.scalar_col)

    else:
        print("📄 Standard Plot Mode Enabled")
        default_cmap = "RdYlBu_r"
        output_suffix = ""

    cmap = args.cmap or default_cmap

    # --- Determine Output Directory ---
    if args.output_dir:
        out_dir = args.output_dir
    else:
        if args.h5file1 is not None:
            out_dir = args.h5file1.parent / f"tomo_maps{output_suffix}"
        else:
            # csv-only mode without h5 file
            out_dir = Path.cwd() / f"tomo_maps{output_suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Determine HDF5 Elevations to Plot ---
    if csv_only_mode and args.h5file1 is None:
        # CSV-only mode without HDF5
        if args.auto_elevations:
            # Auto-detect elevations from CSV
            elevations_to_plot = detect_elevations_from_csv(
                args.csv_data,
                args.depth_col,
                args.depth_is_elevation,
                args.skip_rows,
                args.sep
            )
            if not elevations_to_plot:
                raise SystemExit("❌ No elevations found in CSV file.")
        elif args.elevations:
            # User specified elevations
            elevations_to_plot = args.elevations
        else:
            raise SystemExit("❌ When using --csv-only without an HDF5 file, you must specify --elevations or use --auto-elevations.")
    elif args.elevations:
        elevations_to_plot = args.elevations
        if args.h5file1 is not None:
            available_elevations = get_all_elevations(args.h5file1)
            valid_user_elevations = [e for e in elevations_to_plot if e in available_elevations]
            invalid_user_elevations = [e for e in elevations_to_plot if e not in available_elevations]
            if invalid_user_elevations:
                print(f"⚠️ Warning: Specified elevations not found in {args.h5file1.name}: {invalid_user_elevations}")
            if not valid_user_elevations:
                 raise SystemExit(f"❌ None of the specified HDF5 elevations were found in {args.h5file1.name}.")
            elevations_to_plot = valid_user_elevations
            if is_ratio_mode:
                elevations_to_plot = [e for e in elevations_to_plot if e in common_elevations]
                if not elevations_to_plot:
                    raise SystemExit("❌ None of the specified elevations are common to both files.")

    elif is_ratio_mode:
        elevations_to_plot = common_elevations
        if not elevations_to_plot:
             raise SystemExit("❌ No common elevations found between HDF5 files for ratio plot.")
    else:
        elevations_to_plot = get_all_elevations(args.h5file1)
        if not elevations_to_plot:
             raise SystemExit(f"❌ No numeric elevation groups found in {args.h5file1}.")

    print(f"📍 Plotting {len(elevations_to_plot)} HDF5 elevation slice(s). Output → {out_dir}")

    # --- Determine Global Color Limits ---
    if is_ratio_mode:
        plot_vmin, plot_vmax = calculate_global_ln_ratio_limits(args.h5file1, args.compared, args.scalar, elevations_to_plot)
        if args.vmin is not None or args.vmax is not None:
             print("   Note: User-specified --vmin/--vmax are ignored for ratio plots. Using calculated symmetric range.")
    elif csv_only_mode and args.h5file1 is None:
        # CSV-only mode without HDF5: use provided limits or defaults
        if args.vmin is not None and args.vmax is not None:
            plot_vmin, plot_vmax = args.vmin, args.vmax
            print(f"📊 Using user-specified {args.scalar} limits: {plot_vmin:.3f} .. {plot_vmax:.3f}")
        else:
            # Use typical defaults for seismic velocities
            if args.scalar == 'vs':
                plot_vmin, plot_vmax = 0.0, 5.0
            elif args.scalar == 'vp':
                plot_vmin, plot_vmax = 0.0, 9.0
            elif args.scalar == 'rho':
                plot_vmin, plot_vmax = 1.0, 4.0
            else:
                plot_vmin, plot_vmax = 0.0, 10.0
            print(f"📊 Using default {args.scalar} limits: {plot_vmin:.3f} .. {plot_vmax:.3f}")
            print(f"   (Specify --vmin and --vmax to override)")
    else:
        plot_vmin, plot_vmax = determine_global_limits(args.h5file1, args.scalar, args.vmin, args.vmax)


    use_cartopy = HAS_CARTOPY and not args.no_cartopy

    # --- Main Plotting Loop ---
    for i, elev in enumerate(elevations_to_plot):
        elev_float_str = f"{float(elev.replace('_','.')):.2f}"
        print(f"\nProcessing HDF5 elevation: {elev_float_str} km ({i+1}/{len(elevations_to_plot)})")
        csv_data_slice = None

        try:
            # --- Load HDF5 Data (skip if csv-only mode) ---
            if csv_only_mode and args.h5file1 is None:
                # CSV-only mode: create dummy lat/lon arrays, will use CSV extent
                lat1 = np.array([0.0])
                lon1 = np.array([0.0])
                data1 = np.array([[np.nan]])
                plot_data = data1
                lat, lon = lat1, lon1
            else:
                lat1, lon1, data1 = load_hdf5_slice(args.h5file1, elev, args.scalar)

                if is_ratio_mode:
                    lat2, lon2, data2 = load_hdf5_slice(args.compared, elev, args.scalar)
                    with np.errstate(divide='ignore', invalid='ignore'):
                        valid_mask = (data1 > 0) & (data2 > 0) & ~np.isnan(data1) & ~np.isnan(data2)
                        ratio_data = np.full(data1.shape, np.nan)
                        ratio_data[valid_mask] = np.log(data2[valid_mask] / data1[valid_mask])
                    plot_data = ratio_data
                    lat, lon = lat1, lon1

                else:
                    plot_data = data1
                    lat, lon = lat1, lon1

            # --- Load CSV Data (if overlay or csv-only mode) ---
            if is_overlay_mode or csv_only_mode:
                 try:
                    target_elev_float = float(elev.replace('_','.'))
                    csv_data_slice = load_csv_data_for_elevation(
                        args.csv_data, target_elev_float,
                        args.lon_col, args.lat_col, args.depth_col, args.scalar_col,
                        args.depth_is_elevation, args.depth_tolerance,
                        args.skip_rows, args.sep
                    )
                 except Exception as csv_e:
                     print(f"   ❌ Error loading CSV data for elevation {elev}: {csv_e}")
                     csv_data_slice = None


            # --- Create Plot ---
            fig, ax = create_map_plot(
                lat, lon, plot_data, elevation=elev, scalar=args.scalar,
                vmin=plot_vmin, vmax=plot_vmax, cmap=cmap, use_cartopy=use_cartopy,
                is_ratio=is_ratio_mode,
                csv_overlay_data=csv_data_slice,
                base_filename=args.h5file1.name if args.h5file1 else "csv_data",
                compared_filename=args.compared.name if args.compared else "",
                csv_only=csv_only_mode,
                no_outline_marker=args.no_outline_marker
            )

            # --- Save Plot ---
            elev_str_fname = elev.replace("_",".")
            if is_ratio_mode:
                 outfile = out_dir / f"ln_ratio_{args.scalar}_elev{elev_str_fname}.png"
            elif csv_only_mode:
                 outfile = out_dir / f"csv_only_{args.scalar}_elev{elev_str_fname}.png"
            elif is_overlay_mode:
                 outfile = out_dir / f"overlay_{args.scalar}_elev{elev_str_fname}.png"
            else:
                 outfile = out_dir / f"{args.scalar}_elev{elev_str_fname}.png"

            fig.savefig(outfile, dpi=args.dpi, bbox_inches='tight')
            plt.close(fig)
            print(f"   ✅ Saved: {outfile}")

        except KeyError as e:
            print(f"   ❌ Skipping HDF5 elevation {elev}: {e}")
        except Exception as e:
            print(f"   ❌ An unexpected error occurred for HDF5 elevation {elev}: {e}")

    print("\n✨ Done.")

if __name__ == "__main__":
    main()
