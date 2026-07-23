# Suggestions

- Define a reusable project-tooling convention for future repositories:
  `<project>` for human-facing workflows, optional domain commands such as
  `<project> cad`, and `<project>ctl` for packaging, deployment, services,
  upgrades, logs, and migrations. Agent discovery should ask which of these
  interfaces exists and is authoritative before using lower-level commands.
  A small future CAD project can be the first independent trial.
