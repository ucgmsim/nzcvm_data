#!/usr/bin/env python3
import argparse
import h5py
import numpy as np

TARGETS = {"vp", "vs", "rho"}  # downcast only these

def copy_attrs(src, dst):
    for k, v in src.attrs.items():
        dst.attrs[k] = v

def chunk_guess(shape):
    # Good default for your 2D (1400x800) datasets; let h5py decide for 1D.
    if len(shape) == 2:
        return (256, 256)
    return True

def main(inp, outp, gzip_level=4):
    with h5py.File(inp, "r") as fin, h5py.File(outp, "w") as fout:
        copy_attrs(fin, fout)

        def visit(name, obj):
            if isinstance(obj, h5py.Group):
                if name != "/":
                    g = fout.require_group(name)
                    copy_attrs(obj, g)
            elif isinstance(obj, h5py.Dataset):
                base = name.split("/")[-1]
                data = obj[()]  # load to memory (fast path for recompress + retype)
                dtype = obj.dtype
                if base in TARGETS and np.issubdtype(dtype, np.floating) and dtype != np.float32:
                    data = data.astype(np.float32, copy=False)
                    dtype = np.float32

                ds = fout.create_dataset(
                    name,
                    data=data,
                    compression="gzip", compression_opts=gzip_level,
                    shuffle=True,
                    chunks=chunk_guess(obj.shape),
                )
                copy_attrs(obj, ds)

        fin.visititems(lambda n, o: visit(n, o))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Downcast vp/vs/rho to float32 and recompress with gzip+shuffle.")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--gzip", type=int, default=4, help="gzip level 1-9 (default 4)")
    args = ap.parse_args()
    main(args.input, args.output, gzip_level=args.gzip)

