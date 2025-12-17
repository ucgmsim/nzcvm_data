from pathlib import Path
from typing import TypedDict

import h5py
import numpy as np
import pytest
import yaml
from pytest_subtests import SubTests
from schema import Optional, Or, Regex, Schema, SchemaError


@pytest.fixture(scope="session")
def nzcvm_registry_path() -> Path:
    return Path(__file__).parent.parent / "nzcvm_registry.yaml"


@pytest.fixture(scope="session")
def nzcvm_root() -> Path:
    return Path(__file__).parent.parent


def test_nzcvm_registry_schema(nzcvm_registry_path: Path) -> None:
    path = Regex(
        # See https://stackoverflow.com/a/537876
        r"[^\0]+",
        error="Must be valid unix path.",
    )
    ident = Regex(r"^[a-zA-Z_][a-zA-Z0-9_]*$", error="Must be valid python identifier.")
    # Source - https://stackoverflow.com/a
    # Posted by Daveo, modified by community. See post 'Timeline' for change history
    # Retrieved 2025-12-17, License - CC BY-SA 4.0
    url = Or(
        Regex(
            r"https?://(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
        ),
        "Personal communication (pending publication)",
        error='Must be a valid URL, or "Personal communication (pending publication)"',
    )
    surface_schema = Schema({"path": path, Optional("submodel"): ident})

    tomography_entry = Schema(
        {
            "name": ident,
            "elev": [Or(int, float)],
            "path": path,
            "author": str,
            Optional("title"): str,
            Optional("url"): Or(
                url,
                [url],
            ),  # Handles single URL, list of URLs, or empty
        }
    )

    basin_entry = Schema(
        {
            "name": ident,
            Optional("type"): Or(1, 2, 3, 4),
            Optional("author"): str,
            Optional("notes"): [str],
            Optional("wiki_images"): [path],
            "boundaries": [path],
            "surfaces": [surface_schema],
            Optional("smoothing"): str,
        }
    )

    submodel_schema = Schema(
        {
            "name": ident,
            "type": Or("vm1d", "tomography", "relation", "perturbation", None),
            Optional("module"): ident,
            Optional("data"): path,
        }
    )
    vs30_schema = Schema({"name": str, "path": path})
    registry_schema = Schema(
        {
            "tomography": [tomography_entry],
            "basin": [basin_entry],
            "basin": [basin_entry],
            "submodel": [submodel_schema],
            "vs30": [vs30_schema],
        }
    )

    with open(nzcvm_registry_path, "r") as f:
        registry = yaml.safe_load(f)

    try:
        registry_schema.validate(registry)
    except SchemaError as e:
        pytest.fail(f"NZCVM Registry is invalid\n{e.code}")


class Tomography(TypedDict):
    name: str
    elev: list[float]
    path: str
    author: str
    title: str
    url: str


def pytest_generate_tests(metafunc) -> None:
    if "model" in metafunc.fixturenames:
        # This assumes you have access to the registry here
        # It creates a separate test case for every model entry
        registry_path = Path(__file__).parent.parent / "nzcvm_registry.yaml"
        with open(registry_path) as f:
            registry = yaml.safe_load(f)
        metafunc.parametrize("model", registry["tomography"], ids=lambda m: m["name"])


def test_tomography_paths_exist(nzcvm_root: Path, model: Tomography) -> None:
    relative_model_path = Path(model["path"])
    model_path = nzcvm_root / relative_model_path
    assert model_path.exists()


def test_tomography_models_are_hdf5(nzcvm_root: Path, model: Tomography) -> None:
    relative_model_path = Path(model["path"])
    model_path = nzcvm_root / relative_model_path
    try:
        with h5py.File(model_path, "r") as f:
            assert len(f.keys()) > 0
    except Exception as e:
        pytest.fail(f"{model['name']} is not a valid hdf5 file: {e}")


def test_tomography_elevations_match(nzcvm_root: Path, model: Tomography) -> None:
    relative_model_path = Path(model["path"])
    model_path = nzcvm_root / relative_model_path
    registry_elevations = sorted(model["elev"])
    with h5py.File(model_path, "r") as f:
        model_elevations = sorted([float(elev) for elev in f.keys()])

    assert registry_elevations == model_elevations, "Model elevations do not match."


