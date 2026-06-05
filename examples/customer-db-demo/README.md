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

- Docker + Docker Compose
- Python 3.9+ with the Anthropic SDK: `pip install -r requirements.txt`
- An Anthropic API key (the demo agent thinks with a real model — routed *through* T8)

## Setup (once)

```bash
cd examples/customer-db-demo
cp .env.example .env          # then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
pip install -r requirements.txt
```

Your key lives only in `.env` (gitignored) and is injected by T8 — the agent never holds it.

## Run it (Streamlit dashboard — recommended)

```bash
docker compose up -d          # boot the stack (or use the sidebar "Boot" button)
streamlit run app.py
```

A live dashboard with the admin control plane in the sidebar and the beats as Run buttons in
the main pane. The attacker canary refreshes in place — through T8 it stays at zero; in the
counterfactual it lights up. Free-play tab lets you type ad-hoc requests with toggles for
"compromised agent" and "bypass T8".

## Run it (terminal, paced)

```bash
./demo.sh                     # the full story, paced (Enter to advance each beat)
#  or ./demo.sh --auto        # no pauses
```

`demo.sh` boots the stack, fetches the demo CA, and walks every beat.

## Drive it yourself

```bash
python3 agent.py              # interactive: type requests, watch T8 govern each call
python3 agent.py --selftest   # tool calls only, no model/key — quick mechanics check
```

Try, for example: *"Prepare a report on customers 40–45"* (only 42 returns), or `x` (a
compromised agent attempts the exfil — T8 blocks it; the attacker pane stays empty).

## Admin control plane

The policy is the lever. Change it live and re-run a request to see behavior flip:

```bash
./admin.sh show                 # current policy
./admin.sh allow 42,131-246     # row scope (ids + ranges)
./admin.sh allow-host partner   # egress allowlist
./admin.sh writes on            # read-only switch
./admin.sh reset                # back to defaults
```

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
