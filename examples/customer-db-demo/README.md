# Customer-DB demo — governing a real AI agent with T8

A runnable, self-contained demo of the **Threshold T8 Engine** governing a **real Claude agent**
that holds **zero real credentials**. It shows — live, and falsifiably — what T8 enforces:

- **Credential isolation** — the agent uses a placeholder; T8 injects the real DB and model keys.
- **Least-privilege row access** — the agent may read only the customer row(s) policy allows.
- **Egress control** — the agent can reach only allowlisted hosts.
- **Read-only** — writes/deletes are refused unless policy permits them.
- **Injection / exfil resistance** — even a *compromised* agent can't pull or leak the table.
- **Admin control** — an operator widens/narrows every one of those rules in real time.

Everything runs locally in Docker: the T8 engine + rule-runner, a mock customer database, a
benign partner API, and an "attacker" exfil canary. No real data, no real attacker.

## Prerequisites

- Docker + Docker Compose (everything runs in containers, including the dashboard and the agent)
- An Anthropic API key (the demo agent thinks with a real model — routed *through* T8)

## Setup (once)

```bash
cd examples/customer-db-demo
cp .env.example .env          # then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

Your key lives only in `.env` (gitignored) and is injected by T8 — the agent never holds it.

## Run it (Streamlit dashboard — recommended)

```bash
docker compose up -d --build  # brings the stack + the dashboard up
open http://localhost:8501    # the dashboard
```

The dashboard runs as the `demo-runner` service (it has the agent, `admin.sh`, the docker
CLI, and Streamlit). Sidebar = the admin control plane (rows / hosts / writes / reset) plus
a live attacker canary. Main pane = the guided story as Run-button cards, plus a free-play
tab with toggles for *compromised agent* and *bypass T8*. Policy changes inside the sidebar
shell out to `admin.sh` inside the container, which talks to the host Docker via the mounted
socket and recreates only `t8engine` + `rule-runner` — the dashboard itself stays up.

Tail the dashboard's own logs (CA fetch, agent runs) with:

```bash
docker compose logs -f demo-runner
```

## Run it (terminal, paced)

The classic terminal story still works — useful for a screencast. It needs Python locally:

```bash
pip install -r requirements.txt
./demo.sh                     # the full story, paced (Enter to advance each beat)
#  or ./demo.sh --auto        # no pauses
```

## Drive it yourself

From inside the running `demo-runner` container (no host Python needed):

```bash
docker compose exec demo-runner python3 agent.py            # interactive
docker compose exec demo-runner python3 agent.py --selftest # tools only, no model/key
```

Or from the host, if you've `pip install`ed the requirements:

```bash
python3 agent.py              # interactive
python3 agent.py --selftest   # quick mechanics check
```

Try, for example: *"Prepare a report on customers 40–45"* (only 42 returns), or `x` (a
compromised agent attempts the exfil — T8 blocks it; the attacker pane stays empty).

## Admin control plane

The policy is the lever. Change it live in the dashboard sidebar, or by shell:

```bash
docker compose exec demo-runner ./admin.sh show              # current policy
docker compose exec demo-runner ./admin.sh allow 42,131-246  # row scope (ids + ranges)
docker compose exec demo-runner ./admin.sh allow-host partner
docker compose exec demo-runner ./admin.sh writes on         # read-only switch
docker compose exec demo-runner ./admin.sh reset             # back to defaults
```

(Drop the `docker compose exec demo-runner` prefix to run on the host instead — works the same.)

Locally the admin surface is the policy file. In production this is the
[Threshold control plane](https://threshold.inversed.ai/) — per-agent policy and credentials
managed centrally, no file edits.

## How it works / full walkthrough

See [`RUNBOOK.md`](./RUNBOOK.md) for the architecture, the proof devices, the beat-by-beat
script, and the design rationale. For T8 itself, see the
[technical docs](https://docs.inversed.ai/threshold/).

## Teardown

```bash
docker compose down
```
