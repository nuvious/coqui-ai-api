# Known issues

Limitations a reader should know about without leaving the repository, and the
copy an autonomous agent can read, since it has no network access and cannot
reach GitHub Issues. The issue tracker is the record for humans. When the two
disagree, the tracker wins.

Each entry below is stated in full in [DESIGN.md](DESIGN.md) under "Known
deviations" or "Open questions". This file is the short list.

## Security

- **The service has no authentication, and CORS allows every origin.** No route
  checks a credential, and the shipped configuration leaves `flask-cors` at its
  permissive default. Do not expose this service to a network you do not trust.
  A security model is decided and recorded in DESIGN.md; none of it is
  implemented yet.

## Dependencies and the container image

- **The project depends on the unmaintained `TTS==0.22.0`.** Coqui AI shut down
  in January 2024. The maintained fork is `coqui-tts`. Migrating to it is EP-01.
- **The published container image carries a large inherited vulnerability
  surface.** A Trivy scan on 2026-07-30 found 435 HIGH and 24 CRITICAL findings
  in `ghcr.io/nuvious/coqui-ai-api`, essentially all of them from the 2023-era
  base image rather than from this project's own code. `pip-audit` cannot see
  them because it only sees what the project installs.
- **The image is not built from `uv.lock`.** The versions the gate audits are not
  the versions that ship.
- **Python is capped below 3.12** by the `TTS==0.22.0` pin.

## Testing

- **No test exercises real synthesis.** The suite mocks the TTS engine, so a
  change that breaks actual audio generation passes the gate. There is no GPU
  runner and no real-model end-to-end check.
- **`make smoke` does not run in CI.** The 16.9 GB base image is at or over the
  free disk on a standard GitHub-hosted runner, so a `Dockerfile` or entrypoint
  break can reach `main` without CI noticing. Run it locally after touching
  either.

## Runtime behaviour

- **All job state is in memory.** A restart loses every job. This is a deliberate
  design decision for a single-process self-hosted service, not a defect, but it
  surprises people who expect jobs to survive a restart.
- **Concurrency under real load is unproven.** `tests/test_lock_ordering.py`
  covers one historical deadlock by construction, not the general case.
