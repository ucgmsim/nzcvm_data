#!/usr/bin/env python3
"""
Compare two HDF5 tomography files using statistical sampling.

This script performs detailed comparison of HDF5 tomography files by sampling
points from each depth level and computing various error metrics including
MAE, relative MAE, RMSE, and maximum absolute difference.
"""

import sys
import traceback
from pathlib import Path
from typing import Annotated

import h5py
import numpy as np
import typer

app = typer.Typer(pretty_exceptions_enable=False)

VARS_DEFAULT = ("vp", "vs", "rho")


def sort_key_level(s: str):
    """
    Sort key function for depth level strings.

    Parameters
    ----------
    s : str
        Level string to convert for sorting.

    Returns
    -------
    float or str
        Numeric value if convertible, otherwise original string.
    """
    try:
        return float(s)
    except ValueError:
        return s


def list_root_groups(h5: h5py.File) -> list[str]:
    """
    List all root groups in an HDF5 file.

    Parameters
    ----------
    h5 : h5py.File
        Open HDF5 file handle.

    Returns
    -------
    list[str]
        List of root group names.
    """
    return [k for k in h5.keys() if isinstance(h5[k], h5py.Group)]


def summarize_file(path: str) -> list[str]:
    """
    Summarize the structure of an HDF5 file.

    Parameters
    ----------
    path : str
        Path to the HDF5 file.

    Returns
    -------
    list[str]
        List of root group names in the file.
    """
    with h5py.File(path, "r") as f:
        grps = list_root_groups(f)
        print(f"- {path}: {len(grps)} root groups")
        preview = ", ".join(sorted(grps, key=sort_key_level)[:8])
        if len(grps) > 8:
            preview += ", …"
        print(f"  groups: {preview}")
        # peek first group for shapes/dtypes
        if grps:
            gname = sorted(grps, key=sort_key_level)[0]
            g = f[gname]
            for ds in ("vp", "vs", "rho", "latitudes", "longitudes"):
                if ds in g:
                    print(f"  {gname}/{ds}: shape={g[ds].shape}, dtype={g[ds].dtype}")
        return grps


def build_row_plan(
    ny: int, nx: int, n_samples: int, rng: np.random.Generator, replace: bool
) -> tuple[dict[int, np.ndarray], int]:
    """
    Build a sampling plan for selecting points from a 2D grid.

    Parameters
    ----------
    ny : int
        Number of rows in the grid.
    nx : int
        Number of columns in the grid.
    n_samples : int
        Target number of samples to select.
    rng : np.random.Generator
        Random number generator.
    replace : bool
        Whether to sample with replacement.

    Returns
    -------
    tuple[dict[int, np.ndarray], int]
        A mapping from row indices to column indices, and total unique points count.
    """
    total = ny * nx
    n = min(n_samples, total)
    lin = rng.choice(total, size=n, replace=replace)
    lin = np.unique(lin)  # drop duplicates to keep point selection valid
    jj, ii = np.divmod(lin, nx)

    plan: dict[int, list] = {}
    for r, c in zip(jj, ii):
        plan.setdefault(int(r), []).append(int(c))

    # sort & unique columns per row
    unique_points = 0
    plan_sorted: dict[int, np.ndarray] = {}
    for r, cols in plan.items():
        arr = np.array(cols, dtype=np.int64)
        arr = np.unique(arr)  # increasing order
        plan_sorted[r] = arr
        unique_points += arr.size
    return plan_sorted, unique_points


