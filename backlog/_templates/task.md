---
id: T-__NN__-__MM__-__TT__
type: task
schema_version: 1
title: __TITLE__
epic: EP-__NN__
story: US-__NN__-__MM__
status: todo
deps: []
scope: [] # repo-relative paths (or prefixes) this task works in; the dirty-tree check uses it
          # to tell a relevant uncommitted file from an irrelevant one. Optional: leave empty
          # for no declared scope.
commit:
  type: feat
  scope: repo
---

## Objective

What this task makes true, and why it matters. One paragraph. Point at the section of the
specification that governs it rather than restating it.

## Acceptance criteria

Each one must be checkable by running something. The session self-reports against this list, and
the orchestrator re-runs the gate independently, so a criterion nobody can check is a criterion
nobody meets.

- [ ]
- [ ]

## Constraints

Pointers into the specification. Rules this task must not break, and why they exist.

## Out of scope

Mandatory. Name what an eager agent would wrongly pull in, and which task owns it instead. This
section is binding.
