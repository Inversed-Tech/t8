---
name: t8engine-setup
description: Stand up a local T8 Engine instance (Threshold's HTTP/MCP proxy) on the user's machine via Docker Compose. Use when the user wants to "install t8engine", "set up Threshold locally", route an agent's HTTPS traffic through a policy proxy, install permission rules in front of an LLM/tool API, or get a CA-trusted HTTPS MITM dev proxy. Covers compose layout, route TOML, .env, optional rule-runner, two integration modes (HTTPS_PROXY+CA vs. HTTPS-prefix), and CA install for Debian/Alpine/RHEL/macOS.
---

You are setting up a **local T8 Engine** for the user. T8 is Threshold's data plane: a small HTTP/MCP proxy that sits in front of upstream APIs (LLMs, tool servers, etc.) and intercepts agent traffic so policies, credential swaps, and audit hooks can be applied without changing agent code.

**This skill is local-only.** The user runs two Docker containers (`t8engine` + `rule-runner`). No backend, frontend, database, or account is required. The enterprise control plane at `https://threshold.inversed.ai/` is optional and only relevant if the user wants per-agent credentials managed remotely — flag it once and move on unless they ask.

**Container platform.** This skill is written for Docker Compose because that's the common path. The two images are plain OCI containers, so t8 runs equivalently on Podman (`podman compose`, or a Quadlet/Kubernetes unit), Kubernetes (a `Deployment` + `Service` per image, with `t8engine.toml` as a `ConfigMap` and secrets as a `Secret`), or any cloud container runner (ECS, Cloud Run, Fly, etc.). If the user is on one of those, translate the compose file into the equivalent shape — keep the two images, the rule-runner kept off the public network, the config file mounted read-only, and the same env-var contract. Everything else in this skill (routes, rules, CA install, integration modes) applies unchanged.

## Pinned images

Use these exact tags when generating the compose file:

- `ghcr.io/inversed-tech/t8engine:v0.1`
- `ghcr.io/inversed-tech/rule-runner:v0.1`

If the user later wants to upgrade, they pull a newer published tag from `ghcr.io/inversed-tech/t8engine` and `ghcr.io/inversed-tech/rule-runner`.

## How to run the setup

Work through the steps below in order. At each step, **show the user what you're about to write/run** before doing it, and ask for confirmation if you're about to touch a file outside the current working directory (e.g. shell rc files, system trust stores).

### Step 0 — Pre-flight

Before generating anything, verify:

1. `docker` and `docker compose` are available (`docker compose version`). If not, ask the user to install Docker Desktop / Docker Engine first.
2. Pick a directory. Default: `./t8engine-local/` in the user's current working directory. Confirm with the user.
3. Pick a host port for T8. Default `1800`. If `1800` is taken (`ss -tlnp sport = :1800` or `lsof -iTCP:1800 -sTCP:LISTEN`), suggest `18000`.
4. Ask the user which **integration mode** they want — see "Integration modes" below. The choice affects the agent-side config, not the compose file, so you can set up the stack first and decide later, but it's good to surface the trade-off early.

### Step 1 — Create the files

Inside the chosen directory, create three files:

#### `compose.yaml`

```yaml
services:
  t8engine:
    image: ghcr.io/inversed-tech/t8engine:v0.1
    ports:
      - "127.0.0.1:${T8_PORT:-1800}:1800"
    env_file:
      - path: .env
        required: false
    environment:
      T8_CONFIG_FILE: /t8engine.toml
      T8_CA_SEED: ${T8_CA_SEED:-}
      RULE_RUNNER_URL: http://rule-runner:8080
      # Optional: connect to the enterprise control plane for per-agent
      # credentials. Leave empty for purely local operation.
      CONTROL_PLANE_URL: ${CONTROL_PLANE_URL:-}
    volumes:
      - ./t8engine.toml:/t8engine.toml:ro
    depends_on:
      - rule-runner
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://localhost:1800/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
      interval: 30s
      timeout: 2s
      retries: 5
      start_period: 2s

  rule-runner:
    image: ghcr.io/inversed-tech/rule-runner:v0.1
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://localhost:8080/healthz').then(r=>r.ok||process.exit(1)).catch(()=>process.exit(1))"]
      interval: 5s
      timeout: 3s
      retries: 5
```

Notes for you, the agent:

- The rule-runner has no published port — it's only reached from t8engine over the compose network. Don't expose it on the host.
- `T8_CA_SEED` is referenced from `.env`; if the user skips persistence, the variable resolves to empty and t8 generates a transient CA on each restart (fine, but the CA cert must be re-installed after every restart).
- `RULE_RUNNER_URL` enables rule evaluation. To disable rules entirely, **remove** the line (don't set it to empty — the t8engine code treats unset as "skip rules"). Default: leave it in.
- **Port binding — pick the least exposure that works.** The default `"127.0.0.1:${T8_PORT:-1800}:1800"` only reaches T8 from the same host. Adjust based on where the target agent runs:
  - **Same compose project** (agent is another service in this `compose.yaml`): drop the `ports:` mapping entirely. Other services reach T8 at `http://t8engine:1800` over the compose network — no host port needed.
  - **Same host, outside compose** (agent runs on the user's machine): keep the default `127.0.0.1:…` bind.
  - **Different host** (agent on another machine/VM/container host): change the bind to `0.0.0.0:…` (or a specific LAN interface). Warn the user this exposes T8 to anything that can reach that interface — they should front it with TLS + auth, restrict via firewall, or use an SSH tunnel / Tailscale instead of binding publicly.

#### `t8engine.toml`

Start with a minimal placeholder so the user can `docker compose up` immediately:

```toml
# T8 Engine route + rule config. See:
#   https://github.com/Inversed-Tech/threshold/blob/main/t8engine/t8engine.example.toml
#   https://github.com/Inversed-Tech/threshold/blob/main/docs/t8engine.md
#   https://github.com/Inversed-Tech/threshold/blob/main/docs/rule-scripts.md
#
# `${VAR_NAME}` is interpolated from the environment (loaded from .env).
# An unset variable is a startup error; empty string is allowed.
#
# IMPORTANT: ${...} is interpolated EVERYWHERE including inside comments.
# Do not write ${...} in a comment unless the variable is set.

# Example: inject the real Anthropic key from .env on every Anthropic request.
# Uncomment and edit when ready.
#
# [[routes]]
#     prefix = "https://api.anthropic.com"
#     [routes.headers]
#         authorization = "Bearer __ANTHROPIC_API_KEY__"

# Example permission rule. Denies DELETE on the Anthropic API.
#
# [[rules]]
# id = "anthropic-read-only"
# script = """
# function rule(ctx) {
#   if (ctx.kind !== 'http') return { action: 'allow' };
#   if (ctx.host === 'api.anthropic.com' && ctx.method === 'DELETE') {
#     return { action: 'deny', reason: 'DELETE not permitted on Anthropic API' };
#   }
#   return { action: 'allow' };
# }
# """
```

(The literal `__ANTHROPIC_API_KEY__` is a placeholder — replace it with `${ANTHROPIC_API_KEY}` when the user has added their key to `.env`. We use `__...__` rather than `${...}` in the **commented-out** example because t8 interpolates inside comments too.)

#### `.env`

```bash
# t8engine local config. KEEP THIS FILE OUT OF GIT.

# Optional: deterministic CA — keeps the installed CA cert valid across
# restarts. Generate once with:
#   openssl rand -hex 32
# Then paste below. If unset, T8 mints a fresh transient CA each boot.
T8_CA_SEED=

# Optional: enterprise control plane for per-agent credential management.
# Leave empty for purely local operation.
# CONTROL_PLANE_URL=https://threshold.inversed.ai

# Optional: alternate host port (default 1800).
# T8_PORT=18000

# Upstream API keys go here, then referenced from t8engine.toml as ${VAR_NAME}.
# Example:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
```

After writing the files, also generate a `T8_CA_SEED` and offer to populate it (`openssl rand -hex 32`). Strongly recommend doing this — it's the difference between installing the CA once vs. on every restart.

Add `.env` to a local `.gitignore` if the directory is inside a repo.

### Step 2 — Boot the stack

```bash
cd <chosen-dir>
docker compose up -d
docker compose logs -f t8engine  # confirm "Config loaded"
curl -fsS http://localhost:1800/healthz   # → {"status":"ok"}
```

If the health check fails:
- `docker compose logs t8engine` — most failures are TOML parse errors or unresolved `${VAR}` references. The error message is precise.
- `docker compose logs rule-runner` — should print "Server listening at 0.0.0.0:8080".

### Step 3 — Pick an integration mode (user-facing decision)

Explain both options and let the user choose. **You can come back and switch later — both can coexist.**

#### Option A — HTTPS Prefix (no CA install)

The agent sends requests to T8 with the upstream URL embedded in the path. Works for any SDK that lets you set a custom base URL.

```
Real upstream:  https://api.anthropic.com/v1/messages
Through T8:     http://localhost:1800/https://api.anthropic.com/v1/messages
```

Agent-side change (Anthropic SDK as example):

```bash
export ANTHROPIC_BASE_URL="http://localhost:1800/https://api.anthropic.com"
```

Or in Python:

```python
client = anthropic.Anthropic(base_url="http://localhost:1800/https://api.anthropic.com")
```

**Pros:** no CA, no system changes, works across languages/SDKs that honour a base URL.
**Cons:** doesn't catch traffic from libraries that hard-code the upstream host (some MCP clients, curl with full URLs, etc.). Only HTTP between the agent and T8 unless the user fronts T8 with their own TLS terminator.

#### Option B — HTTPS Proxy with CA install (catches 100% of HTTPS)

The agent sets `HTTPS_PROXY` and trusts T8's CA. Every outbound HTTPS connection is intercepted regardless of how the agent code is written.

```bash
export HTTPS_PROXY=http://localhost:1800
```

Then install the CA — see Step 4.

**Pros:** total coverage. Required if the user can't control SDK base URLs.
**Cons:** must install a CA cert in the system trust store and/or language runtime; some hardened applications pin certs and refuse.

Most users picking this for an LLM agent project want Option B. Recommend it unless the user has a specific reason (sandboxed environment, container where they can't `update-ca-certificates`, etc.).

### Step 4 — Install the CA (Option B only)

T8 serves both the cert and a self-installing script.

**One-liner (auto-detects Debian/Ubuntu/Alpine/RHEL/Fedora/Arch/macOS):**

```bash
curl -fsSL http://localhost:1800/ca.sh | sh
```

The script also prints the language-runtime env vars to set (`NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE`, etc.).

**Manual, by platform** (use when `ca.sh` fails or the user wants control):

```bash
curl -fsSL http://localhost:1800/ca.crt -o t8-engine-ca.crt
```

| Platform | Command |
|---|---|
| Debian / Ubuntu / Devcontainers | `sudo cp t8-engine-ca.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates` |
| Alpine | same as Debian |
| RHEL / Fedora / CentOS | `sudo cp t8-engine-ca.crt /etc/pki/ca-trust/source/anchors/ && sudo update-ca-trust extract` |
| macOS | `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain t8-engine-ca.crt` |

**Language runtimes that don't use the system store** (do *in addition* to the OS install, not instead of it):

```bash
# Node.js
export NODE_EXTRA_CA_CERTS=/absolute/path/to/t8-engine-ca.crt

# Python requests / httpx
export REQUESTS_CA_BUNDLE=/absolute/path/to/t8-engine-ca.crt
# or, more broadly:
export SSL_CERT_FILE=/absolute/path/to/t8-engine-ca.crt

# Some Python projects pin certifi — append to the bundle:
cat t8-engine-ca.crt >> "$(python -c 'import certifi; print(certifi.where())')"
```

If `T8_CA_SEED` was set in `.env`, this is a **one-time** install. Without the seed, the CA changes on every `docker compose restart t8engine` and the install must be redone.

### Step 5 — Add a route (optional, demonstrates value)

If the user has an upstream credential they want T8 to inject (so the agent only ever sees a placeholder), edit `t8engine.toml`:

```toml
[[routes]]
    prefix = "https://api.anthropic.com"
    [routes.headers]
        authorization = "Bearer ${ANTHROPIC_API_KEY}"
```

Add `ANTHROPIC_API_KEY=sk-ant-…` to `.env`, then:

```bash
docker compose up -d --force-recreate t8engine
```

The agent's code keeps `ANTHROPIC_API_KEY=t8-managed` (or any placeholder); T8 strips the placeholder and injects the real key on the way out.

### Step 6 — Add a rule (optional)

Rules are JS/TS functions that run for every proxied request. Full schema and examples: <https://github.com/Inversed-Tech/threshold/blob/main/docs/rule-scripts.md>.

Minimal example — block a specific host:

```toml
[[rules]]
id = "block-evil"
script = """
function rule(ctx) {
  if (ctx.kind !== 'http') return { action: 'allow' };
  if (ctx.host.endsWith('evil.example.com')) {
    return { action: 'deny', reason: 'host blocked by policy' };
  }
  return { action: 'allow' };
}
"""
```

Restart t8engine after editing. A denied request comes back as `403 {"error":"Denied by rule","reason":"…","ruleId":"…"}`.

### Step 7 — Verify end-to-end

After the user has configured an agent or an SDK to go through T8, sanity-check from a shell first:

```bash
# Option A (HTTPS prefix mode):
curl -v http://localhost:1800/https://example.com/

# Option B (HTTPS proxy mode), assuming CA installed:
curl -v -x http://localhost:1800 https://example.com/

# Should return 200 with example.com content. Logs:
docker compose logs t8engine --tail=20
```

A successful proxied call logs a `"proxy"` line with `target`, `via`, and (if matched) `rewrite`.

## Integration modes — quick reference

| | HTTPS Prefix (Option A) | HTTPS Proxy + CA (Option B) |
|---|---|---|
| Agent env var | `…_BASE_URL=http://localhost:1800/<upstream>` | `HTTPS_PROXY=http://localhost:1800` |
| CA install needed | No | Yes (see Step 4) |
| Coverage | Only APIs whose base URL is configurable | All outbound HTTPS |
| Good for | SDK-based agents (Anthropic/OpenAI/Gemini SDKs) | Black-box agents, MCP clients, mixed tooling |

## Enterprise control plane (optional, mention briefly)

If the user mentions Threshold, agent management, or "per-agent credentials", point them at `https://threshold.inversed.ai/`:

- Sign up, create an agent, mint a `t8ak_…` agent key.
- Set `CONTROL_PLANE_URL=https://threshold.inversed.ai` in `.env`, restart t8engine.
- The agent sends the `t8ak_…` token in `Authorization: Bearer …` (or any of the configured agent-key headers). T8 looks up that agent's per-route credentials from the control plane and injects them — overriding any local TOML route for the same prefix.
- Without `CONTROL_PLANE_URL`, none of this is active — everything stays local.

Don't push the control plane; this skill is about the local install.

## Troubleshooting

**`Undefined env var in config`** — t8engine interpolates `${...}` in *every* part of the TOML, comments included. Remove or rewrite any `${...}` reference whose variable isn't in `.env`.

**`502 Upstream unreachable`** — t8engine reached the upstream but the connection failed. Check the upstream URL is correct and (if MITM mode) that the upstream isn't pinning a public CA the agent can't reach.

**`Container unhealthy` on first `compose up`** — race between t8engine and rule-runner. `docker compose logs rule-runner` — if it's listening, restart t8engine: `docker compose restart t8engine`.

**HTTPS proxy mode: Python `httpx` complains about missing AKI** — the t8engine image includes the AKI extension in generated certs, so this should not happen with the pinned image. If it does, the CA is from a stale t8engine version — pull the pinned tag explicitly: `docker compose pull t8engine`.

**CA cert silently rejected by macOS / Linux** — the system trust store was updated but the language runtime uses its own. Set `NODE_EXTRA_CA_CERTS` / `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` *in addition* to the OS install.

**CA invalidates after every restart** — `T8_CA_SEED` is not set or was changed. Set it in `.env`, re-install the CA once, never change the seed again.

## Files this skill writes

When you finish, the user should have:

```
<chosen-dir>/
  compose.yaml      # the two-service stack (committed if shared)
  t8engine.toml     # routes + rules (committed without secrets)
  .env              # API keys, CA seed (gitignored)
  .gitignore        # contains .env (if dir is in a repo)
```

Nothing else. The skill should not modify the user's shell rc files, `~/.docker/`, or system trust store without explicit confirmation at each touch.