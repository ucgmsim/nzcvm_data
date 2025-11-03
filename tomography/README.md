# Tomography Models in NZCVM

The tomography models in the NZCVM provide the background velocity structure for New Zealand. These models are derived from seismic travel-time data and offer a lower-resolution (~10 km) representation of the subsurface velocity structure.

## Available Tomography Models

The NZCVM currently supports the following tomography models:

1. EP2010: Based on New Zealand-wide model 1.0 by Eberhart-Phillips et al. (2010).
2. EP2017: Based on NZWide 2.1 model by Eberhart-Phillips et al. (2017). 
3. EP2020: Based on NZWide 2.2 model by Eberhart-Phillips et al. (2020).
4. EP2022: Based on NZWide 2.3 model by Eberhart-Phillips et al. (2022).
5. EP2025: Based on NZWide 3.1 model by Eberhart-Phillips et al. (2025).
6. CHOW2020: Based on the North Island Adjoint tomography model (Chow et al. 2020)
7. BASSET2025: Based on Hikurangi subduction model (Bassett et al, 2025)
8. CHOW2020_EP2020_MIX: Combination of the CHOW2020 model (Chow et al. 2020) in North Island and the EP2020 model for the rest

## Tomography Model Definition

Tomography models are defined in the `nzcvm_registry.yaml` file. Here's an example of a tomography model definition:

```yaml
tomography:
  - name: EP2020
    elev: [ 15, 1, -3, -8, -15, -23, -30, -38, -48, -65, -85, -105, -130, -155, -185, -225, -275, -370, -620, -750 ]
    path: global/tomography/ep2020.h5
    author: Eberhart-Phillips et al. (2020)
    title: New Zealand Wide model 2.2 seismic velocity and Qs and Qp models for New Zealand
    url: https://10.5281/zenodo.3779523
```

The key components of a tomography model definition are:

- **name**: Identifier for the tomography model.
- **elev**: Array of elevation values (in kilometers) for the model.
- **path**: Path to the tomography model data file (in HDF5 format).
- **author**: Name of the author(s) or organization that created the model.
- **title**: Title or description of the model.
- **url**: URL where the model can be accessed or downloaded.


## Tomography Submodels

Tomography submodels are used to compute velocity values at specific locations based on the tomography model data. These submodels are defined in the `nzcvm_registry.yaml` file and are associated with surfaces in the model version configuration.

```yaml
submodel:
    - name: ep_tomography_submod_v2010
      type: tomography
      module: ep_tomography_submod_v2010
```

The `module` specifies the name of the accompanying Python code that prescribes how to calculate velocity at locations within the region below the `surface`.


## Data Format

Tomography model data is stored in HDF5 format. Two format versions are supported:

### Optimized Format (v2, Recommended)

The optimized format stores coordinates once at the root level, saving ~400MB per file:

```
/ (root)
├── latitudes (1400,)          # Stored once at root
├── longitudes (800,)          # Stored once at root
├── -750/                      # Depth group
│   ├── vp (1400, 800)        # P-wave velocity
│   ├── vs (1400, 800)        # S-wave velocity
│   └── rho (1400, 800)       # Density
├── -85/                       # Another depth group
│   ├── vp (1400, 800)
│   ├── vs (1400, 800)
│   └── rho (1400, 800)
...
```

**Attributes** (root level):
- `schema`: "NZTomographyLevelStacked v2"
- `optimized_structure`: True
- `data_dtype_vp_vs_rho`: "float32" or "float64"
- `coord_dtype_lat_lon`: "float64"
- `compression`: "gzip:4"

**Benefits**:
- ~12-15% file size reduction
- Faster I/O (coordinates read once)
- Guaranteed coordinate consistency

### Legacy Format (v1)

The old format duplicates coordinates in each depth group:

```
/ (root)
├── -750/
│   ├── latitudes (1400,)     # Duplicated in each group
│   ├── longitudes (800,)     # Duplicated in each group
│   ├── vp (1400, 800)
│   ├── vs (1400, 800)
│   └── rho (1400, 800)
├── -85/
│   ├── latitudes (1400,)     # Same data, duplicated
│   ├── longitudes (800,)     # Same data, duplicated
│   ├── vp (1400, 800)
│   ├── vs (1400, 800)
│   └── rho (1400, 800)
...
```

### Data Types and Compression

- **Coordinates**: float64 for precision
- **Velocity/Density**: float32 (sufficient for ~0.1% precision)
- **Compression**: gzip level 4 with shuffle filter
- **Chunking**: (256, 256) for 2D datasets

### Reading HDF5 Files

All reading utilities in `tools/` support both formats automatically via `hdf5_utils.py`:

```python
import h5py
from hdf5_utils import get_coordinates, load_depth_data

# Automatic format detection
with h5py.File('ep2020.h5', 'r') as f:
    # Works with both v1 and v2 formats
    lat, lon = get_coordinates(f)
    data = load_depth_data(f, -85, variables=['vp', 'vs', 'rho'])
```

### Converting to Optimized Format

Use `optimize_hdf5_structure.py` to convert existing files:

```bash
python tools/optimize_hdf5_structure.py input.h5 output.h5
```

New files created with `tomo_in2h5.py` use the optimized format by default:

```bash
python tools/tomo_in2h5.py input_dir/ model_name --optimized
```

## References

[//]: # (- Donna Eberhart-Phillips, Martin Reyners, Stephen Bannister, Mark Chadwick, Susan Ellis; Establishing a Versatile 3-D Seismic Velocity Model for New Zealand. *Seismological Research Letters* 2010; 81 &#40;6&#41;: 992–1000. doi: [https://doi.org/10.1785/gssrl.81.6.992]&#40;https://doi.org/10.1785/gssrl.81.6.992&#41;.)
- Donna Eberhart-Phillips, Stephen Bannister, Martin Reyners, and Stuart Henrys. "New Zealand Wide Model 2.2 Seismic Velocity and Qs and Qp Models for New Zealand". *Zenodo*, May 1, 2020. [https://doi.org/10.5281/zenodo.3779523](https://doi.org/10.5281/zenodo.3779523).
- Bryant Chow, Yoshihiro Kaneko, Carl Tape, Ryan Modrak, John Townend, An automated workflow for adjoint tomography—waveform misfits and synthetic inversions for the North Island, New Zealand, Geophysical Journal International, Volume 223, Issue 3, December 2020, Pages 1461–1480, https://doi.org/10.1093/gji/ggaa381
