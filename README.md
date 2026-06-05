# t8 — Claude Code plugins for Threshold

This repo is a [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces.md) for integrating the Threshold T8 Engine into agentic workflows. See the [landing page](https://inversed.ai/) for product context and the [technical docs](https://docs.inversed.ai/threshold/) for architecture.

## Install

From inside Claude Code:

```
/plugin marketplace add Inversed-Tech/t8
/plugin install t8engine-setup@t8
```

That's it. The `t8engine-setup` skill becomes available immediately — ask Claude Code something like "set me up with t8engine locally" and it will walk you through the Docker Compose stack, route TOML, optional rules, and CA installation.

## Plugins in this marketplace

| Plugin | What it does |
|---|---|
| [`t8engine-setup`](./plugins/t8engine-setup) | Stands up a local T8 Engine (proxy + rule-runner) via Docker Compose, configures routes/rules, and walks through the two integration modes (HTTPS prefix vs. HTTPS proxy + CA). |

## Examples

| Example | What it shows |
|---|---|
| [`customer-db-demo`](./examples/customer-db-demo) | A runnable demo: a **real Claude agent holding zero real credentials**, governed by T8. Shows credential isolation, least-privilege row access, egress control, read-only enforcement, injection/exfil resistance, and a live **admin control plane** — all locally in Docker. `cd examples/customer-db-demo && ./demo.sh`. |

## Updating

To pull newer plugin versions:

```
/plugin marketplace update t8
```

## Layout

```
.claude-plugin/
  marketplace.json                  ← marketplace registry
plugins/
  t8engine-setup/
    .claude-plugin/plugin.json      ← plugin manifest
    skills/t8engine-setup/SKILL.md  ← the skill itself
examples/
  customer-db-demo/                 ← runnable T8 governance demo (./demo.sh)
```

## License

Apache-2.0. See individual plugin `plugin.json` for per-plugin metadata.

## See also

- [Threshold Homepage](https://inversed.ai/)
- [Threshold Control Plane](https://threshold.inversed.ai/) — the enterprise solution on top of the T8 engine.
