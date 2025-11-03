"""
Utility functions for reading HDF5 tomography files with backward compatibility.

Supports both old format (coordinates in each group) and new optimized format
(coordinates at root level).
"""

import h5py
import numpy as np
from typing import Tuple


def get_coordinates(
    h5_file: h5py.File,
    depth_group: str | h5py.Group | None = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Get latitude and longitude coordinates from HDF5 file.

    Supports both formats:
    - New optimized format: coordinates stored at root level
    - Old format: coordinates stored in each depth group

    Parameters
    ----------
    h5_file : h5py.File
        Open HDF5 file object
    depth_group : str or h5py.Group, optional
        Depth group name or object. If None and old format is used,
        will raise an error.

    Returns
    -------
    latitudes : np.ndarray
        Array of latitude values
    longitudes : np.ndarray
        Array of longitude values

    Raises
    ------
    ValueError
        If coordinates are not found in either location

    Examples
    --------
    >>> with h5py.File('ep2020.h5', 'r') as f:
    ...     # New format (coordinates at root)
    ...     lat, lon = get_coordinates(f)
    ...
    ...     # Old format (coordinates in group)
    ...     lat, lon = get_coordinates(f, '-85')
    """
    # Check if coordinates are at root level (new optimized format)
    if 'latitudes' in h5_file and 'longitudes' in h5_file:
        latitudes = h5_file['latitudes'][:]
        longitudes = h5_file['longitudes'][:]
        return latitudes, longitudes

    # Fall back to group level (old format)
    if depth_group is None:
        raise ValueError(
            "Coordinates not found at root level and no depth_group specified. "
            "This file uses the old format - please specify a depth_group."
        )

    # Get group object if string was provided
    if isinstance(depth_group, str):
        if depth_group not in h5_file:
            raise ValueError(f"Depth group '{depth_group}' not found in file")
        group = h5_file[depth_group]
    else:
        group = depth_group

    # Check for coordinates in group
    if 'latitudes' not in group or 'longitudes' not in group:
        raise ValueError(
            f"Coordinates not found in group '{depth_group}' or at root level"
        )

    latitudes = group['latitudes'][:]
    longitudes = group['longitudes'][:]
    return latitudes, longitudes


def is_optimized_format(h5_file: h5py.File) -> bool:
    """
    Check if HDF5 file uses the optimized format.

    Parameters
    ----------
    h5_file : h5py.File
        Open HDF5 file object

    Returns
    -------
    bool
        True if file uses optimized format (coordinates at root level),
        False if using old format (coordinates in each group)
    """
    return 'latitudes' in h5_file and 'longitudes' in h5_file


def get_depth_groups(h5_file: h5py.File) -> list[str]:
    """
    Get list of depth group names from HDF5 file.

    Filters out non-group items and coordinate datasets at root level.

    Parameters
    ----------
    h5_file : h5py.File
        Open HDF5 file object

    Returns
    -------
    list[str]
        Sorted list of depth group names (sorted numerically)
    """
    depth_groups = []
    for key in h5_file.keys():
        # Skip coordinate datasets at root level
        if key in ['latitudes', 'longitudes', 'coords']:
            continue
        # Check if it's a group
        if isinstance(h5_file[key], h5py.Group):
            depth_groups.append(key)

    # Sort numerically
    return sorted(depth_groups, key=lambda x: float(x))


def load_depth_data(
    h5_file: h5py.File,
    depth: str | float,
    variables: list[str] | None = None
) -> dict[str, np.ndarray]:
    """
    Load data for a specific depth level.

    Parameters
    ----------
    h5_file : h5py.File
        Open HDF5 file object
    depth : str or float
        Depth level to load (e.g., '-85' or -85)
    variables : list[str], optional
        List of variables to load (e.g., ['vp', 'vs', 'rho']).
        If None, loads all available variables.

    Returns
    -------
    dict[str, np.ndarray]
        Dictionary with keys:
        - 'latitudes': latitude array
        - 'longitudes': longitude array
        - variable names (e.g., 'vp', 'vs', 'rho')

    Examples
    --------
    >>> with h5py.File('ep2020.h5', 'r') as f:
    ...     data = load_depth_data(f, -85)
    ...     vp = data['vp']
    ...     lat = data['latitudes']
    """
    # Convert depth to string if needed
    depth_str = str(int(depth)) if float(depth) == int(float(depth)) else str(depth)

    if depth_str not in h5_file:
        available = get_depth_groups(h5_file)
        raise ValueError(
            f"Depth '{depth_str}' not found. Available depths: {available}"
        )

    group = h5_file[depth_str]

    # Get coordinates (handles both formats automatically)
    latitudes, longitudes = get_coordinates(h5_file, group)

    # Prepare result dictionary
    result = {
        'latitudes': latitudes,
        'longitudes': longitudes
    }

    # Determine which variables to load
    if variables is None:
        # Load all datasets in the group except coordinates
        variables = [
            key for key in group.keys()
            if key not in ['latitudes', 'longitudes', 'coords']
        ]

    # Load requested variables
    for var in variables:
        if var not in group:
            raise ValueError(
                f"Variable '{var}' not found in depth group '{depth_str}'. "
                f"Available: {list(group.keys())}"
            )
        result[var] = group[var][:]

    return result
