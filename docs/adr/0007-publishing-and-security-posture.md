# ADR 0007 — Publishing target and security posture

- **Status**: Accepted (2026-09-08)

## Context

The plugin will run unsandboxed inside every installer's shell process, and
marketplace verification only covers a snapshot commit. Trust must be earned
by the README's security section and minimal dependency surface.

## Decision

- **Publish to the Omarchy marketplace.** Public repo
  `github.com/Aniakea/zhipu-coding-usage`, MIT license, English README.
- Install: `omarchy plugin add https://github.com/Aniakea/zhipu-coding-usage --enable`.
- Development workflow: `omarchy plugin clone omarchy.clock --edit` scaffold →
  replace with our files, keep dev clone under `~/.config/omarchy/plugins/`,
  permanent ID only at publish time, then drop `omarchy.clonedFrom`.
- Pre-submission checklist:
  1. `omarchy plugin validate "$PLUGIN_DIR"` passes.
  2. `qmllint -I "$OMARCHY_PATH/shell"` passes on all QML files.
  3. Click / Escape / summon / hide / disable / re-enable / shell restart /
     removal tested.
  4. `preview.png` of the real bar + panel captured.
- README **must** document (marketplace rules): external deps (`python3`
  stdlib-only, optional `notify-send`), the two network hosts contacted
  (`open.bigmodel.cn` / `api.z.ai`), where the key lives and who reads it
  (ADR 0004), the state/config directories touched, and that removal leaves
  `~/.local/state/omarchy/zhipu/` behind (with the one-line `rm -rf`).

## Consequences

- No telemetry, no external runtime deps beyond python3 + optional libnotify.
- Security review surface = 1 Python file + 2–3 QML files + manifest.
- Snapshot verification will pin the reviewed commit; releases should be
  tagged so the marketplace tracks them.
