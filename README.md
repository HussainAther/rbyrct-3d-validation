# Three dimensional adaptive ray acquisition validation

Code and recorded synthetic results for **Adaptive Ray Acquisition in Three-Dimensional Tomography: Reconstruction Benefits and Failure Modes Under Forward-Model Mismatch**, by Syed Hussain Ather.

Study 1 is experiment 04P; Study 2 is experiment 04Q-B. Both use four deterministic analytic phantom families. These are numerical experiments, not physical scanner measurements. Earlier scripts and results document policy development and auxiliary checks.

## Published manuscript archive

Version 1.0-manuscript is archived at https://doi.org/10.5281/zenodo.23600802. The immutable ZIP corresponds to commit cea7b2da99a2de8059d88ebf185ff995aca9f127 (tag v1.0-manuscript). Its SHA-256 is 4ebd171048b745c93360a86ebc8b0a7f871bec65361dfd97a9da9280985aaed0. Later documentation updates do not change that archived snapshot.

## Installation

Create a clean environment with `conda env create -f environment.yml`, or install `requirements.txt` into Python 3.12. The scientific calculations require Python, NumPy and SciPy; their pins match the original recorded versions. Pandas and Matplotlib are for plotting. ASTRA was used by earlier experiments 04C–04F and is not needed for the manuscript studies or current unit suite.

`validation/04r/` retains the original Windows environment records byte-for-byte. Its UTF-16 `requirements_frozen.txt` contains local build paths and is provenance evidence, not a portable installer or lockfile. The portable pins do not recreate the full Windows binary build.

## Validate the archive

```sh
python -m unittest discover -v
python audit_results.py
```

There are 80 tests: the existing 77 and three acquired-prefix replay tests in `test_causal_replay.py`. Replay is local and deterministic, not a full noninterference proof. The audit verifies 480 metrics and 384 comparisons per study, complete unique scenario-policy keys, positive finite RMSE, recomputed gains, and ten byte-identical repeat scientific CSVs. Protocols agree except `output_dir`; timing is excluded.

To compare Tables 1–7 with a manuscript, run `python audit_results.py PATH_TO_MANUSCRIPT.docx`. This uses only the standard library to read the Word tables.

## Reproduce full experiments

```sh
python reproduce_study.py study1 rerun/study1
python reproduce_study.py study2 rerun/study2
```

These commands use all parameters from the archived full-study protocols and reject existing output directories. Exact repeatability is established only for the recorded same-environment Windows repetitions. The 23 October 2026 check ran the unit suite and its small end-to-end simulation on macOS, not full studies. Cross-platform byte identity is not asserted.

## Regenerate figures

```sh
python make_figures.py . figures
```

All five figures are written as 600 dpi PNGs and PDFs with vector labels and marks. Figure 1 is a schematic; Figure 2 uses original phantom arrays; Figures 3–5 use the full-study paired-case CSVs. Scientific CSVs are never modified by plotting.

## Integrity

`SHA256SUMS` lists source, result and provenance files in the prepared archive, excluding `.git`, generated cache files and the manifest itself. Verify with `sha256sum -c SHA256SUMS` or macOS `shasum -a 256 -c SHA256SUMS`.

Published metrics digests:

- Study 1: `fc5d702855b74f1551e56057dd8ea3f4606e8518d2b98ec88c441a5ba13c810c`
- Study 2: `50b03f2d14d6eb2046dfb19021bc53a4bd274073597543f45fce642cab7f246a`

`.gitattributes` disables line-ending conversion for scientific CSV and JSON files. Do not save these files with tools that rewrite line endings. Manuscript files, generated figures and delivery ZIPs are excluded from Git.

## License

Python code and software documentation/configuration are MIT licensed (LICENSE_CODE.txt). Scientific data and provenance in results/ and validation/ are CC BY 4.0 (DATA_LICENSE.txt). These licenses were approved by the author on 23 October 2026.
