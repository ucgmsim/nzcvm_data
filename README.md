[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# NZCVM Community Data Repository

Welcome to the **New Zealand Community Velocity Model (NZCVM) Data Repository** — a curated, version-controlled archive of seismic velocity model input datasets for New Zealand.
 
This repository supports community contributions, collaborative review, and open access to datasets used for building 3D velocity models, including tomography, 1D profiles, Vs30 surfaces, and region-specific basin models.
 

---

## 📁 Repository Structure

- **global**: Contains national-scale datasets that serve as the foundation for NZCVM simulations.
    - **surface/**: Holds surface elevation or topography grids used in model generation.
    - **tomography/**: Contains national tomography models like NZWIDE, which provide the seismic velocity structure across New Zealand. See [Tomography](wiki/Tomography.md) for details on national tomography models.
    - **vm1d/**: Includes 1D velocity models that define velocity profiles varying with depth.
    - **vs30/**: Contains Vs30 maps, which provide shear-wave velocity values for
- **regional**: Contains basin-specific datasets for local regions. See [Basins](wiki/Basins.md) for details on the 44 basin models (as of August 2025).
    - Each subdirectory (e.g., **Canterbury**, **Wellington**) contains:
        - Basin model data (surfaces, boundaries, velocity overrides)
        - 1D profiles or Vs30 maps specific to that region
        - Tools or scripts for processing regional data
- **wiki** : Contains documentations
- **tools**: Contains scripts and utilities for processing, resampling, or converting model data formats.


---

## 📌 Purpose

This repository serves as the **community-managed data layer** of the NZCVM software ecosystem. Datasets in this repository are used by the NZCVM engine to generate 3D seismic velocity models.

All contributions follow a transparent review process and are tracked by version, enabling reproducibility and long-term stewardship.

---
## 🔽 Cloning this Repository (with Git LFS)

Some datasets in this repo (e.g., `.h5` tomography/surface files) are large and tracked with **Git Large File Storage (LFS)**.
If Git LFS is not installed, you will only download small pointer files (~100 B) and tools like `h5py` will fail to open them.

### 1) Install Git LFS

Follow the official guide:
👉 https://docs.github.com/en/repositories/working-with-files/managing-large-files/installing-git-large-file-storage

**macOS (Homebrew)**
```bash
brew install git-lfs
git lfs install
```

**Linux**
```bash
sudo apt-get install -y git-lfs   # Debian/Ubuntu
# or
sudo yum install -y git-lfs       # RHEL/CentOS/Fedora
git lfs install
```

**Windows**
- Install from https://git-lfs.com/ (then run `git lfs install` in Git Bash or PowerShell).

### 2) Clone and fetch LFS objects
```bash
git clone https://github.com/ucgmsim/nzcvm_data.git
cd nzcvm_data
git lfs pull
```

### 3) Verify that large files are materialized
```bash
ls -lh global/surface/
# .h5 files should be MBs/GBs, not ~100 bytes.
```

**Troubleshooting**
- If you still see ~100 B files, run:
  ```bash
  git lfs fetch --all
  git lfs checkout
  git lfs status
  ```
- If you’re using this repo via a symlink or submodule from another project, run the `git lfs` commands **inside this repo’s directory**.

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
2. **Create a new directory** (if needed) under either:
   - `global/` (for national-scale datasets)
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

## 📑 Registry Integration

All accepted datasets will be listed in the central `nzcvm_registry.yaml` file located in the root of this repository. 
This registry defines which tomography models, basin models, and submodels are recognized by the NZCVM engine.

Once your data contribution is reviewed and merged:
- A new **entry will be added to the registry**.
- The entry includes dataset name, paths to boundaries/surfaces, version metadata, and references to submodels.
- Your data will become discoverable and usable through NZCVM config files.

Each entry in the registry follows a standard structure:

```yaml
- name: Canterbury_v19p1
  author: Robin Lee
  boundaries:
    - regional/Canterbury/Canterbury_outline_WGS84.txt
  surfaces:
    - path: regional/Canterbury/Canterbury_Basement_WGS84.in
  submodel: canterbury1d_v2
  notes:
    - Pre-Quaternary geology
```
To request inclusion:

- Include a proposed entry in your pull request (or describe it in your PR message).
- Maintainers will review and append it to nzcvm_registry.yaml if accepted.
---

**Need help?**  
Contact us via GitHub Issues or email: [sung.bae@canterbury.ac.nz]

Thanks for contributing to the NZCVM community!

---

# Data Formats

See [DataFormats](wiki/DataFormats.md) for detailed information about supported data formats and conventions.
