[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# NZCVM Community Data Repository

Welcome to the **New Zealand Community Velocity Model (NZCVM) Data Repository** — a curated, version-controlled archive of seismic velocity model input datasets for New Zealand.

This repository supports community contributions, collaborative review, and open access to datasets used for building 3D velocity models, including tomography, 1D profiles, Vs30 surfaces, and region-specific basin models.

---

## 📌 Purpose

This repository serves as the **community-managed data layer** of the NZCVM software ecosystem. Datasets in this repository are used by the NZCVM engine to generate 3D seismic velocity models.

All contributions follow a transparent review process and are tracked by version, enabling reproducibility and long-term stewardship.

---

## 🧠 NZCVM Modeling Code

The NZCVM engine that consumes these datasets is available at:

🔗 [NZCVM Velocity Modeling Code](https://github.com/ucgmsim/velocity_modelling)

This repository contains the core software for building and querying 3D seismic velocity models using the datasets hosted here.

---

## 📁 Repository Structure

- **surface/**: Surface elevation or topography grids used in model generation.
- **tomography/**: National tomography models (e.g., NZWIDE, EP2020, EP2025).
- **vm1d/**: 1D velocity models defining depth-dependent velocity profiles.
- **vs30/**: Vs30 maps providing near-surface shear-wave velocity.
- **regional/**: Basin-specific datasets for local regions across NZ (e.g., Canterbury, Wellington, Gisborne).
- **wiki/**: Documentation and format specifications.
- **tools/**: Scripts/utilities for processing model data.
- **src/nzcvm_data/**: Python CLI package that manages data installation and configuration.

---

## 🔽 Installing the Data Manager CLI

This repository now provides a **pip-installable CLI** (`nzcvm-data`) that manages the dataset location.  
The package contains only the CLI, not the heavy data files. Data are cloned or registered once into a canonical location on disk.

### Option 1 — Developer install (you already cloned this repo)

```bash
git clone https://github.com/ucgmsim/nzcvm_data.git
cd nzcvm_data
pip install -e .
nzcvm-data install --path ~/nzcvm_data   # register existing clone
```

### Option 2 — User install (direct from GitHub)

```bash
pip install git+https://github.com/ucgmsim/nzcvm_data.git
```

Then fetch the data:

```bash
# Full data (includes large HDF5 files via git-lfs)
nzcvm-data install

# Or, lightweight (only boundaries/small files, skips LFS)
nzcvm-data install --no-lfs
```

Check the configured location:
```bash
nzcvm-data where
```

Optional environment variable for other tools:
```bash
export NZCVM_DATA_ROOT=$(nzcvm-data where)
```

### Data root resolution order

When other projects (e.g. `velocity_modelling`) look for the data, they check in this order:

1. `--nzcvm-data-root` CLI argument  
2. `NZCVM_DATA_ROOT` environment variable  
3. `~/.config/nzcvm_data/config.json` saved by `nzcvm-data install`  
4. Default path `~/.local/cache/nzcvm_data_root`  
5. Interactive prompt (if running in a terminal)

---

## 🧰 Legacy Manual Install (advanced users)

If you prefer, you can still clone the repo and pull LFS objects manually. You will need [Git LFS](https://git-lfs.github.com/) installed.
See [Git LFS installation instructions](https://docs.github.com/en/repositories/working-with-files/managing-large-files/installing-git-large-file-storage) for installation details.

```bash
git clone https://github.com/ucgmsim/nzcvm_data.git
cd nzcvm_data
git lfs pull
```

Verify large files:
```bash
ls -lh surface/
# .h5 files should be MBs/GBs, not ~100 bytes.
```

---

## 🤝 How to Contribute

We welcome contributions of new or updated velocity model datasets from across the research community. You can contribute:

- 📍 New or updated **basin models** (surface, boundary, smoothing)
- 🗺️ Region-specific **tomography models**
- 📉 Site-specific **1D profiles** or **Vs30 maps**
- 🔧 Tools or scripts for processing model inputs (e.g., resampling, formatting)

### 🪜 Contribution Process
<img width="500" alt="Reviewing_Process" src="https://github.com/user-attachments/assets/c7168097-75fa-4c7e-b717-eef5472c84a0" />


1. **Fork** this repository to your own GitHub account.
2. **Create a new subdirectory** (if needed) under the appropriate folder:
   - `tomography/<ModelName>/` (for national tomography models)
   - `regional/<RegionName>/` (for local basin or subregion data)
3. **Add your data**:
   - Include relevant data files (e.g., `surface.h5`, `boundary.geojson`, `v1d.fd_modfile`). See [DataFormats](wiki/DataFormats.md) for format specifications.
   - Provide a `README.md` describing:
     - Source and authorship
     - Format and units
     - Recommended use
     - Reference publication (if available)
   - Include version info (e.g., `v1.0`, `v1.1`, etc.)

4. **Optional**: If your dataset includes a processing script, place it under `tools/` or alongside the data with documentation.

5. **Open a Pull Request (PR)** with a brief description of:
   - What region/model your data covers
   - Whether it is new or replaces a previous version
   - Any known limitations or assumptions

### ✅ Review Process

- Your PR will be reviewed for:
  - Completeness and clarity of metadata
  - Format consistency with existing data
  - Scientific soundness and provenance

We may suggest edits or clarifications before merging. Once accepted, your dataset will become part of the official NZCVM community archive.



---

## 📑 Registry Integration

All accepted datasets are listed in `nzcvm_registry.yaml`, which defines recognized tomography models, basin models, and submodels for the NZCVM engine.

---

**Need help?**  
Open a GitHub Issue or email: [sung.bae@canterbury.ac.nz]

Thanks for contributing to the NZCVM community!
