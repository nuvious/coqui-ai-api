---
id: T-01-02-03
type: task
schema_version: '2'
title: Record the migrated image size and Trivy scan
epic: EP-01
story: US-01-02
status: todo
deps:
- T-01-02-02
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

- [ ] The built image size is recorded in `DESIGN.md` beside the old figure.
- [ ] A Trivy scan of the new image is recorded with its HIGH and CRITICAL counts
      and the date, in the same form as the existing baseline.
- [ ] `KNOWN_ISSUES.md` reflects whatever the scan actually found. If the surface
      is smaller but not gone, say what remains rather than deleting the entry.
- [ ] If the new image is small enough to fit a standard GitHub-hosted runner,
      that fact is recorded in `DESIGN.md`, "Future work", against the existing
      note about returning `make smoke` to CI. Recorded, not acted on.

> [!IMPORTANT]
> This task needs Docker and network access, and the development container has
> neither. It cannot be completed by an autonomous session. Prepare the exact
> commands the maintainer should run and the exact text to record once they have
> the output, then escalate rather than inventing numbers.
>
> Writing a plausible-looking scan result into `DESIGN.md` would be the single
> worst outcome available in this epic. Every later decision about the base image
> reads these figures as measurements.

## Constraints

- The existing baseline was produced with the `aquasec/trivy` image, per
  `DESIGN.md`, "Future work". Use the same method so the two numbers compare.
- Record the scan under "Known deviations" if a real surface remains, and delete
  the deviation only if it is genuinely gone. `DESIGN.md` distinguishes findings
  from plans, and a resolved finding leaves the list rather than being annotated.

## Out of scope

- Adding Trivy to `make verify`. The gate runs offline by recorded decision, and
  a release-time image scan is separate future work.
- Returning `make smoke` to CI, even if the measurement says it would now fit.
