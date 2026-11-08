# RBYRCT-08AJ-AP — Read-Only Production Qualification Evidence Review

**Scope:** Reconcile the disabled 480-job AA contract against the completed **AN (8³, 40/40)** and **AO (32³, selected 20/40)** engineering-audit evidence. AP does **not** execute reconstructions, unlock the cohort, certify 480 jobs, approve a scientific method, sign a resource policy, or freeze sources. The independent AP report-structure checker does not repeat independent MART numerical replay.

## Install

Extract these four files into the existing `rbyrct-3d-05a` project root:

- `experiment_08aj_ap.py`
- `experiment_08aj_ap_audit.py`
- `test_experiment_08aj_ap.py`
- `README_08AJ_AP.md`

Requires Python 3.9+ and pytest for tests; the AP scripts themselves use Python standard library only. The prior AA, AN and AO results must remain unchanged.

## PowerShell commands

Run from project root, within `(rbyrct-3d)`:

```powershell
python -m pytest test_experiment_08aj_ap.py -q

$apRoot = "results\experiment08aj_ap\qualification_first"
New-Item -ItemType Directory -Force -Path "results\experiment08aj_ap\audit_inputs" | Out-Null

# Capture the existing independent AN and AO audits as JSON files.
# These commands REPLAY engineering reconstructions for verification; they
# do not modify or execute the locked prospective study.
python experiment_08aj_an_audit.py @anArgs --require-complete |
    Out-File -FilePath "results\experiment08aj_ap\audit_inputs\an8_audit.json" -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "AN 8-cube numerical audit failed" }

python experiment_08aj_an_audit.py @aoArgs |
    Out-File -FilePath "results\experiment08aj_ap\audit_inputs\ao32_audit.json" -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "AO 32-cube numerical audit failed" }

$apArgs = @(
    "--output-dir", $apRoot,
    "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
    "--an8-dir", "results\experiment08aj_an\engineering_8_first",
    "--ao-dir", "results\experiment08aj_an\engineering_32_ao_first",
    "--an8-audit", "results\experiment08aj_ap\audit_inputs\an8_audit.json",
    "--ao-audit", "results\experiment08aj_ap\audit_inputs\ao32_audit.json"
)

python experiment_08aj_ap.py --mode prepare @apArgs
if ($LASTEXITCODE -ne 0) { throw "AP qualification report preparation failed" }

python experiment_08aj_ap.py --mode check @apArgs
if ($LASTEXITCODE -ne 0) { throw "AP evidence drift or invalid report" }

python experiment_08aj_ap_audit.py --output-dir $apRoot
if ($LASTEXITCODE -ne 0) { throw "AP independent report-structure audit failed" }

Get-Content "$apRoot\qualification_report.json"
```

`$anArgs` and `$aoArgs` are the PowerShell arrays from the verified earlier stages. If they are no longer present in the current session, define them again using the paths shown above plus AA and M paths. **PowerShell note:** Windows PowerShell 5.1 may add a UTF-8 BOM to the captured audit. AP accepts both BOM and no-BOM UTF-8 files. You can also use direct redirection:

```powershell
python experiment_08aj_an_audit.py @anArgs --require-complete > "results\experiment08aj_ap\audit_inputs\an8_audit.json"
python experiment_08aj_an_audit.py @aoArgs > "results\experiment08aj_ap\audit_inputs\ao32_audit.json"
```

AP's `--mode check` compares the complete reconstructed report against the saved bytes, including input hashes. Never rerun `--mode prepare` in an existing output directory.

## Optional previously prepared Y scientific register

Supply `--y-dir results\experiment08aj_y\consolidation_first` if it exists and is the verified Y directory. Its status and decision register are included as unapproved review evidence; AP does not treat Y as a signed authorization. Use the exact same `--y-dir` option for prepare and check.

## Expected outcome

- `AP_READ_ONLY_EVIDENCE_RECONCILED_NOT_APPROVED`
- AA: 480 disabled job specifications, 96 measurement groups, 24 objects, 2 acquisition seeds
- AN: 40 reported independently audited engineering jobs at 8³
- AO: 20 reported independently audited engineering jobs at 32³ across four complete five-policy groups
- Five gates still blocked, **production execution disabled**
- Separate structural review: `AP_INDEPENDENT_REPORT_STRUCTURE_PASS`

AP verifies audit JSON status, job coverage, result errors, and final receipt linkage, **not** the saved measurement and reconstruction arrays. Its structural auditor is deliberately not described as an independent numerical audit. The AN/AO auditor runs immediately prior to AP are the numerical evidence, and the saved JSON hashes preserve provenance. Further source-tree, environment, and 480-job production certification remain separate tasks.

## Readiness blockers

| Gate | Requirement still unresolved |
| --- | --- |
| G1 | Named approval of 24 related synthetic phantoms, family morphology and generalization limits |
| G2 | Named approval of fixed-24-object descriptive estimand and any conditional generator-level inference, assumptions, multiplicity and sensitivity analysis |
| G3 | Named, explicit approval of resource/failure policy, including limits and controlled retry rules |
| G4 | A true 480-job object-parameterized backend and independent production outcome auditor, both qualified without executing prospective objects prematurely |
| G5 | Formal source/environment lock, independent drift verification and explicitly recorded scientific signoff; subsequent authorization remains separate |

**No performance claim, confirmatory results, automatic permission escalation, or protocol freeze follows from AP.**
