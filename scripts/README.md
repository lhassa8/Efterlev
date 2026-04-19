# scripts/

Developer-facing helper scripts. Not part of the shipped `efterlev` package and
not imported by the library code. Each script is intended to be runnable
standalone via `uv run python scripts/<name>.py`.

## Contents

- `trestle_smoke.py` — loads the vendored NIST SP 800-53 Rev 5 catalog via
  `compliance-trestle` and prints metadata plus a recursive control count.
  Used once pre-hackathon to confirm the Python 3.12 install is clean.

These scripts are expected to be replaced or removed as the real library and
primitive wiring lands during the hackathon.
