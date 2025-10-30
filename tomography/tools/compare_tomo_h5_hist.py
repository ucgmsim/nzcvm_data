import argparse
import h5py
import numpy as np
import matplotlib.pyplot as plt

def load_variable(h5file, varname):
    """Load all values of the given variable (e.g., 'vp', 'vs', 'rho') from an HDF5 file."""
    values = []
    with h5py.File(h5file, "r") as f:
        for depth in f:
            if depth not in f:
                continue
            group = f[depth]
            if varname in group:
                values.append(group[varname][:])
    if not values:
        raise ValueError(f"No data found for {varname} in {h5file}")
    return np.concatenate([v.ravel() for v in values if v is not None])

def main(old_file, new_file):
    # Variables to compare
    variables = {
        "vp": "P-wave Velocity (km/s)",
        "vs": "S-wave Velocity (km/s)",
        "rho": "Density (g/cm³)"
    }

    for var, label in variables.items():
        try:
            new_vals = load_variable(new_file, var)
            old_vals = load_variable(old_file, var)

            # Remove zero or negative values (invalid)
            new_vals = new_vals[new_vals > 0]
            old_vals = old_vals[old_vals > 0]

            # Plot histogram
            plt.figure(figsize=(10, 5))
            bins = np.linspace(min(new_vals.min(), old_vals.min()), max(new_vals.max(), old_vals.max()), 100)

            # Plot old data with narrower appearance
            plt.hist(old_vals, bins=bins, alpha=0.6, label=f"Old ({old_file})", density=True,
                     histtype='step', linewidth=2, color='blue')

            # Plot new data with filled bars
            plt.hist(new_vals, bins=bins, alpha=0.8, label=f"New ({new_file})", density=True,
                     color='tan')

            plt.title(f"{label} Distribution Comparison")
            plt.xlabel(label)
            plt.ylabel("Normalized Frequency")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plt.show()

        except Exception as e:
            print(f"Error while processing {var}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare variable distributions between two HDF5 files.")
    parser.add_argument("old_file", help="Path to the old HDF5 file")
    parser.add_argument("new_file", help="Path to the new HDF5 file")
    args = parser.parse_args()

    main(args.old_file, args.new_file)
