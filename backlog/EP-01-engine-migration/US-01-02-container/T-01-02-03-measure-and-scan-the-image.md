---
id: T-01-02-03
type: task
schema_version: '2'
title: Record the migrated image size and Trivy scan
epic: EP-01
story: US-01-02
status: blocked
deps:
- T-01-02-01
scope:
- DESIGN.md
- KNOWN_ISSUES.md
commit:
  type: docs
  scope: design
---

## Objective

`DESIGN.md` records a 2026-07-30 baseline for the old image: 16.9 GB base, 17.1 GB
built, 435 HIGH and 24 CRITICAL from Trivy. The point of the migration is to move
those numbers. An unmeasured migration cannot be said to have worked, and the
next person to ask "is the image still bad" deserves an answer with a date on it.

## Acceptance criteria

- [ ] The **shipped image** is built with `docker build -t coqui-ai-api:latest .`
      — the CUDA (cu121) default, byte-identical to what `make smoke` builds and
      what `.github/workflows/docker-build.yml` ships. Its built size is recorded
      in `DESIGN.md` beside the old figure and **labelled CUDA**, so it is not
      misread as a slim CPU image.
- [ ] The **CPU variant** size is also recorded (built with the `cpu` build arg,
      see below). It is the redistribution-clean, runner-fit measurement; the
      reasoning is settled in `DESIGN.md`, "The runtime image base, and which
      PyTorch it ships", under "What the shipped CUDA image redistributes".
- [ ] The runtime **base** size (`python:3.11-slim-bookworm`) is recorded, so the
      base-to-base shrink from the old 16.9 GB engine base is visible.
- [ ] A Trivy scan of the **shipped CUDA image** (`coqui-ai-api:latest`) is
      recorded with its HIGH and CRITICAL counts and the date, in the same form
      as the existing 2026-07-30 baseline (435 HIGH / 24 CRITICAL). Compare
      built-to-built: the old *shipped* image was 17.1 GB CUDA (cu118), not the
      16.9 GB base.
- [ ] `KNOWN_ISSUES.md` reflects whatever the scan actually found. If the surface
      is smaller but not gone, say what remains rather than deleting the entry.
- [ ] The `make smoke` / GitHub-runner fit is recorded in `DESIGN.md`, "Future
      work", keyed off **both** sizes: the CUDA image likely does not fit, the CPU
      variant likely does, and returning `make smoke` to CI would mean building
      the CPU variant. Recorded, not acted on.

> [!IMPORTANT]
> This task needs Docker and network access, and the development container has
> neither — this remains true for the next autonomous session. It **cannot** be
> completed by an autonomous session. The build method (`docker build`), the
> variants to record (shipped CUDA + CPU), and the licence question are already
> settled (see below and `DESIGN.md`); what is left is purely the four measured
> numbers, which the maintainer must supply by running the commands below.
>
> Writing a plausible-looking size or scan result into `DESIGN.md` would be the
> single worst outcome available in this epic. Every later decision about the base
> image reads these figures as measurements. Fill the `<PLACEHOLDER>` tokens
> verbatim from real output; do not invent, estimate, or round from memory.

## Constraints

- Build method is decided: plain `docker build`, **not** `docker compose build`.
  All build paths produce identical image content (one `Dockerfile`, one default
  build arg); `docker build` is what ships and what `make smoke` uses, and the old
  compose tag `ai-tts-coqui-ai-api:latest` was a checkout-dir-dependent cosmetic
  name of the *old* engine-based build that no longer exists.
- The existing baseline was produced with the `aquasec/trivy` image, per
  `DESIGN.md`, "Future work". Use the same **tool** so the two scan numbers
  compare. (This "same method" constraint is about Trivy, not the build command.)
- Record the scan under "Known deviations" if a real surface remains, and delete
  the deviation only if it is genuinely gone. `DESIGN.md` distinguishes findings
  from plans, and a resolved finding leaves the list rather than being annotated.

## Commands to run (maintainer, on a machine with Docker + network, from repo root)

