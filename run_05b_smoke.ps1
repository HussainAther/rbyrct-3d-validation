# Run from the repository root with your rbyrct-3d Conda environment activated.
$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Python tests failed" }
python experiment_05b_benchmark.py --size 4 --budget 16 --mart-epochs 8
if ($LASTEXITCODE -ne 0) { throw "MART numerical benchmark failed" }
$runId = Get-Date -Format "yyyyMMdd_HHmmss"
$common = @("--size", "4", "--angles", "2", "--factor", "2", "--phantoms", "branches", "--object-types", "replicated", "--offsets", "0", "--budgets", "16", "--seeds", "271828", "--noise-fractions", "0", "--warm-rays", "12", "--batch", "4", "--provisional-epochs", "2", "--diagnostic-epochs", "2", "--mart-epochs", "2", "--candidate-pool", "8", "--diagnostic-every", "4")
python experiment_05b_04p.py @common --output-dir "results/experiment05b_04p_$runId"
if ($LASTEXITCODE -ne 0) { throw "MART 04P smoke failed" }
python experiment_05b_04qb.py @common --output-dir "results/experiment05b_04qb_$runId"
if ($LASTEXITCODE -ne 0) { throw "MART 04QB smoke failed" }
Write-Host "MART numerical and study smoke tests completed; results are exploratory."
