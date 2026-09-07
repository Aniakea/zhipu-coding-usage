# ADR 0004 — API key handling

- **Status**: Accepted (2026-09-08); amended 2026-09-08 with a third source

## Context

The plugin needs one Zhipu Coding Plan API key per account. Keys exist in the
wild under several environment-variable conventions, and the shell process
should never hold the key (ADR 0002).

## Decision

Lookup order (first hit wins):

1. **Environment** (read by the collector only, never by QML):
   `ZHIPUAI_API_KEY` → `ZAI_API_KEY` → `GLM_API_KEY`
2. **Config file**: `~/.config/omarchy/zhipu-coding-usage.json`
   ```json
   {
     "apiKey": "…",
     "region": "cn",
     "notify": true,
     "organization": null,
     "project": null
   }
   ```
3. **opencode auth store** (amendment): `~/.local/share/opencode/auth.json`,
   provider ids `zhipuai-coding-plan`/`zhipu`/`zhipuai` → region `cn`,
   `zai-coding-plan`/`zai` → region `intl`. Mirrors copilot-companion's
   `gh auth token` lookup: Omarchy users running opencode against a GLM
   coding plan already hold the key there, so the plugin works zero-config.

Rules:

- Env wins over the config file (user decision, Round 1).
- The key is used **only** to build the `Authorization` header for the
  configured region's host. It is never written to the state file, never
  logged, never passed on a command line that other users could read.
- Missing key ⇒ collector exits non-zero with a plain message; panel shows a
  "no API key configured" state instead of zeros.
- Region defaults to `cn`; README documents that the key and region must match
  (the two regions' keys are not interchangeable).

## Consequences

- Works zero-config for users who already export a Zhipu/z.ai key.
- Plaintext-at-rest risk is inherited from the config file; mitigated by
  `0600` permissions set on first write, and documented in the README security
  section.
- No key rotation/refresh handling — out of scope v1.
- Multi-account (both regions simultaneously) deferred; the config schema
  deliberately leaves room (single object now, array later).

## Second amendment (2026-09-08, decoupled from OpenCode)

The runtime opencode fallback is **removed**. Runtime resolution is exactly
two sources: environment variables, then the plugin's own config file. Two
explicit one-time commands own key setup instead:

- `--set-key [KEY]` — writes the key (prompted silently when omitted) to the
  config file, mode 0600;
- `--import-key` — copies the key from OpenCode's credential store into the
  config **once**, on explicit user invocation, printing only a masked echo.

Rationale: a silent read of another application's credential store is a fuzzy
trust boundary for a marketplace-listed plugin, and in practice it made
OpenCode the de-facto key owner (no env, no config → the plugin only worked
because OpenCode happened to hold the key). The import keeps migration
one command long while making the runtime dependency graph empty.
