# Plamp Host Tool Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Plamp bootstrap install an explicitly labeled runtime toolchain and agentic-efficiency toolchain, with practical documentation for humans and agents.

**Architecture:** Define the two Debian package groups as Bash arrays in the existing bootstrap script and install each group under an honest heading. Protect the exact package contract with source-level unit tests, then document package-to-command purpose and safe starter examples without changing `plampctl` delegation or service behavior.

**Tech Stack:** Bash, Debian `apt`, Python `unittest`, Markdown.

## Global Constraints

- Runtime and agentic-efficiency groups install by default; there is no opt-in flag.
- Runtime packages are exactly `bash coreutils findutils grep sed tar cron git curl ca-certificates ffmpeg python3-picamera2 avahi-daemon avahi-utils libnss-mdns`.
- Agentic-efficiency packages are exactly `ripgrep gh shellcheck jq usbutils lsof strace openscad`.
- OpenSCAD documentation warns that Raspberry Pi CGAL renders are CPU- and memory-heavy and graphical previews may require a display server.
- Existing `--public` nginx behavior remains unchanged.
- UART, Pico transport, model detection, and platform enforcement are out of scope.

---

### Task 1: Enforce and install the two package groups

**Files:**
- Modify: `tests/test_bootstrap_installer.py`
- Modify: `deploy/bootstrap/install-plamp.sh`

**Interfaces:**
- Consumes: the existing unconditional `apt-get update` and optional `--public` nginx install.
- Produces: Bash arrays `runtime_packages` and `agentic_efficiency_packages`, each passed separately to `apt-get install`.

- [ ] **Step 1: Replace the broad installer test with failing package-contract tests**

Add `import re`, a `package_group()` helper that extracts a named Bash array, and these tests:

```python
def package_group(script: str, name: str) -> list[str]:
    match = re.search(rf"^{name}=\(\n(?P<body>.*?)^\)$", script, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"missing package group: {name}")
    return match.group("body").split()


class BootstrapInstallerTests(unittest.TestCase):
    def test_install_script_separates_runtime_dependencies(self):
        script = INSTALLER.read_text(encoding="utf-8")

        self.assertEqual(
            package_group(script, "runtime_packages"),
            [
                "bash", "coreutils", "findutils", "grep", "sed", "tar", "cron",
                "git", "curl", "ca-certificates", "ffmpeg", "python3-picamera2",
                "avahi-daemon", "avahi-utils", "libnss-mdns",
            ],
        )
        self.assertIn("Installing Plamp runtime dependencies", script)

    def test_install_script_installs_agentic_efficiency_tools_by_default(self):
        script = INSTALLER.read_text(encoding="utf-8")

        self.assertEqual(
            package_group(script, "agentic_efficiency_packages"),
            ["ripgrep", "gh", "shellcheck", "jq", "usbutils", "lsof", "strace", "openscad"],
        )
        self.assertIn("Installing tools for agentic efficiency", script)
        self.assertIn('apt-get install -y "${agentic_efficiency_packages[@]}"', script)
```

- [ ] **Step 2: Run the tests and confirm they fail because the arrays are absent**

Run:

```bash
python3 -m unittest tests.test_bootstrap_installer -v
```

Expected: both tests fail with `missing package group`.

- [ ] **Step 3: Define and install both package groups**

Immediately before the existing package-install section, define:

```bash
runtime_packages=(
  bash
  coreutils
  findutils
  grep
  sed
  tar
  cron
  git
  curl
  ca-certificates
  ffmpeg
  python3-picamera2
  avahi-daemon
  avahi-utils
  libnss-mdns
)

agentic_efficiency_packages=(
  ripgrep
  gh
  shellcheck
  jq
  usbutils
  lsof
  strace
  openscad
)
```

Keep one `apt-get update`. Replace the current combined install command with:

```bash
echo "==> Installing Plamp runtime dependencies"
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${runtime_packages[@]}"

echo "==> Installing tools for agentic efficiency"
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${agentic_efficiency_packages[@]}"
```

Leave the conditional nginx install immediately afterward.

- [ ] **Step 4: Run installer tests and Bash syntax verification**

Run:

```bash
python3 -m unittest tests.test_bootstrap_installer -v
bash -n deploy/bootstrap/install-plamp.sh
```

Expected: both installer tests pass and Bash exits zero.

### Task 2: Document the host toolbox

**Files:**
- Create: `docs/host-tools.md`
- Modify: `README.md`
- Modify: `tests/test_bootstrap_installer.py`

**Interfaces:**
- Consumes: the exact runtime and agentic package lists from Task 1.
- Produces: an installation-section link and a package/command/purpose reference with safe examples.

- [ ] **Step 1: Add a failing documentation-contract test**

Add:

```python
def test_host_tools_documentation_is_linked_and_covers_agent_commands(self):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    tools_doc = (ROOT / "docs" / "host-tools.md").read_text(encoding="utf-8")

    self.assertIn("[Host tools](./docs/host-tools.md)", readme)
    for command in ("rg", "gh", "shellcheck", "jq", "lsusb", "lsof", "strace", "openscad"):
        self.assertIn(f"`{command}`", tools_doc)
    self.assertIn("sed -n", tools_doc)
    self.assertIn("sed -i.bak", tools_doc)
    self.assertIn("CPU- and memory-heavy", tools_doc)
```

- [ ] **Step 2: Run the documentation test and confirm it fails**

Run:

```bash
python3 -m unittest tests.test_bootstrap_installer.BootstrapInstallerTests.test_host_tools_documentation_is_linked_and_covers_agent_commands -v
```

Expected: `ERROR` because `docs/host-tools.md` does not exist.

- [ ] **Step 3: Write the tool reference and README link**

Create `docs/host-tools.md` with:

- A runtime table containing every `runtime_packages` package and its command/purpose.
- An agentic-efficiency table containing every `agentic_efficiency_packages` package and its command/purpose.
- Read-only starter examples for `rg --files`, `rg`, `sed -n`, `jq`, `gh`, `shellcheck`, `lsusb`, `lsof`, and `strace`.
- A backup-preserving `sed -i.bak` example.
- OpenSCAD CLI generation guidance and the exact CPU/memory/display warning.

After the installation examples in `README.md`, add:

```markdown
The installer labels required runtime dependencies separately from the tools
included for humans and agents. See [Host tools](./docs/host-tools.md).
```

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
python3 -m unittest tests.test_bootstrap_installer -v
bash -n deploy/bootstrap/install-plamp.sh
python3 -m unittest discover -s tests -v
git diff --check
```

Expected: all tests pass, Bash exits zero, and Git reports no whitespace errors.

- [ ] **Step 5: Commit the implementation**

Run:

```bash
git add deploy/bootstrap/install-plamp.sh tests/test_bootstrap_installer.py docs/host-tools.md README.md docs/superpowers/plans/2026-07-17-host-tool-contract.md
git commit -m "Install and document Plamp host tools"
```
