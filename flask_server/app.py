# app.py  –  MathGesture Flask API Server
# Run: python app.py

import re
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from math import sqrt

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com"
    "/v1beta/models/gemini-2.0-flash:generateContent"
)
DB_PATH = os.path.join(os.path.dirname(__file__), "progress.db")

DIFFICULTY_LEVELS = [
    "Single-Digit Addition and Subtraction",
    "Single-Digit Multiplication and Division",
    "Two-Digit Addition",
    "Two-Digit Subtraction",
    "Mixed Two-Digit Operations",
]

# ── Session constants ─────────────────────────────────────────────────────────
QUESTIONS_PER_SESSION        = 5   # All 5 are scored — no warm-up split
CALIBRATION_SESSIONS_REQUIRED = 1  # Single onboarding session at Level 0

# RT-aware difficulty engine:
# Requires this many prior scored sessions at the current level before
# the RT baseline is considered reliable enough to influence advancement.
RT_BASELINE_MIN_SESSIONS = 3

# If a patient scores ≥4/5 but their session RT is more than this ratio
# above their personal baseline, hold the level rather than advance.
RT_COMPENSATION_THRESHOLD = 1.15

_SAFE_MATH_RE = re.compile(r"^[\d\s\+\-\*\/\(\)]+$")

app = Flask(__name__)
CORS(app)


