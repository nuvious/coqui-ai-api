# Guidance for Claude

All contributor, architecture, testing, and release guidance for this project
lives in a single source of truth: **[CONTRIBUTING.md](CONTRIBUTING.md)**. What
the project is *meant to be*, and what has been deliberately decided about it,
lives in **[DESIGN.md](DESIGN.md)**.

Read both before making changes. In particular:

- **CONTRIBUTING.md, "The gate"**: `make verify` is the one command that checks
  the repository. Run it before declaring anything done.
- **CONTRIBUTING.md, "For AI agents"**, whose Rule 0 requires that every completed
  task review and (if necessary) update both `README.md` (user-facing docs) and
  `CONTRIBUTING.md` (developer/agent docs).
- **DESIGN.md, "Known deviations" and "Open questions"**: read these before
  assuming something is a bug.
