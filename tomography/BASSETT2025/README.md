# BASSETT2025 Hikurangi Tomography Data

## Overview

This directory contains the Hikurangi 3D tomography model from Bassett et al. (2025), converted to NZCVM-compatible HDF5 format.

## Data Processing Output

The following output shows the analysis and conversion process:

```
(py312) seb56@mantle:/mnt/mantle_data/seb56/tomo_conversion/Bassett$ python analyze_and_convert_hikurangi2.py 
======================================================================
HIKURANGI TOMOGRAPHY CONVERSION
======================================================================
📥 Reading Hikurangi data...
   Total points: 33,289,947

======================================================================
UNIT DETECTION AND VERIFICATION
======================================================================

Raw value ranges (excluding near-zero values):
   Vp:  min=0.350, max=9.000, median=7.970
   Vs:  min=0.150, max=5.350, median=4.550
   Rho: min=1001.000, max=3170.000, median=3150.000

======================================================================
UNIT DETECTION RESULTS:
======================================================================

VELOCITY UNITS:
   ✅ Vp and Vs appear to be in km/s
      (Vp median 7.97 km/s, Vs median 4.55 km/s)

DENSITY UNITS:
   ⚠️  Density appears to be in kg/m³ (NOT g/cm³!)
      (median 3150 kg/m³)
   🔄 Will convert to g/cm³ by dividing by 1000

DATA QUALITY CHECKS:
   Very low Vp (<1.0): 948,814 points (2.9%)
   Very low Vs (<0.3): 948,814 points (2.9%)
   ℹ️  Note: Many low velocity values detected.
      These might be:
      - Water layer (Vp~1.5 km/s, Vs~0)
      - Very soft sediments
      - Flag/placeholder values
      - Incorrect units

======================================================================
⚠️  CONVERSION WILL BE APPLIED:
   Vp: multiply by 1.0
   Vs: multiply by 1.0
   Rho: multiply by 0.001
======================================================================

🔄 Applying unit conversions...
   ✅ Conversions applied
   New Vp range: 0.350 to 9.000 km/s
   New Vs range: 0.150 to 5.350 km/s
   New Rho range: 1.001 to 3.170 g/cm³
```

## Grid Structure Analysis

```
======================================================================
GRID STRUCTURE ANALYSIS
======================================================================

1. ORIENTATION & COORDINATE SYSTEM:
   Model X range: -400.0 to 240.0 km
   Model Y range: -550.0 to 450.0 km
   Number of unique X values: 321
   Number of unique Y values: 501
   X spacing regular: True
   X spacing: 2.000 km
   Y spacing regular: True
   Y spacing: 2.000 km

2. GEOGRAPHIC DOMAIN:
   ⚠️  Data crosses 180° dateline!
   Raw longitude: -180.000°E to 180.000°E (spans 360.0°)
   Adjusted to: 169.299°E to 182.146°E (0-360 range)
   Latitude: -45.037°S to -34.357°S
   Span: 12.847° lon × 10.680° lat

3. DEPTH LEVELS:
   Number of depth levels: 207
   Depth range: -3.00 to 100.00 km
   Depth spacing regular: True
   Depth spacing: 0.500 km
   First 10 depths: [-3.  -2.5 -2.  -1.5 -1.  -0.5  0.   0.5  1.   1.5]
   Last 10 depths: [ 95.5  96.   96.5  97.   97.5  98.   98.5  99.   99.5 100. ]

4. POINTS PER DEPTH LEVEL:
   Min points: 160,821
   Max points: 160,821
   Mean points: 160,821
   Consistent: True

5. ROTATION ANALYSIS:
   Estimated rotation: -38.8° (approximate)

6. PARAMETER SUMMARY:
   Vp: 0.350 to 9.000 km/s
   Vs: 0.150 to 5.350 km/s
   Vp/Vs: 1.580 to 2.350
   Density: 1.001 to 3.170 g/cm³

7. DATA CONSTRAINT:
   Constrained points (flag=1): 3,220,637 (9.7%)
   Unconstrained points (flag=0): 30,069,310 (90.3%)
```

## Target Grid Configuration

