import itertools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict, no_type_check

import h5py
import numpy as np
import pytest
import shapely
import yaml
from pytest import Metafunc
from pytest_subtests import SubTests
from schema import Optional, Or, Regex, Schema, SchemaError


@pytest.fixture(scope="session")
def nzcvm_registry_path() -> Path:
    return Path(__file__).parent.parent / "nzcvm_registry.yaml"


@pytest.fixture(scope="session")
def nzcvm_root() -> Path:
    return Path(__file__).parent.parent


@no_type_check
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
            "url": Or(url, [url], None),  # Handles single URL, list of URLs, or empty
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


class Surface(TypedDict):
    path: str
    submodel: NotRequired[str]


class Basin(TypedDict):
    name: str
    author: str
    notes: list[str]
    wiki_images: list[str]
    boundaries: list[str]
    surfaces: list[Surface]
    smoothing: NotRequired[str]


class Vs30(TypedDict):
    name: str
    path: str


class Submodel(TypedDict):
    name: str
    type: str
    module: str
    data: NotRequired[str]


def pytest_generate_tests(metafunc: Metafunc) -> None:
    registry_path = Path(__file__).parent.parent / "nzcvm_registry.yaml"
    with open(registry_path) as f:
        registry = yaml.safe_load(f)
    if "model" in metafunc.fixturenames:
        # This assumes you have access to the registry here
        # It creates a separate test case for every model entry
        metafunc.parametrize("model", registry["tomography"], ids=lambda m: m["name"])
    elif "basin" in metafunc.fixturenames:
        metafunc.parametrize("basin", registry["basin"], ids=lambda m: m["name"])
    elif "vs30" in metafunc.fixturenames:
        metafunc.parametrize("vs30", registry["vs30"], ids=lambda m: m["name"])
    elif "submodel" in metafunc.fixturenames:
        metafunc.parametrize("submodel", registry["submodel"], ids=lambda m: m["name"])


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
                assert np.all(lat_diffs_km > 0) or np.all(lat_diffs_km < 0), (
                    "Latitudes neither strictly ascending or descending"
                )
                assert np.min(latitude) >= -90 and np.max(latitude) <= 90, (
                    "Latitudes must be between -90 and 90."
                )
                assert lat_diffs_km == pytest.approx(
                    np.full(len(lat_diffs_km), lat_diffs_km[0]), abs=LATITUDE_TOLERANCE
                )

                lon_diffs_deg = np.diff(longitude)  # Shape (N-1,)
                assert np.all(lon_diffs_deg > 0) or np.all(lon_diffs_deg < 0), (
                    "Longitudes neither strictly ascending or descending"
                )
                assert np.min(longitude) >= 0 and np.max(longitude) <= 185, (
                    "Longitudes must be between 0 and 185."
                )


# NOTE: Values for QUALITY_BOUNDS are not physically derived
QUALITY_BOUNDS = {"vp": (0, 11.0), "vs": (0, 7.0), "rho": (0, 5.0)}


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


def test_basin_boundaries_exist(
    subtests: SubTests, nzcvm_root: Path, basin: Basin
) -> None:
    for boundary in basin["boundaries"]:
        boundary_relative_path = Path(boundary)
        name = basin["name"]
        with subtests.test(
            msg=f"Checking boundary {boundary_relative_path.stem}",
            basin=name,
            boundary=boundary_relative_path.stem,
        ):
            boundary_path = nzcvm_root / boundary_relative_path
            assert boundary_path.exists()


def test_basin_boundaries_are_valid_geojson(
    subtests: SubTests, nzcvm_root: Path, basin: Basin
) -> None:
    for boundary in basin["boundaries"]:
        boundary_relative_path = Path(boundary)
        name = basin["name"]
        boundary_name = boundary_relative_path.stem

        with subtests.test(
            msg=f"Checking boundary {boundary_name}", basin=name, boundary=boundary_name
        ):
            boundary_path = nzcvm_root / boundary_relative_path

            try:
                geojson_str = boundary_path.read_text()
                geom_collection = shapely.from_geojson(geojson_str)
            except (OSError, ValueError, Exception) as e:
                pytest.fail(f"Model {name} has invalid boundary {boundary_name}: {e}")

            assert isinstance(geom_collection, shapely.GeometryCollection)
            assert shapely.is_valid(geom_collection), (
                "Geometry is topologically invalid"
            )

            assert not shapely.is_empty(geom_collection), "Geometry is empty"

            assert all(
                isinstance(geom, shapely.Polygon) for geom in geom_collection.geoms
            )


def test_basin_paths_exist(nzcvm_root: Path, basin: Basin) -> None:
    if match := re.match(r"^(\w+)_v\d+p\d+$", basin["name"]):
        basin_canonical_name = match.group(1)
        assert basin_canonical_name
        basin_path = nzcvm_root / "regional" / basin_canonical_name
        assert basin_path.exists()
        if "wiki_images" in basin:
            assert all(
                (basin_path / Path(image)).exists() for image in basin["wiki_images"]
            )
    else:
        pytest.fail("basin name does not follow structure name_vxxpxx")


