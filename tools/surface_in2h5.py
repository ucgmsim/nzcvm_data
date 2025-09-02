"""
Convert ASCII format surface file (.in) from plain text format to HDF5.

The HDF5 file will contain the following data:
- **Attributes**:
  - `nrows`: Number of latitude points (integer)
  - `ncols`: Number of longitude points (integer)

- **Datasets**:
  - `latitude`: 1D array of latitude values [shape: (nrows,)]
  - `longitude`: 1D array of longitude values [shape: (ncols,)]
  - `elevation`: 2D array of elevation or depth values [shape: (nrows, ncols)]

Usage:
    python surface_in2h5.py <input_file> [--out-dir <output_directory>]

"""

from pathlib import Path
from typing import Annotated, Optional

import h5py
import numpy as np
import typer

from qcore import cli

app = typer.Typer(pretty_exceptions_enable=False)


def ascii_to_hdf5(input_file_path: str | Path, output_file_path: str | Path):
    """
    Convert Digital Elevation Model (DEM) from plain text format to HDF5.

    Parameters
    ----------
    input_file_path : str or Path
        Path to the input DEM file.
    output_file_path : str or Path
        Path to the output HDF5 file.
    """
    # Ensure paths are Path objects
    input_file_path = Path(input_file_path)
    output_file_path = Path(output_file_path)

    print(f"Converting {input_file_path} to {output_file_path}")

    try:
        with open(input_file_path, "r") as f:
            # Read dimensions
            # (The .in format begins with: nrows ncols, then nrows lats, ncols lons,
            # followed by nrows*ncols raster values, with arbitrary line breaks).
            dims = f.readline().split()
            if len(dims) < 2:
                raise ValueError("First line must contain 'nrows ncols'")
            nrows, ncols = int(dims[0]), int(dims[1])

            # === Robust flat-stream reads (ignore physical line breaks) ===
            #  read latitude as a flat stream of exactly nrows floats
            lat_values = np.fromfile(f, dtype=float, count=nrows, sep=" ")
            if lat_values.size != nrows:
                raise ValueError(
                    f"Expected {nrows} latitude values, got {lat_values.size}"
                )

            # read longitude as a flat stream of exactly ncols floats
            lon_values = np.fromfile(f, dtype=float, count=ncols, sep=" ")
            if lon_values.size != ncols:
                raise ValueError(
                    f"Expected {ncols} longitude values, got {lon_values.size}"
                )

            # read raster as ONE flat stream of nrows*ncols floats
            data = np.fromfile(f, dtype=float, count=nrows * ncols, sep=" ")
            if data.size != nrows * ncols:
                raise ValueError(
                    f"Expected {nrows * ncols} raster values, got {data.size}"
                )

            # reshape to (nrows, ncols) —  HDF5 loader uses [:].T later
            elevation_data = data.reshape((nrows, ncols))

        # Create the output directory if it doesn't exist
        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create HDF5 file
        with h5py.File(output_file_path, "w") as hf:
            # Store metadata
            hf.attrs["nrows"] = nrows
            hf.attrs["ncols"] = ncols

            # Create datasets with compression
            # (Optionally add chunks; gzip default level is fine)
            hf.create_dataset("latitude", data=lat_values, compression="gzip")
            hf.create_dataset("longitude", data=lon_values, compression="gzip")
            hf.create_dataset("elevation", data=elevation_data, compression="gzip")

        print(f"Conversion complete. HDF5 file saved to {output_file_path}")

    except Exception as e:
        if isinstance(e, (SystemExit, KeyboardInterrupt)):
            raise  # Re-raise critical exceptions
        raise ValueError(f"Error during conversion: {str(e)}")


@cli.from_docstring(app)
def convert_surface_to_h5(
    input_file: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, help="Path to the input DEM file"),
    ],
    out_dir: Annotated[
        Optional[Path],
        typer.Option(help="Output directory (default is same as input file)"),
    ] = None,
):
    """
    Convert ASCII format surface file (.in) from plain text format to HDF5.

    This tool takes a surface file in ASCII format and converts it to a more
    efficient HDF5 format, preserving all data.

    Parameters
    ----------
    input_file : Path
        Path to the input DEM file.
    out_dir : Path, optional
        Output directory for the converted file. If not specified, the output
        file will be saved in the same directory as the input file with a .h5
        extension.
    """
    input_path = Path(input_file)

    if out_dir:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{input_path.stem}.h5"
    else:
        output_path = input_path.with_suffix(".h5")

    ascii_to_hdf5(input_path, output_path)


if __name__ == "__main__":
    app()
