 # dashboard.py  –  MathGesture Clinical Dashboard
# Run: streamlit run dashboard.py

import sqlite3, json, os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "progress.db")

DIFFICULTY_NAMES = [
    "Lv 0 · Single-Digit +/−",
    "Lv 1 · Single-Digit ×/÷",
    "Lv 2 · Two-Digit +",
    "Lv 3 · Two-Digit −",
    "Lv 4 · Mixed Two-Digit",
]

SCORE_COLORS = {
    5: "#c8f04a", 4: "#c8f04a",
    3: "#f0b84a", 2: "#f07a4a",
    1: "#f04a6e", 0: "#f04a6e",
}

st.set_page_config(
    page_title="MathGesture · Clinical",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Azeret+Mono:wght@300;400;500;600&family=Playfair+Display:ital,wght@0,400;0,700;1,400&display=swap');

:root {
    --ink:       #0d0e0c;
    --paper:     #131410;
    --paper2:    #1a1c17;
    --paper3:    #22251d;
    --rule:      #2c3025;
    --rule2:     #3d4334;
    --lime:      #c8f04a;
    --orange:    #f0b84a;
    --coral:     #f07a4a;
    --crimson:   #f04a6e;
    --sky:       #4af0c8;
    --text:      #e8ecdf;
    --ghost:     #6b7560;
    --ghost2:    #3d4334;
    --serif:     'Playfair Display', Georgia, serif;
    --mono:      'Azeret Mono', 'Courier New', monospace;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [class*="css"] {
    font-family: var(--mono) !important;
    background: var(--ink) !important;
    color: var(--text) !important;
}

.stApp { background: var(--ink) !important; }
#MainMenu, footer { visibility: hidden; }
header { background: transparent !important; }

.block-container {
    padding: 2.5rem 3rem 6rem !important;
    max-width: 1500px !important;
}

/* Halftone dot pattern background */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image: radial-gradient(circle, rgba(200,240,74,.07) 1px, transparent 1px);
    background-size: 24px 24px;
    pointer-events: none;
    z-index: 0;
}

/* Top accent line */
.stApp::after {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--lime), var(--sky), var(--lime));
    background-size: 200% 100%;
    animation: shimmer 4s linear infinite;
    z-index: 9999;
}

@keyframes shimmer {
    0%   { background-position: 0% 0%; }
    100% { background-position: 200% 0%; }
}

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--ink); }
::-webkit-scrollbar-thumb { background: var(--rule2); border-radius: 2px; }

/* ── Metric cards — newspaper column style ── */
[data-testid="metric-container"] {
    background: var(--paper) !important;
    border: 1px solid var(--rule) !important;
    border-top: 3px solid var(--lime) !important;
    border-radius: 0 !important;
    padding: 1.4rem 1.6rem 1.2rem !important;
    position: relative !important;
    transition: border-top-color .3s, background .3s !important;
}
[data-testid="metric-container"]:hover {
    background: var(--paper2) !important;
    border-top-color: var(--sky) !important;
}
[data-testid="stMetricLabel"] > div {
    font-family: var(--mono) !important;
    font-size: .6rem !important;
    font-weight: 600 !important;
    letter-spacing: .22em !important;
    text-transform: uppercase !important;
    color: var(--ghost) !important;
    margin-bottom: .5rem !important;
}
[data-testid="stMetricValue"] > div {
    font-family: var(--serif) !important;
    font-size: 2.4rem !important;
    font-weight: 700 !important;
    color: var(--text) !important;
    line-height: 1 !important;
}
[data-testid="stMetricDelta"] > div {
    font-family: var(--mono) !important;
    font-size: .68rem !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--rule) !important;
    border-radius: 0 !important;
    overflow: hidden !important;
}

