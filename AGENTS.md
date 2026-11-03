# Guidance for AI agents

This file holds agent-specific guidance only. Everything that applies to human
contributors and agents alike (setup, the gate, testing, code conventions,
architecture, releases) lives in **[CONTRIBUTING.md](CONTRIBUTING.md)**, and what
the project is _meant to be_, along with what has been deliberately decided about
it, lives in **[DESIGN.md](DESIGN.md)**. A rule a human contributor also needs
belongs there, not here.

Read both before making changes. In particular:

- **CONTRIBUTING.md, "The gate"**: `make verify` is the one command that checks
  the repository. Run it before declaring anything done.
- **CONTRIBUTING.md, "Documentation is part of done"**, whose Rule 0 requires
  that every completed task review and (if necessary) update `README.md`
  (user-facing docs), `CONTRIBUTING.md` (shared developer docs), and this file
  when the change touches an agent-only rule.
- **CONTRIBUTING.md, "Code style & conventions"**: the response-shape contract,
  the security posture, and the conventions the tools cannot check.
- **DESIGN.md, "Known deviations" and "Open questions"**: read these before
  assuming something is a bug.

## Additional rules for agents

These are inlined verbatim into every autonomous session prompt by
`.orchestrator.yaml` (`prompts.house_rules`). Keep them short enough to be read
and specific enough to be followed. Where a rule restates a shared convention
from CONTRIBUTING.md it is a reminder, and CONTRIBUTING.md is the authority.

- **Run `make verify` before declaring a task done.** It is the gate. Your claim
  that the work is correct is a claim, its exit code is the evidence. Do not
  lower the coverage threshold, add a mypy override for this project's own code,
  or widen a flake8 ignore to make a change pass.
- **Git: commit on your own task branch, nothing else.** You may run `git add`
  and `git commit` on the branch the orchestrator put you on, and you may read
  history freely (`log`, `diff`, `blame`, `show`, `status`). You may not create
  or switch branches, merge, push, tag, or rewrite history (`rebase`, `reset
  --hard`, `push --force`). Merging and pushing belong to the maintainer on the
  host.

  > [!NOTE]
  > This is a deliberate override of the backlog-orchestrator default, which
  > forbids agents from running git at all. The trade is recorded in
  > [DESIGN.md](DESIGN.md). If you escalate partway through a task, say plainly
  > in the escalation what you have already committed, because the orchestrator
  > cannot infer it.

- **Never weaken the security posture.** The rule is in CONTRIBUTING.md, "Code
  style & conventions": no route that skips authentication, no wider CORS
  allowlist, and never a logged or echoed token. The global no-authentication
  switch is a deployment choice, not something a task reaches for to make a test
  pass.
- **The `pip-audit` ignore list is closed to you.** The gate's ignores
  (PYSEC-2026-2289, PYSEC-2026-2290, CVE-2026-9856 and PYSEC-2026-4174) are
  enumerated, justified and dated in [DESIGN.md](DESIGN.md), "The transformers
  pin, and four accepted advisories". Do not add one to make a change pass, not
  even with a written justification, and do not edit the `audit` target,
  `pyproject.toml` or `uv.lock` to move an advisory out of the way. Adding an
  ignore is a maintainer decision reached by escalation. Removing the existing
  four once `coqui-tts` allows `transformers >= 5.10.0` is expected and
  encouraged.

  **A new advisory does not, by itself, block your task.** If `make verify` fails
  _only_ at the audit step, on an advisory you did not introduce, it is not your
  task's failure and halting on it would stop the whole run over something no task
  can fix. Treat it the way you treat a host-only check. Concretely, all four must
  hold:

  1. The audit step is the only failing step. Format, lint, types and tests are
     green, at the normal coverage threshold and with no relaxations.
  2. Your task's `scope` does not include `pyproject.toml`, `uv.lock` or the
     `Makefile`, and you changed none of them.
  3. The failure reproduces on the pre-existing tree. Verify it, do not assume it:
     stash or otherwise set your changes aside, run `make audit`, and confirm the
     same advisory appears. If it only appears with your changes applied, you
     introduced it, and it _is_ your task's failure.
  4. You report it in the task result, plainly, as an unresolved gate failure
     left for the maintainer: the advisory id, the affected package and version,
     the fix version, and the evidence from (3).

  Then finish the task and report it done. If any of the four does not hold,
  escalate instead. Do not silence the advisory either way.
- **Do not declare `soundfile`.** CONTRIBUTING.md, "Code style & conventions",
  explains why it is used but undeclared. Declaring it needs `uv lock` to
  re-run, which needs network access the sandbox does not have (`uv lock
  --offline` cannot resolve this project's graph from cache), so an edit to
  `pyproject.toml` or `uv.lock` to declare it fails the gate rather than fixing
  anything.
- Follow the response-shape rule and the refactoring rule in CONTRIBUTING.md,
  "Code style & conventions". The compatibility fields are frozen, native shapes
  may evolve when recorded, and code that must change to be testable gates its
  side effects rather than losing functionality.
- **If the specification does not answer your question, stop and say so.** Read
  [DESIGN.md](DESIGN.md), including its open questions and known deviations,
  before assuming something is a bug. Inventing a plausible answer and building on
  it is worse than halting: the resolution to a genuine gap is an edit to these
  documents, so a question answered only in chat will be asked again next session.
- You have no network access. That is how the run loop is meant to work, not a
  gap in the specification. Follow the standards already recorded in
  CONTRIBUTING.md, DESIGN.md and here rather than escalating because you cannot
  check a source. It also means you cannot read the GitHub issue tracker, so
  `KNOWN_ISSUES.md` in the repository root is the copy you can read.
- **Host-only checks are the maintainer's, not a bar you must clear.** Some
  acceptance criteria can only be verified on a host the sandbox does not have:
  anything that needs Docker (`docker build`, `make smoke`, comparing versions
  inside a built image) or the network the run loop denies (resolving a CUDA
  wheel index). The dev container has no Docker socket and no network, by design.
  For a task like that your bar for "done" is: make the file changes correctly,
  pass `make verify`, and run whatever offline check the task offers. Then state
  plainly in the task result which criteria are left for a maintainer to verify
  on the host, and never claim a build, smoke run, or resolution you could not
  execute. A well-formed task marks those host-only checks as maintainer-verified
  rather than agent-blocking; reporting an honest "maintainer-verified on host"
  for them completes the task, it does not fail it. If a task instead lists a
  host-only check as an ordinary acceptance criterion you are expected to tick,
  that mismatch is itself a spec gap; escalate it rather than looping on a box
  you cannot check.
