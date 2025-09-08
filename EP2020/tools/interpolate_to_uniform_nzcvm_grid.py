import numpy as np
import pandas as pd
import h5py
from scipy.interpolate import griddata
from pathlib import Path

def read_ep_txt(txt_path):
    col_names = [
        "vp", "vp_o_vs", "vs", "rho", "sf_vp", "sf_vp_o_vs",
        "x", "y", "depth", "lat", "lon"
    ]
    df = pd.read_csv(
        txt_path,
        sep=r"\s+",
        skiprows=2,
        names=col_names,
        engine="python"
    )
    df['depth']=-1*df['depth']

    return df


def load_nzcvm_grid(h5_path):
    with h5py.File(h5_path, "r") as f:
        depth_keys = sorted(f.keys(), key=lambda x: float(x))
        depth = np.array([float(k) for k in depth_keys])
        group0 = f[depth_keys[0]]
        lat = group0["latitudes"][:]
        lon = group0["longitudes"][:]
    return lat, lon, depth

def interpolate_property_to_grid(df, lat, lon, depth, field_name):
    nlat, nlon, ndepth = len(lat), len(lon), len(depth)
    out = np.full((ndepth, nlat, nlon), np.nan, dtype=np.float32)

    for iz, d in enumerate(depth):
        df_d = df[np.isclose(df["depth"], d, atol=1e-3)]
        if df_d.empty:
            print(f"⚠️ No data at depth={d:.2f} km")
            continue

        points = df_d[["lon", "lat"]].values
        values = df_d[field_name].values
        lon_grid, lat_grid = np.meshgrid(lon, lat)

        interp = griddata(points, values, (lon_grid, lat_grid), method="linear", fill_value=0.0)
        out[iz] = interp

    return out


def write_epstyle_hdf5(output_path, lats, lons, depth_list, vp_stack, vs_stack, rho_stack):
    """
    Writes EP-style tomography HDF5.
    Each depth slice becomes a group named by depth in km.
    
    Args:
        lats (1D array): Latitude values (nlat,)
        lons (1D array): Longitude values (nlon,)
        depth_list (1D array): Depths in km (nz,)
        vp_stack, vs_stack, rho_stack: 3D arrays (nz, nlat, nlon)
    """
    nlat, nlon = len(lats), len(lons)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    coords = np.stack([lat_grid, lon_grid], axis=-1)  # shape: (nlat, nlon, 2)

    vp_stack[np.isnan(vp_stack)]=-999.0
    vs_stack[np.isnan(vs_stack)]=-999.0
    rho_stack[np.isnan(rho_stack)]=-999.0


    with h5py.File(output_path, "w") as f:
        for iz, depth in enumerate(depth_list):
            grp = f.create_group(f"{depth:.0f}")
            grp.create_dataset("latitudes", data=lats)
            grp.create_dataset("longitudes", data=lons)
            grp.create_dataset("coords", data=coords)
            grp.create_dataset("vp", data=vp_stack[iz])
            grp.create_dataset("vs", data=vs_stack[iz])
            grp.create_dataset("rho", data=rho_stack[iz])

    print(f"✅ Saved EP-style HDF5 to {output_path}")

def main():
    input_txt = Path("vlnzw2p2dnxyzltln.tbl.txt")
    ref_h5 = Path("../../EP2010/ep2010.h5")
    out_h5 = Path("../ep2020_uniform.h5")

    print("📥 Reading EP-style TXT...")
    df = read_ep_txt(input_txt)
    print(set(df['depth']))

    print("📐 Loading NZCVM grid...")
    lat, lon, depth = load_nzcvm_grid(ref_h5)

    print("📊 Interpolating vp...")
    vp = interpolate_property_to_grid(df, lat, lon, depth, "vp")
    print("📊 Interpolating vs...")
    vs = interpolate_property_to_grid(df, lat, lon, depth, "vs")
    print("📊 Interpolating rho...")
    rho = interpolate_property_to_grid(df, lat, lon, depth, "rho")

    print("💾 Writing to output HDF5...")
    write_epstyle_hdf5(out_h5, lat, lon, depth, vp, vs, rho)

if __name__ == "__main__":
    main()

