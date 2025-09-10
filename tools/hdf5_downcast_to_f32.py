#!/usr/bin/env python3
"""
Downcast HDF5 tomography data from float64 to float32 with compression.

This script converts vp, vs, and rho datasets from float64 to float32
while recompressing the entire file with gzip compression and shuffle filter.
"""

from pathlib import Path
from typing import Annotated

import h5py
import numpy as np
import typer

app = typer.Typer(pretty_exceptions_enable=False)

TARGETS = {"vp", "vs", "rho"}  # downcast only these


def copy_attrs(src: h5py.Group | h5py.Dataset, dst: h5py.Group | h5py.Dataset) -> None:
    """
    Copy all attributes from source to destination object.

    Parameters
    ----------
    src : h5py.Group or h5py.Dataset
        Source HDF5 object.
    dst : h5py.Group or h5py.Dataset
        Destination HDF5 object.
    """
    for k, v in src.attrs.items():
        dst.attrs[k] = v


def chunk_guess(shape: tuple) -> tuple | bool:
    """
    Guess appropriate chunk size for HDF5 dataset.

    Parameters
    ----------
    shape : tuple
        Shape of the dataset.

    Returns
    -------
    tuple or True
        Chunk shape for 2D datasets, True for automatic chunking for 1D.
    """
    # Good default for your 2D (1400x800) datasets; let h5py decide for 1D.
    if len(shape) == 2:
        return (256, 256)
    return True


def downcast_hdf5(inp: str, outp: str, gzip_level: int = 4) -> None:
    """
    Convert HDF5 file with float64 to float32 downcast and recompression.

    Parameters
    ----------
    inp : str
        Input HDF5 file path.
    outp : str
        Output HDF5 file path.
    gzip_level : int, optional
        Gzip compression level (1-9). Default is 4.
    """
    with h5py.File(inp, "r") as fin, h5py.File(outp, "w") as fout:
        copy_attrs(fin, fout)

        def visit(name: str, obj: h5py.Group | h5py.Dataset) -> None:
            if isinstance(obj, h5py.Group):
                if name != "/":
                    g = fout.require_group(name)
                    copy_attrs(obj, g)
            elif isinstance(obj, h5py.Dataset):
                base = name.split("/")[-1]
                data = obj[()]  # load to memory (fast path for recompress + retype)
                dtype = obj.dtype
                if (
                    base in TARGETS
                    and np.issubdtype(dtype, np.floating)
                    and dtype != np.float32
                ):
                    data = data.astype(np.float32, copy=False)
                    dtype = np.float32

                ds = fout.create_dataset(
                    name,
                    data=data,
                    compression="gzip",
                    compression_opts=gzip_level,
                    shuffle=True,
                    chunks=chunk_guess(obj.shape),
                )
                copy_attrs(obj, ds)

        fin.visititems(lambda n, o: visit(n, o))


@app.command()
def main(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="Input HDF5 file path"
        ),
    ],
    output_file: Annotated[
        Path,
        typer.Argument(
            dir_okay=False,
            help="Output HDF5 file path"
        ),
    ],
    gzip: Annotated[
        int,
        typer.Option(
            min=1,
            max=9,
            help="Gzip compression level (1-9)"
        ),
    ] = 4,
) -> None:
    """
    Downcast vp/vs/rho to float32 and recompress with gzip+shuffle.

    Parameters
    ----------
    input_file : Path
        Input HDF5 file path.
    output_file : Path
        Output HDF5 file path.
    gzip : int, optional
        Gzip compression level (1-9). Default is 4.
    """
    downcast_hdf5(str(input_file), str(output_file), gzip_level=gzip)


if __name__ == "__main__":
    app()
