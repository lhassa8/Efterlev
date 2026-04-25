# Smoke fixture

Minimal Terraform with deliberate compliance gaps, used only by the
release-verification workflow `.github/workflows/release-smoke.yml`
(SPEC-09).

**This is not example Terraform.** Do not copy `fixture.tf` into a real
codebase — it is intentionally non-compliant and designed to fail scan
with known findings.

## Contract

Running `efterlev init && efterlev scan` against this directory must
produce:

- At least one HTML report in `.efterlev/reports/`.
- At least one evidence record in `.efterlev/store.db`.
- Non-zero exit **only** when `--fail-on-finding` is set.

`assert.py` in this directory enforces that contract. It is called by
the smoke matrix after the scan step.

## What each resource exists to exercise

| Resource | Detector expected | What triggers it |
|---|---|---|
| `aws_s3_bucket.smoke_logs` | `aws.encryption_s3_at_rest` | Missing `server_side_encryption_configuration` |
| `aws_lb_listener.smoke_http` | `aws.tls_on_lb_listeners` | `protocol = "HTTP"` instead of HTTPS |

Two is sufficient for a smoke test. Breadth is covered by the main
detector test suite under `tests/detectors/`.

## If you need to add fixtures

Keep this fixture minimal. If you need deeper coverage for a new
detector, add it to the detector's own `fixtures/` directory under
`src/efterlev/detectors/<source>/<capability>/fixtures/`, not here.
The smoke fixture's only job is to prove the installed tool works
end-to-end on every platform and install method the matrix covers.