def test_basin_surfaces_exist(
    subtests: SubTests, nzcvm_root: Path, basin: Basin
) -> None:
    for surface in basin["surfaces"]:
        relative_surface_path = Path(surface["path"])
        name = basin["name"]
        surface_name = relative_surface_path.stem
        with subtests.test(
            msg=f"Checking surface {surface_name}", basin=name, surface=surface_name
        ):
            surface_path = nzcvm_root / relative_surface_path
            assert surface_path.exists()


def test_basin_surfaces_are_valid_hdf5(
    subtests: SubTests, nzcvm_root: Path, basin: Basin
) -> None:
    for surface in basin["surfaces"]:
        relative_surface_path = Path(surface["path"])
        name = basin["name"]
        surface_name = relative_surface_path.stem
        with subtests.test(
            msg=f"Checking surface {surface_name}", basin=name, surface=surface_name
        ):
            surface_path = nzcvm_root / relative_surface_path
            try:
                with h5py.File(surface_path, "r") as f:
                    assert "elevation" in f.keys()
                    assert "latitude" in f.keys()
                    assert "longitude" in f.keys()
            except Exception as e:
                pytest.fail(f"{surface_name} is not a valid hdf5 file: {e}")


def test_surface_geo_gridpoints(
    subtests: SubTests, nzcvm_root: Path, basin: Basin
) -> None:
    for surface in basin["surfaces"]:
        relative_surface_path = Path(surface["path"])
        name = basin["name"]
        surface_name = relative_surface_path.stem
        with subtests.test(
            msg=f"Checking surface {surface_name}", basin=name, surface=surface_name
        ):
            surface_path = nzcvm_root / relative_surface_path
            with h5py.File(surface_path, "r") as f:
                latitude = np.array(f["latitude"])
                longitude = np.array(f["longitude"])

                lat_diffs_km = np.diff(latitude) * LAT_DEGREES_PER_KM
                assert np.all(lat_diffs_km > 0) or np.all(lat_diffs_km < 0), "Latitudes not monotonic"
                assert latitude[0] >= -90 and latitude[-1] <= 90, (
                    "Latitudes must be between -90 and 90."
                )

                lon_diffs_deg = np.diff(longitude)  # Shape (N-1,)
                assert np.all(lon_diffs_deg > 0), "Longitudes not strictly ascending"
                assert longitude[0] >= 0 and longitude[-1] <= 185, (
                    "Longitudes must be between 0 and 185."
                )

                elevation = np.array(f["elevation"])
                assert elevation.shape == (len(latitude), len(longitude)), (
                    "Elevation shape must be match latitude and longitude"
                )
                assert not np.isnan(elevation).any(), "Elevations cannot be NaN"
                assert elevation.min() >= -10000, "Elevations cannot be below -10000m"
                assert elevation.max() <= 10000, "Elevations cannot be above 10000m"


