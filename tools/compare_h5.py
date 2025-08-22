#!/usr/bin/env python3
import argparse, sys, traceback
import h5py, numpy as np
from typing import List, Dict, Tuple

VARS_DEFAULT = ("vp", "vs", "rho")

def sort_key_level(s: str):
    try: return float(s)
    except Exception: return s

def list_root_groups(h5: h5py.File) -> List[str]:
    return [k for k in h5.keys() if isinstance(h5[k], h5py.Group)]

def summarize_file(path: str) -> List[str]:
    with h5py.File(path, "r") as f:
        grps = list_root_groups(f)
        print(f"- {path}: {len(grps)} root groups")
        preview = ", ".join(sorted(grps, key=sort_key_level)[:8])
        if len(grps) > 8: preview += ", …"
        print(f"  groups: {preview}")
        # peek first group for shapes/dtypes
        if grps:
            gname = sorted(grps, key=sort_key_level)[0]
            g = f[gname]
            for ds in ("vp","vs","rho","latitudes","longitudes"):
                if ds in g:
                    print(f"  {gname}/{ds}: shape={g[ds].shape}, dtype={g[ds].dtype}")
        return grps

def build_row_plan(ny: int, nx: int, n_samples: int, rng: np.random.Generator, replace: bool) -> Tuple[Dict[int, np.ndarray], int]:
    """
    Returns a mapping: row -> sorted unique column indices, and the total unique points count.
    Ensures h5py-friendly (increasing) indices along each axis.
    """
    total = ny * nx
    n = min(n_samples, total)
    lin = rng.choice(total, size=n, replace=replace)
    lin = np.unique(lin)  # drop duplicates to keep point selection valid
    jj, ii = np.divmod(lin, nx)

    plan: Dict[int, list] = {}
    for r, c in zip(jj, ii):
        plan.setdefault(int(r), []).append(int(c))

    # sort & unique columns per row
    unique_points = 0
    plan_sorted: Dict[int, np.ndarray] = {}
    for r, cols in plan.items():
        arr = np.array(cols, dtype=np.int64)
        arr = np.unique(arr)        # increasing order
        plan_sorted[r] = arr
        unique_points += arr.size
    return plan_sorted, unique_points

def compare_levels(f1, f2, levels: List[str], vars_to_check: List[str], n_samples: int,
                   rng: np.random.Generator, with_replacement: bool, eps: float):
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
            print(f"  [skip] shape mismatch for {ref}: {g1[ref].shape} vs {g2[ref].shape}")
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
            sq_sum  = 0.0
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
                sq_sum  += float((diff * diff).sum())
                n_count += int(a.size)
                if a.size:
                    max_abs = max(max_abs, float(absdiff.max()))

            if n_count == 0:
                print(f"  {name}: no comparable samples")
                continue

            mae   = abs_sum / n_count
            relmae= rel_sum / n_count
            rmse  = np.sqrt(sq_sum / n_count)
            print(f"  {name}: MAE={mae:.3e}  relMAE={relmae:.3e}  RMSE={rmse:.3e}  max|Δ|={max_abs:.3e}")

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
        overall_rmse= np.sqrt(totals_rmse_sq[name] / totals_cnt[name])
        print(f"  {name}: MAE={overall_mae:.3e}  relMAE={overall_rel:.3e}  RMSE={overall_rmse:.3e}  max|Δ|={totals_max[name]:.3e}")

def main():
    ap = argparse.ArgumentParser(description="Compare two HDF5 tomography files (row-grouped random sampling per level).")
    ap.add_argument("file_a")
    ap.add_argument("file_b")
    ap.add_argument("-v", "--vars", nargs="+", default=list(VARS_DEFAULT),
                    help=f"Datasets to compare (default: {', '.join(VARS_DEFAULT)})")
    ap.add_argument("-n", "--samples", type=int, default=200_000, help="Target random points per level (unique after de-dup)")
    ap.add_argument("--seed", type=int, default=0, help="RNG seed")
    ap.add_argument("--first-level-only", action="store_true", help="Compare only the shallowest common level")
    ap.add_argument("--with-replacement", action="store_true", help="Sample with replacement before unique()")
    ap.add_argument("--eps", type=float, default=1e-9, help="Epsilon for relative error denominator")
    ap.add_argument("--debug", action="store_true", help="Show tracebacks on errors")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)

    print("=== Structure check ===")
    try:
        grps_a = summarize_file(args.file_a)
        grps_b = summarize_file(args.file_b)
    except Exception:
        if args.debug: traceback.print_exc()
        sys.exit(2)

    common = sorted(set(grps_a) & set(grps_b), key=sort_key_level)
    only_a = sorted(set(grps_a) - set(grps_b), key=sort_key_level)
    only_b = sorted(set(grps_b) - set(grps_a), key=sort_key_level)

    print("\n=== Level set comparison ===")
    print(f"Common levels: {len(common)}")
    if only_a: print(f"Only in A ({len(only_a)}): {only_a[:8]}{' …' if len(only_a)>8 else ''}")
    if only_b: print(f"Only in B ({len(only_b)}): {only_b[:8]}{' …' if len(only_b)>8 else ''}")
    if not common:
        print("No common levels — nothing to compare.")
        sys.exit(1)

    levels = common[:1] if args.first_level_only else common
    print(f"\nWill compare {len(levels)} level(s): {levels[:8]}{' …' if len(levels)>8 else ''}")

    with h5py.File(args.file_a, "r") as f1, h5py.File(args.file_b, "r") as f2:
        compare_levels(f1, f2, levels, args.vars, args.samples, rng, args.with_replacement, args.eps)

if __name__ == "__main__":
    main()

