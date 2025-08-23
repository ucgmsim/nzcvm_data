# Tomography Models in NZCVM

The tomography models in the NZCVM provide the background velocity structure for New Zealand. These models are derived from seismic travel-time data and offer a lower-resolution (~10 km) representation of the subsurface velocity structure.

## Available Tomography Models

The NZCVM currently supports the following tomography models:

1. EP2010: Based on New Zealand-wide model 1.0 by Eberhart-Phillips et al. (2010).
2. EP2020: Based on NZWide 2.2 model by Eberhart-Phillips et al. (2020). 
3. EP2025: Based on NZWide 3.1 model by Eberhart-Phillips et al. (2025).
4. CHOW2020_EP2020_MIX: Combination of the CHOW2020 model (Chow et al. 2020) in North Island and the EP2020 model for the rest

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

This submodel is a type of `tomography`, and it retrieves more information associated with the `tomography` value from the registry (in this case, `2010_NZ_OFFSHORE`). The `module` specifies the name of the accompanying Python code that prescribes how to calculate velocity at locations within the region below the `surface`.


## Data Format

Tomography model data is stored in HDF5 format. For details on the structure and contents of these files, see the [Data Formats](DataFormats.md) page.

## References

[//]: # (- Donna Eberhart-Phillips, Martin Reyners, Stephen Bannister, Mark Chadwick, Susan Ellis; Establishing a Versatile 3-D Seismic Velocity Model for New Zealand. *Seismological Research Letters* 2010; 81 &#40;6&#41;: 992–1000. doi: [https://doi.org/10.1785/gssrl.81.6.992]&#40;https://doi.org/10.1785/gssrl.81.6.992&#41;.)
- Donna Eberhart-Phillips, Stephen Bannister, Martin Reyners, and Stuart Henrys. "New Zealand Wide Model 2.2 Seismic Velocity and Qs and Qp Models for New Zealand". *Zenodo*, May 1, 2020. [https://doi.org/10.5281/zenodo.3779523](https://doi.org/10.5281/zenodo.3779523).
- Bryant Chow, Yoshihiro Kaneko, Carl Tape, Ryan Modrak, John Townend, An automated workflow for adjoint tomography—waveform misfits and synthetic inversions for the North Island, New Zealand, Geophysical Journal International, Volume 223, Issue 3, December 2020, Pages 1461–1480, https://doi.org/10.1093/gji/ggaa381