# ── Database ──────────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id               TEXT    NOT NULL DEFAULT 'default',
                timestamp             TEXT    NOT NULL,
                difficulty_before     INTEGER NOT NULL,
                difficulty_after      INTEGER NOT NULL,
                correct_count         INTEGER NOT NULL,
                questions             TEXT    NOT NULL,
                answers               TEXT    NOT NULL,
                evaluations           TEXT    NOT NULL,
                response_times        TEXT    NOT NULL DEFAULT '[]',
                question_difficulties TEXT    NOT NULL DEFAULT '[]',
                is_calibration        INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id      TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at   TEXT NOT NULL
            )
        """)
        # Non-destructive upgrades for pre-existing databases
        for col, definition in [
            ("user_id",               "TEXT    NOT NULL DEFAULT 'default'"),
            ("response_times",        "TEXT    NOT NULL DEFAULT '[]'"),
            ("question_difficulties", "TEXT    NOT NULL DEFAULT '[]'"),
            ("is_calibration",        "INTEGER NOT NULL DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass


init_db()


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_difficulty(level: int) -> bool:
    return 0 <= level < len(DIFFICULTY_LEVELS)


def sanitise_user_id(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", str(raw).strip())
    return cleaned if cleaned else "default"


def safe_eval(expression: str) -> int | None:
    if not _SAFE_MATH_RE.match(expression):
        return None
    try:
        result = eval(compile(expression, "<string>", "eval"), {"__builtins__": {}})
        return int(result)
    except Exception:
        return None


def normalise_question(q: str) -> str:
    expr = q.replace("?", "").replace("=", "").strip()
    expr = expr.replace("x", "*").replace("X", "*").replace("÷", "//")
    expr = re.sub(r"(?<!/)/(?!/)", "//", expr)
    return expr


def get_fallback(level: int) -> tuple[list[str], list[str]]:
    """Returns (questions[5], tags[5]) randomly sampled from a larger pool."""
    import random

    pools: list[list[tuple[str, str]]] = [
        # Level 0: single-digit add/sub, answer 0–4
        [
            ("1 + 0", "easy"), ("0 + 3", "easy"), ("2 + 1", "easy"),
            ("1 + 1", "easy"), ("4 + 0", "easy"), ("0 + 0", "easy"),
            ("2 + 2", "medium"), ("1 + 3", "medium"), ("3 + 1", "medium"),
            ("5 - 1", "medium"), ("6 - 3", "medium"), ("7 - 4", "medium"),
            ("8 - 5", "medium"), ("9 - 6", "hard"), ("9 - 7", "hard"),
            ("7 - 5", "hard"), ("8 - 6", "hard"), ("5 - 5", "medium"),
            ("6 - 6", "easy"), ("3 - 3", "easy"), ("4 - 1", "medium"),
            ("3 - 0", "easy"), ("9 - 9", "medium"), ("8 - 4", "hard"),
        ],
        # Level 1: single-digit mul/div, answer 0–4
        [
            ("2 x 1", "easy"), ("1 x 3", "easy"), ("4 x 1", "easy"),
            ("1 x 0", "easy"), ("3 x 0", "easy"), ("0 x 9", "easy"),
            ("2 x 2", "medium"), ("4 / 2", "medium"), ("6 / 2", "medium"),
            ("8 / 2", "medium"), ("6 / 3", "medium"), ("9 / 3", "hard"),
            ("8 / 4", "hard"), ("3 x 1", "easy"), ("4 / 4", "medium"),
            ("1 x 2", "easy"), ("2 / 1", "easy"), ("3 / 1", "medium"),
            ("0 x 5", "easy"), ("0 x 7", "easy"), ("1 x 1", "easy"),
        ],
        # Level 2: two-digit addition, answer 0–4
        [
            ("10 + 14", "easy"), ("21 + 13", "medium"), ("30 + 20", "easy"),
            ("11 + 11", "medium"), ("42 + 7", "medium"), ("33 + 16", "hard"),
            ("12 + 10", "easy"), ("20 + 31", "medium"), ("15 + 25", "hard"),
            ("44 + 5", "medium"), ("37 + 12", "hard"), ("13 + 21", "medium"),
            ("50 + 1", "easy"), ("24 + 13", "medium"), ("18 + 30", "hard"),
            ("22 + 11", "medium"), ("41 + 8", "medium"), ("60 + 40", "easy"),
        ],
        # Level 3: two-digit subtraction, answer 0–4
        [
            ("25 - 22", "easy"), ("40 - 38", "medium"), ("33 - 31", "medium"),
            ("50 - 50", "easy"), ("44 - 41", "medium"), ("19 - 17", "hard"),
            ("53 - 50", "medium"), ("67 - 64", "hard"), ("88 - 85", "hard"),
            ("15 - 12", "easy"), ("27 - 24", "medium"), ("36 - 33", "medium"),
            ("71 - 68", "hard"), ("99 - 96", "hard"), ("12 - 10", "easy"),
            ("30 - 30", "easy"), ("45 - 42", "medium"), ("61 - 58", "hard"),
        ],
        # Level 4: mixed two-digit operations, answer 0–4
        [
            ("12 + 8", "easy"), ("25 - 23", "medium"), ("10 x 0", "easy"),
            ("30 - 10", "easy"), ("15 - 13", "medium"), ("11 x 0", "easy"),
            ("20 / 10", "medium"), ("50 - 47", "hard"), ("24 / 6", "hard"),
            ("13 + 21", "medium"), ("99 - 97", "hard"), ("16 / 4", "hard"),
            ("33 - 30", "medium"), ("40 / 10", "hard"), ("18 - 14", "hard"),
            ("22 - 22", "easy"), ("44 - 41", "medium"), ("12 / 3", "hard"),
        ],
    ]

    idx = level if 0 <= level < len(pools) else 0
    pool = pools[idx]
    chosen = random.sample(pool, min(QUESTIONS_PER_SESSION, len(pool)))
    return [q for q, _ in chosen], [t for _, t in chosen]


def ensure_user_exists(conn: sqlite3.Connection, user_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (user_id, display_name, created_at) VALUES (?, ?, ?)",
            (user_id, f"User {user_id}",
             datetime.utcnow().isoformat(timespec="seconds")),
        )


def count_calibration_sessions(conn: sqlite3.Connection, user_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE user_id = ? AND is_calibration = 1",
        (user_id,)
    ).fetchone()
    return row[0] if row else 0


def get_rt_baseline(
    conn: sqlite3.Connection,
    user_id: str,
    difficulty: int,
) -> float | None:
    """
    Mean RT across the patient's most recent scored sessions at this
    difficulty level. Returns None when insufficient data exists.
    """
    rows = conn.execute(
        """SELECT response_times FROM sessions
           WHERE user_id = ? AND difficulty_after = ? AND is_calibration = 0
           ORDER BY id DESC LIMIT ?""",
        (user_id, difficulty, RT_BASELINE_MIN_SESSIONS),
    ).fetchall()

    if len(rows) < RT_BASELINE_MIN_SESSIONS:
        return None

    means = []
    for r in rows:
        rt  = json.loads(r["response_times"]) if r["response_times"] else []
        rts = [v for v in rt if v > 0]
        if rts:
            means.append(sum(rts) / len(rts))

    return sum(means) / len(means) if means else None


def get_recent_questions(
    conn: sqlite3.Connection, user_id: str, difficulty: int, limit: int = 3
) -> list[str]:
    """
    Return a flat list of questions from the user's most recent sessions
    at the given difficulty level, so Gemini can be told to avoid them.
    """
    rows = conn.execute(
        """SELECT questions FROM sessions
           WHERE user_id = ? AND difficulty_before = ?
           ORDER BY id DESC LIMIT ?""",
        (user_id, difficulty, limit),
    ).fetchall()
    recent: list[str] = []
    for r in rows:
        recent.extend(json.loads(r["questions"]) if r["questions"] else [])
    return recent


# ── Routes: Users ─────────────────────────────────────────────────────────────

@app.route("/users", methods=["GET"])
def list_users():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT u.user_id, u.display_name, u.created_at,
                      COUNT(s.id)      AS session_count,
                      MAX(s.timestamp) AS last_session
               FROM   users u
               LEFT JOIN sessions s ON u.user_id = s.user_id
               GROUP  BY u.user_id ORDER BY u.user_id ASC"""
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/users/<raw_uid>", methods=["POST"])
def upsert_user(raw_uid: str):
    user_id      = sanitise_user_id(raw_uid)
    data         = request.get_json(silent=True) or {}
    display_name = str(data.get("display_name", f"User {user_id}")).strip()[:80]
    with get_db() as conn:
        conn.execute(
            """INSERT INTO users (user_id, display_name, created_at) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET display_name = excluded.display_name""",
            (user_id, display_name,
             datetime.utcnow().isoformat(timespec="seconds")),
        )
    return jsonify({"user_id": user_id, "display_name": display_name})


