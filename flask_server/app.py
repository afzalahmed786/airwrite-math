

import re
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "GEMINI_API_KEY")
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

# Only these characters are permitted in a sanitised math expression.
# Blocks any attempt to smuggle code through the question string.
_SAFE_MATH_RE = re.compile(r"^[\d\s\+\-\*\/\(\)]+$")

app = Flask(__name__)
CORS(app)


# ── Database ──────────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    """
    Context-manager wrapper around SQLite so connections are always closed,
    even when an exception is raised inside the `with` block.
    """
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
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id           TEXT    NOT NULL DEFAULT 'default',
                timestamp         TEXT    NOT NULL,
                difficulty_before INTEGER NOT NULL,
                difficulty_after  INTEGER NOT NULL,
                correct_count     INTEGER NOT NULL,
                questions         TEXT    NOT NULL,
                answers           TEXT    NOT NULL,
                evaluations       TEXT    NOT NULL,
                response_times    TEXT    NOT NULL DEFAULT '[]'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id      TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at   TEXT NOT NULL
            )
        """)
        # Non-destructive upgrades for databases created before these columns existed
        for col, definition in [
            ("user_id",        "TEXT NOT NULL DEFAULT 'default'"),
            ("response_times", "TEXT NOT NULL DEFAULT '[]'"),
        ]:
            try:
                conn.execute(
                    f"ALTER TABLE sessions ADD COLUMN {col} {definition}"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists — expected on every run after the first


init_db()


# ── Validation helpers ────────────────────────────────────────────────────────

def is_valid_difficulty(level: int) -> bool:
    return 0 <= level < len(DIFFICULTY_LEVELS)


def sanitise_user_id(raw: str) -> str:
    """
    Strip whitespace and keep only alphanumeric characters and underscores.
    Returns 'default' for an empty or entirely-invalid value.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", raw.strip())
    return cleaned if cleaned else "default"


def safe_eval(expression: str) -> int | None:
    """
    Evaluate a simple arithmetic expression without using eval().
    Returns None if the expression is malformed or unsafe.

    Supported operators: + - * // (integer division)
    The expression must contain only digits, spaces, and operator characters.
    """
    # Reject anything that contains characters we don't expect
    if not _SAFE_MATH_RE.match(expression):
        return None
    try:
        # ast.literal_eval can't handle operators, so we use compile() +
        # exec() restricted to an empty namespace — far safer than bare eval().
        code    = compile(expression, "<string>", "eval")
        allowed = {"__builtins__": {}}
        result  = eval(code, allowed)          # noqa: S307  (intentionally restricted)
        return int(result)
    except Exception:
        return None


def normalise_question(q: str) -> str:
    """
    Convert a human-readable math question into a form safe_eval can process.
    Removes trailing '?' / '=' and converts operator symbols.
    """
    expr = q.replace("?", "").replace("=", "").strip()
    expr = expr.replace("x", "*").replace("X", "*").replace("÷", "//")
    # Convert single '/' to integer division '//' only when not already '//'
    expr = re.sub(r"(?<!/)/(?!/)", "//", expr)
    return expr


def get_fallback(level: int) -> list[str]:
    fallbacks: list[list[str]] = [
        ["1 + 2", "4 - 1", "2 + 2", "3 - 0", "1 + 1"],
        ["2 x 1", "8 / 2", "3 x 1", "9 / 3", "2 x 2"],
        ["10 + 14", "20 + 22", "11 + 11", "30 + 11", "12 + 10"],
        ["25 - 10", "40 - 20", "33 - 11", "15 - 5",  "22 - 12"],
        ["12 + 8",  "25 - 5",  "10 x 2",  "6 / 2",   "30 - 10"],
    ]
    return fallbacks[level] if 0 <= level < len(fallbacks) else fallbacks[0]


# ── User helpers ──────────────────────────────────────────────────────────────

def ensure_user_exists(conn: sqlite3.Connection, user_id: str) -> None:
    """
    Insert a default user record if this user_id has never been seen.
    Accepts an open connection so the caller controls the transaction.
    """
    row = conn.execute(
        "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (user_id, display_name, created_at) VALUES (?, ?, ?)",
            (
                user_id,
                f"User {user_id}",
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )


# ── Route: List Users ─────────────────────────────────────────────────────────

@app.route("/users", methods=["GET"])
def list_users():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT u.user_id, u.display_name, u.created_at,
                      COUNT(s.id)        AS session_count,
                      MAX(s.timestamp)   AS last_session
               FROM   users u
               LEFT JOIN sessions s ON u.user_id = s.user_id
               GROUP  BY u.user_id
               ORDER  BY u.user_id ASC"""
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Route: Create / Update User Display Name ──────────────────────────────────

@app.route("/users/<raw_user_id>", methods=["POST"])
def upsert_user(raw_user_id: str):
    user_id      = sanitise_user_id(raw_user_id)
    data         = request.get_json(silent=True) or {}
    display_name = str(data.get("display_name", f"User {user_id}")).strip()[:80]

    with get_db() as conn:
        conn.execute(
            """INSERT INTO users (user_id, display_name, created_at) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET display_name = excluded.display_name""",
            (user_id, display_name, datetime.utcnow().isoformat(timespec="seconds")),
        )
    return jsonify({"user_id": user_id, "display_name": display_name})


# ── Route: Generate Questions ─────────────────────────────────────────────────

@app.route("/generate_questions", methods=["GET"])
def generate_questions():
    try:
        difficulty = int(request.args.get("difficulty", 0))
        user_id    = sanitise_user_id(request.args.get("user_id", "default"))

        if not is_valid_difficulty(difficulty):
            return jsonify({"error": "Invalid difficulty level"}), 400

        with get_db() as conn:
            ensure_user_exists(conn, user_id)

        prompt = (
            f"Generate 5 unique math questions for Level {difficulty}.\n"
            "Level 0: Basic addition/subtraction (e.g., '1 + 2', '4 - 1')\n"
            "Level 1: Basic multiplication/division (e.g., '2 x 1', '8 / 2')\n"
            "Level 2: Double-digit addition (e.g., '10 + 14', '20 + 22')\n"
            "Level 3: Double-digit subtraction (e.g., '25 - 10', '40 - 20')\n"
            "Level 4: Mixed operations (e.g., '12 + 8', '10 x 2')\n"
            "RULES: The numerical answer MUST be a single digit between 0 and 4 inclusive. "
            "One question per line. Do NOT include answers, labels, or serial numbers. "
            "Do NOT number the questions (no '1.', '2.', etc.)."
        )

        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents":       [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 800},
            },
            timeout=10,
        )

        if response.status_code == 429:
            print("QUOTA EXHAUSTED — returning fallback questions")
            return jsonify({"questions": get_fallback(difficulty)})

        if response.status_code == 200:
            raw_text  = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            questions = []
            for line in raw_text.split("\n"):
                # Strip leading serial numbers such as "1.", "1)", "Q1:"
                line = re.sub(r"^\s*(?:\d+[\.\):]|Q\d+[\.\):]?)\s*", "", line).strip()
                if line:
                    questions.append(line)
            return jsonify({"questions": questions[:5]})

        # Any other non-200 status — fall back silently
        return jsonify({"questions": get_fallback(difficulty)})

    except Exception as exc:
        print(f"generate_questions error: {exc}")
        return jsonify({"questions": get_fallback(0)})


