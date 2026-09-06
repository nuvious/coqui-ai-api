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

- **The published container image's vulnerability surface has not been
  remeasured since the engine migration.** A Trivy scan on 2026-07-30, against
  the old `TTS==0.22.0`-based image, found 435 HIGH and 24 CRITICAL findings,
  essentially all of them from the 2023-era base image rather than from this
  project's own code. The migration to a slim base is expected to shrink this,
  but nothing has re-run the scan against the shipped image yet. Descoped to
  maintainer-run future work; full reasoning in DESIGN.md, "Future work",
  "Measure and scan the migrated image".
- **The engine pins `transformers==5.0.0`, which carries three accepted CVEs.**
  `coqui-tts` 0.27.5 cannot import on `transformers > 5.0.0` (it uses a symbol
  removed in 5.1.0), and no `transformers` release both imports and audits fully
  clean. The project pins 5.0.0 and ignores exactly three advisories in
  `pip-audit`: **PYSEC-2026-2289** (Trainer `torch.load` RCE; this project never
  trains), **PYSEC-2026-2290** (LightGlue loader RCE; this project never loads
  LightGlue) and **CVE-2026-9856** (path traversal in `save_pretrained()`; this
  project never calls it, and loads no `transformers` tokenizer or processor).
  All three are in code paths XTTS-v2 inference does not exercise. To be removed
  when `coqui-tts` allows `transformers >= 5.10.0`. Full reasoning in DESIGN.md,
  "The transformers pin, and three accepted advisories".

  CVE-2026-9856 was added on 2026-09-06, after the first two; the threshold for
  dropping the ignores rose from 5.5.0 to 5.10.0 with it. Because that gap keeps
  widening, DESIGN.md, "Future work" now carries a spike on escaping the pin
  outright rather than waiting on a `coqui-tts` release.

## Testing

- **No test exercises real synthesis.** The suite mocks the TTS engine, so a
  change that breaks actual audio generation passes the gate. There is no GPU
  runner and no real-model end-to-end check.
- **`make smoke`'s fit on a GitHub-hosted runner has not been reconfirmed since
  the engine migration.** The old 16.9 GB base image was at or over the free
  disk on a standard runner, which is why `make smoke` runs locally instead of
  in CI. The migration to a slim base is expected to change that, but nothing
  has measured the built image's size yet. Run `make smoke` locally after
  touching the `Dockerfile` or entrypoint until that measurement happens; full
  reasoning in DESIGN.md, "Future work", "Measure and scan the migrated image".

## Runtime behaviour

- **All job state is in memory.** A restart loses every job. This is a deliberate
  design decision for a single-process self-hosted service, not a defect, but it
  surprises people who expect jobs to survive a restart.
- **Concurrency under real load is unproven.** `tests/test_lock_ordering.py`
  covers one historical deadlock by construction, not the general case. The
  blocking `POST /v1/audio/speech` facade now exists and holds a request thread
  for the whole synthesis; exercising it under the test suite surfaced no
  lock-ordering violation, but that is not a load test.