def compare_levels(
    f1: h5py.File,
    f2: h5py.File,
    levels: list[str],
    vars_to_check: list[str],
    n_samples: int,
    rng: np.random.Generator,
    with_replacement: bool,
    eps: float,
):
    """
    Compare data between two HDF5 files across multiple depth levels.

    Parameters
    ----------
    f1 : h5py.File
        First HDF5 file handle.
    f2 : h5py.File
        Second HDF5 file handle.
    levels : list[str]
        List of depth levels to compare.
    vars_to_check : list[str]
        List of variable names to compare.
    n_samples : int
        Number of sample points to use for comparison.
    rng : np.random.Generator
        Random number generator.
    with_replacement : bool
        Whether to sample with replacement.
    eps : float
        Epsilon value for relative error calculations.
    """
    totals_abs = {v: 0.0 for v in vars_to_check}
    totals_rel = {v: 0.0 for v in vars_to_check}
    totals_rmse_sq = {v: 0.0 for v in vars_to_check}
    totals_cnt = {v: 0 for v in vars_to_check}
    totals_max = {v: 0.0 for v in vars_to_check}

    for lvl in levels:
        print(f"\nLevel {lvl}:")
        g1, g2 = f1[lvl], f2[lvl]
        ref = next((v for v in vars_to_check if v in g1 and v in g2), None)
        if ref is None:
            print("  [skip] none of requested datasets present in both files here")
            continue
        if g1[ref].shape != g2[ref].shape:
            print(
                f"  [skip] shape mismatch for {ref}: {g1[ref].shape} vs {g2[ref].shape}"
            )
            continue

        ny, nx = g1[ref].shape
        row_plan, n_eff = build_row_plan(ny, nx, n_samples, rng, with_replacement)
        print(f"  sampling {n_eff} unique points across {len(row_plan)} rows")

        for name in vars_to_check:
            if name not in g1 or name not in g2:
                print(f"  {name}: [missing in one file] skip")
                continue

            # stream metrics row-by-row to respect monotonic index rule
            abs_sum = 0.0
            rel_sum = 0.0
            sq_sum = 0.0
            n_count = 0
            max_abs = 0.0

            ds1, ds2 = g1[name], g2[name]
            for r, cols in row_plan.items():
                a = ds1[r, cols].astype(np.float64, copy=False)
                b = ds2[r, cols].astype(np.float64, copy=False)
                diff = a - b
                absdiff = np.abs(diff)
                denom = np.maximum(eps, np.abs(a))

                abs_sum += float(absdiff.sum())
                rel_sum += float((absdiff / denom).sum())
                sq_sum += float((diff * diff).sum())
                n_count += int(a.size)
                if a.size:
                    max_abs = max(max_abs, float(absdiff.max()))

            if n_count == 0:
                print(f"  {name}: no comparable samples")
                continue

            mae = abs_sum / n_count
            relmae = rel_sum / n_count
            rmse = np.sqrt(sq_sum / n_count)
            print(
                f"  {name}: MAE={mae:.3e}  relMAE={relmae:.3e}  RMSE={rmse:.3e}  max|Δ|={max_abs:.3e}"
            )

            totals_abs[name] += abs_sum
            totals_rel[name] += rel_sum
            totals_rmse_sq[name] += sq_sum
            totals_cnt[name] += n_count
            totals_max[name] = max(totals_max[name], max_abs)

    print("\n=== Overall (sample-weighted across processed levels) ===")
    for name in vars_to_check:
        if totals_cnt[name] == 0:
            print(f"  {name}: no comparable samples")
            continue
        overall_mae = totals_abs[name] / totals_cnt[name]
        overall_rel = totals_rel[name] / totals_cnt[name]
        overall_rmse = np.sqrt(totals_rmse_sq[name] / totals_cnt[name])
        print(
            f"  {name}: MAE={overall_mae:.3e}  relMAE={overall_rel:.3e}  RMSE={overall_rmse:.3e}  max|Δ|={totals_max[name]:.3e}"
        )


@app.command()
def main(
    file_a: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="First HDF5 file to compare"
        ),
    ],
    file_b: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="Second HDF5 file to compare"
        ),
    ],
    vars: Annotated[
        list[str],
        typer.Option(
            "-v", "--vars",
            help=f"Datasets to compare (default: {', '.join(VARS_DEFAULT)})"
        ),
    ] = list(VARS_DEFAULT),
    samples: Annotated[
        int,
        typer.Option(
            "-n", "--samples",
            min=1,
            help="Target random points per level (unique after de-dup)"
        ),
    ] = 200_000,
    seed: Annotated[
        int,
        typer.Option(help="RNG seed")
    ] = 0,
    first_level_only: Annotated[
        bool,
        typer.Option(
            "--first-level-only",
            help="Compare only the shallowest common level"
        ),
    ] = False,
    with_replacement: Annotated[
        bool,
        typer.Option(
            "--with-replacement",
            help="Sample with replacement before unique()"
        ),
    ] = False,
    eps: Annotated[
        float,
        typer.Option(
            min=0.0,
            help="Epsilon for relative error denominator"
        ),
    ] = 1e-9,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Show tracebacks on errors"
        ),
    ] = False,
) -> None:
    """
    Compare two HDF5 tomography files (row-grouped random sampling per level).

    Parameters
    ----------
    file_a : Path
        First HDF5 file to compare.
    file_b : Path
        Second HDF5 file to compare.
    vars : list[str], optional
        Datasets to compare.
    samples : int, optional
        Target random points per level.
    seed : int, optional
        RNG seed.
    first_level_only : bool, optional
        Compare only the shallowest common level.
    with_replacement : bool, optional
        Sample with replacement before unique().
    eps : float, optional
        Epsilon for relative error denominator.
    debug : bool, optional
        Show tracebacks on errors.
    """
    rng = np.random.default_rng(seed)

    print("=== Structure check ===")
    try:
        grps_a = summarize_file(str(file_a))
        grps_b = summarize_file(str(file_b))
    except (OSError, IOError, KeyError) as e:
        if debug:
            traceback.print_exc()
        else:
            print(f"Error reading HDF5 files: {e}", file=sys.stderr)
        raise typer.Exit(2)

    common = sorted(set(grps_a) & set(grps_b), key=sort_key_level)
    only_a = sorted(set(grps_a) - set(grps_b), key=sort_key_level)
    only_b = sorted(set(grps_b) - set(grps_a), key=sort_key_level)

    print("\n=== Level set comparison ===")
    print(f"Common levels: {len(common)}")
    if only_a:
        print(
            f"Only in A ({len(only_a)}): {only_a[:8]}{' …' if len(only_a) > 8 else ''}"
        )
    if only_b:
        print(
            f"Only in B ({len(only_b)}): {only_b[:8]}{' …' if len(only_b) > 8 else ''}"
        )
    if not common:
        print("No common levels — nothing to compare.")
        raise typer.Exit(1)

    levels = common[:1] if first_level_only else common
    print(
        f"\nWill compare {len(levels)} level(s): {levels[:8]}{' …' if len(levels) > 8 else ''}"
    )

    with h5py.File(str(file_a), "r") as f1, h5py.File(str(file_b), "r") as f2:
        compare_levels(
            f1,
            f2,
            levels,
            vars,
            samples,
            rng,
            with_replacement,
            eps,
        )


if __name__ == "__main__":
    app()
