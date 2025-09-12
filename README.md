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


---

## Install

If you are interested in both the data **and** the NZCVM modeling code, please visit:

🔗 [NZCVM Velocity Modeling Code (velocity_modelling)](https://github.com/ucgmsim/velocity_modelling)

That repository provides the full modeling engine and will guide you through linking to this data repository.

---

If you only want to obtain the **data** (for use with your own tools or for later integration with `velocity_modelling`), follow these steps:

```bash
# Clone the data
git clone https://github.com/ucgmsim/nzcvm_data.git ~/nzcvm_data
cd ~/nzcvm_data

# Install Git LFS if you need large files (HDF5, etc.)
# See: https://docs.github.com/en/repositories/working-with-files/managing-large-files/installing-git-large-file-storage
git lfs install
git lfs pull   # omit if you only need non-LFS assets

# (Optional) record your chosen path for future convenience
mkdir -p ~/.config/nzcvm_data
echo '{"data_root": "'$HOME'/nzcvm_data"}' > ~/.config/nzcvm_data/config.json
```

Verify large files:
```bash
ls -lh surface/
# .h5 files should be MBs/GBs, not ~100 bytes.
```

You can always install [velocity_modelling](https://github.com/ucgmsim/velocity_modelling) later to use this data with the full NZCVM engine.

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
