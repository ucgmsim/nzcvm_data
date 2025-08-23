# Data Formats in NZCVM

This section provides detailed information about the various data formats used in the NZCVM for surfaces, boundaries, tomography, 1D velocity models, and smoothing data.

## Global/Regional(Basin) Surface Data Format

Two data formats are used for surface data: ASCII grid files and HDF5 grid files, which contain elevation or depth data on a 2D grid.

- HDF5 grid files (`.h5`): Preferred for new data.

Surface data files are stored in HDF5 format in `global/surface/` and `regional/<basin_name>/` directories.
 
**Attributes:**
- `nrows`: Number of latitude points.
- `ncols`: Number of longitude points.

**Datasets:**
- `latitude`: 1D array, shape (nrows,)
- `longitude`: 1D array, shape (ncols,)
- `elevation`: 2D array, shape (nrows, ncols)

All datasets are typically gzip-compressed. 
If you have ASCII grid files in the following format, they can be converted to HDF5 format using the provided `tools/surface_ascii2h5.py` script.

**ASCII Grid Format:**
```
ny (number of latitudes) nx (number of longitudes)
lat_1 lat_2 lat_3 ... lat_ny
lon_1 lon_2 lon_3 ... lon_nx
z_value_1_1 z_value_1_2 ... z_value_1_nx
z_value_2_1 z_value_2_2 ... z_value_2_nx
...
z_value_ny_1 z_value_ny_2 ... z_value_ny_nx
```
Where:
- `nx` and `ny` are the number of grid points in the x and y directions.
- `z_value_lat_lon` is the elevation or depth value at grid point (lat, lon).

#### Example

```
180 227 
-45.590000 -45.585000 ... -44.695000
169.270000 169.275000 ... 170.400000
14.313100 14.595800 ...
...
15.695500 16.386100 ...
```


**Python Access Example:**
```python
import h5py
with h5py.File('surface_data.h5', 'r') as f:
    nrows = f.attrs['nrows']
    ncols = f.attrs['ncols']
    latitude = f['latitude'][:]
    longitude = f['longitude'][:]
    elevation = f['elevation'][:]
```

## Boundary Data Format

Boundary files **must be provided in `.geojson` format**. This format defines closed polygons for basin boundaries and is required for all new and updated boundary data.

**Format (.geojson):**
```
{
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [lon_1, lat_1],
                        [lon_2, lat_2],
                        ...,
                        [lon_n, lat_n]
                    ]
                ]
            }
        }
    ]
}
```
- The polygon must be closed: the first and last coordinate pair should be identical.

**Example (.geojson):**
```
{
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [169.4797587, -45.04172434],
                        [169.4804985, -45.04138952],
                        [169.4827699, -45.04122473],
                        ...
                        [169.4797587, -45.04172434]
                    ]
                ]
            }
        }
    ]
}
```

If you have boundary data in `.txt` format (longitude/latitude pairs), you can convert it to `.geojson` using the provided tool:
```
tools/boundary_txt_to_geojson.py
```

**Note:** Only `.geojson` boundary files are accepted for NZCVM. Legacy `.txt` files must be converted before use.

## Tomography Data Format

Tomography data is stored in HDF5 (`.h5`), containing 3D grids of velocity values.

**Structure:**
```
/
├── "elevation1"
│   ├── latitudes
│   ├── longitudes
│   ├── vp
│   ├── vs
│   └── rho
├── "elevation2"
│   └── ...
```
- Each elevation group contains arrays for latitudes, longitudes, vp, vs, rho.

**Python Access Example:**
```python
import h5py
with h5py.File('EP2010.h5', 'r') as f:
    elevations = list(f.keys())
    elev = elevations[0]
    latitudes = f[elev]['latitudes'][:]
    longitudes = f[elev]['longitudes'][:]
    vp = f[elev]['vp'][:]
    vs = f[elev]['vs'][:]
    rho = f[elev]['rho'][:]
```

## 1D Velocity Model Format

1D velocity models (`.fd_modfile`) define velocity profiles varying only with depth.

**Format:**
```
header
vp_1 vs_1 rho_1 qp_1 qs_1 bottom_depth_1
...
vp_n vs_n rho_n qp_n qs_n bottom_depth_n
```
- `vp`: P-wave velocity (km/s)
- `vs`: S-wave velocity (km/s)
- `rho`: Density (g/cm³)
- `qp`, `qs`: Quality factors
- `bottom_depth`: Layer bottom (km)

**Example:**
```
DEF HST
    1.80   0.50   1.81   50.0   25.0    0.400
    ...
```

## Smoothing Data Format

Smoothing files define regions for velocity model transitions.

**Format:**
```
lon_1 lat_1
lon_2 lat_2
...
lon_n lat_n
```
- Same as boundary format, but not required to be closed.

**Example:**
```
170.00831948 -46.23795676
...
```

## Data Locations

- **Surface data**: `global/surface/`, `regional/<basin_name>/`
- **Boundary data**: `regional/<basin_name>/`
- **Tomography data**: `global/tomography/`
- **1D velocity models**: `global/vm1d/`
- **Smoothing data**: `regional/<basin_name>/`

File naming conventions:
- Version suffix `_v<version_number>` is recommended (e.g., `v25p5`).
- If omitted, latest version is assumed.