# ── Route: Evaluate Answers ───────────────────────────────────────────────────

@app.route("/evaluate_answers", methods=["POST"])
def evaluate_answers():
    try:
        data = request.get_json(silent=True)

        if not data or not all(
            k in data for k in ("answers", "questions", "difficulty")
        ):
            return jsonify({"error": "Missing required fields: answers, questions, difficulty"}), 400

        answers        = data["answers"]
        questions      = data["questions"]
        difficulty     = int(data["difficulty"])
        user_id        = sanitise_user_id(data.get("user_id", "default"))
        response_times = data.get("response_times", [])

        if not is_valid_difficulty(difficulty):
            return jsonify(
                {"error": f"difficulty must be 0–{len(DIFFICULTY_LEVELS) - 1}"}
            ), 400

        if len(answers) != 5 or len(questions) != 5:
            return jsonify(
                {"error": "Exactly 5 questions and 5 answers are required"}
            ), 400

        # Ensure exactly 5 response time entries; pad with 0 if the device sent fewer
        response_times = list(response_times)[:5]
        response_times += [0] * (5 - len(response_times))

        evaluations   = []
        correct_count = 0

        for q, a in zip(questions, answers):
            user_ans    = str(a).strip()
            expr        = normalise_question(q)
            result      = safe_eval(expr)

            if result is not None:
                correct_ans = str(result)
            else:
                print(f"safe_eval failed: '{q}' → '{expr}'")
                correct_ans = "Error"

            is_correct = user_ans == correct_ans
            if is_correct:
                correct_count += 1

            evaluations.append({
                "question":       q,
                "user_answer":    user_ans,
                "correct_answer": correct_ans,
                "is_correct":     is_correct,
            })

        if   correct_count >= 4: new_difficulty = min(difficulty + 1, len(DIFFICULTY_LEVELS) - 1)
        elif correct_count >= 2: new_difficulty = difficulty
        else:                    new_difficulty = max(difficulty - 1, 0)

        with get_db() as conn:
            ensure_user_exists(conn, user_id)
            conn.execute(
                """INSERT INTO sessions
                   (user_id, timestamp, difficulty_before, difficulty_after,
                    correct_count, questions, answers, evaluations, response_times)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                ),
            )

        return jsonify({
            "evaluations":    evaluations,
            "correct_count":  correct_count,
            "new_difficulty": new_difficulty,
            "message":        f"Current difficulty: {DIFFICULTY_LEVELS[new_difficulty]}",
        })

    except Exception as exc:
        return jsonify({"error": f"Server error: {str(exc)}"}), 500


# ── Route: Get Last Difficulty for a User ─────────────────────────────────────

@app.route("/get_difficulty", methods=["GET"])
def get_difficulty():
    user_id = sanitise_user_id(request.args.get("user_id", "default"))
    with get_db() as conn:
        row = conn.execute(
            "SELECT difficulty_after FROM sessions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if row is None:
        return jsonify({"difficulty": None, "found": False})
    return jsonify({"difficulty": row["difficulty_after"], "found": True})


# ── Route: Stats for a User ───────────────────────────────────────────────────

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
            rows         = conn.execute(
                "SELECT * FROM sessions ORDER BY id ASC"
            ).fetchall()
            display_name = "All Users"
            user_id      = ""

    empty_response = {
        "user_id":                 user_id,
        "display_name":            display_name,
        "total_sessions":          0,
        "average_score":           0,
        "best_score":              0,
        "avg_response_time_ms":    0,
        "current_difficulty":      0,
        "current_difficulty_name": DIFFICULTY_LEVELS[0],
        "difficulty_levels":       DIFFICULTY_LEVELS,
        "sessions":                [],
        "difficulty_over_time":    [],
        "scores_over_time":        [],
        "response_time_over_time": [],
    }

    if not rows:
        return jsonify(empty_response)

    sessions_out:       list[dict] = []
    all_response_times: list[int]  = []

    for r in rows:
        rt = json.loads(r["response_times"]) if r["response_times"] else []
        avg_rt = round(sum(rt) / len(rt), 1) if rt else 0
        sessions_out.append({
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
            "avg_response_time_ms": avg_rt,
        })
        all_response_times.extend(t for t in rt if t > 0)

    scores          = [r["correct_count"] for r in rows]
    global_avg_rt   = (
        round(sum(all_response_times) / len(all_response_times), 1)
        if all_response_times else 0
    )

    return jsonify({
        "user_id":                 user_id,
        "display_name":            display_name,
        "total_sessions":          len(rows),
        "average_score":           round(sum(scores) / len(scores), 2),
        "best_score":              max(scores),
        "avg_response_time_ms":    global_avg_rt,
        "current_difficulty":      rows[-1]["difficulty_after"],
        "current_difficulty_name": DIFFICULTY_LEVELS[rows[-1]["difficulty_after"]],
        "difficulty_levels":       DIFFICULTY_LEVELS,
        "sessions":                sessions_out,
        "difficulty_over_time":    [
            {"session": r["id"], "difficulty": r["difficulty_after"]} for r in rows
        ],
        "scores_over_time":        [
            {"session": r["id"], "score": r["correct_count"]} for r in rows
        ],
        "response_time_over_time": [
            {"session": s["id"], "avg_ms": s["avg_response_time_ms"]}
            for s in sessions_out
        ],
    })


# ── Route: Clear Stats for a User (or all) ────────────────────────────────────

@app.route("/stats/clear", methods=["POST"])
def clear_stats():
    data    = request.get_json(silent=True) or {}
    user_id = sanitise_user_id(data.get("user_id", ""))

    with get_db() as conn:
        if user_id and user_id != "default":
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            msg = f"Session history cleared for user '{user_id}'."
        else:
            conn.execute("DELETE FROM sessions")
            # Reset the auto-increment counter so IDs restart from 1
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'sessions'")
            msg = "All session history cleared."

    return jsonify({"message": msg})

# ── Route: Delete User ────────────────────────────────────────────────────────

@app.route("/users/<raw_user_id>", methods=["DELETE"])
def delete_user(raw_user_id: str):
    """
    Deletes the user record AND all of their sessions.
    Returns 404 if the user does not exist.
    """
    user_id = sanitise_user_id(raw_user_id)

    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

        if row is None:
            return jsonify({"error": f"User '{user_id}' not found."}), 404

        # Delete sessions first (no FK constraint, but keeps it explicit)
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users   WHERE user_id = ?", (user_id,))

    return jsonify({
        "message": f"User '{user_id}' and all their sessions have been deleted."
    })

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