```
======================================================================
EP2020 REFERENCE GRID
======================================================================

Grid dimensions: 1400 × 800 × 25
Latitude: -48.000°S to -33.000°S
Longitude: 165.000°E to 180.000°E
Depths: 25 levels from -750 to 15 km
Latitude spacing: -0.0107° (-1.19 km)
Longitude spacing: 0.0188° (1.58 km)

======================================================================
TARGET GRID DETERMINATION
======================================================================

Original grid spacing:
   Model space: 2.000 km × 2.000 km
   Geographic: ~0.0234° × 0.0180°

Using EP2020 grid spacing for compatibility:
   0.0188° × 0.0107°

Target grid dimensions: 1001 × 689 × 207
Target points per level: 689,689
Target total points: 142,765,623

Converting longitudes back to -180 to 180 range...
   Longitude range: -179.981°E to 180.000°E
```

## Interpolation Results

```
======================================================================
INTERPOLATION
======================================================================

Interpolating 207 depth levels...
   Level 1/207: depth = -3.00 km
      Coverage: 46.5%
   Level 10/207: depth = 1.50 km
      Coverage: 46.5%
   Level 20/207: depth = 6.50 km
      Coverage: 46.5%
   Level 30/207: depth = 11.50 km
      Coverage: 46.5%
   Level 40/207: depth = 16.50 km
      Coverage: 46.5%
   Level 50/207: depth = 21.50 km
      Coverage: 46.5%
   Level 60/207: depth = 26.50 km
      Coverage: 46.5%
   Level 70/207: depth = 31.50 km
      Coverage: 46.5%
   Level 80/207: depth = 36.50 km
      Coverage: 46.5%
   Level 90/207: depth = 41.50 km
      Coverage: 46.5%
   Level 100/207: depth = 46.50 km
      Coverage: 46.5%
   Level 110/207: depth = 51.50 km
      Coverage: 46.5%
   Level 120/207: depth = 56.50 km
      Coverage: 46.5%
   Level 130/207: depth = 61.50 km
      Coverage: 46.5%
   Level 140/207: depth = 66.50 km
      Coverage: 46.5%
   Level 150/207: depth = 71.50 km
      Coverage: 46.5%
   Level 160/207: depth = 76.50 km
      Coverage: 46.5%
   Level 170/207: depth = 81.50 km
      Coverage: 46.5%
   Level 180/207: depth = 86.50 km
      Coverage: 46.5%
   Level 190/207: depth = 91.50 km
      Coverage: 46.5%
   Level 200/207: depth = 96.50 km
      Coverage: 46.5%
   Level 207/207: depth = 100.00 km
      Coverage: 46.5%

Interpolation complete:
   Vp coverage: 46.5%
   Vs coverage: 46.5%
   Rho coverage: 46.5%
```

## Output Files

```
======================================================================
WRITING HDF5
======================================================================

Writing to: hikurangi_uniform.h5
Grid: 1001 lat × 689 lon × 207 depth
   Written group '-3'
   Written group '6.5'
   Written group '16.5'
   Written group '26.5'
   Written group '36.5'
   Written group '46.5'
   Written group '56.5'
   Written group '66.5'
   Written group '76.5'
   Written group '86.5'
   Written group '96.5'
   Written group '100'

✅ Successfully saved Hikurangi HDF5 to hikurangi_uniform.h5   
   Actual file size: 153.7 MB
   Compression ratio: 8.5x


```

## Processing Summary

### Key Processing Steps:
1. **Unit Detection**: Automatic detection and conversion of density from kg/m³ to g/cm³
2. **Grid Analysis**: Analysis of irregular tomography grid structure and rotation
3. **Dateline Handling**: Proper handling of data crossing the 180° meridian
4. **Interpolation**: Conversion to regular geographic grid compatible with EP2020
5. **HDF5 Output**: Export in NZCVM-compatible format with gzip compression (level 4) and float32 precision

### Final Grid Specifications:
- **Dimensions**: 1001 × 689 × 207 (lat × lon × depth)
- **Geographic Coverage**: 179.98°W to 180.00°E, 45.04°S to 34.36°S
- **Depth Range**: -3.0 to 100.0 km (0.5 km spacing)
- **Data Coverage**: 46.5% of grid points contain interpolated values
- **Coordinate System**: Geographic (WGS84)

## Citation

Bassett, D., Henrys, S., Tozer, B., van Avendonk, H., Gase, A., Bangs, N., et al. (2025). Crustal structure of the Hikurangi subduction zone revealed by four decades of Onshore-Offshore seismic data: Implications for the dimensions and slip behavior of the seismogenic zone. *Journal of Geophysical Research: Solid Earth*, 130, e2024JB030268. https://doi.org/10.1029/2024JB030268
