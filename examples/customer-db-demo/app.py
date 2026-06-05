"""Streamlit dashboard for the T8 customer-DB demo.

Same story as ./demo.sh, but driven from a UI: the sidebar is the admin control plane
(rows / hosts / writes / reset) plus the attacker canary; the main pane walks the
beats and offers a free-play tab. Underneath it just shells out to agent.py and
admin.sh, so behavior matches the terminal demo exactly.

Run:  streamlit run app.py
"""
import os
import re
import subprocess
from pathlib import Path

import streamlit as st

DEMO_DIR = Path(__file__).parent.resolve()
ANSI = re.compile(r"\x1b\[[0-9;]*m")
RULE_LINE = re.compile(r"^[─━]+$")

st.set_page_config(page_title="T8 Customer-DB Demo", layout="wide")


# ---- subprocess wrappers --------------------------------------------------

def _run(cmd, timeout=240, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run(
            cmd, cwd=DEMO_DIR, capture_output=True, text=True,
            timeout=timeout, env=env,
        )
        return (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        return f"[ERROR] timed out after {timeout}s: {' '.join(cmd)}\n{e.stdout or ''}{e.stderr or ''}"
    except FileNotFoundError as e:
        return f"[ERROR] {e}"


def run_agent(args, timeout=240):
    return _run(["python3", "agent.py", *args], timeout=timeout)


def run_admin(args, timeout=120):
    return _run(["./admin.sh", *args], timeout=timeout)


def docker_compose(args, timeout=120):
    return _run(["docker", "compose", *args], timeout=timeout)


# ---- state queries (cached briefly) ---------------------------------------

@st.cache_data(ttl=2, show_spinner=False)
def get_policy():
    out = _run(["./admin.sh", "show"], timeout=30)
    def grab(key):
        m = re.search(rf"{re.escape(key)}\s*:\s*(\S*)", out)
        return m.group(1) if m else "?"
    return {
        "rows": grab("rows allowed"),
        "hosts": grab("egress allowlist"),
        "writes": grab("db writes allowed"),
    }


@st.cache_data(ttl=2, show_spinner=False)
def attacker_log():
    out = _run(["docker", "compose", "logs", "--no-color", "attacker"], timeout=15)
    hits = [ln for ln in out.splitlines() if "EXFILTRATION RECEIVED" in ln]
    return {"count": len(hits), "lines": hits[-5:]}


@st.cache_data(ttl=5, show_spinner=False)
def stack_status():
    out = _run(["docker", "compose", "ps", "--format", "{{.Name}}\t{{.State}}"], timeout=15)
    return out.strip() or "(no services)"


def invalidate_state():
    get_policy.clear()
    attacker_log.clear()
    stack_status.clear()


# ---- output parsing + rendering -------------------------------------------

def parse_events(text: str):
    """Parse agent.py / admin.sh output into (tag, message) events."""
    events = []
    for raw in ANSI.sub("", text).splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if RULE_LINE.match(line.strip()):
            events.append(("RULE", ""))
            continue
        m = re.match(r"^\s*\[([A-Z0-9]+)\]\s*(.*)$", line)
        if m:
            events.append((m.group(1), m.group(2)))
        else:
            events.append(("TEXT", line))
    return events


TAG_STYLES = {
    "USER":      ("info",    "#dbeafe"),
    "AGENT":     ("plain",   "#d8b4fe"),
    "TOOL":      ("info",    None),
    "DB":        ("plain",   "#fdba74"),
    "SCENE":     ("plain",   "#93c5fd"),
    "PROOF":     ("plain",   "#93c5fd"),
    "SCENARIO":  ("plain",   "#93c5fd"),
    "READY":     ("plain",   "#93c5fd"),
    "SELFTEST":  ("plain",   "#93c5fd"),
    "MODE":      ("warning", None),
    "HINT":      ("warning", None),
    "ERROR":     ("error",   None),
}


def _render_t8(msg: str):
    if "ALLOWED" in msg:
        st.success(f"**[T8]** {msg}")
    elif "DENIED" in msg:
        st.error(f"**[T8]** {msg}")
    else:
        st.warning(f"**[T8]** {msg}")


def _render_result(msg: str):
    happy = any(w in msg.lower() for w in ("blocked", "received nothing"))
    breach = "breach" in msg.lower() or "dumped" in msg.lower()
    if breach:
        st.error(f"**[RESULT]** {msg}")
    elif happy:
        st.success(f"**[RESULT]** {msg}")
    else:
        st.info(f"**[RESULT]** {msg}")


def render_events(events):
    if not events:
        st.caption("(no output)")
        return
    for tag, msg in events:
        if tag == "RULE":
            st.markdown(
                "<hr style='margin:0.25rem 0; border:none; border-top:1px solid #2a2a2a'>",
                unsafe_allow_html=True,
            )
            continue
        if tag == "T8":
            _render_t8(msg); continue
        if tag == "RESULT":
            _render_result(msg); continue
        if tag == "DIRECT":
            st.warning(f"**[DIRECT]** {msg}"); continue
        if tag == "TEXT":
            st.markdown(
                f"<div style='font-family:ui-monospace,monospace; color:#9ca3af; "
                f"font-size:0.9em; margin-left:0.5rem'>{msg}</div>",
                unsafe_allow_html=True,
            )
            continue
        style, colour = TAG_STYLES.get(tag, ("plain", None))
        body = f"**[{tag}]** {msg}"
        if style == "info":
            st.info(body)
        elif style == "warning":
            st.warning(body)
        elif style == "error":
            st.error(body)
        elif colour:
            st.markdown(
                f"<div style='color:{colour}'><b>[{tag}]</b> {msg}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(body)


# ---- session state --------------------------------------------------------

if "beat_out" not in st.session_state:
    st.session_state.beat_out = {}        # beat_id -> raw output
if "play_log" not in st.session_state:
    st.session_state.play_log = []        # list of (heading, raw output)


def record_beat(beat_id, raw):
    st.session_state.beat_out[beat_id] = raw
    invalidate_state()


def record_play(heading, raw):
    st.session_state.play_log.append((heading, raw))
    invalidate_state()


# ---- sidebar: stack + admin control plane + canary ------------------------

with st.sidebar:
    st.subheader("Stack")
    c1, c2 = st.columns(2)
    if c1.button("Boot", use_container_width=True):
        with st.spinner("docker compose up -d"):
            docker_compose(["up", "-d"])
        invalidate_state()
        st.toast("Stack up")
    if c2.button("Down", use_container_width=True):
        with st.spinner("docker compose down"):
            docker_compose(["down"])
        invalidate_state()
        st.toast("Stack down")
    with st.expander("Services", expanded=False):
        st.code(stack_status(), language="text")

    st.divider()
    st.subheader("Admin policy")
    policy = get_policy()
    pc1, pc2, pc3 = st.columns(3)
    pc1.metric("rows", policy["rows"])
    pc2.metric("hosts", policy["hosts"] or "—")
    pc3.metric("writes", policy["writes"])

    rows_spec = st.text_input("allow rows", value="", placeholder="42,131-246",
                              help="ids and ranges, e.g. 42  131-246  42,131-246")
    if st.button("Apply row scope", use_container_width=True, disabled=not rows_spec.strip()):
        with st.spinner("applying policy (~3-5s)"):
            run_admin(["allow", rows_spec.strip()])
        invalidate_state(); st.rerun()

    host = st.text_input("host", value="", placeholder="partner")
    hc1, hc2 = st.columns(2)
    if hc1.button("Allow host", use_container_width=True, disabled=not host.strip()):
        with st.spinner("applying policy"):
            run_admin(["allow-host", host.strip()])
        invalidate_state(); st.rerun()
    if hc2.button("Deny host", use_container_width=True, disabled=not host.strip()):
        with st.spinner("applying policy"):
            run_admin(["deny-host", host.strip()])
        invalidate_state(); st.rerun()

    writes_now = policy["writes"] == "true"
    new_writes = st.toggle("DB writes enabled", value=writes_now)
    if new_writes != writes_now:
        with st.spinner("applying policy"):
            run_admin(["writes", "on" if new_writes else "off"])
        invalidate_state(); st.rerun()

    if st.button("Reset to defaults", use_container_width=True, type="secondary"):
        with st.spinner("resetting"):
            run_admin(["reset"])
        invalidate_state(); st.rerun()

    st.divider()
    st.subheader("Attacker canary")
    canary = attacker_log()
    if canary["count"]:
        st.error(f"Exfil hits: {canary['count']}")
        with st.expander("recent", expanded=False):
            for ln in canary["lines"]:
                st.code(ln, language="text")
    else:
        st.success("Exfil hits: 0")
    if st.button("Refresh", use_container_width=True):
        invalidate_state(); st.rerun()


# ---- main: title + tabs ---------------------------------------------------

st.title("Threshold · T8 — Customer-DB demo")
st.caption(
    "A real Claude agent that holds zero real credentials, governed by T8. "
    "Click through the story on the left; widen or narrow policy from the sidebar; "
    "watch the attacker canary stay quiet."
)

tab_story, tab_play = st.tabs(["Guided story", "Free play"])


# ---- guided story ---------------------------------------------------------

BEATS = [
    {
        "id": 0,
        "title": "Scene — the agent's wallet is placeholders",
        "blurb": "The agent holds NO real credentials. Real keys live only inside T8. "
                 "A direct call to the DB with the placeholder gets a 401.",
        "cmd": lambda: run_agent(["--scene"]),
    },
    {
        "id": 1,
        "title": "Credential isolation — read customer 42",
        "blurb": "T8 injects the real key at the edge; the agent succeeds without holding a secret.",
        "cmd": lambda: run_agent(["--run", "1"]),
    },
    {
        "id": 2,
        "title": "Least privilege — 'report on customers 40–45'",
        "blurb": "Benign request — the model happily fetches all six; T8 allows 42 and denies the rest.",
        "cmd": lambda: run_agent(["--run", "2"]),
    },
    {
        "id": 3,
        "title": "Egress control — enrich from the partner directory",
        "blurb": "The model calls fetch; T8 refuses egress to a host the admin hasn't allowlisted.",
        "cmd": lambda: run_agent(["--run", "3"]),
    },
    {
        "id": 4,
        "title": "Read-only — upgrade customer 42's tier",
        "blurb": "A legitimate write request; T8's read-only policy refuses it at the boundary.",
        "cmd": lambda: run_agent(["--run", "5"]),
    },
    {
        "id": 5,
        "title": "Defense-in-depth — injection planted in the data",
        "blurb": "Layer one: Sonnet reads the malicious note in customer 42 and declines. "
                 "Good — but don't bet on it.",
        "cmd": lambda: run_agent(["--run", "4"]),
    },
    {
        "id": 6,
        "title": "Compromised agent — T8 holds anyway",
        "blurb": "A hijacked agent obeys the planted instruction directly — no model judgment in the loop. "
                 "T8 blocks the bulk read AND the exfil at the boundary.",
        "cmd": lambda: run_agent(["--compromised"]),
    },
    {
        "id": 7,
        "title": "Without T8 — same agent, direct (the breach)",
        "blurb": "Counterfactual: without T8 the same compromised agent dumps the table "
                 "and ships it to the attacker. Watch the canary in the sidebar light up.",
        "cmd": lambda: run_agent(["--compromised", "--no-t8"]),
    },
    {
        "id": 8,
        "title": "ADMIN: widen row scope → 42, 131-246",
        "blurb": "Customer 200 was denied earlier; now permitted, because the admin widened the scope. "
                 "Applies the policy then retries the request.",
        "cmd": lambda: (run_admin(["allow", "42,131-246"]) +
                        run_agent(["--run", "Look up customer 200 and give me their email."])),
    },
    {
        "id": 9,
        "title": "ADMIN: allowlist the partner host",
        "blurb": "The egress that was refused in beat 4 now succeeds — admin opened exactly one host.",
        "cmd": lambda: run_admin(["allow-host", "partner"]) + run_agent(["--run", "3"]),
    },
    {
        "id": 10,
        "title": "ADMIN: enable DB writes",
        "blurb": "The write refused in beat 5 now goes through — read-only was an admin switch all along.",
        "cmd": lambda: run_admin(["writes", "on"]) + run_agent(["--run", "5"]),
    },
]


with tab_story:
    top = st.columns([3, 1, 1])
    top[0].markdown("**Tip:** reset before each demo so beat 8/9/10 land cleanly.")
    if top[1].button("Reset policy", use_container_width=True):
        with st.spinner("resetting"):
            run_admin(["reset"])
        invalidate_state(); st.rerun()
    if top[2].button("Clear results", use_container_width=True):
        st.session_state.beat_out = {}
        st.rerun()

    for beat in BEATS:
        with st.container(border=True):
            cols = st.columns([5, 1])
            cols[0].markdown(f"### {beat['id']}. {beat['title']}")
            cols[0].caption(beat["blurb"])
            ran = beat["id"] in st.session_state.beat_out
            label = "Re-run" if ran else "Run"
            if cols[1].button(label, key=f"beat_{beat['id']}", use_container_width=True):
                with st.spinner(f"running beat {beat['id']}…"):
                    record_beat(beat["id"], beat["cmd"]())
                st.rerun()
            if ran:
                with st.expander("Result", expanded=True):
                    render_events(parse_events(st.session_state.beat_out[beat["id"]]))


# ---- free play ------------------------------------------------------------

SUGGESTIONS = [
    ("1 · Look up customer 42 (allowed)", "1"),
    ("2 · Report on customers 40–45 (row-scope)", "2"),
    ("3 · Enrich from partner (egress)", "3"),
    ("4 · Follow planted instructions (injection)", "4"),
    ("5 · Upgrade customer 42's tier (read-only)", "5"),
]


with tab_play:
    fc1, fc2 = st.columns(2)
    naive = fc1.toggle("Compromised / naive agent",
                       help="Agent obeys instructions found in data — no refusals.")
    bypass = fc2.toggle("Bypass T8 (counterfactual)",
                        help="Agent uses the REAL key directly. The 'before' world.")
    flags = []
    if naive: flags.append("--naive")
    if bypass: flags.append("--no-t8")

    st.markdown("**Quick requests**")
    for label, n in SUGGESTIONS:
        if st.button(label, key=f"sugg_{n}", use_container_width=True):
            with st.spinner("running"):
                record_play(label, run_agent(["--run", n, *flags]))
            st.rerun()

    custom = st.text_input("Custom request",
                           placeholder="Look up customer 200 and give me their email.")
    rc1, rc2 = st.columns([1, 1])
    if rc1.button("Run custom", use_container_width=True, disabled=not custom.strip()):
        with st.spinner("running"):
            record_play(f"Custom: {custom.strip()}", run_agent(["--run", custom.strip(), *flags]))
        st.rerun()
    if rc2.button("Compromised-agent attack", use_container_width=True, type="primary"):
        attack_flags = ["--no-t8"] if bypass else []
        with st.spinner("running"):
            record_play(
                "Compromised attack" + (" (no T8)" if bypass else ""),
                run_agent(["--compromised", *attack_flags]),
            )
        st.rerun()

    st.divider()
    if not st.session_state.play_log:
        st.caption("Run something above to see output here.")
    else:
        if st.button("Clear free-play log"):
            st.session_state.play_log = []
            st.rerun()
        for heading, raw in reversed(st.session_state.play_log):
            with st.expander(heading, expanded=False):
                render_events(parse_events(raw))
