```
======================================================================
Eberhart-Phillips TOMOGRAPHY INTERPOLATION (IMPROVED)
======================================================================

   Improvements in this version:
   - Configurable fill value for regions outside data coverage
   - Optional longitude extension beyond 180deg meridian
   - All input depth levels retained by default

   Current settings:
   Fill value: NaN
     Using NaN (recommended - avoids boundary artifacts)
   Compression level: 4
   Longitude extension: 5.0deg

   Reading EP-style TXT...
   Found 20 depth levels in input data
   Longitude range: 152.52deg to 192.52deg
   Latitude range: -56.67deg to -26.43deg

   Loading NZCVM grid...
   Extended longitude grid by 5.00deg (267 points)
   New longitude range: 165.00deg to 185.01deg
   Grid: 1400 lat x 1067 lon = 1,493,800 points per level
   Longitude range: 165.00deg to 185.01deg
   Latitude range: -48.00deg to -33.00deg


   Depth compatibility analysis:
   Input data depths: 20 levels
   Reference grid depths: 20 levels
   Common depths: 20
   Using input depths only: 20 levels

   Interpolating vp...
   [INFO] Longitude normalization: Using 0-360 deg convention (grid extends to 185.01 deg)
   Interpolating vs...
   [INFO] Longitude normalization: Using 0-360 deg convention (grid extends to 185.01 deg)
   Interpolating rho...
   [INFO] Longitude normalization: Using 0-360 deg convention (grid extends to 185.01 deg)

   Writing to output HDF5...

   NaN statistics (will be stored as -999.0):
      VP:  190,160 / 29,876,000 (0.64%)
      VS:  190,160 / 29,876,000 (0.64%)
      RHO: 190,160 / 29,876,000 (0.64%)

   Writing HDF5 with compression:
   Output: ep2010_ver2.h5
   Grid: 1400 lat x 1067 lon x 20 depth
   Compression: gzip level 4 + shuffle filter
   Uncompressed size estimate: 797.8 MB (0.78 GB)
   Written group '-750' (1/20)
   Written group '-225' (5/20)
   Written group '-85' (10/20)
   Written group '-23' (15/20)
   Written group '15' (20/20)

   Successfully saved EP-style HDF5 to ep2010_ver2.h5
   Actual file size: 93.5 MB (0.09 GB)
   Compression ratio: 8.5x
   Space saved: 704.3 MB (0.69 GB)

======================================================================
CONVERSION COMPLETE!
======================================================================

   Notes:
   - NaN values (uncovered regions) are stored as -999.0 in the HDF5 file
   - Use reader/visualization code that recognizes -999.0 as missing data
   - Check coverage statistics above for data quality assessment

```
