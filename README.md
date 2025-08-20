# NZCVM Community Data Repository

Welcome to the **New Zealand Community Velocity Model (NZCVM) Data Repository** — a curated, version-controlled archive of seismic velocity model input datasets for Aotearoa New Zealand.

This repository supports community contributions, collaborative review, and open access to datasets used for building 3D velocity models, including tomography, 1D profiles, Vs30 surfaces, and region-specific basin models.

---

## 📁 Repository Structure
```
.
├── global/ # Nation-wide or reference datasets
│   ├── surface/ # Surface elevation or topography grids
│   ├── tomography/ # National tomography models (e.g., NZWIDE)
│   │   └── tools/ # Utility scripts for processing tomography data
│   ├── vm1d/ # 1D velocity models (reference profiles)
│   └── vs30/ # Vs30 (shear-wave velocity) maps
└── regional/ # Localised basin and crustal models by region
    ├── Canterbury/
    ├── Wellington/
    └── ...

```

- Each **regional/** subdirectory contains basin model data for that geographic area, including surface definitions, boundaries, and velocity overrides.
- The **global/** directory holds national-scale inputs used as the base layer in NZCVM simulations.

---

## 📌 Purpose

This repository serves as the **community-managed data layer** of the NZCVM software ecosystem. Datasets in this repository are used by the NZCVM engine to generate 3D seismic velocity models.

All contributions follow a transparent review process and are tracked by version, enabling reproducibility and long-term stewardship.

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
