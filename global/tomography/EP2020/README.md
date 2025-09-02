# EP2020 Tomography Model

The EP2020 tomography model, as defined in the NZCVM registry, provides a foundational background velocity structure for New Zealand. It is an essential component for integrating more detailed regional and basin models.

## Model Details

This model is explicitly defined in the `nzcvm_registry.yaml` file, which acts as the central source of truth for its properties:

* **Name:** `EP2020`

* **Author:** Eberhart-Phillips et al. (2020)

* **Title:** New Zealand Wide model 2.2 seismic velocity and Q structure

* **Data Path:** `global/tomography/ep2020.h5`

* **Elevation Layers (`elev`):** The model is defined on 20 discrete elevation layers, specified in kilometers. These layers range from 15 km above sea level down to 750 km below, providing a deep velocity profile.

## Data Integration and Visualization

The raw data for the EP2020 model consists of scattered points of seismic velocity. For use within the 3D velocity model, this data is processed by interpolating these points onto a regular, uniform grid. The interpolated data forms a series of smooth planes at different elevations.

The image below illustrates this process at the 1 km elevation layer. The image on the left shows the original data as individual, scattered points, while the image on the right shows the result after interpolation—a continuous, gridded plane that can be used for calculations and visualization.

![The EP2020 model showing scattered original data points and the interpolated, continuous data plane at 1 km elevation.](uploaded:ksnip_20250806-163959.jpg-70db2902-ec5c-4be5-9153-c0fa1276a687)

## References

* Eberhart-Phillips, D., & Reyners, M. et al. (2020). *New Zealand Wide model 2.2 seismic velocity and Q structure*. New Zealand Journal of Geology and Geophysics.