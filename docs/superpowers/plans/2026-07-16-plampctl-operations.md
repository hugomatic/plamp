# Plampctl Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add discoverable local status, logs, and readiness-aware restart operations.

**Architecture:** Small Bash helpers print commands, query systemd, and poll the existing HTTP root. All mutating workflows share the readiness helper.

**Tech Stack:** Bash and Python `unittest` command stubs.

### Task 1: Operational commands

**Files:** Modify `plampctl`; modify `tests/test_plampctl.py`.

- [ ] Add failing stub tests for status, logs options, command echoing, immediate readiness, retry, and timeout.
- [ ] Implement shared command-printing and readiness helpers plus `status` and `logs` dispatch/help.
- [ ] Route restart, upgrade, and reinstall completion through readiness.
- [ ] Run focused and full tracked tests, commit, and push.