@app.route("/users/<raw_uid>", methods=["DELETE"])
def delete_user(raw_uid: str):
    user_id = sanitise_user_id(raw_uid)
    with get_db() as conn:
        if not conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone():
            return jsonify({"error": f"User '{user_id}' not found."}), 404
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users   WHERE user_id = ?", (user_id,))
    return jsonify({"message": f"User '{user_id}' and all sessions deleted."})


# ── Route: Generate Questions ─────────────────────────────────────────────────

@app.route("/generate_questions", methods=["GET"])
def generate_questions():
    """
    Returns QUESTIONS_PER_SESSION (5) questions with per-question difficulty
    tags. All 5 are scored — there is no warm-up split.

    Response: {"questions": [...], "tags": ["easy"|"medium"|"hard", ...]}
    """
    try:
        difficulty = int(request.args.get("difficulty", 0))
        user_id    = sanitise_user_id(request.args.get("user_id", "default"))

        if not is_valid_difficulty(difficulty):
            return jsonify({"error": "Invalid difficulty level"}), 400

        with get_db() as conn:
            ensure_user_exists(conn, user_id)
            recent_qs = get_recent_questions(conn, user_id, difficulty)

        # Build an "avoid these" clause if the user has recent history
        avoid_clause = ""
        if recent_qs:
            avoid_clause = (
                "\nAVOID REPEATS — do NOT reuse any of these recent questions:\n"
                + ", ".join(f'"{q}"' for q in recent_qs[:15])
                + "\nGenerate COMPLETELY DIFFERENT questions.\n"
            )

        prompt = (
            f"Return a JSON array of exactly {QUESTIONS_PER_SESSION} math questions. "
            f"Nothing else. No explanation. No markdown. No preamble. Only the JSON array.\n"
            f"Difficulty level: {difficulty}\n"
            "Level 0: single digit addition/subtraction only (e.g. '7 - 3', '5 + 0', '9 - 6')\n"
            "Level 1: single digit multiplication/division only (e.g. '6 / 3', '4 x 1', '8 / 4')\n"
            "Level 2: two digit addition only (e.g. '13 + 21', '45 + 5', '37 + 12')\n"
            "Level 3: two digit subtraction only (e.g. '44 - 41', '53 - 50', '27 - 24')\n"
            "Level 4: mixed two digit operations (e.g. '15 - 13', '11 x 0', '24 / 6')\n"
            "STRICT RULES:\n"
            "1. The answer to every question MUST be exactly 0, 1, 2, 3, or 4.\n"
            "2. Questions must use only numbers and operators (+, -, x, /). No words.\n"
            "3. No question numbering, no labels, no explanations.\n"
            "4. Tag each as easy, medium, or hard.\n"
            "5. Return ONLY this exact format:\n"
            '   [{"q":"7 - 3","tag":"easy"},{"q":"9 - 6","tag":"medium"}]\n'
            "VARIETY IS CRITICAL:\n"
            "6. Each question must use DIFFERENT numbers — no two questions should "
            "look similar.\n"
            "7. Mix the target answers: use at least 3 different answers from {0,1,2,3,4}.\n"
            "8. Use LARGER operands when possible. For Level 0, prefer digits 5-9 "
            "(e.g. '9 - 7' not just '1 + 1'). For Levels 2-4, use varied two-digit numbers.\n"
            "9. Include at least one question whose answer is 0.\n"
            + avoid_clause
        )

        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": 400,
                    "temperature": 0.9,      # higher = more variety in questions
                    "topP": 0.95,
                },
                "systemInstruction": {
                    "parts": [{"text": "You are a math question generator. You output only valid JSON arrays. You never output words, explanations, or markdown."}]
                },
            },
            timeout=12,
        )

        if response.status_code == 429:
            qs, tags = get_fallback(difficulty)
            return jsonify({"questions": qs, "tags": tags})

        if response.status_code == 200:
            raw = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            raw = re.sub(r"```json|```", "", raw).strip()
            try:
                items     = json.loads(raw)
                questions = []
                tags      = []
                for item in items[:QUESTIONS_PER_SESSION]:
                    q = re.sub(
                        r"^\s*(?:\d+[\.\):]|Q\d+[\.\):]?)\s*",
                        "", str(item.get("q", "")).strip()
                    ).strip()
                    t = str(item.get("tag", "medium")).lower()
                    if t not in ("easy", "medium", "hard"):
                        t = "medium"
                    if q:
                        questions.append(q)
                        tags.append(t)
            except (json.JSONDecodeError, TypeError):
                # Fall back to plain-text extraction with medium tags
                lines = [
                    re.sub(r"^\s*(?:\d+[\.\):]|Q\d+[\.\):]?)\s*", "", ln).strip()
                    for ln in raw.split("\n") if ln.strip()
                ]
                questions = lines[:QUESTIONS_PER_SESSION]
                tags      = ["medium"] * len(questions)

            # Pad to exactly QUESTIONS_PER_SESSION if needed
            if len(questions) < QUESTIONS_PER_SESSION:
                fb_q, fb_t = get_fallback(difficulty)
                questions += fb_q[len(questions):QUESTIONS_PER_SESSION]
                tags      += fb_t[len(tags):QUESTIONS_PER_SESSION]

            return jsonify({
                "questions": questions[:QUESTIONS_PER_SESSION],
                "tags":      tags[:QUESTIONS_PER_SESSION],
            })

        # Non-200 fallback
        qs, tags = get_fallback(difficulty)
        return jsonify({"questions": qs, "tags": tags})

    except Exception as exc:
        print(f"generate_questions error: {exc}")
        qs, tags = get_fallback(0)
        return jsonify({"questions": qs, "tags": tags})


