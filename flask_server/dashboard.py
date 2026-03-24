# dashboard.py  –  MathGesture Clinical Dashboard
# Run: streamlit run dashboard.py
# Set FLASK_URL env var for Railway/cloud mode, else reads local SQLite.

import json
import os
from math import sqrt

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────

try:
    import sqlite3
    _HAS_SQLITE = True
except ImportError:
    _HAS_SQLITE = False

DB_PATH   = os.path.join(os.path.dirname(__file__), "progress.db")
FLASK_URL = os.environ.get("FLASK_URL", "").rstrip("/")
_USE_API  = bool(FLASK_URL)

if _USE_API:
    import requests as _req

QUESTIONS_PER_SESSION = 5

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

TAG_COLORS = {"easy": "#4af0c8", "medium": "#f0b84a", "hard": "#f04a6e"}

SAT_COLORS = {
    "normal":        "#c8f04a",
    "compensating":  "#f0b84a",
    "impulsive":     "#4af0c8",
    "deteriorating": "#f04a6e",
}

# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MathGesture · Clinical",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Azeret+Mono:wght@300;400;500;600&family=Playfair+Display:ital,wght@0,400;0,700;1,400&display=swap');
:root{--ink:#0d0e0c;--paper:#131410;--paper2:#1a1c17;--rule:#2c3025;--rule2:#3d4334;--lime:#c8f04a;--orange:#f0b84a;--coral:#f07a4a;--crimson:#f04a6e;--sky:#4af0c8;--violet:#a78bfa;--text:#e8ecdf;--ghost:#6b7560;--serif:'Playfair Display',Georgia,serif;--mono:'Azeret Mono','Courier New',monospace;}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body,[class*="css"]{font-family:var(--mono)!important;background:var(--ink)!important;color:var(--text)!important;}
.stApp{background:var(--ink)!important;}#MainMenu,footer{visibility:hidden;}header{background:transparent!important;}
.block-container{padding:2.5rem 3rem 6rem!important;max-width:1500px!important;}
.stApp::before{content:'';position:fixed;inset:0;background-image:radial-gradient(circle,rgba(200,240,74,.07) 1px,transparent 1px);background-size:24px 24px;pointer-events:none;z-index:0;}
.stApp::after{content:'';position:fixed;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--lime),var(--sky),var(--lime));background-size:200% 100%;animation:shimmer 4s linear infinite;z-index:9999;}
@keyframes shimmer{0%{background-position:0% 0%;}100%{background-position:200% 0%;}}
::-webkit-scrollbar{width:5px;height:5px;}::-webkit-scrollbar-track{background:var(--ink);}::-webkit-scrollbar-thumb{background:var(--rule2);border-radius:2px;}
[data-testid="metric-container"]{background:var(--paper)!important;border:1px solid var(--rule)!important;border-top:3px solid var(--lime)!important;border-radius:0!important;padding:1.4rem 1.6rem 1.2rem!important;position:relative!important;transition:border-top-color .3s,background .3s!important;}
[data-testid="metric-container"]:hover{background:var(--paper2)!important;border-top-color:var(--sky)!important;}
[data-testid="stMetricLabel"]>div{font-family:var(--mono)!important;font-size:.6rem!important;font-weight:600!important;letter-spacing:.22em!important;text-transform:uppercase!important;color:var(--ghost)!important;margin-bottom:.5rem!important;}
[data-testid="stMetricValue"]>div{font-family:var(--serif)!important;font-size:2.4rem!important;font-weight:700!important;color:var(--text)!important;line-height:1!important;}
[data-testid="stMetricDelta"]>div{font-family:var(--mono)!important;font-size:.68rem!important;}
[data-testid="stDataFrame"]{border:1px solid var(--rule)!important;border-radius:0!important;overflow:hidden!important;}
.stButton>button{background:transparent!important;border:1px solid var(--rule2)!important;color:var(--lime)!important;font-family:var(--mono)!important;font-size:.7rem!important;font-weight:600!important;letter-spacing:.12em!important;border-radius:0!important;padding:.55rem 1.4rem!important;text-transform:uppercase!important;transition:all .2s!important;position:relative!important;overflow:hidden!important;}
.stButton>button::before{content:'';position:absolute;inset:0;background:var(--lime);transform:scaleX(0);transform-origin:left;transition:transform .2s!important;z-index:-1;}
.stButton>button:hover{color:var(--ink)!important;border-color:var(--lime)!important;}
.stButton>button:hover::before{transform:scaleX(1);}
[data-testid="stSidebar"]{background:var(--paper)!important;border-right:1px solid var(--rule)!important;}
[data-testid="stSidebar"] .block-container{padding:2rem 1.5rem!important;}
[data-testid="stExpander"]{background:var(--paper)!important;border:1px solid var(--rule)!important;border-radius:0!important;}
[data-testid="stExpander"] summary{font-family:var(--mono)!important;font-size:.75rem!important;color:var(--coral)!important;letter-spacing:.08em!important;}
[data-testid="stSelectbox"] label,[data-testid="stTextInput"] label{display:none!important;}
[data-testid="stSelectbox"]>div>div,[data-testid="stTextInput"]>div>div>input{background:var(--paper2)!important;border:1px solid var(--rule)!important;border-radius:0!important;color:var(--text)!important;font-family:var(--mono)!important;font-size:.8rem!important;}
[data-testid="stCheckbox"] label{font-family:var(--mono)!important;font-size:.75rem!important;color:var(--ghost)!important;}
hr{border:none!important;border-top:1px solid var(--rule)!important;margin:2rem 0!important;}
.sec{font-family:var(--serif);font-size:1.4rem;font-weight:400;font-style:italic;color:var(--text);border-bottom:1px solid var(--rule);padding-bottom:.6rem;margin-bottom:1.5rem;margin-top:2rem;display:flex;align-items:baseline;gap:1rem;}
.sec-tag{font-family:var(--mono);font-size:.55rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--lime);font-style:normal;background:rgba(200,240,74,.08);padding:.2rem .55rem;border:1px solid rgba(200,240,74,.2);}
.sec-tag-warn{font-family:var(--mono);font-size:.55rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--orange);font-style:normal;background:rgba(240,184,74,.08);padding:.2rem .55rem;border:1px solid rgba(240,184,74,.2);}
.clabel{font-family:var(--mono);font-size:.58rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--ghost);margin-bottom:.5rem;}
.alert-box{background:rgba(240,74,110,.04);border:1px solid rgba(240,74,110,.25);border-left:4px solid var(--crimson);padding:1.2rem 1.5rem;margin-bottom:1rem;font-family:var(--mono);font-size:.78rem;color:var(--crimson);line-height:1.7;}
.alert-box strong{font-weight:600;letter-spacing:.04em;}
.warn-box{background:rgba(240,184,74,.04);border:1px solid rgba(240,184,74,.25);border-left:4px solid var(--orange);padding:1rem 1.3rem;margin-bottom:1rem;font-family:var(--mono);font-size:.76rem;color:var(--orange);line-height:1.7;}
.warn-box strong{font-weight:600;}
.build-box{border-left:3px solid var(--rule2);padding:.5rem 1rem;margin-bottom:1rem;font-family:var(--mono);font-size:.68rem;color:var(--ghost);line-height:1.6;}
.q-card{background:var(--paper);border:1px solid var(--rule);border-top-width:3px;padding:1.2rem;min-height:200px;position:relative;transition:background .2s;}
.q-card:hover{background:var(--paper2);}
.q-num{font-family:var(--mono);font-size:.55rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--ghost);margin-bottom:.6rem;}
.q-tag{font-family:var(--mono);font-size:.58rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;padding:.15rem .4rem;display:inline-block;margin-bottom:.5rem;}
.q-text{font-family:var(--serif);font-size:1.3rem;color:var(--text);margin-bottom:.5rem;line-height:1.2;}
.q-answer{font-size:.82rem;margin-top:.3rem;}
.q-time{font-family:var(--mono);font-size:.65rem;color:var(--orange);margin-top:.5rem;letter-spacing:.05em;}
.q-sat{font-family:var(--mono);font-size:.6rem;margin-top:.4rem;font-weight:600;letter-spacing:.06em;}
.pt-card{padding:1rem 1.1rem;margin-bottom:.4rem;border-left:3px solid transparent;transition:all .2s;}
.pt-card.active{background:rgba(200,240,74,.04);border-left-color:var(--lime);}
.pt-id{font-family:var(--mono);font-size:.58rem;font-weight:600;letter-spacing:.15em;text-transform:uppercase;color:var(--lime);margin-bottom:.25rem;}
.pt-name{font-family:var(--serif);font-size:1rem;color:var(--text);margin-bottom:.3rem;}
.pt-meta{font-family:var(--mono);font-size:.58rem;color:var(--ghost);display:flex;gap:.8rem;flex-wrap:wrap;}
.info-panel{background:var(--paper);border:1px solid var(--rule);padding:1.2rem 1.5rem;margin-bottom:1.2rem;font-family:var(--mono);font-size:.75rem;color:var(--ghost);line-height:1.8;}
.info-panel strong{color:var(--text);font-weight:600;}
.info-panel .info-title{font-family:var(--serif);font-size:1rem;font-style:italic;color:var(--text);margin-bottom:.8rem;}
.info-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:.8rem;}
.info-quad{padding:.8rem 1rem;border-left:3px solid;font-family:var(--mono);font-size:.7rem;line-height:1.7;}
.info-quad .quad-label{font-weight:600;letter-spacing:.08em;margin-bottom:.2rem;}
.info-quad .quad-desc{color:var(--ghost);}
.info-terms{display:grid;grid-template-columns:auto 1fr;gap:.4rem 1rem;margin-top:.6rem;align-items:baseline;}
.info-terms dt{font-weight:600;color:var(--text);white-space:nowrap;}
.info-terms dd{color:var(--ghost);}
</style>
""", unsafe_allow_html=True)


# ── Data layer ────────────────────────────────────────────────────────────────

def _api_get(path, params=None):
    try:
        r = _req.get(f"{FLASK_URL}{path}", params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.session_state["_api_error"] = str(exc)
        return None

def _api_post(path, body=None):
    try:
        r = _req.post(f"{FLASK_URL}{path}", json=body or {}, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.session_state["_api_error"] = str(exc)
        return None

def _api_delete(path):
    try:
        r = _req.delete(f"{FLASK_URL}{path}", timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.session_state["_api_error"] = str(exc)
        return None

def api_get(path: str, params: dict = None) -> dict | list | None:
    """GET from Flask API. Returns parsed JSON or None on any error."""
    try:
        r = requests.get(f"{FLASK_URL}{path}", params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.session_state["_api_error"] = str(exc)
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_is_calibration(df: pd.DataFrame) -> pd.DataFrame:
    if "is_calibration" not in df.columns:
        df = df.copy()
        df["is_calibration"] = False
    else:
        df = df.copy()
        df["is_calibration"] = df["is_calibration"].apply(
            lambda v: bool(v) if v is not None else False
        )
    return df


@st.cache_data(ttl=60)
def load_users() -> list:
    if _USE_API:
        data = _api_get("/users")
        return data if isinstance(data, list) else []
    conn = get_connection()
    if conn is None:
        return []
    rows = conn.execute(
        "SELECT u.user_id, u.display_name, u.created_at, "
        "COUNT(s.id) as session_count, MAX(s.timestamp) as last_session, "
        "ROUND(AVG(s.correct_count),2) as avg_score "
        "FROM users u LEFT JOIN sessions s ON u.user_id=s.user_id "
        "GROUP BY u.user_id ORDER BY u.user_id ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=60)
def load_sessions(user_id: str) -> pd.DataFrame:
    if _USE_API:
        data = _api_get("/stats", params={"user_id": user_id})
        if not data or not data.get("sessions"):
            return pd.DataFrame()
        raw = data["sessions"]
    else:
        conn = get_connection()
        if conn is None:
            return pd.DataFrame()
        rows = conn.execute(
            "SELECT * FROM sessions WHERE user_id=? ORDER BY id ASC", (user_id,)
        ).fetchall()
        conn.close()
        if not rows:
            return pd.DataFrame()
        raw = []
        for r in rows:
            rt   = json.loads(r["response_times"])        if r["response_times"]        else []
            tags = json.loads(r["question_difficulties"]) if r["question_difficulties"] else []
            keys = r.keys()
            is_cal = bool(r["is_calibration"]) if "is_calibration" in keys else False
            raw.append({
                "id":                    r["id"],
                "user_id":               r["user_id"],
                "timestamp":             r["timestamp"],
                "difficulty_before":     r["difficulty_before"],
                "difficulty_after":      r["difficulty_after"],
                "correct_count":         r["correct_count"],
                "questions":             json.loads(r["questions"]),
                "answers":               json.loads(r["answers"]),
                "evaluations":           json.loads(r["evaluations"]),
                "response_times":        rt,
                "question_difficulties": tags,
                "is_calibration":        is_cal,
            })

    records = []
    for s in raw:
        rt   = s.get("response_times", [])
        tags = s.get("question_difficulties", [])
        while len(tags) < QUESTIONS_PER_SESSION:
            tags.append("medium")
        valid = [v for v in rt if v > 0]
        is_cal = bool(s.get("is_calibration") or False)
        records.append({
            "id":                    s["id"],
            "user_id":               s["user_id"],
            "timestamp":             s["timestamp"],
            "difficulty_before":     s["difficulty_before"],
            "difficulty_after":      s["difficulty_after"],
            "correct_count":         s["correct_count"],
            "questions":             s["questions"],
            "answers":               s["answers"],
            "evaluations":           s["evaluations"],
            "response_times":        rt,
            "question_difficulties": tags,
            "avg_response_time_ms":  round(sum(valid)/len(valid), 1) if valid else 0,
            "is_calibration":        is_cal,
        })

    df = pd.DataFrame(records)
    return _ensure_is_calibration(df)


def update_display_name(user_id, new_name):
    if _USE_API:
        _api_post(f"/users/{user_id}", {"display_name": new_name})
    else:
        conn = get_connection()
        if conn:
            conn.execute("UPDATE users SET display_name=? WHERE user_id=?",
                         (new_name, user_id))
            conn.commit(); conn.close()
    st.cache_data.clear()

def clear_user_sessions(user_id):
    if _USE_API:
        _api_post("/stats/clear", {"user_id": user_id})
    else:
        conn = get_connection()
        if conn:
            conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            conn.commit(); conn.close()
    st.cache_data.clear()

def delete_user_and_sessions(user_id):
    if _USE_API:
        _api_delete(f"/users/{user_id}")
    else:
        conn = get_connection()
        if conn:
            conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            conn.commit(); conn.close()
    st.cache_data.clear()
    if "sel" in st.session_state:
        del st.session_state["sel"]
    st.success(f"Patient '{user_id}' removed.")
    st.rerun()


# ── Analytics ─────────────────────────────────────────────────────────────────

def scored_only(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    if "is_calibration" not in df.columns:
        return df.copy()
    return df[~df["is_calibration"].astype(bool)].copy()


# REMOVED: compute_streak — gamification metric with no clinical value


def sat_classify(rt_ms: float, is_correct: bool, mean_rt: float) -> str:
    fast = rt_ms < mean_rt
    if fast and is_correct:     return "normal"
    if fast and not is_correct: return "impulsive"
    if not fast and is_correct: return "compensating"
    return "deteriorating"


def compute_session_sat(row: pd.Series) -> dict:
    rts  = row["response_times"]
    evs  = row["evaluations"]
    mean = row["avg_response_time_ms"]
    counts = {"normal":0,"compensating":0,"impulsive":0,"deteriorating":0}
    if mean <= 0 or not rts:
        return counts | {"compensation_ratio": 0.0}
    correct_slow = 0
    total_correct = 0
    for i, ev in enumerate(evs):
        rt_v = rts[i] if i < len(rts) else 0
        if rt_v <= 0:
            continue
        label = sat_classify(rt_v, ev["is_correct"], mean)
        counts[label] += 1
        if ev["is_correct"]:
            total_correct += 1
            if rt_v >= mean:
                correct_slow += 1
    comp = round(correct_slow / total_correct, 2) if total_correct > 0 else 0.0
    return counts | {"compensation_ratio": comp}


def correct_rt_series(df: pd.DataFrame) -> pd.DataFrame:
    sdf  = scored_only(df)
    rows = []
    for _, row in sdf.iterrows():
        rts = row["response_times"]
        evs = row["evaluations"]
        crt = [rts[i] for i, ev in enumerate(evs)
               if ev["is_correct"] and i < len(rts) and rts[i] > 0]
        if crt:
            rows.append({
                "id":               row["id"],
                "difficulty_after": row["difficulty_after"],
                "correct_rt_mean":  round(sum(crt)/len(crt), 1),
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["id", "difficulty_after", "correct_rt_mean"])


# ── Alert system ──────────────────────────────────────────────────────────────

def response_time_trend_flag(df: pd.DataFrame) -> tuple[bool, str, str]:
    sdf = scored_only(df)
    if sdf.empty:
        return False, "", "ok"

    current_level = int(sdf["difficulty_after"].iloc[-1])
    same_level    = sdf[
        (sdf["avg_response_time_ms"] > 0) &
        (sdf["difficulty_after"] == current_level)
    ].copy()
    n = len(same_level)

    if n < 10:
        needed = 10 - n
        return False, (
            f"⏳  MONITORING BUILDING AT LEVEL {current_level}  ·  "
            f"{needed} more scored session{'s' if needed > 1 else ''} needed "
            f"({n}/10 collected)"
        ), "building"

    baseline = same_level.iloc[-5:-3]["avg_response_time_ms"]
    recent   = same_level.iloc[-3:]["avg_response_time_ms"]
    if baseline.empty or recent.empty:
        return False, "", "ok"

    b_mean = baseline.mean()
    b_std  = baseline.std()
    r_mean = recent.mean()
    nb     = len(baseline)

    if b_mean == 0 or b_std == 0:
        return False, "", "ok"

    z = (r_mean - b_mean) / (b_std / sqrt(nb))

    if z > 2.0:
        b_s = round(b_mean/1000, 1)
        r_s = round(r_mean/1000, 1)
        pct = (r_mean - b_mean) / b_mean * 100
        return True, (
            f"SUSTAINED PROCESSING SLOWDOWN DETECTED  ·  "
            f"At Level {current_level}: last 3 sessions averaged {r_s}s "
            f"vs baseline {b_s}s (+{pct:.0f}%)  ·  "
            f"Z = {z:.2f} (threshold 2.0, p<0.025)  ·  "
            f"Comparison restricted to scored sessions at same difficulty level  ·  "
            f"Consider neurological follow-up."
        ), "alert"

    return False, "", "ok"


def compensation_alert(df: pd.DataFrame) -> tuple[bool, str]:
    sdf = scored_only(df)
    if sdf.empty:
        return False, ""

    current_level = int(sdf["difficulty_after"].iloc[-1])
    same_level    = sdf[
        (sdf["avg_response_time_ms"] > 0) &
        (sdf["difficulty_after"] == current_level)
    ].copy()

    if len(same_level) < 8:
        return False, ""

    crt = correct_rt_series(same_level)
    if len(crt) < 8:
        return False, ""

    b_crt  = crt.iloc[-8:-3]["correct_rt_mean"]
    r_crt  = crt.iloc[-3:]["correct_rt_mean"]
    b_mean = b_crt.mean()
    b_std  = b_crt.std()
    r_mean = r_crt.mean()
    nb     = len(b_crt)

    if b_mean == 0 or b_std == 0:
        return False, ""

    z               = (r_mean - b_mean) / (b_std / sqrt(nb))
    recent_accuracy = same_level.iloc[-3:]["correct_count"].mean()

    if z > 1.65 and recent_accuracy >= 3.5:
        b_s = round(b_mean/1000, 1)
        r_s = round(r_mean/1000, 1)
        pct = (r_mean - b_mean) / b_mean * 100
        return True, (
            f"EARLY COMPENSATION PATTERN  ·  "
            f"Accuracy maintained ({recent_accuracy:.1f}/5) but correct-answer RT "
            f"rose from {b_s}s to {r_s}s (+{pct:.0f}%)  ·  "
            f"Z = {z:.2f} (threshold 1.65, p<0.05)  ·  "
            f"Patient is slowing to preserve accuracy — precursor to measurable decline  ·  "
            f"Earlier review recommended."
        )
    return False, ""


# ── Plotly theme ──────────────────────────────────────────────────────────────

def blayout(**kw):
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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

def chart_difficulty(df):
    sdf = scored_only(df)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sdf["id"], y=sdf["difficulty_after"], mode="lines+markers",
        line=dict(color="#c8f04a", width=2),
        marker=dict(color="#c8f04a", size=6, line=dict(color="#0d0e0c", width=1.5)),
        marker=dict(color="#c8f04a", size=6, line=dict(color="#0d0e0c", width=1.5)),
        fill="tozeroy", fillcolor="rgba(200,240,74,0.04)",
        hovertemplate="Session #%{x} — Level %{y}<extra></extra>",
    ))
    fig.update_layout(**blayout(
        height=210, showlegend=False,
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False, title="session"),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False,
                   range=[-0.4,4.6], dtick=1,
                   tickvals=[0,1,2,3,4], ticktext=["L0","L1","L2","L3","L4"]),
    ))
    return fig


def chart_scores(df):
    sdf    = scored_only(df)
    colors = [SCORE_COLORS.get(int(s), "#3d4334") for s in sdf["correct_count"]]
    fig    = go.Figure(go.Bar(
        x=sdf["id"], y=sdf["correct_count"],
        marker=dict(color=colors, cornerradius=2),
        hovertemplate="Session #%{x} — %{y}/5<extra></extra>",
    ))
    fig.update_layout(**blayout(
        height=210, showlegend=False,
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False, title="session"),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False, range=[0,5.8], dtick=1),
    ))
    return fig


def chart_accuracy_pie(df):
    sdf         = scored_only(df)
    total_q     = len(sdf) * QUESTIONS_PER_SESSION
    total_right = int(sdf["correct_count"].sum())
    pct         = int(total_right / total_q * 100) if total_q else 0
    fig = go.Figure(go.Pie(
        labels=["Correct","Incorrect"],
        values=[total_right, total_q - total_right],
        hole=0.74,
        marker=dict(colors=["#c8f04a","#2c3025"],
                    line=dict(color="#0d0e0c", width=3)),
        textinfo="none",
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    fig.update_layout(**blayout(
        height=210, showlegend=False,
        annotations=[dict(
            text=f"{pct}%",
            font=dict(size=26, color="#e8ecdf", family="Playfair Display, serif"),
            font=dict(size=26, color="#e8ecdf", family="Playfair Display, serif"),
            showarrow=False,
        )],
    ))
    return fig


def chart_level_dist(df):
    sdf    = scored_only(df)
    counts = sdf["difficulty_after"].value_counts().sort_index()
    fig    = go.Figure(go.Bar(
        x=[f"L{i}" for i in counts.index], y=counts.values,
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


def chart_response_time(df):
    sdf   = scored_only(df)
    valid = sdf[sdf["avg_response_time_ms"] > 0].copy()
    if valid.empty:
        fig = go.Figure()
        fig.update_layout(**blayout(height=240, annotations=[dict(
            text="No response time data yet", showarrow=False,
            font=dict(color="#6b7560", size=12, family="Azeret Mono, monospace"),
            xref="paper", yref="paper", x=0.5, y=0.5,
        )]))
        return fig
    avg_s   = valid["avg_response_time_ms"] / 1000.0
    rolling = avg_s.rolling(window=3, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=valid["id"], y=avg_s, mode="lines+markers", name="Avg RT",
        x=valid["id"], y=avg_s, mode="lines+markers", name="Avg RT",
        line=dict(color="#f0b84a", width=2.5),
        marker=dict(color="#f0b84a", size=6, line=dict(color="#0d0e0c", width=1.5)),
        fill="tozeroy", fillcolor="rgba(240,184,74,0.05)",
        marker=dict(color="#f0b84a", size=6, line=dict(color="#0d0e0c", width=1.5)),
        fill="tozeroy", fillcolor="rgba(240,184,74,0.05)",
        hovertemplate="Session #%{x}<br>%{y:.2f}s<extra></extra>",
    ))
    if len(valid) >= 3:
        fig.add_trace(go.Scatter(
            x=valid["id"], y=rolling, mode="lines", name="3-session trend",
            x=valid["id"], y=rolling, mode="lines", name="3-session trend",
            line=dict(color="#f04a6e", width=2, dash="dot"),
            hovertemplate="Trend: %{y:.2f}s<extra></extra>",
        ))
    fig.update_layout(**blayout(
        height=240, showlegend=False,
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False, title="session"),
                   tickfont=dict(size=9), zeroline=False, title="session"),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False,
                   rangemode="tozero", title="seconds"),
    ))
    return fig


def chart_correct_rt(df):
    crt = correct_rt_series(df)
    if crt.empty:
        fig = go.Figure()
        fig.update_layout(**blayout(height=220, annotations=[dict(
            text="Insufficient data", showarrow=False,
            font=dict(color="#6b7560", size=12, family="Azeret Mono, monospace"),
            xref="paper", yref="paper", x=0.5, y=0.5,
        )]))
        return fig
    y_s     = crt["correct_rt_mean"] / 1000.0
    rolling = y_s.rolling(window=3, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=crt["id"], y=y_s, mode="lines+markers", name="Correct-answer RT",
        line=dict(color="#a78bfa", width=2.5),
        marker=dict(color="#a78bfa", size=6, line=dict(color="#0d0e0c", width=1.5)),
        fill="tozeroy", fillcolor="rgba(167,139,250,0.05)",
        hovertemplate="Session #%{x}<br>%{y:.2f}s<extra></extra>",
    ))
    if len(crt) >= 3:
        fig.add_trace(go.Scatter(
            x=crt["id"], y=rolling, mode="lines", name="3-session trend",
            line=dict(color="#f0b84a", width=2, dash="dot"),
            hovertemplate="Trend: %{y:.2f}s<extra></extra>",
        ))
    fig.update_layout(**blayout(
        height=220, showlegend=False,
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False, title="session"),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False,
                   rangemode="tozero", title="seconds"),
    ))
    return fig


def chart_compensation_ratio(df):
    rows_out = []
    for _, row in scored_only(df).iterrows():
        sat = compute_session_sat(row)
        rows_out.append({"id": row["id"], "ratio": sat["compensation_ratio"]})
    if not rows_out:
        fig = go.Figure()
        fig.update_layout(**blayout(height=220))
        return fig
    rdf  = pd.DataFrame(rows_out)
    roll = rdf["ratio"].rolling(window=3, min_periods=1).mean()
    fig  = go.Figure()
    fig.add_trace(go.Bar(
        x=rdf["id"], y=rdf["ratio"],
        marker=dict(color="#f0b84a", cornerradius=2),
        hovertemplate="Session #%{x}<br>%{y:.0%}<extra></extra>",
    ))
    if len(rdf) >= 3:
        fig.add_trace(go.Scatter(
            x=rdf["id"], y=roll, mode="lines", name="3-session trend",
            line=dict(color="#f04a6e", width=2, dash="dot"),
            hovertemplate="Trend: %{y:.0%}<extra></extra>",
        ))
    fig.update_layout(**blayout(
        height=220, showlegend=False,
        xaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False, title="session"),
        yaxis=dict(gridcolor="#2c3025", linecolor="#2c3025",
                   tickfont=dict(size=9), zeroline=False,
                   range=[0,1.1], tickformat=".0%", title="ratio"),
    ))
    return fig


# REMOVED: chart_sat_scatter — information overload for rehabilitation clinicians;
# compensation index and correct-answer RT already capture the actionable signal.


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(users: list, connected: bool) -> str | None:
    with st.sidebar:
        st.markdown(
            '<div style="margin-bottom:2rem;padding-bottom:1.5rem;'
            'border-bottom:1px solid #2c3025">'
            '<div style="font-family:\'Playfair Display\',serif;font-size:1.5rem;'
            'font-weight:700;color:#e8ecdf;letter-spacing:-.02em;line-height:1.1">'
            'MathGesture</div>'
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.55rem;'
            'font-weight:600;letter-spacing:.25em;color:#6b7560;'
            'text-transform:uppercase;margin-top:.4rem">Clinical Dashboard</div>'
            '</div>', unsafe_allow_html=True,
        )
        if _USE_API:
            st.markdown(
                f'<div style="font-family:\'Azeret Mono\',monospace;font-size:.55rem;'
                f'letter-spacing:.1em;color:#6b7560;margin-bottom:1.2rem">'
                f'⚡ {FLASK_URL}</div>',
                unsafe_allow_html=True,
            )
        if not users:
            st.markdown(
                '<p style="font-family:\'Azeret Mono\',monospace;font-size:.75rem;'
                'color:#6b7560;line-height:1.8">No patients on record.<br/>'
                'Complete a device session first.</p>',
                unsafe_allow_html=True,
            )
            if st.button("↺  Refresh", use_container_width=True):
                st.cache_data.clear(); st.rerun()
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
        cur  = next((i for i, o in enumerate(opts)
                     if o.startswith(str(st.session_state.sel))), 0)
        raw  = st.selectbox("patient", opts, index=cur,
                            label_visibility="collapsed")
        sel  = raw.split("  ·  ")[0].strip()
        st.session_state.sel = sel

        st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

        for u in users:
            active = str(u["user_id"]) == sel
            cls    = "pt-card active" if active else "pt-card"
            last   = (u["last_session"] or "—")[:10]
            avg    = f"{u['avg_score']}/5" if u.get("avg_score") else "—"
            avg    = f"{u['avg_score']}/5" if u.get("avg_score") else "—"
            st.markdown(
                f'<div class="{cls}"><div class="pt-id">ID · {u["user_id"]}</div>'
                f'<div class="pt-name">{u["display_name"]}</div>'
                f'<div class="pt-meta"><span>{u["session_count"]} sessions</span>'
                f'<span>avg {avg}</span><span>{last}</span></div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        st.markdown("---")

        active_user = next((u for u in users if str(u["user_id"]) == sel), None)
        if active_user:
            with st.expander("🗑  Remove Patient"):
                st.markdown(
                    f'<p style="font-family:\'Azeret Mono\',monospace;'
                    f'font-size:.7rem;color:#6b7560;line-height:1.8">'
                    f'Permanently removes '
                    f'Permanently removes '
                    f'<span style="color:#f04a6e;font-weight:600">'
                    f'{active_user["display_name"]}</span> '
                    f'and all their sessions.</p>',
                    unsafe_allow_html=True,
                )
                confirmed = st.checkbox("I understand this is irreversible",
                                        key=f"del_confirm_{sel}")
                if st.button(f"Remove {active_user['display_name']}",
                             disabled=not confirmed, key=f"del_btn_{sel}"):
                    delete_user_and_sessions(active_user["user_id"])

        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
        if st.button("↺  Refresh", use_container_width=True):
            st.cache_data.clear(); st.rerun()

    return sel


# ── Main view ─────────────────────────────────────────────────────────────────

def render_user_view(user_id: str, display_name: str):

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
            f'line-height:1">{display_name}</h1></div>',
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
                st.success("Saved."); st.rerun()

    st.markdown("---")

    # Server badge — shows which backend this data came from
    st.markdown(
        f'<div class="server-badge">⚡  {FLASK_URL}</div>',
        unsafe_allow_html=True,
    )

    df = load_sessions(user_id)

    scored = scored_only(df)
    cal    = df[df["is_calibration"].astype(bool)] if not df.empty else pd.DataFrame()

    if df.empty:
        st.markdown(
            f'<div style="text-align:center;padding:6rem 1rem">'
            f'<div style="font-family:\'Playfair Display\',serif;font-size:3rem;'
            f'font-style:italic;color:#2c3025;margin-bottom:1rem">No sessions yet</div>'
            f'<div style="font-family:\'Azeret Mono\',monospace;font-size:.65rem;'
            f'letter-spacing:.18em;color:#6b7560">'
            f'COMPLETE A ROUND ON THE DEVICE  ·  USER ID {user_id}</div>'
            f'</div>', unsafe_allow_html=True,
        )
        return

    # Calibration note
    if not cal.empty and scored.empty:
        st.markdown(
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.72rem;'
            'color:#4af0c8;border-left:3px solid #4af0c8;padding:.6rem 1rem;'
            'margin-bottom:1rem">'
            '◈  Calibration session recorded.  '
            'Scoring begins from the next session.  '
            'This session is excluded from all biomarker calculations.'
            '</div>',
            unsafe_allow_html=True,
        )

    # Alerts
    rt_flagged, rt_msg, rt_state = response_time_trend_flag(df)
    comp_flagged, comp_msg       = compensation_alert(df)

    if rt_flagged:
        st.markdown(
            f'<div class="alert-box"><strong>⚠  CLINICAL ALERT</strong>'
            f'<br/>{rt_msg}</div>',
            unsafe_allow_html=True,
        )
    elif comp_flagged:
        st.markdown(
            f'<div class="warn-box"><strong>◈  EARLY WARNING</strong>'
            f'<br/>{comp_msg}</div>',
            unsafe_allow_html=True,
        )
    elif rt_state == "building" and not scored.empty:
        st.markdown(f'<div class="build-box">{rt_msg}</div>',
                    unsafe_allow_html=True)

    # KPIs
    st.markdown(
        '<div class="sec"><span class="sec-tag">Overview</span>Key Indicators</div>',
        unsafe_allow_html=True,
    )

    if scored.empty:
        st.markdown(
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.75rem;'
            'color:#6b7560;padding:1rem 0">No scored sessions yet.</div>',
            unsafe_allow_html=True,
        )
    else:
        total    = len(scored)
        accuracy = round(scored["correct_count"].sum() /
                         (total * QUESTIONS_PER_SESSION) * 100, 1)
        curr_lv  = int(scored["difficulty_after"].iloc[-1])

        vrt         = scored[scored["avg_response_time_ms"] > 0]["avg_response_time_ms"]
        avg_rt_s    = round(vrt.mean()/1000, 2) if not vrt.empty else 0.0
        recent_rt_s = round(vrt.iloc[-3:].mean()/1000, 2) if len(vrt) >= 3 else None
        rt_delta    = f"last 3: {recent_rt_s}s" if recent_rt_s else None

        recent_sat = [compute_session_sat(row)
                      for _, row in scored.tail(5).iterrows()]
        comp_index = (round(sum(s["compensation_ratio"] for s in recent_sat)
                            / len(recent_sat), 2) if recent_sat else 0.0)
        prev_sat   = ([compute_session_sat(row)
                       for _, row in scored.iloc[-6:-5].iterrows()]
                      if len(scored) >= 8 else [])
        prev_comp  = (round(sum(s["compensation_ratio"] for s in prev_sat)
                            / len(prev_sat), 2) if prev_sat else None)
        comp_delta = f"prev: {prev_comp:.0%}" if prev_comp is not None else None

        # ── Row 1: Core metrics ───────────────────────────────────────────────
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        r1c1.metric("Scored Sessions", total,
                    f"+{len(cal)} cal" if not cal.empty else None)
        r1c2.metric("Accuracy",       f"{accuracy}%")
        r1c3.metric("Current Level",  f"Lv {curr_lv}",
                    DIFFICULTY_NAMES[curr_lv].split("·")[1].strip())
        r1c4.metric("Avg Resp Time",  f"{avg_rt_s}s", rt_delta,
                    delta_color="inverse")

        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

        # REMOVED: Row 2 (avg score, best score, best streak, level ups)
        # These were engagement/gamification metrics with no clinical value.

        # ── SAT explainer (collapsible) ───────────────────────────────────────
        with st.expander("ⓘ  Understanding the biomarkers below"):
            st.markdown(
                '<div class="info-panel" style="border:none;padding:0;margin:0">'
                '<div class="info-title">Why response time matters more than score</div>'
                '<p>When cognitive decline begins, patients instinctively '
                '<strong>slow down to maintain accuracy</strong> — a pattern '
                'called <strong>compensation</strong>. Their scores stay high, '
                'but they need more time to achieve the same results. '
                'Standard tests that only check correct/incorrect miss this entirely.</p>'
                '<p style="margin-top:.6rem">The metrics below are designed to detect '
                'this pattern <strong>before scores drop</strong>, potentially months '
                'earlier than traditional assessments.</p>'
                '<dl class="info-terms" style="margin-top:1rem">'
                '<dt style="color:#f0b84a">Compensation Idx</dt>'
                '<dd>What fraction of correct answers took longer than average. '
                'A healthy patient answers correctly <em>and</em> quickly. '
                'A rising index means correct answers are requiring more effort.</dd>'
                '<dt style="color:#a78bfa">Correct-Ans RT</dt>'
                '<dd>Average response time on <em>only</em> the questions answered correctly. '
                'Isolates cognitive processing speed from guessing. '
                'If this rises while accuracy holds steady, the patient is compensating.</dd>'
                '<dt style="color:#c8f04a">SAT Pattern</dt>'
                '<dd>The dominant speed-accuracy profile across recent sessions. '
                '<strong>Normal</strong> = fast and correct. '
                '<strong>Compensating</strong> = slow but correct (early warning). '
                '<strong>Impulsive</strong> = fast but wrong. '
                '<strong>Deteriorating</strong> = slow and wrong (late stage).</dd>'
                '<dt style="color:#6b7560">Sessions at Lv</dt>'
                '<dd>How many scored sessions exist at the current difficulty level. '
                'The clinical alert system needs at least 10 to establish a reliable '
                'baseline. Until then, monitoring is building.</dd>'
                '</dl>'
                '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)

        # ── Row 2: SAT / compensation biomarkers (was Row 3) ──────────────────
        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        r2c1.metric("Compensation Idx", f"{comp_index:.0%}", comp_delta,
                    delta_color="inverse",
                    help="Fraction of correct answers answered slowly. Rising = compensation.")

        last3_sat = {"normal":0,"compensating":0,"impulsive":0,"deteriorating":0}
        for _, row in scored.tail(3).iterrows():
            s = compute_session_sat(row)
            for k in last3_sat:
                last3_sat[k] += s[k]
        dominant  = max(last3_sat, key=last3_sat.get)
        dom_label = {"normal":"Normal","compensating":"Compensating",
                     "impulsive":"Impulsive","deteriorating":"Deteriorating"}[dominant]
        r2c2.metric("SAT Pattern", dom_label,
                    help="Dominant quadrant, last 3 sessions.")

        crt_df = correct_rt_series(df)
        if len(crt_df) >= 6:
            crt_r = crt_df.iloc[-3:]["correct_rt_mean"].mean()
            crt_e = crt_df.iloc[-6:-3]["correct_rt_mean"].mean()
            crt_p = round((crt_r - crt_e) / crt_e * 100, 1) if crt_e > 0 else 0
            crt_v = f"{round(crt_r/1000, 2)}s"
            crt_d = f"{'+' if crt_p >= 0 else ''}{crt_p}% vs prev 3"
        else:
            crt_v, crt_d = "—", None
        r2c3.metric("Correct-Ans RT", crt_v, crt_d, delta_color="inverse",
                    help="RT on correct answers only. Rising = compensation slope.")
        r2c4.metric("Sessions at Lv",
                    len(scored[scored["difficulty_after"] == curr_lv]),
                    help="Scored sessions at current level. Alert needs 10.")

    st.markdown("---")

    # Performance charts
    if not scored.empty:
        st.markdown(
            '<div class="sec"><span class="sec-tag">Performance</span>'
            'Session Analytics</div>',
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
            'Processing Speed Biomarker  ·  Avg Response Time per Session (seconds)'
            '</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(chart_response_time(df), use_container_width=True,
                        config={"displayModeBar": False})

        st.markdown("---")
        st.markdown(
            '<div class="sec"><span class="sec-tag-warn">SAT</span>'
            'Speed-Accuracy Tradeoff Analysis</div>',
            unsafe_allow_html=True,
        )

        # ── SAT quadrant guide ────────────────────────────────────────────────
        with st.expander("ⓘ  How to read the charts below"):
            st.markdown(
                '<div class="info-panel" style="border:none;padding:0;margin:0">'
                '<div class="info-title">The four response patterns</div>'
                '<p>Each question a patient answers is classified into one of four '
                'quadrants based on two factors: <strong>was it correct?</strong> '
                'and <strong>was it fast or slow?</strong> (relative to that session\'s '
                'average response time).</p>'
                '<div class="info-grid">'
                '<div class="info-quad" style="border-color:#c8f04a;background:rgba(200,240,74,.04)">'
                '<div class="quad-label" style="color:#c8f04a">Normal</div>'
                '<div class="quad-desc">Fast + Correct — the healthy pattern. '
                'The patient knows the answer and responds quickly.</div></div>'
                '<div class="info-quad" style="border-color:#f0b84a;background:rgba(240,184,74,.04)">'
                '<div class="quad-label" style="color:#f0b84a">Compensating</div>'
                '<div class="quad-desc">Slow + Correct — the early warning pattern. '
                'The patient still gets it right but needs extra time. '
                'A shift from Normal to Compensating over weeks is the '
                'earliest signal of cognitive decline.</div></div>'
                '<div class="info-quad" style="border-color:#4af0c8;background:rgba(74,240,200,.04)">'
                '<div class="quad-label" style="color:#4af0c8">Impulsive</div>'
                '<div class="quad-desc">Fast + Wrong — the patient responds quickly '
                'but incorrectly. May indicate attention lapses, rushing, '
                'or difficulty understanding the question.</div></div>'
                '<div class="info-quad" style="border-color:#f04a6e;background:rgba(240,74,110,.04)">'
                '<div class="quad-label" style="color:#f04a6e">Deteriorating</div>'
                '<div class="quad-desc">Slow + Wrong — the patient takes extra time '
                'and still gets it wrong. Indicates the compensation strategy '
                'is no longer sufficient. This is the latest-stage pattern.</div></div>'
                '</div>'
                '<p style="margin-top:1rem"><strong>What to watch for:</strong> '
                'A gradual migration from Normal → Compensating across sessions, '
                'while scores remain high. This means the patient is working harder '
                'to maintain performance.</p>'
                '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown(
                '<div class="clabel" style="color:#a78bfa">'
                'Correct-Answer RT Trend  ·  Rising = Compensation</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(chart_correct_rt(df), use_container_width=True,
                            config={"displayModeBar": False})
            st.markdown(
                '<div style="font-family:var(--mono);font-size:.65rem;'
                'color:var(--ghost);line-height:1.7;padding:.4rem .2rem;'
                'border-top:1px solid var(--rule)">'
                '<span style="color:#a78bfa">Purple line</span> = average '
                'response time for correctly answered questions each session. '
                '<span style="color:#f0b84a">Dotted line</span> = 3-session '
                'rolling trend.<br>'
                '<strong style="color:var(--text)">Reading it:</strong> '
                'A flat or falling trend is healthy. '
                'A rising trend while scores stay high means the patient needs '
                'more time to answer correctly — the compensation pattern. '
                'Look for a sustained upward drift over 4+ sessions, not single spikes '
                '(one slow session can be fatigue or distraction).'
                '</div>',
                unsafe_allow_html=True,
            )
        with sc2:
            st.markdown(
                '<div class="clabel" style="color:#f0b84a">'
                'Compensation Ratio  ·  Correct Answers That Were Slow</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(chart_compensation_ratio(df), use_container_width=True,
                            config={"displayModeBar": False})
            st.markdown(
                '<div style="font-family:var(--mono);font-size:.65rem;'
                'color:var(--ghost);line-height:1.7;padding:.4rem .2rem;'
                'border-top:1px solid var(--rule)">'
                '<span style="color:#f0b84a">Bars</span> = fraction of correct '
                'answers that took longer than the session average. '
                '<span style="color:#f04a6e">Dotted line</span> = 3-session '
                'rolling trend.<br>'
                '<strong style="color:var(--text)">Reading it:</strong> '
                'A ratio near 0% means correct answers came quickly (healthy). '
                'A ratio near 50%+ means the patient is getting answers right '
                'but struggling for time. A trend climbing from 20% → 40% → 60% '
                'over several sessions is a strong compensation signal — '
                'flag for clinical review even if scores remain 4/5 or 5/5.'
                '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

    # Session history table
    st.markdown(
        '<div class="sec"><span class="sec-tag">History</span>All Sessions</div>',
        unsafe_allow_html=True,
    )

    rows_out = []
    for _, row in df.iloc[::-1].iterrows():
        ba     = int(row["difficulty_before"])
        af     = int(row["difficulty_after"])
        is_cal = bool(row["is_calibration"])
        ch     = "▲ UP" if af > ba else ("▼ DOWN" if af < ba else "— SAME")
        rt     = row["avg_response_time_ms"]
        sat    = compute_session_sat(row) if not is_cal else {}
        rows_out.append({
            "#":         f"#{int(row['id'])}",
            "Type":      "CAL" if is_cal else "SCORED",
            "Timestamp": str(row["timestamp"]).replace("T", "  ")[:16],
            "Score":     f"{int(row['correct_count'])}/5",
            "Avg RT":    f"{rt/1000:.1f}s" if rt > 0 else "—",
            "Comp":      f"{sat.get('compensation_ratio', 0):.0%}" if sat else "—",
            "SAT":       (max({k:v for k,v in sat.items()
                               if k != "compensation_ratio"},
                              key=lambda k: sat[k]).title()
                          if sat else "—"),
            "Lv Before": ba,
            "Lv After":  af,
            "Change":    ch if not is_cal else "— CAL",
            "Level":     DIFFICULTY_NAMES[af],
        })

    st.dataframe(
        pd.DataFrame(rows_out),
        use_container_width=True,
        hide_index=True,
        column_config={
            "#":         st.column_config.TextColumn("#",          width="small"),
            "Type":      st.column_config.TextColumn("Type",       width="small"),
            "Timestamp": st.column_config.TextColumn("Timestamp",  width="medium"),
            "Score":     st.column_config.TextColumn("Score",      width="small"),
            "Avg RT":    st.column_config.TextColumn("Avg RT",     width="small"),
            "Comp":      st.column_config.TextColumn("Comp",       width="small"),
            "SAT":       st.column_config.TextColumn("SAT",        width="medium"),
            "Lv Before": st.column_config.NumberColumn("Lv Before",width="small"),
            "Lv After":  st.column_config.NumberColumn("Lv After", width="small"),
            "Change":    st.column_config.TextColumn("Change",     width="small"),
            "Level":     st.column_config.TextColumn("Level",      width="large"),
        },
    )

    st.markdown("---")

    # Session drilldown
    st.markdown(
        '<div class="sec"><span class="sec-tag">Drilldown</span>'
        'Per-Question Review</div>',
        unsafe_allow_html=True,
    )

    opts = [
        f"#{int(r['id'])}  ·  "
        f"{'CAL' if bool(r['is_calibration']) else 'SCORED'}  ·  "
        f"{str(r['timestamp'])[:10]}  ·  "
        f"{int(r['correct_count'])}/5  ·  "
        f"RT {r['avg_response_time_ms']/1000:.1f}s"
        for _, r in df.iloc[::-1].iterrows()
    ]
    sel_opt = st.selectbox("session", opts, label_visibility="collapsed")
    sel_id  = int(sel_opt.split("  ·  ")[0].lstrip("#"))
    sel_row = df[df["id"] == sel_id].iloc[0]
    is_cal  = bool(sel_row["is_calibration"])
    evs     = sel_row["evaluations"]
    rts     = sel_row["response_times"]
    tags    = sel_row["question_difficulties"]
    mean    = sel_row["avg_response_time_ms"]

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    qc = st.columns(5)
    for i, ev in enumerate(evs):
        with qc[i]:
            ok    = ev["is_correct"]
            tc    = "#c8f04a" if ok else "#f04a6e"
            icon  = "✓" if ok else "✗"
            ans_c = "#c8f04a" if ok else "#f04a6e"
            rt_v  = rts[i] if i < len(rts) else 0
            rt_d  = f"{rt_v/1000:.1f}s" if rt_v > 0 else "—"
            tag   = tags[i] if i < len(tags) else "medium"
            tag_c = TAG_COLORS.get(tag, "#6b7560")

            sat_html = ""
            if rt_v > 0 and mean > 0 and not is_cal:
                sat_lbl   = sat_classify(rt_v, ok, mean)
                sat_color = SAT_COLORS[sat_lbl]
                sat_html  = (f'<div class="q-sat" style="color:{sat_color}">'
                             f'◈  {sat_lbl.upper()}</div>')

            wrong_html = (
                f'<div class="q-answer" style="color:#6b7560">'
                f'expected: <span style="color:#e8ecdf">'
                f'{ev["correct_answer"]}</span></div>'
            ) if not ok else ""

            st.markdown(
                f'<div class="q-card" style="border-top-color:{tc}">'
                f'<div class="q-num">Q{i+1}'
                f'<span style="float:right;font-size:.95rem;color:{tc}">'
                f'{icon}</span></div>'
                f'<div class="q-tag" style="color:{tag_c};'
                f'background:rgba(0,0,0,.2);border:1px solid {tag_c}30">'
                f'{tag.upper()}</div>'
                f'<div class="q-text">{ev["question"]}</div>'
                f'<div class="q-answer" style="color:{ans_c}">'
                f'{ev["user_answer"]}</div>'
                f'{wrong_html}'
                f'<div class="q-time">⏱  {rt_d}</div>'
                f'{sat_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # REMOVED: SAT scatter plot per session — the compensation index and
    # correct-answer RT already capture the clinically actionable signal.
    # The scatter plot added granularity useful for researchers but was
    # information overload for rehabilitation clinicians doing weekly checks.

    st.markdown("---")

    with st.expander(f"⚠  Danger Zone — {display_name}"):
        st.markdown(
            f'<p style="font-family:\'Azeret Mono\',monospace;font-size:.75rem;'
            f'color:#6b7560;line-height:1.8">Permanently deletes all sessions for '
            f'<span style="color:#f04a6e;font-weight:600">{user_id}</span>.</p>',
            unsafe_allow_html=True,
        )
        ok = st.checkbox("I understand this is irreversible", key=f"ck_{user_id}")
        ok = st.checkbox("I understand this is irreversible", key=f"ck_{user_id}")
        if st.button(f"Erase {display_name}'s data",
                     disabled=not ok, key=f"del_{user_id}"):
            clear_user_sessions(user_id)
            st.success("Data erased.")
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not _USE_API and not os.path.exists(DB_PATH):
        st.markdown(
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'justify-content:center;height:75vh;gap:1.5rem">'
            '<div style="font-family:\'Playfair Display\',serif;font-size:3.5rem;'
            'font-style:italic;color:#2c3025">Database not found</div>'
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.65rem;'
            'color:#6b7560;letter-spacing:.18em">'
            'RUN app.py AND COMPLETE AT LEAST ONE DEVICE SESSION</div>'
            '</div>', unsafe_allow_html=True,
        )
        return

    if sel_id is None:
        st.markdown(
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'justify-content:center;height:75vh;gap:1.5rem">'
            '<div style="font-family:\'Playfair Display\',serif;font-size:3.5rem;'
            'font-style:italic;color:#2c3025">No patients yet</div>'
            '<div style="font-family:\'Azeret Mono\',monospace;font-size:.65rem;'
            'color:#6b7560;letter-spacing:.18em">'
            'COMPLETE A SESSION ON THE DEVICE TO REGISTER A PATIENT</div>'
            '</div>', unsafe_allow_html=True,
        )
        return

    u    = next((u for u in users if str(u["user_id"]) == sel_id), None)
    name = u["display_name"] if u else sel_id
    render_user_view(sel_id, name)


if __name__ == "__main__":
    main()