def read_smoothing_boundary(smoothing_path: Path) -> shapely.LineString:
    coords: list[tuple[float, float]] = []
    with open(smoothing_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            line_coords = re.split(r"\s+", line)
            assert len(line_coords) == 2
            lon_str, lat_str = line_coords
            assert lon_str and lat_str
            coords.append((float(lon_str), float(lat_str)))

    return shapely.LineString(coords)


def test_basin_smoothing_contained_in_boundaries(
    subtests: SubTests, nzcvm_root: Path, basin: Basin
) -> None:
    if "smoothing" not in basin:
        pytest.skip("basin has no smoothing boundary")

    boundaries = []
    for boundary in basin["boundaries"]:
        boundary_relative_path = Path(boundary)
        boundary_path = nzcvm_root / boundary_relative_path
        geojson_str = boundary_path.read_text()
        geom_collection = shapely.from_geojson(geojson_str)
        assert isinstance(geom_collection, shapely.GeometryCollection)
        for geom in geom_collection.geoms:
            assert isinstance(geom, shapely.Polygon)
            boundaries.append(geom.exterior)

    # Add a small smoothing boundary buffer to account for the fact
    # that smoothing boundary is not perfectly contained in the basin
    # boundary.
    boundary_geometry = shapely.buffer(shapely.union_all(boundaries), 0.001)
    smoothing_surface_relative_path = basin["smoothing"]
    smoothing_surface_path = nzcvm_root / Path(smoothing_surface_relative_path)
    smoothing_boundary = read_smoothing_boundary(smoothing_surface_path)

    assert boundary_geometry.contains(smoothing_boundary)


def test_basin_surfaces_contain_boundaries(
    subtests: SubTests, nzcvm_root: Path, basin: Basin
) -> None:
    for boundary, surface in itertools.product(basin["boundaries"], basin["surfaces"]):
        boundary_relative_path = Path(boundary)
        surface_relative_path = Path(surface["path"])
        basin_name = basin["name"]
        boundary_name = boundary_relative_path.stem
        surface_name = surface_relative_path.stem

        with subtests.test(
            msg=f"Checking boundary {boundary_name}",
            basin=basin_name,
            boundary=boundary_name,
            surface=surface_name,
        ):
            boundary_path = nzcvm_root / boundary_relative_path

            geojson_str = boundary_path.read_text()
            geom_collection = shapely.from_geojson(geojson_str)
            surface_path = nzcvm_root / surface_relative_path
            with h5py.File(surface_path, "r") as f:
                latitudes = np.array(f["latitude"])
                longitudes = np.array(f["longitude"])
            elevation_boundary = shapely.box(
                xmin=longitudes.min(),
                xmax=longitudes.max(),
                ymin=latitudes.min(),
                ymax=latitudes.max(),
            )
            assert shapely.contains(elevation_boundary, geom_collection)


def test_vs30_file_exists(nzcvm_root: Path, vs30: Vs30) -> None:
    relative_path = Path(vs30["path"])

    vs30_path = nzcvm_root / relative_path
    assert vs30_path.exists(), f"Vs30 file missing at {vs30_path}"


def test_vs30_is_valid_hdf5(nzcvm_root: Path, vs30: Vs30) -> None:
    relative_path = Path(vs30["path"])

    vs30_path = nzcvm_root / relative_path

    try:
        with h5py.File(vs30_path, "r") as f:
            assert "elevation" in f.keys(), (
                "Dataset 'elevation' (vs30) missing from HDF5"
            )
            assert "latitude" in f.keys()
            assert "longitude" in f.keys()
    except Exception as e:
        name = vs30["name"]
        pytest.fail(f"Vs30 file {name} is not a valid hdf5 file: {e}")


def test_vs30_geo_gridpoints(nzcvm_root: Path, vs30: Vs30) -> None:
    relative_path = Path(vs30["path"])
    vs30_path = nzcvm_root / relative_path

    with h5py.File(vs30_path, "r") as f:
        latitude = np.array(f["latitude"])
        longitude = np.array(f["longitude"])
        vs30_values = np.array(f["elevation"])

        lat_diffs = np.diff(latitude)
        assert np.all(lat_diffs > 0), "Latitudes not strictly ascending"
        assert latitude[0] >= -90 and latitude[-1] <= 90, (
            "Latitudes out of world bounds"
        )

        lon_diffs = np.diff(longitude)
        assert np.all(lon_diffs > 0), "Longitudes not strictly ascending"
        assert longitude[0] >= 0 and longitude[-1] <= 185, (
            "Longitudes out of NZCVM bounds"
        )

        assert vs30_values.shape == (len(latitude), len(longitude)), (
            f"Vs30 shape {vs30_values.shape} does not match lat/lon dimensions"
        )

        assert not np.isnan(vs30_values).any(), "Vs30 data contains NaNs"
        assert vs30_values.min() >= 0, (
            f"Vs30 values below 0 detected: {vs30_values.min()}"
        )
        assert vs30_values.max() <= 2000, (
            f"Vs30 values above 2000 detected: {vs30_values.max()}"
        )


def test_submodel_data_exists_where_relevant(
    nzcvm_root: Path, submodel: Submodel
) -> None:
    assert ("data" in submodel) == (submodel["type"] == "vm1d"), (
        "Submodel has data iff submodel is a vm1d"
    )
    if "data" in submodel:
        data_relative_path = Path(submodel["data"])
        data_path = nzcvm_root / data_relative_path
        assert data_path.exists()


@dataclass
class SubmodelData:
    vp: float
    vs: float
    rho: float
    qp: float
    qs: float
    thickness: float


def parse_submodel_data(submodel_path: Path) -> list[SubmodelData]:
    rows = []
    with open(submodel_path, "r") as f:
        header = next(f).strip()
        assert header == "DEF HST"
        for line in f:
            row = re.split(r"\s+", line.strip())
            floats = [float(x) for x in row]
            assert len(floats) == 6
            rows.append(SubmodelData(*floats))
    return rows


def test_submodel_data_is_valid(
    subtests: SubTests, nzcvm_root: Path, submodel: Submodel
) -> None:
    if "data" in submodel:
        data_relative_path = Path(submodel["data"])
        data_path = nzcvm_root / data_relative_path
        data = parse_submodel_data(data_path)
        vp_min, vp_max = QUALITY_BOUNDS["vp"]
        vs_min, vs_max = QUALITY_BOUNDS["vs"]
        rho_min, rho_max = QUALITY_BOUNDS["rho"]
        for i, row in enumerate(data):
            with subtests.test(msg=f"Checking row {i+1}", row=row):
                assert vp_min <= row.vp <= vp_max, f"Vp {row.vp} out of bounds"
                assert vs_min <= row.vs <= vs_max, f"Vs {row.vs} out of bounds"
                assert rho_min <= row.rho <= rho_max, f"Rho {row.rho} out of bounds"
                assert row.thickness >= 0, f"Negative thickness: {row.thickness}"
                assert row.qp > 0, f"Non-positive Qp: {row.qp}"
                assert row.qs > 0, f"Non-positive Qs: {row.qs}"
    else:
        pytest.skip(f"Submodel {submodel['name']} has no data")