# ── Route: Evaluate Answers ───────────────────────────────────────────────────

@app.route("/evaluate_answers", methods=["POST"])
def evaluate_answers():
    """
    All QUESTIONS_PER_SESSION (5) answers are scored.
    No warm-up / measurement split.

    Calibration sessions (is_calibration=true):
      - Evaluated and stored.
      - No difficulty adjustment.
      - Excluded from RT baseline and alert calculations.

    RT-aware difficulty (scored sessions, ≥3 prior sessions at level):
      - If correct_count ≥ 4 but session RT > 1.15× personal baseline:
        hold rather than advance.
    """
    try:
        data = request.get_json(silent=True)
        print("=== evaluate_answers received ===")
        print(data)
        print("=================================")
        if not data or not all(
            k in data for k in ("answers", "questions", "difficulty")
        ):
            return jsonify({"error": "Missing required fields"}), 400

        answers        = data["answers"]
        questions      = data["questions"]
        difficulty     = int(data["difficulty"])
        user_id        = sanitise_user_id(data.get("user_id", "default"))
        response_times = list(data.get("response_times", []))[:QUESTIONS_PER_SESSION]
        diff_tags      = list(data.get("question_difficulties", []))[:QUESTIONS_PER_SESSION]
        is_calibration = bool(data.get("is_calibration", False))

        if not is_valid_difficulty(difficulty):
            return jsonify({"error": f"difficulty must be 0–{len(DIFFICULTY_LEVELS)-1}"}), 400
        # NEW — accepts any count between 1 and 10, pads response_times and tags to match
        n = len(questions)
        if n == 0 or len(answers) != n:
            return jsonify({"error": "answers and questions arrays must be the same non-zero length"}), 400
        if n > 10:
            return jsonify({"error": "Maximum 10 questions per session"}), 400

        # Pad response_times and diff_tags to match actual question count
        response_times = list(data.get("response_times", []))[:n]
        response_times += [0] * (n - len(response_times))
        diff_tags      = list(data.get("question_difficulties", []))[:n]
        diff_tags      += ["medium"] * (n - len(diff_tags))

        # ── Evaluate all questions ────────────────────────────────────────────
        evaluations   = []
        correct_count = 0
        for q, a in zip(questions, answers):
            user_ans    = str(a).strip()
            result      = safe_eval(normalise_question(q))
            correct_ans = str(result) if result is not None else "Error"
            is_correct  = user_ans == correct_ans
            if is_correct:
                correct_count += 1
            evaluations.append({
                "question":       q,
                "user_answer":    user_ans,
                "correct_answer": correct_ans,
                "is_correct":     is_correct,
            })

        # ── Session mean RT ───────────────────────────────────────────────────
        valid_rts      = [v for v in response_times if v > 0]
        session_rt_mean = sum(valid_rts) / len(valid_rts) if valid_rts else 0

        # ── Adaptive difficulty ───────────────────────────────────────────────
        is_compensating = False
        if is_calibration:
            new_difficulty = difficulty   # calibration never changes level
        else:
            with get_db() as conn:
                ensure_user_exists(conn, user_id)
                rt_baseline = get_rt_baseline(conn, user_id, difficulty)

            is_compensating = (
                rt_baseline is not None
                and session_rt_mean > 0
                and (session_rt_mean / rt_baseline) > RT_COMPENSATION_THRESHOLD
            )

            if   correct_count >= 4 and not is_compensating:
                new_difficulty = min(difficulty + 1, len(DIFFICULTY_LEVELS) - 1)
            elif correct_count >= 4 and is_compensating:
                new_difficulty = difficulty   # hold — RT-aware block
            elif correct_count >= 2:
                new_difficulty = difficulty
            else:
                new_difficulty = max(difficulty - 1, 0)

        # ── Persist ───────────────────────────────────────────────────────────
        with get_db() as conn:
            ensure_user_exists(conn, user_id)
            conn.execute(
                """INSERT INTO sessions
                   (user_id, timestamp, difficulty_before, difficulty_after,
                    correct_count, questions, answers, evaluations,
                    response_times, question_difficulties, is_calibration)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    datetime.utcnow().isoformat(timespec="seconds"),
                    difficulty,
                    new_difficulty,
                    correct_count,
                    json.dumps(questions),
                    json.dumps(answers),
                    json.dumps(evaluations),
                    json.dumps(response_times),
                    json.dumps(diff_tags),
                    int(is_calibration),
                ),
            )

        return jsonify({
            "evaluations":    evaluations,
            "correct_count":  correct_count,
            "new_difficulty": new_difficulty,
            "is_compensating": is_compensating,
            "message":        f"Difficulty: {DIFFICULTY_LEVELS[new_difficulty]}",
        })

    except Exception as exc:
        return jsonify({"error": f"Server error: {str(exc)}"}), 500


# ── Route: Get Difficulty + Calibration Status ────────────────────────────────

@app.route("/get_difficulty", methods=["GET"])
def get_difficulty():
    """
    Returns the patient's last scored difficulty and calibration status.

    The device uses calibration_required to decide whether to mark the
    next session as is_calibration=True and lock it to Level 0.
    Once calibration_sessions_done >= calibration_sessions_required,
    calibration_required is False and normal scoring begins.
    """
    user_id = sanitise_user_id(request.args.get("user_id", "default"))

    with get_db() as conn:
        ensure_user_exists(conn, user_id)

        # Last scored session difficulty
        row = conn.execute(
            """SELECT difficulty_after FROM sessions
               WHERE user_id = ? AND is_calibration = 0
               ORDER BY id DESC LIMIT 1""",
            (user_id,),
        ).fetchone()

        cal_done = count_calibration_sessions(conn, user_id)

    return jsonify({
        "difficulty":                    row["difficulty_after"] if row else None,
        "found":                         row is not None,
        "calibration_required":          cal_done < CALIBRATION_SESSIONS_REQUIRED,
        "calibration_sessions_done":     cal_done,
        "calibration_sessions_required": CALIBRATION_SESSIONS_REQUIRED,
    })


# ── Route: Stats ──────────────────────────────────────────────────────────────

@app.route("/stats", methods=["GET"])
def stats():
    user_id = sanitise_user_id(request.args.get("user_id", ""))

    with get_db() as conn:
        if user_id and user_id != "default":
            rows = conn.execute(
                "SELECT * FROM sessions WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            ).fetchall()
            u_row        = conn.execute(
                "SELECT display_name FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            display_name = u_row["display_name"] if u_row else user_id
        else:
            rows         = conn.execute("SELECT * FROM sessions ORDER BY id ASC").fetchall()
            display_name = "All Users"
            user_id      = ""

    if not rows:
        return jsonify({
            "user_id": user_id, "display_name": display_name,
            "total_sessions": 0, "scored_sessions": 0, "calibration_sessions": 0,
            "average_score": 0, "best_score": 0, "avg_response_time_ms": 0,
            "current_difficulty": 0,
            "current_difficulty_name": DIFFICULTY_LEVELS[0],
            "difficulty_levels": DIFFICULTY_LEVELS,
            "sessions": [], "difficulty_over_time": [],
            "scores_over_time": [], "response_time_over_time": [],
        })

    sessions_out: list[dict] = []
    all_rt:       list[int]  = []

    for r in rows:
        rt   = json.loads(r["response_times"])         if r["response_times"]         else []
        tags = json.loads(r["question_difficulties"])  if r["question_difficulties"]  else []
        valid_rt = [v for v in rt if v > 0]
        avg_rt   = round(sum(valid_rt) / len(valid_rt), 1) if valid_rt else 0

        sessions_out.append({
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
            "avg_response_time_ms":  avg_rt,
            "is_calibration":        bool(r["is_calibration"]),
        })
        all_rt.extend(valid_rt)

    scored     = [s for s in sessions_out if not s["is_calibration"]]
    scores     = [s["correct_count"] for s in scored] if scored else [0]
    global_rt  = round(sum(all_rt) / len(all_rt), 1) if all_rt else 0

    return jsonify({
        "user_id":                 user_id,
        "display_name":            display_name,
        "total_sessions":          len(rows),
        "scored_sessions":         len(scored),
        "calibration_sessions":    len(rows) - len(scored),
        "average_score":           round(sum(scores) / len(scores), 2),
        "best_score":              max(scores),
        "avg_response_time_ms":    global_rt,
        "current_difficulty":      rows[-1]["difficulty_after"],
        "current_difficulty_name": DIFFICULTY_LEVELS[rows[-1]["difficulty_after"]],
        "difficulty_levels":       DIFFICULTY_LEVELS,
        "sessions":                sessions_out,
        "difficulty_over_time":    [
            {"session": s["id"], "difficulty": s["difficulty_after"]}
            for s in scored
        ],
        "scores_over_time":        [
            {"session": s["id"], "score": s["correct_count"]}
            for s in scored
        ],
        "response_time_over_time": [
            {"session": s["id"], "avg_ms": s["avg_response_time_ms"]}
            for s in scored
        ],
    })


# ── Route: Clear Stats ────────────────────────────────────────────────────────

@app.route("/stats/clear", methods=["POST"])
def clear_stats():
    data    = request.get_json(silent=True) or {}
    user_id = sanitise_user_id(data.get("user_id", ""))
    with get_db() as conn:
        if user_id and user_id != "default":
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            msg = f"Cleared sessions for '{user_id}'."
        else:
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'sessions'")
            msg = "All sessions cleared."
    return jsonify({"message": msg})


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)