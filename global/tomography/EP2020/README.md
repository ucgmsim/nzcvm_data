# EP2020 Tomography Model

The EP2020 tomography model, as defined in the NZCVM registry, provides a foundational background velocity structure for New Zealand. It is an essential component for integrating more detailed regional and basin models.

## Model Details

This model is explicitly defined in the `nzcvm_registry.yaml` file, which acts as the central source of truth for its properties:

* **Name:** `EP2020`

* **Author:** Eberhart-Phillips et al. (2020)

* **Title:** New Zealand Wide model 2.2 seismic velocity and Q structure

* **Data Path:** `global/tomography/ep2020.h5`

* **Elevation Layers (`elev`):** The model is defined on 20 discrete elevation layers, specified in kilometers. These layers range from 15 km above sea level down to 750 km below, providing a deep velocity profile.

| Original Data (TXT)                                                                                                  | Interpolated Data (HDF5)                                                                                                     |
|----------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| <img src="images/ep2020_original_spatial_distribution.png" alt="Original Spatial Distribution" style="width:100%;"/> | <img src="images/ep2020_interpolated_spatial_distribution.png" alt="Interpolated Spatial Distribution" style="width:100%;"/> |

The left panel (TXT) shows the original tomography dataset in its native EP2020 format, where grid points follow the model's rotated coordinate system and include irregular spacing near the dateline. The right panel (HDF5) shows the same model after interpolation onto a uniform rectilinear latitude–longitude grid, producing a contiguous domain (165–180°E, 36–48°S) suitable for consistent analysis and visualization.
## Data Integration and Visualization

The raw data for the EP2020 model consists of scattered points of seismic velocity. For use within the 3D velocity model, this data is processed by interpolating these points onto a regular, uniform grid. The interpolated data forms a series of smooth planes at different elevations.


## References

* Eberhart-Phillips, D., & Reyners, M. et al. (2020). *New Zealand Wide model 2.2 seismic velocity and Q structure*. New Zealand Journal of Geology and Geophysics.