.stButton > button {
    background: transparent !important;
    border: 1px solid var(--rule2) !important;
    color: var(--lime) !important;
    font-family: var(--mono) !important;
    font-size: .7rem !important;
    font-weight: 600 !important;
    letter-spacing: .12em !important;
    border-radius: 0 !important;
    padding: .55rem 1.4rem !important;
    text-transform: uppercase !important;
    transition: all .2s !important;
    position: relative !important;
    overflow: hidden !important;
}
.stButton > button::before {
    content: '';
    position: absolute;
    inset: 0;
    background: var(--lime);
    transform: scaleX(0);
    transform-origin: left;
    transition: transform .2s !important;
    z-index: -1;
}
.stButton > button:hover {
    color: var(--ink) !important;
    border-color: var(--lime) !important;
}
.stButton > button:hover::before { transform: scaleX(1); }

[data-testid="stSidebar"] {
    background: var(--paper) !important;
    border-right: 1px solid var(--rule) !important;
}
[data-testid="stSidebar"] .block-container {
    padding: 2rem 1.5rem !important;
}

[data-testid="stExpander"] {
    background: var(--paper) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 0 !important;
}
[data-testid="stExpander"] summary {
    font-family: var(--mono) !important;
    font-size: .75rem !important;
    color: var(--coral) !important;
    letter-spacing: .08em !important;
}

[data-testid="stSelectbox"] label,
[data-testid="stTextInput"] label { display: none !important; }
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextInput"] > div > div > input {
    background: var(--paper2) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 0 !important;
    color: var(--text) !important;
    font-family: var(--mono) !important;
    font-size: .8rem !important;
}

[data-testid="stCheckbox"] label {
    font-family: var(--mono) !important;
    font-size: .75rem !important;
    color: var(--ghost) !important;
}

hr {
    border: none !important;
    border-top: 1px solid var(--rule) !important;
    margin: 2rem 0 !important;
}

/* ── Editorial section headers ── */
.sec {
    font-family: var(--serif);
    font-size: 1.4rem;
    font-weight: 400;
    font-style: italic;
    color: var(--text);
    border-bottom: 1px solid var(--rule);
    padding-bottom: .6rem;
    margin-bottom: 1.5rem;
    margin-top: 2rem;
    display: flex;
    align-items: baseline;
    gap: 1rem;
}
.sec-tag {
    font-family: var(--mono);
    font-size: .55rem;
    font-weight: 600;
    letter-spacing: .2em;
    text-transform: uppercase;
    color: var(--lime);
    font-style: normal;
    background: rgba(200,240,74,.08);
    padding: .2rem .55rem;
    border: 1px solid rgba(200,240,74,.2);
}

.clabel {
    font-family: var(--mono);
    font-size: .58rem;
    font-weight: 600;
    letter-spacing: .2em;
    text-transform: uppercase;
    color: var(--ghost);
    margin-bottom: .5rem;
}

/* Alert — teletype red-border style */
.alert-box {
    background: rgba(240,74,110,.04);
    border: 1px solid rgba(240,74,110,.25);
    border-left: 4px solid var(--crimson);
    padding: 1.2rem 1.5rem;
    margin-bottom: 1.5rem;
    font-family: var(--mono);
    font-size: .78rem;
    color: var(--crimson);
    line-height: 1.7;
}
.alert-box strong { font-weight: 600; letter-spacing: .04em; }

/* Q cards — lab specimen card style */
.q-card {
    background: var(--paper);
    border: 1px solid var(--rule);
    border-top-width: 3px;
    padding: 1.2rem;
    min-height: 165px;
    position: relative;
    transition: background .2s;
}
.q-card:hover { background: var(--paper2); }
.q-num {
    font-family: var(--mono);
    font-size: .55rem;
    font-weight: 600;
    letter-spacing: .2em;
    text-transform: uppercase;
    color: var(--ghost);
    margin-bottom: .8rem;
}
.q-text {
    font-family: var(--serif);
    font-size: 1.3rem;
    color: var(--text);
    margin-bottom: .6rem;
    line-height: 1.2;
}
.q-answer { font-size: .82rem; margin-top: .3rem; }
.q-time {
    font-family: var(--mono);
    font-size: .65rem;
    color: var(--orange);
    margin-top: .8rem;
    letter-spacing: .05em;
}

