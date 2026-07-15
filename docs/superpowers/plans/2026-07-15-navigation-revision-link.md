# Navigation Revision Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the separate GitHub navigation link with one revision link to the running commit.

**Architecture:** `plamp_web.server` resolves the short Git revision once during startup and passes it into page renderers. `plamp_web.pages` remains a pure renderer: `main_nav` escapes the supplied revision and links known revisions to the repository commit URL.

**Tech Stack:** Python, FastAPI, `unittest`, server-rendered HTML.

## Global Constraints

- Render `[rev <short revision>]` after the other navigation items.
- Remove the separate `GitHub` link.
- Link known revisions to `https://github.com/hugomatic/plamp/commit/<revision>`.
- Render unlinked `[rev unknown]` if Git revision discovery fails.
- Page rendering must not execute Git.

---

### Task 1: Shared revision-aware navigation

**Files:**
- Modify: `plamp_web/pages.py`
- Modify: `plamp_web/server.py`
- Test: `tests/test_pages.py`
- Test: `tests/test_config_api.py`

**Interfaces:**
- Consumes: existing `git_output(["git", "rev-parse", "--short", "HEAD"], repo_root=REPO_ROOT)`.
- Produces: `main_nav(controller_ids: list[str] | None = None, revision: str = "unknown") -> str`; page renderers accept an optional `revision` and pass it to `main_nav`.

- [ ] **Step 1: Write failing renderer and startup tests**

Add tests asserting that `main_nav(revision="ebaf545")` contains only `<a href="https://github.com/hugomatic/plamp/commit/ebaf545">[rev ebaf545]</a>`, that `main_nav(revision="unknown")` contains unlinked `[rev unknown]`, and that startup stores the result of the existing short-revision Git command.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest tests.test_pages tests.test_config_api -v`

Expected: failures because `main_nav` and page renderers do not accept a revision and startup does not store one.

- [ ] **Step 3: Implement the minimal revision flow**

In `pages.py`, remove the GitHub link, add a revision argument to `main_nav` and each shared-nav page renderer, escape the revision, link it only when it is non-empty and not `unknown`, and pass it into every `main_nav` call.

In `server.py`, initialize `APP_REVISION = "unknown"`; during startup assign the short Git result or `"unknown"`; pass `APP_REVISION` into every page renderer.

- [ ] **Step 4: Run focused and full tests**

Run focused tests as in Step 2, then run:

`UV_CACHE_DIR=/tmp/uv-cache /home/hugo/.local/bin/uv run python -m unittest discover -s tests -q`

Expected: all tests pass.

- [ ] **Step 5: Commit, push, and deploy**

Commit `plamp_web/pages.py`, `plamp_web/server.py`, and their tests. Push `feature/agent-first-pico-report-clean`, deploy it using `./plampctl remote-install hugo@sprout.local ~/plamp --branch feature/agent-first-pico-report-clean`, and confirm the rendered home page contains the deployed revision link.
