# Breakthrough

Multi-component PFAS ion exchange breakthrough simulator, built on the EPA's own
[Homogeneous Surface Diffusion Model (HSDM)](https://github.com/USEPA/Water_Treatment_Models).

Most breakthrough tools model one PFAS compound in isolation. Real source water contains many,
each binding the resin with a different strength. Short-chain compounds break through first and
can be physically displaced off the resin by longer-chain compounds arriving later, pushing
effluent temporarily above influent concentration. This tool models that competition directly,
using EPA's transport equations, not a single-species curve fit.

## What it does

Given the PFAS species you actually measured, their concentrations, and your column geometry,
it predicts:

- **Breakthrough time** - the day effluent first crosses a regulatory limit or chosen threshold,
  per species
- **Limiting species** - which compound actually governs changeout, which is often not the one
  with the strictest regulatory limit
- **Bed volumes** - the standard unit for comparing IX systems independent of scale
- **Cost** - resin charge, changeouts per year, cost per 1,000 gallons treated
- **Required bed depth** - solved backwards from a target service life

## Pages

| Page | Purpose |
|---|---|
| Dashboard | Compliance status and bed-life summary at a glance |
| Simulator | Run a multi-species competitive breakthrough simulation |
| Design solver | Solve for the bed depth needed to hit a target service life |
| Bed & flow | Column geometry, resin specs, and commercial resin presets |
| Selectivity data | Full editable parameter table with provenance for every value |
| Selectivity calculator | Estimate selectivity for a species with no published value |
| Alkalinity converter | Convert pH + alkalinity to the bicarbonate input the model needs |
| Film transfer estimator | Gnielinski correlation for the film transfer coefficient, kL |

## Parameter provenance

Every selectivity coefficient (KxA) in the app is labeled by where it came from:

- **EPA measured** - five PFCAs (PFBA, PFPeA, PFHxA, PFHpA, PFOA), taken directly from EPA's
  published example workbook, `Shiny-IEX/Examples/example_input_medium.xlsx`, in the
  [USEPA/Water_Treatment_Models](https://github.com/USEPA/Water_Treatment_Models) repository.
  Molecular weights from `PSDM/PFAS_properties.xlsx` in the same repo.
- **Derived** - three PFSAs (PFBS, PFHxS, PFOS), set at 100x the same-chain-length PFCA value,
  following Liu et al., *Strong Base Anion Exchange Selectivity of Nine Perfluoroalkyl Chemicals
  Relevant to Drinking Water*, ACS ES&T Water (2023), which reports sulfonate selectivity
  roughly two orders of magnitude above carboxylates at equal chain length.
- **Extrapolated** - PFNA, from a log-linear regression fitted to EPA's own PFCA series
  (R² = 0.963, 0.403 log₁₀ units per CF₂).

This parameter set reproduces the published PFAS breakthrough order from NEWMOA's ion exchange
case history review exactly:
PFBA < PFPeA < PFHxA < PFHpA < PFOA < PFNA < PFBS < PFHxS < PFOS.

All values are editable in **Selectivity data**, and the **Selectivity calculator** page provides
three independent ways to estimate a value that isn't published: from chain length, from a
measured column result, or scaled from a reference compound.

## Resin presets

Specifications for three commercial PFAS-selective resins, taken from manufacturer product data
sheets:

| Resin | Capacity | Matrix | Functional group |
|---|---|---|---|
| CalRes 2301 (Calgon Carbon) | 0.51 eq/L min | Macroporous | Tributylamine |
| AmberLite PSR2 Plus (DuPont) | ≥ 0.7 eq/L | Gel | Quaternary amine |
| Purofine PFA694E (Purolite) | not published¹ | Gel | Complex amino |

¹ Purolite's public data sheet does not list total exchange capacity. A placeholder value is
used and flagged in the app; confirm with the vendor before relying on it.

## Engine

The physics is unmodified EPA code: [`ixpy.hsdmix`](https://github.com/USEPA/Water_Treatment_Models/tree/master/IonExchangeModel),
solving the multi-component HSDM transport equations via orthogonal collocation. This app builds
the input workbook in memory and calls that engine directly - no reimplementation of the
underlying chemistry.

## Running locally

```bash
git clone <this-repo>
cd <this-repo>
pip install -r requirements.txt
git clone https://github.com/USEPA/Water_Treatment_Models.git
streamlit run app.py
```

The EPA repository must be cloned alongside `app.py` since the model imports directly from it.

## Files

```
app.py      Page routing and UI
core.py     Simulation logic, PFAS/resin parameter database
style.py    Theme
requirements.txt
.streamlit/config.toml   Streamlit theme configuration
```

## Limitations

This is a screening tool, not a substitute for pilot testing. Derived and extrapolated
selectivity values carry real uncertainty - the ordering they produce is validated against
published data, but absolute bed-volume predictions for the derived sulfonates have not been
checked against column data. Cost estimates cover resin media only and exclude vessels,
installation, labor, and spent-resin disposal.
