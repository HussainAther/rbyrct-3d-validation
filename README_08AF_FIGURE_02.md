# RBYRCT 08AF: Figure 2 – real 08M/08Q reconstruction slices

**No experiments are rerun. The frozen 08M and replayed 08Q archives are read-only.**

In the repo root `C:\Users\shuss\Downloads\rbyrct-3d-05a`, extract the two `.py` files and this README. Using PowerShell with conda env `rbyrct-3d`:

```powershell
python -m pytest test_figure_02_08m_reconstructions.py -q
python figure_02_08m_reconstructions.py `
    --08m-dir ..\rbyrct-results\experiment08m\frozen_first `
    --08q-dir ..\rbyrct-results\experiment08q\full_replay_first `
    --output-dir figures\08af\figure02_first `
    --inspect-phantom
```

The script checks 08M object summary, regenerates the selected object's truth and defect mask with repository functions, requires both to have identical SHA256 fingerprints to the frozen object manifest, verifies the two 08Q `.npy` source hashes, validates global RMSE against the 08Q independently replayed RMSE table, and only then renders identical-scale reconstruction/error images.

It chooses the lower of the two median objects under the frozen primary global gain, then the matched model and numerically smallest acquisition seed, and the x-slice through the median defect-mask coordinate. These rules are determined before displaying images. One illustrative object is **not** a substitute for the eight-object quantitative plot.

Outputs are PDF (vector container with rasterized voxels), SVG, PNG, and a JSON manifest in `figures\08af\figure02_first`.

View result:

```powershell
Get-Content "figures\08af\figure02_first\figure_02_manifest.json"
Start-Process "figures\08af\figure02_first\Figure_02_08M_reconstruction_comparison.png"
```

**If the source-return-type check fails**, do not bypass the verification. Post the complete traceback plus the printed `defect_phantom array returns` and `defect_support arrays` diagnostics. We can adapt extraction to your exact repository function shapes without compromising provenance. The script refuses to overwrite an existing output directory: use `figure02_second` for reruns.

Figure 3 visual QA note: its mean annotations visually overlap the lowest object row; revise positioning independently rather than editing frozen values or the figure PDF by hand.