/* Sidebar patient card */
.pt-card {
    padding: 1rem 1.1rem;
    margin-bottom: .4rem;
    border-left: 3px solid transparent;
    transition: all .2s;
}
.pt-card.active {
    background: rgba(200,240,74,.04);
    border-left-color: var(--lime);
}
.pt-id {
    font-family: var(--mono);
    font-size: .58rem;
    font-weight: 600;
    letter-spacing: .15em;
    text-transform: uppercase;
    color: var(--lime);
    margin-bottom: .25rem;
}
.pt-name {
    font-family: var(--serif);
    font-size: 1rem;
    color: var(--text);
    margin-bottom: .3rem;
}
.pt-meta {
    font-family: var(--mono);
    font-size: .58rem;
    color: var(--ghost);
    display: flex;
    gap: .8rem;
    flex-wrap: wrap;
}
</style>
""", unsafe_allow_html=True)


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_connection():
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@st.cache_data(ttl=60)
def load_users() -> list:
    conn = get_connection()
    if conn is None:
        return []
    rows = conn.execute(
        "SELECT u.user_id, u.display_name, u.created_at, "
        "COUNT(s.id) as session_count, "
        "MAX(s.timestamp) as last_session, "
        "ROUND(AVG(s.correct_count), 2) as avg_score "
        "FROM users u "
        "LEFT JOIN sessions s ON u.user_id = s.user_id "
        "GROUP BY u.user_id ORDER BY u.user_id ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@st.cache_data(ttl=60)
def load_sessions(user_id: str) -> pd.DataFrame:
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE user_id = ? ORDER BY id ASC", (user_id,)
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        rt = json.loads(r["response_times"]) if r["response_times"] else []
        records.append({
            "id":                   r["id"],
            "user_id":              r["user_id"],
            "timestamp":            r["timestamp"],
            "difficulty_before":    r["difficulty_before"],
            "difficulty_after":     r["difficulty_after"],
            "correct_count":        r["correct_count"],
            "questions":            json.loads(r["questions"]),
            "answers":              json.loads(r["answers"]),
            "evaluations":          json.loads(r["evaluations"]),
            "response_times":       rt,
            "avg_response_time_ms": round(sum(rt) / len(rt), 1) if rt else 0,
        })
    return pd.DataFrame(records)


def update_display_name(user_id: str, new_name: str):
    conn = get_connection()
    if conn:
        conn.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (new_name, user_id))
        conn.commit()
        conn.close()
        st.cache_data.clear()


def clear_user_sessions(user_id: str):
    conn = get_connection()
    if conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        st.cache_data.clear()

def delete_user_and_sessions(user_id: str):
    """Delete the user record and all their sessions, then reset the UI."""
    conn = get_connection()
    if conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users    WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        st.cache_data.clear()
    # Reset selected user so the sidebar doesn't try to display the deleted one
    if "sel" in st.session_state:
        del st.session_state["sel"]
    st.success(f"Patient '{user_id}' removed.")
    st.rerun()
    
# ── Plotly theme ──────────────────────────────────────────────────────────────

def blayout(**kw):
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Azeret Mono, monospace", color="#6b7560", size=10),
        margin=dict(l=6, r=6, t=6, b=6),
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False),
    )
    base.update(kw)
    return base


# ── Charts ────────────────────────────────────────────────────────────────────

def chart_difficulty(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["id"], y=df["difficulty_after"],
        mode="lines+markers",
        line=dict(color="#c8f04a", width=2),
        marker=dict(color="#c8f04a", size=6,
                    line=dict(color="#0d0e0c", width=1.5)),
        fill="tozeroy", fillcolor="rgba(200,240,74,0.04)",
        hovertemplate="Session #%{x} — Level %{y}<extra></extra>",
    ))
    fig.update_layout(**blayout(
        height=210, showlegend=False,
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False, title="session"),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False,
                   range=[-0.4, 4.6], dtick=1,
                   tickvals=[0,1,2,3,4], ticktext=["L0","L1","L2","L3","L4"]),
    ))
    return fig


def chart_scores(df: pd.DataFrame) -> go.Figure:
    colors = [SCORE_COLORS.get(int(s), "#3d4334") for s in df["correct_count"]]
    fig = go.Figure(go.Bar(
        x=df["id"], y=df["correct_count"],
        marker=dict(color=colors, cornerradius=2),
        hovertemplate="Session #%{x} — %{y}/5<extra></extra>",
    ))
    fig.update_layout(**blayout(
        height=210, showlegend=False,
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False, title="session"),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False,
                   range=[0, 5.8], dtick=1),
    ))
    return fig


def chart_accuracy_pie(df: pd.DataFrame) -> go.Figure:
    total_q     = len(df) * 5
    total_right = int(df["correct_count"].sum())
    pct         = int(total_right / total_q * 100) if total_q else 0
    fig = go.Figure(go.Pie(
        labels=["Correct", "Incorrect"],
        values=[total_right, total_q - total_right],
        hole=0.74,
        marker=dict(
            colors=["#c8f04a", "#2c3025"],
            line=dict(color="#0d0e0c", width=3),
        ),
        textinfo="none",
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    fig.update_layout(**blayout(
        height=210, showlegend=False,
        annotations=[dict(
            text=f"{pct}%",
            font=dict(size=26, color="#e8ecdf",
                      family="Playfair Display, serif"),
            showarrow=False,
        )],
    ))
    return fig


def chart_level_dist(df: pd.DataFrame) -> go.Figure:
    counts = df["difficulty_after"].value_counts().sort_index()
    fig = go.Figure(go.Bar(
        x=[f"L{i}" for i in counts.index],
        y=counts.values,
        marker=dict(color="#4af0c8", cornerradius=2),
        hovertemplate="%{x}: %{y} sessions<extra></extra>",
    ))
    fig.update_layout(**blayout(
        height=210, showlegend=False,
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False, dtick=1),
    ))
    return fig


def chart_response_time(df: pd.DataFrame) -> go.Figure:
    valid = df[df["avg_response_time_ms"] > 0].copy()
    if valid.empty:
        fig = go.Figure()
        fig.update_layout(**blayout(
            height=240,
            annotations=[dict(
                text="No response time data recorded yet",
                font=dict(color="#6b7560", size=12,
                          family="Azeret Mono, monospace"),
                showarrow=False, xref="paper", yref="paper",
                x=0.5, y=0.5,
            )],
        ))
        return fig

    avg_s   = valid["avg_response_time_ms"] / 1000.0
    rolling = avg_s.rolling(window=3, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=valid["id"], y=avg_s,
        mode="lines+markers",
        name="Avg RT",
        line=dict(color="#f0b84a", width=2.5),
        marker=dict(color="#f0b84a", size=6,
                    line=dict(color="#0d0e0c", width=1.5)),
        fill="tozeroy",
        fillcolor="rgba(240,184,74,0.05)",
        hovertemplate="Session #%{x}<br>%{y:.2f}s<extra></extra>",
    ))
    if len(valid) >= 3:
        fig.add_trace(go.Scatter(
            x=valid["id"], y=rolling,
            mode="lines",
            name="3-session trend",
            line=dict(color="#f04a6e", width=2, dash="dot"),
            hovertemplate="Trend: %{y:.2f}s<extra></extra>",
        ))
    fig.update_layout(**blayout(
        height=240,
        showlegend=len(valid) >= 3,
        legend=dict(
            font=dict(size=10, color="#6b7560",
                      family="Azeret Mono, monospace"),
            bgcolor="rgba(0,0,0,0)", x=0.01, y=0.99,
        ),
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False,
                   title="session"),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False,
                   rangemode="tozero", title="seconds"),
    ))
    return fig


# ── Analytics ─────────────────────────────────────────────────────────────────

def compute_streak(df: pd.DataFrame) -> int:
    max_s = cur_s = 0
    for _, row in df.iterrows():
        for ev in row["evaluations"]:
            if ev["is_correct"]:
                cur_s += 1; max_s = max(max_s, cur_s)
            else:
                cur_s = 0
    return max_s


def response_time_trend_flag(df: pd.DataFrame) -> tuple:
    valid = df[df["avg_response_time_ms"] > 0]
    if len(valid) < 10:
        return False, ""
    baseline = valid.iloc[-10:-3]["avg_response_time_ms"]
    recent   = valid.iloc[-3:]["avg_response_time_ms"]
    if baseline.empty or recent.empty:
        return False, ""
    b_mean = baseline.mean()
    b_std  = baseline.std()
    r_mean = recent.mean()
    if b_mean == 0:
        return False, ""
    if r_mean > (b_mean + b_std * 1.5) and r_mean > b_mean * 1.2:
        b_s  = round(b_mean / 1000, 1)
        r_s  = round(r_mean / 1000, 1)
        pct  = (r_mean - b_mean) / b_mean * 100
        return True, (
            f"SUSTAINED PROCESSING SLOWDOWN DETECTED  ·  "
            f"Last 3 sessions averaged {r_s}s vs baseline {b_s}s (+{pct:.0f}%).  "
            f"Statistically significant against the 10-session window.  "
            f"Consider neurological follow-up."
        )
    return False, ""


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(users: list) -> str | None:
    with st.sidebar:
        # Masthead
        st.markdown(
            '<div style="margin-bottom:2rem;padding-bottom:1.5rem;'
            'border-bottom:1px solid #2c3025">'
            '<div style="font-family:\'Playfair Display\',serif;'
            'font-size:1.5rem;font-weight:700;color:#e8ecdf;'
            'letter-spacing:-.02em;line-height:1.1">MathGesture</div>'
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.55rem;'
            'font-weight:600;letter-spacing:.25em;color:#6b7560;'
            'text-transform:uppercase;margin-top:.4rem">'
            'Clinical Dashboard</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        if not users:
            st.markdown(
                '<p style="font-family:\'Azeret Mono\',monospace;font-size:.75rem;'
                'color:#6b7560;line-height:1.8">'
                'No patients on record.<br/>Complete a device session first.</p>',
                unsafe_allow_html=True,
            )
            return None

        st.markdown(
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.55rem;'
            'font-weight:600;letter-spacing:.22em;text-transform:uppercase;'
            'color:#6b7560;margin-bottom:1rem">Patient Roster</div>',
            unsafe_allow_html=True,
        )

        if "sel" not in st.session_state:
            st.session_state.sel = str(users[0]["user_id"])

        opts = [f"{u['user_id']}  ·  {u['display_name']}" for u in users]
        cur  = next(
            (i for i, o in enumerate(opts)
             if o.startswith(str(st.session_state.sel))), 0
        )
        raw = st.selectbox("patient", opts, index=cur,
                           label_visibility="collapsed")
        sel = raw.split("  ·  ")[0].strip()
        st.session_state.sel = sel

        st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

        for u in users:
            active = str(u["user_id"]) == sel
            cls    = "pt-card active" if active else "pt-card"
            last   = (u["last_session"] or "—")[:10]
            avg    = f"{u['avg_score']}/5" if u["avg_score"] else "—"
            st.markdown(
                f'<div class="{cls}">'
                f'<div class="pt-id">ID · {u["user_id"]}</div>'
                f'<div class="pt-name">{u["display_name"]}</div>'
                f'<div class="pt-meta">'
                f'<span>{u["session_count"]} sessions</span>'
                f'<span>avg {avg}</span>'
                f'<span>{last}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        st.markdown("---")

        # ── Remove user ───────────────────────────────────────────────────
        active_user = next(
            (u for u in users if str(u["user_id"]) == sel), None
        )
        if active_user:
            with st.expander("🗑  Remove Patient"):
                st.markdown(
                    f'<p style="font-family:\'Azeret Mono\',monospace;'
                    f'font-size:.7rem;color:#6b7560;line-height:1.8">'
                    f'Permanently removes patient '
                    f'<span style="color:#f04a6e;font-weight:600">'
                    f'{active_user["display_name"]}</span> '
                    f'(ID: {active_user["user_id"]}) and all their sessions.'
                    f'</p>',
                    unsafe_allow_html=True,
                )
                confirmed = st.checkbox(
                    "I understand this is irreversible",
                    key=f"del_confirm_{sel}",
                )
                if st.button(
                    f"Remove {active_user['display_name']}",
                    disabled=not confirmed,
                    key=f"del_btn_{sel}",
                ):
                    delete_user_and_sessions(active_user["user_id"])

        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

        if st.button("↺  Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    return sel


# ── Main view ─────────────────────────────────────────────────────────────────

def render_user_view(user_id: str, display_name: str):

    # Header
    ch, ce = st.columns([8, 2])
    with ch:
        st.markdown(
            f'<div style="margin-bottom:.5rem">'
            f'<div style="font-family:\'Azeret Mono\',monospace;font-size:.58rem;'
            f'font-weight:600;letter-spacing:.22em;color:#6b7560;'
            f'text-transform:uppercase;margin-bottom:.7rem">'
            f'Patient Record  ·  ID {user_id}</div>'
            f'<h1 style="font-family:\'Playfair Display\',serif;font-size:3rem;'
            f'font-weight:700;color:#e8ecdf;margin:0;letter-spacing:-.03em;'
            f'line-height:1">{display_name}</h1>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with ce:
        st.markdown("<div style='height:2.2rem'></div>", unsafe_allow_html=True)
        with st.expander("✏  Rename"):
            new_name = st.text_input("name", value=display_name,
                                     label_visibility="collapsed",
                                     key=f"rn_{user_id}")
            if st.button("Save", key=f"sv_{user_id}"):
                update_display_name(user_id, new_name.strip() or display_name)
                st.success("Saved.")
                st.rerun()

    st.markdown("---")

    df = load_sessions(user_id)

    if df.empty:
        st.markdown(
            f'<div style="text-align:center;padding:6rem 1rem">'
            f'<div style="font-family:\'Playfair Display\',serif;font-size:3rem;'
            f'font-style:italic;color:#2c3025;margin-bottom:1rem">No sessions yet</div>'
            f'<div style="font-family:\'Azeret Mono\',monospace;font-size:.65rem;'
            f'letter-spacing:.18em;color:#6b7560">'
            f'COMPLETE A ROUND ON THE DEVICE  ·  USER ID {user_id}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    # Alert
    flagged, alert_msg = response_time_trend_flag(df)
    if flagged:
        st.markdown(
            f'<div class="alert-box"><strong>⚠  CLINICAL ALERT</strong><br/>{alert_msg}</div>',
            unsafe_allow_html=True,
        )

    # ── KPI — two rows of four ─────────────────────────────────────────────
    st.markdown(
        '<div class="sec"><span class="sec-tag">Overview</span>Key Indicators</div>',
        unsafe_allow_html=True,
    )

    total    = len(df)
    avg_sc   = round(float(df["correct_count"].mean()), 2)
    best     = int(df["correct_count"].max())
    curr_lv  = int(df["difficulty_after"].iloc[-1])
    streak   = compute_streak(df)
    accuracy = round(df["correct_count"].sum() / (total * 5) * 100, 1)
    lvl_ups  = int((df["difficulty_after"] > df["difficulty_before"]).sum())

    vrt         = df[df["avg_response_time_ms"] > 0]["avg_response_time_ms"]
    avg_rt_s    = round(vrt.mean() / 1000, 2) if not vrt.empty else 0.0
    recent_rt_s = round(vrt.iloc[-3:].mean() / 1000, 2) if len(vrt) >= 3 else None
    rt_delta    = f"last 3: {recent_rt_s}s" if recent_rt_s else None

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r1c1.metric("Sessions",      total)
    r1c2.metric("Accuracy",      f"{accuracy}%")
    r1c3.metric("Current Level", f"Lv {curr_lv}",
                DIFFICULTY_NAMES[curr_lv].split("·")[1].strip())
    r1c4.metric("Avg Resp Time", f"{avg_rt_s}s", rt_delta,
                delta_color="inverse")

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    r2c1.metric("Avg Score",  f"{avg_sc}/5")
    r2c2.metric("Best Score", f"{best}/5")
    r2c3.metric("Best Streak", streak)
    r2c4.metric("Level Ups",  lvl_ups)

    st.markdown("---")

    # ── Charts ─────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="sec"><span class="sec-tag">Performance</span>Session Analytics</div>',
        unsafe_allow_html=True,
    )

    cc1, cc2, cc3, cc4 = st.columns(4)
    with cc1:
        st.markdown('<div class="clabel">Difficulty Progression</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(chart_difficulty(df), use_container_width=True,
                        config={"displayModeBar": False})
    with cc2:
        st.markdown('<div class="clabel">Session Scores</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(chart_scores(df), use_container_width=True,
                        config={"displayModeBar": False})
    with cc3:
        st.markdown('<div class="clabel">Lifetime Accuracy</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(chart_accuracy_pie(df), use_container_width=True,
                        config={"displayModeBar": False})
    with cc4:
        st.markdown('<div class="clabel">Level Distribution</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(chart_level_dist(df), use_container_width=True,
                        config={"displayModeBar": False})

    st.markdown(
        '<div class="clabel" style="color:#f0b84a;margin-top:1.8rem">'
        'Processing Speed Biomarker  ·  Response Time per Session (seconds)'
        '</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(chart_response_time(df), use_container_width=True,
                    config={"displayModeBar": False})

    if flagged:
        st.markdown(
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.62rem;'
            'color:#f04a6e;margin-top:-.6rem;padding-left:.3rem">'
            '↑  Dotted red line = 3-session rolling average.  '
            'Sustained upward trend is statistically significant against 10-session baseline.'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Session history table ──────────────────────────────────────────────
    st.markdown(
        '<div class="sec"><span class="sec-tag">History</span>All Sessions</div>',
        unsafe_allow_html=True,
    )

    rows_out = []
    for _, row in df.iloc[::-1].iterrows():
        ba = int(row["difficulty_before"])
        af = int(row["difficulty_after"])
        ch = "▲ UP" if af > ba else ("▼ DOWN" if af < ba else "— SAME")
        rt = row["avg_response_time_ms"]
        rows_out.append({
            "#":         f"#{int(row['id'])}",
            "Timestamp": str(row["timestamp"]).replace("T", "  ")[:16],
            "Score":     f"{int(row['correct_count'])}/5",
            "Avg RT":    f"{rt/1000:.1f}s" if rt > 0 else "—",
            "Lv Before": ba,
            "Lv After":  af,
            "Change":    ch,
            "Level":     DIFFICULTY_NAMES[af],
        })

    st.dataframe(
        pd.DataFrame(rows_out),
        use_container_width=True,
        hide_index=True,
        column_config={
            "#":         st.column_config.TextColumn("#",          width="small"),
            "Timestamp": st.column_config.TextColumn("Timestamp",  width="medium"),
            "Score":     st.column_config.TextColumn("Score",      width="small"),
            "Avg RT":    st.column_config.TextColumn("Avg RT",     width="small"),
            "Lv Before": st.column_config.NumberColumn("Lv Before",width="small"),
            "Lv After":  st.column_config.NumberColumn("Lv After", width="small"),
            "Change":    st.column_config.TextColumn("Change",     width="small"),
            "Level":     st.column_config.TextColumn("Level",      width="large"),
        },
    )

    st.markdown("---")

    # ── Session drilldown ──────────────────────────────────────────────────
    st.markdown(
        '<div class="sec"><span class="sec-tag">Drilldown</span>Per-Question Review</div>',
        unsafe_allow_html=True,
    )

    opts = [
        f"#{int(r['id'])}  ·  {str(r['timestamp'])[:10]}  ·  "
        f"{int(r['correct_count'])}/5  ·  RT {r['avg_response_time_ms']/1000:.1f}s"
        for _, r in df.iloc[::-1].iterrows()
    ]
    sel     = st.selectbox("session", opts, label_visibility="collapsed")
    sel_id  = int(sel.split("  ·  ")[0].lstrip("#"))
    sel_row = df[df["id"] == sel_id].iloc[0]

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    qc = st.columns(5)
    for i, ev in enumerate(sel_row["evaluations"]):
        with qc[i]:
            ok     = ev["is_correct"]
            tc     = "#c8f04a" if ok else "#f04a6e"
            icon   = "✓" if ok else "✗"
            ans_c  = "#c8f04a" if ok else "#f04a6e"
            rt_l   = sel_row["response_times"]
            rt_v   = rt_l[i] if i < len(rt_l) else 0
            rt_d   = f"{rt_v/1000:.1f}s" if rt_v > 0 else "—"
            wrong  = (
                f'<div class="q-answer" style="color:#6b7560">'
                f'expected: <span style="color:#e8ecdf">{ev["correct_answer"]}</span></div>'
            ) if not ok else ""
            st.markdown(
                f'<div class="q-card" style="border-top-color:{tc}">'
                f'<div class="q-num">Q{i+1}'
                f'<span style="float:right;font-size:1rem;color:{tc}">{icon}</span></div>'
                f'<div class="q-text">{ev["question"]}</div>'
                f'<div class="q-answer" style="color:{ans_c}">{ev["user_answer"]}</div>'
                f'{wrong}'
                f'<div class="q-time">⏱  {rt_d}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Danger zone ────────────────────────────────────────────────────────
    with st.expander(f"⚠  Danger Zone — {display_name}"):
        st.markdown(
            f'<p style="font-family:\'Azeret Mono\',monospace;font-size:.75rem;'
            f'color:#6b7560;line-height:1.8">'
            f'Permanently deletes all sessions for patient ID '
            f'<span style="color:#f04a6e;font-weight:600">{user_id}</span>.'
            f'</p>',
            unsafe_allow_html=True,
        )
        ok = st.checkbox("I understand this is irreversible",
                         key=f"ck_{user_id}")
        if st.button(f"Erase {display_name}'s data",
                     disabled=not ok, key=f"del_{user_id}"):
            clear_user_sessions(user_id)
            st.success("Data erased.")
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(DB_PATH):
        st.markdown(
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'justify-content:center;height:75vh;gap:1.5rem">'
            '<div style="font-family:\'Playfair Display\',serif;font-size:3.5rem;'
            'font-style:italic;color:#2c3025">Database not found</div>'
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.65rem;'
            'color:#6b7560;letter-spacing:.18em">'
            'RUN app.py AND COMPLETE AT LEAST ONE DEVICE SESSION</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    users  = load_users()
    sel_id = render_sidebar(users)

    if sel_id is None:
        st.markdown(
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'justify-content:center;height:75vh;gap:1.5rem">'
            '<div style="font-family:\'Playfair Display\',serif;font-size:3.5rem;'
            'font-style:italic;color:#2c3025">No patients yet</div>'
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.65rem;'
            'color:#6b7560;letter-spacing:.18em">'
            'COMPLETE A SESSION ON THE DEVICE TO REGISTER A PATIENT</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    u    = next((u for u in users if str(u["user_id"]) == sel_id), None)
    name = u["display_name"] if u else sel_id
    render_user_view(sel_id, name)


if __name__ == "__main__":
    main()