```bash
# 1. Runtime base image size (both Dockerfile stages start FROM this)
docker pull python:3.11-slim-bookworm
docker image inspect python:3.11-slim-bookworm --format '{{.Size}}' | numfmt --to=iec

# 2a. Build the SHIPPED image: CUDA cu121 default. Identical to `make smoke` and CI.
docker build -t coqui-ai-api:latest .
docker image inspect coqui-ai-api:latest --format '{{.Size}}' | numfmt --to=iec

# 2b. Build the CPU variant (one build arg; this is the gate's own resolution)
docker build --build-arg TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cpu \
    -t coqui-ai-api:cpu .
docker image inspect coqui-ai-api:cpu --format '{{.Size}}' | numfmt --to=iec

# 3. Trivy scan of the SHIPPED (CUDA) image -- same tool as the 2026-07-30 baseline
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image \
    --severity HIGH,CRITICAL coqui-ai-api:latest
# Record the total HIGH and total CRITICAL, and where they come from (OS packages
# vs specific Python deps), from the summary at the end of the output.
```

Yields six values: `<BASE_SIZE>`, `<CUDA_BUILT_SIZE>`, `<CPU_BUILT_SIZE>`,
`<HIGH>`, `<CRITICAL>`, and today's `<DATE>`.

## Text to record once the numbers are known

**`DESIGN.md`, "The engine dependency" table — replace the `Images` row:**

```
| Images | `ghcr.io/coqui-ai/tts:v0.22.0`, 16.9 GB base / 17.1 GB built, 2023-era (CUDA cu118) | `python:3.11-slim-bookworm` base (<BASE_SIZE>); shipped image <CUDA_BUILT_SIZE> built (CUDA cu121), CPU variant <CPU_BUILT_SIZE>; measured <DATE> |
```

**`DESIGN.md`, "Known deviations" — REPLACE the "The runtime image inherits a
large, dated vulnerability surface" bullet** with (delete it entirely only if the
new scan is genuinely 0/0, per the Constraints):

```
- **The runtime image [still carries / now carries a smaller] vulnerability surface.**
  A Trivy scan of the shipped CUDA image `coqui-ai-api:latest` on <DATE> found
  **<HIGH> HIGH and <CRITICAL> CRITICAL** findings [-- down from 435 HIGH / 24
  CRITICAL on 2026-07-30 --], from <summarise per the scan output: remaining OS
  packages of the slim base and/or specific Python deps>. None of this is reachable
  by `pip-audit`, which only sees what the project installs.
```

**`DESIGN.md`, "Known deviations" — update the "The container smoke test cannot
run on GitHub-hosted runners" bullet** using both sizes against the runner's free
disk (~14 GB on the current standard GitHub-hosted runner image — verify GitHub's
documented value at record time, since there is no network here to check it live).
State whether the CUDA image fits and whether the CPU variant fits.

**`DESIGN.md`, "Future work" — append to the "Return `make smoke` to CI" bullet:**

```
(Measured <DATE>: the shipped CUDA image is <CUDA_BUILT_SIZE>, which [does/does
not] fit a standard GitHub-hosted runner's free disk; the CPU variant is
<CPU_BUILT_SIZE>, which [does/does not]. Returning `make smoke` to CI would mean
building the CPU variant. Not yet acted on.)
```

**`DESIGN.md`, "Future work" — optionally append to the "Scan the built image
(Trivy)" bullet:** `(A second measurement was taken <DATE> against the migrated
image; see "Known deviations".)` — only if it reads better than the pure
forward-looking text.

**`KNOWN_ISSUES.md`, "Dependencies and the container image" — rewrite the "The
published container image carries a large inherited vulnerability surface"
bullet** to match whatever `DESIGN.md`'s Known deviations ends up saying (smaller
numbers, or the entry removed if the surface is genuinely gone). The two documents
must not disagree; `KNOWN_ISSUES.md` is the short copy of `DESIGN.md`.

No file outside this task's `scope:` (`DESIGN.md`, `KNOWN_ISSUES.md`) changes.
Recording the runner-fit fact is in scope; acting on it (wiring Trivy into
`make verify`, returning `make smoke` to CI) is explicitly Out of scope below.

## Out of scope

- Adding Trivy to `make verify`. The gate runs offline by recorded decision, and
  a release-time image scan is separate future work.
- Returning `make smoke` to CI, even if the measurement says it would now fit.
