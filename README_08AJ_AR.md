# RBYRCT-08AJ-AR — Noncohort Manifest-to-Numerical-Worker Qualification

**Engineering-only. No prospective execution.** This package is the **first integration stage** toward G4, not G4 approval or a full 480-job production executor. It uses the existing, Windows-verified AN numerical/checkpoint worker, but controls its object/seed/model/policy inputs through a **canonical, source-locked engineering manifest** rather than free-form CLI selectors. Its whitelist remains the two noncohort AN objects and two engineering seeds. Source hashes and the AA disabled 480-job contract are revalidated before every dispatch. The auditor independently replays numerical results via the existing AN auditor.

## Files (extract to repository root)

- `experiment_08aj_ar.py` — immutable manifest construction, AA contract check, fail-closed manifest-to-AN-worker dispatch.
- `experiment_08aj_ar_audit.py` — read-only manifest-to-numerical-evidence reconciliation and independent AN replay.
- `test_experiment_08aj_ar.py` — local control tests using the AN test's stubbed numerical fixture (requires `test_experiment_08aj_an.py`).
- `README_08AJ_AR.md` — this guide.

Requires the existing `experiment_08aj_aa.py`, `experiment_08aj_m.py`, `experiment_08aj_an.py`, `experiment_08aj_an_audit.py`, and their earlier numerical dependencies and source files in the unchanged repo root. Preserve all AN/AO/AP evidence.

## Windows PowerShell — first numerical integration at 8^3

```powershell
python -m pytest test_experiment_08aj_ar.py -q

$arArgs = @(
    '--output-dir', 'results\experiment08aj_ar\manifest_8_first',
    '--aa-dir', 'results\experiment08aj_aa\disabled_path_first',
    '--m-dir', 'results\experiment08aj_m\contract_first'
)

python experiment_08aj_ar.py --mode prepare @arArgs --n 8
python experiment_08aj_ar.py --mode check @arArgs

$jid = 'engineering_alpha__seed_a__same__information_diag'
python experiment_08aj_ar.py --mode catalogue @arArgs --job-id $jid
python experiment_08aj_ar.py --mode dispatch @arArgs --job-id $jid
python experiment_08aj_ar.py --mode run @arArgs --job-id $jid `
    --stop-after-rows 32 --wall-seconds 600 --max-mib 8192
python experiment_08aj_ar.py --mode run @arArgs --job-id $jid `
    --wall-seconds 600 --max-mib 8192

python experiment_08aj_ar_audit.py @arArgs
```

Expected final `AR_INDEPENDENT_ENGINEERING_MANIFEST_AUDIT_PASS`, `engineering_jobs_numerically_audited: 1`, `max_abs_replay_error: 0.0` and `abs_rmse_difference: 0.0`, all production gate flags false.

### Expand to a second object and different seed/model

```powershell
$jid2 = 'engineering_beta__seed_b__independent__uniform_multiscale'
python experiment_08aj_ar.py --mode catalogue @arArgs --job-id $jid2
python experiment_08aj_ar.py --mode dispatch @arArgs --job-id $jid2
python experiment_08aj_ar.py --mode run @arArgs --job-id $jid2 `
    --wall-seconds 600 --max-mib 8192
python experiment_08aj_ar_audit.py @arArgs
```

Expected 2 independently audited jobs and 2 measurement groups. The AR manifest has all 40 combinations but none are executed on `prepare` or `check`. `--require-complete` is intended only when all 40 engineering jobs have been executed.

## Important limitations / next work

1. **Not yet general object parameterization.** The manifest consists only of a fixed, source-coded engineering allowlist. AN is still the underlying hard-coded noncohort fixture generator. This deliberately prevents AR from accepting arbitrary prospective seeds or objects.
2. **Not a novel numerical backend.** AR routes jobs into AN, which was already tested at 8^3 and 32^3; it does not replace the AN worker. It does prove manifest-selected dispatch into the actual numerical/checkpoint/audit pathway on Windows once run there.
3. **No production unlock.** The AA 480 specification contract remains disabled. AR performs zero prospective object generation, zero prospective acquisitions, and zero prospective RMSE calculations.
4. **G4 remains pending.** After AR, build and qualify a genuinely parameterized backend accepting an approved object definition independent of AN's hard-coded fixtures, integrate into a 480-job production roster behind explicit review gates, test all integrity/failure requirements, and separately approve scientific decisions and operational policy. Never infer authorization from this engineering pass.
5. **Resource limits.** AR passes the same supervisor settings to AN; Windows Job Object enforcement is in AN/AH. 600 s and 8192 MiB are provisional engineering values, not approved production limits. No automatic retries.
6. **Evidence immutability.** Run in a fresh output directory; AR refuses `prepare` on an existing root. Never edit earlier AN, AO or AA source/evidence in place. If tests fail, keep the failed evidence for diagnosis.

The local tests operate on stubbed sparse-matrix numerics; the real end-to-end confirmation must come from the user's Windows repository. Gate statuses remain `production_execution_allowed: false`, `production_480_job_certified: false`, `resource_policy_approved: false`.
