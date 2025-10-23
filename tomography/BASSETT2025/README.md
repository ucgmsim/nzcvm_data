======================================================================
HIKURANGI TOMOGRAPHY CONVERSION
======================================================================

📝 Compression settings:
   Level: 4
   Shuffle filter: disabled
   Coordinate dtype: float32
📥 Reading Hikurangi data...
   Note: created column 'elevation' = -depth (km). Elevation >0 = above sea level.
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

3. ELEVATION LEVELS (km):
   Number of elevation levels: 207
   Elevation range: -100.00 to 3.00 km (positive = above sea level)
   Elevation spacing regular: True
   Elevation spacing: 0.500 km
   First 10 elevations: [-100.   -99.5  -99.   -98.5  -98.   -97.5  -97.   -96.5  -96.   -95.5]
   Last 10 elevations: [-1.5 -1.  -0.5 -0.   0.5  1.   1.5  2.   2.5  3. ]

4. POINTS PER ELEVATION LEVEL:
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

🔄 Adjusting longitude values in dataframe...
   ✅ Longitudes adjusted to 0-360 range for interpolation

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
LLDOZED/g' {} +
Target points per level: 689,689
Target total points: 142,765,623

Converting longitudes back to -180 to 180 range...
   Longitude range: -179.981°E to 180.000°E

📊 Creating coverage visualization...
   Saved to hikurangi_coverage.png

======================================================================
INTERPOLATION OPTIONS
======================================================================

You can interpolate using:
   1. All points (default)
   2. Only constrained points (constraint=1)

======================================================================
INTERPOLATION
======================================================================

Interpolating 207 elevation levels...
   Level 1/207: elevation = -100.00 km
      Coverage: 46.5%
   Level 10/207: elevation = -95.50 km
      Coverage: 46.5%
   Level 20/207: elevation = -90.50 km
      Coverage: 46.5%
   Level 30/207: elevation = -85.50 km
      Coverage: 46.5%
   Level 40/207: elevation = -80.50 km
      Coverage: 46.5%
   Level 50/207: elevation = -75.50 km
      Coverage: 46.5%
   Level 60/207: elevation = -70.50 km
      Coverage: 46.5%
   Level 70/207: elevation = -65.50 km
      Coverage: 46.5%
   Level 80/207: elevation = -60.50 km
      Coverage: 46.5%
   Level 90/207: elevation = -55.50 km
      Coverage: 46.5%
   Level 100/207: elevation = -50.50 km
      Coverage: 46.5%
   Level 110/207: elevation = -45.50 km
      Coverage: 46.5%
   Level 120/207: elevation = -40.50 km
      Coverage: 46.5%
   Level 130/207: elevation = -35.50 km
      Coverage: 46.5%
   Level 140/207: elevation = -30.50 km
      Coverage: 46.5%
   Level 150/207: elevation = -25.50 km
      Coverage: 46.5%
   Level 160/207: elevation = -20.50 km
      Coverage: 46.5%
   Level 170/207: elevation = -15.50 km
      Coverage: 46.5%
   Level 180/207: elevation = -10.50 km
      Coverage: 46.5%
   Level 190/207: elevation = -5.50 km
      Coverage: 46.5%
   Level 200/207: elevation = -0.50 km
      Coverage: 46.5%
   Level 207/207: elevation = 3.00 km
      Coverage: 46.5%

Interpolation complete:
   Vp coverage: 46.5%
   Vs coverage: 46.5%
   Rho coverage: 46.5%

======================================================================
WRITING HDF5
======================================================================

Writing to: hikurangi_uniform.h5
Grid: 1001 lat × 689 lon × 207 depth
Compression: gzip level 4
Shuffle filter: disabled
Coordinate dtype: float32
Uncompressed size estimate: 2723.0 MB
   Written group '-100.00'
   Written group '-90.50'
   Written group '-80.50'
   Written group '-70.50'
   Written group '-60.50'
   Written group '-50.50'
   Written group '-40.50'
   Written group '-30.50'
   Written group '-20.50'
   Written group '-10.50'
   Written group '-0.50'
   Written group '3.00'

✅ Successfully saved Hikurangi HDF5 to hikurangi_uniform.h5
   Actual file size: 315.8 MB
   Compression ratio: 8.6x

======================================================================
CONVERSION COMPLETE!
======================================================================

Output file: hikurangi_uniform.h5
Visualization: hikurangi_coverage.png