def test_tomography_compatible_shapes(
    subtests: SubTests, nzcvm_root: Path, model: Tomography
) -> None:
    model_path = nzcvm_root / model["path"]

    with h5py.File(model_path, "r") as f:
        for elev, group in f.items():
            name = model["name"]
            with subtests.test(msg=f"Checking elevation {elev}", model=name, elev=elev):
                lat_shape = group["latitudes"].shape
                lon_shape = group["longitudes"].shape

                # Check data arrays against (lat, lon)
                expected_data_shape = (lat_shape[0], lon_shape[0])

                for field in ["vp", "vs", "rho"]:
                    actual_shape = group[field].shape
                    assert actual_shape == expected_data_shape, (
                        f"Shape mismatch in {model_path.name} at {elev}m: "
                        f"{field} is {actual_shape}, expected {expected_data_shape}"
                    )


R_EARTH = 6378.139  # km, from: https://github.com/ucgmsim/velocity_modelling/blob/27c7e6e64d7ce1a9e543d58a6e584d498358431c/velocity_modelling/constants.py#L15
LONGITUDE_TOLERANCE = 0.01  # km
LATITUDE_TOLERANCE = 0.01  # km
LAT_DEGREES_PER_KM = np.pi / 180 * R_EARTH


def test_tomography_geo_gridpoints(
    subtests: SubTests, nzcvm_root: Path, model: Tomography
) -> None:
    relative_model_path = Path(model["path"])
    model_path = nzcvm_root / relative_model_path

    with h5py.File(model_path, "r") as f:
        for elev, group in f.items():
            name = model["name"]
            with subtests.test(msg=f"Checking elevation {elev}", model=name, elev=elev):
                latitude = np.array(group["latitudes"])
                longitude = np.array(group["longitudes"])

                lat_diffs_km = np.diff(latitude) * LAT_DEGREES_PER_KM
                assert np.all(lat_diffs_km > 0), "Latitudes not strictly ascending"
                assert latitude[0] >= -90 and latitude[-1] <= 90, (
                    "Latitudes must be between -90 and 90."
                )
                assert lat_diffs_km == pytest.approx(
                    np.full(len(lat_diffs_km), lat_diffs_km[0]), abs=LATITUDE_TOLERANCE
                )

                lon_diffs_deg = np.diff(longitude)  # Shape (N-1,)
                assert np.all(lon_diffs_deg > 0), "Longitudes not strictly ascending"
                assert longitude[0] >= 0 and longitude[-1] <= 185, (
                    "Longitudes must be between 0 and 185."
                )
                cos_lats = np.cos(np.radians(latitude))

                grid_lon_spacings_km = (
                    lon_diffs_deg[np.newaxis, :]
                    * LAT_DEGREES_PER_KM
                    * cos_lats[:, np.newaxis]
                )

                target_km = lon_diffs_deg[0] * LAT_DEGREES_PER_KM * cos_lats[0]

                max_error = np.max(np.abs(grid_lon_spacings_km - target_km))

                assert max_error < LONGITUDE_TOLERANCE, (
                    f"Longitude spacing variation ({max_error:.6f} km) "
                    f"exceeds tolerance ({LONGITUDE_TOLERANCE} km)"
                )


QUALITY_BOUNDS = {"vp": (0, 10.0), "vs": (0, 6.0), "rho": (0, 5.0)}


@pytest.mark.parametrize("quality", ["vp", "rho", "vs"])
def test_tomography_quality(
    subtests: SubTests, nzcvm_root: Path, model: Tomography, quality: str
) -> None:
    relative_model_path = Path(model["path"])
    model_path = nzcvm_root / relative_model_path

    with h5py.File(model_path, "r") as f:
        for elev, group in f.items():
            name = model["name"]
            with subtests.test(msg=f"Checking elevation {elev}", model=name, elev=elev):
                quality_values = np.array(group[quality])
                assert not np.isnan(quality_values).any(), (
                    f"Quality {quality} contains NaN values."
                )
                bounds = QUALITY_BOUNDS.get(quality)
                assert bounds
                min, max = bounds
                quality_min = quality_values.min()
                quality_max = quality_values.max()
                assert quality_min >= min, (
                    f"Quality {quality} minimum value ({quality_min=}) is less than {min}."
                )
                assert quality_max <= max, (
                    f"Quality {quality} maximum value ({quality_max=}) is less than {max}."
                )
