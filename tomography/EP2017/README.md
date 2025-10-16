======================================================================
EP2017 TOMOGRAPHY INTERPOLATION (OPTIMIZED)
======================================================================

📥 Reading EP-style TXT...
   Found 25 depth levels in input data

📐 Loading NZCVM grid...
   Grid: 1400 lat × 800 lon = 1,120,000 points per level


📊 Depth compatibility analysis:
   Input data depths: 25 levels
   Reference grid depths: 25 levels
   Common depths: 25
   ✅ Using input depths only (25 levels)

📊 Interpolating vp...
📊 Interpolating vs...
📊 Interpolating rho...

💾 Writing to output HDF5...

💾 Writing HDF5 with compression:
   Output: ep2017.h5
   Grid: 1400 lat × 800 lon × 25 depth
   Compression: gzip level 4 + shuffle filter
   Uncompressed size estimate: 747.7 MB (0.73 GB)
   Written group '-750' (1/25)
   Written group '-225' (5/25)
   Written group '-85' (10/25)
   Written group '-38' (15/25)
   Written group '-8' (20/25)
   Written group '15' (25/25)

✅ Successfully saved EP-style HDF5 to ep2017.h5
   Actual file size: 100.9 MB (0.10 GB)
   Compression ratio: 7.4x
   Space saved: 646.8 MB (0.63 GB)

======================================================================
CONVERSION COMPLETE!
======================================================================
