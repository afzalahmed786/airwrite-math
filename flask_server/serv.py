from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Difficulty levels
DIFFICULTY_LEVELS = [
    "Single-Digit Addition and subtraction",
    "Single-Digit Multiplication and division",
    "Two-Digit Addition",
    "Two-Digit Subtraction",
    "Mixed Two-Digit Addition and Subtraction",
]

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# -----------------------------
# Utility: Validate difficulty
# -----------------------------
def is_valid_difficulty(level):
    return 0 <= level < len(DIFFICULTY_LEVELS)

# -------------------------------------
# Route: Generate Questions via Gemini
# -------------------------------------
@app.route('/generate_questions', methods=['GET'])
def generate_questions():
    try:
        difficulty = int(request.args.get('difficulty', 0))

        if not is_valid_difficulty(difficulty):
            return jsonify({"error": f"Invalid difficulty level. Must be between 0 and {len(DIFFICULTY_LEVELS) - 1}"}), 400

        prompt = (
            f"Generate 5 unique math questions that are {DIFFICULTY_LEVELS[difficulty]}. "
            "Follow these rules EXACTLY:\n"
            "1. The answer to each question must be a single or multiple digits from the set [0, 1, 2, 3, 4].\n"
            "2. Format each question on a new line. Do NOT include any additional text, empty lines, or explanations."
        )

        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 800}
        }

        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)

        if response.status_code == 200:
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            questions = [line.strip() for line in text.split('\n') if line.strip()]
            return jsonify({"questions": questions[:5]})
        else:
            return jsonify({"error": "Failed to generate questions", "details": response.text}), 500

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# --------------------------------------
# Route: Evaluate Submitted Answers
# --------------------------------------
@app.route('/evaluate_answers', methods=['POST'])
def evaluate_answers():
    try:
        data = request.get_json()

        if not data or not all(k in data for k in ["answers", "questions", "difficulty"]):
            return jsonify({"error": "Invalid data: 'answers', 'difficulty', and 'questions' are required"}), 400

        answers = data["answers"]
        questions = data["questions"]
        difficulty = data["difficulty"]

        if not is_valid_difficulty(difficulty):
            return jsonify({"error": f"Invalid difficulty level. Must be between 0 and {len(DIFFICULTY_LEVELS) - 1}"}), 400

        if len(answers) != 5 or len(questions) != 5:
            return jsonify({"error": "There must be exactly 5 questions and 5 answers"}), 400

        evaluations = []
        correct_count = 0

        for q, a in zip(questions, answers):
            user_ans = str(a).strip()
            
            # 1. CLEAN THE STRING: Remove '=' and whitespace
            clean_q = q.replace("=", "").strip()
            
            # 2. SWAP SYMBOLS: Change human symbols to Python math operators
            clean_q = clean_q.replace("x", "*").replace("X", "*")
            clean_q = clean_q.replace("÷", "//") # Use // for integer results
            
            try:
                # 3. EVALUATE: Now clean_q looks like "1 * 3" instead of "1 x 3 ="
                correct_val = int(eval(clean_q))
                correct_ans = str(correct_val)
            except Exception as e:
                print(f"Failed to evaluate: {clean_q}. Error: {e}")
                correct_ans = "Error"
        
            is_correct = (user_ans == correct_ans)
            
            if is_correct:
                correct_count += 1
            
            evaluations.append({
                "question": q,
                "user_answer": user_ans,
                "correct_answer": correct_ans,
                "is_correct": is_correct
            })

        if correct_count >= 4:
            new_difficulty = min(difficulty + 1, len(DIFFICULTY_LEVELS) - 1)
        elif correct_count >= 2:
            new_difficulty = difficulty
        else:
            new_difficulty = max(difficulty - 1, 0)

        return jsonify({
            "evaluations": evaluations,
            "correct_count": correct_count,
            "new_difficulty": new_difficulty,
            "message": f"Current difficulty: {DIFFICULTY_LEVELS[new_difficulty]}"
        })

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# ------------------------
# App Entry Point (Dev Only)
# ------------------------
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True)
