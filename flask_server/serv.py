from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Google Gemini API endpoint and key
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Difficulty levels with more granularity
DIFFICULTY_LEVELS = [
    "Single-Digit Addition and subtraction",
    "Single-Digit Multiplication and division",
    "Two-Digit Addition",
    "Two-Digit Subtraction",
    "Mixed Two-Digit Addition and Subtraction",
]

@app.route('/generate_questions', methods=['GET'])
def generate_questions():
    try:
        # Get difficulty level from query parameters
        difficulty = int(request.args.get('difficulty', 0))

        # Validate difficulty level
        if difficulty < 0 or difficulty >= len(DIFFICULTY_LEVELS):
            return jsonify({"error": f"Invalid difficulty level. Must be between 0 and {len(DIFFICULTY_LEVELS) - 1}"}), 400

        # Create prompt for Gemini API
        prompt = f"Generate 5 unique math questions that are {DIFFICULTY_LEVELS[difficulty]}. " \
                 "Follow these rules EXACTLY:\n" \
                 "1. The answer to each question must be a single or multiple digits from the set [0, 1, 2, 3, 4].\n" \
                 "2. Format each question on a new line. Do NOT include any additional text, empty lines, or explanations."

        # Send request to Gemini API
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 800}
        }
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=data)

        # Handle Gemini API response
        if response.status_code == 200:
            response_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            questions = [q.strip() for q in response_text.split('\n') if q.strip()]
            return jsonify({"questions": questions[:5]})  # Return first 5 questions
        else:
            return jsonify({"error": "Failed to generate questions", "details": response.text}), 500

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/evaluate_answers', methods=['POST'])
def evaluate_answers():
    try:
        # Get JSON data from the request
        data = request.json

        # Validate the incoming data
        if not data or "answers" not in data or "difficulty" not in data or "questions" not in data:
            return jsonify({"error": "Invalid data: 'answers', 'difficulty', and 'questions' fields are required"}), 400

        answers = data["answers"]
        questions = data["questions"]
        difficulty = data["difficulty"]

        # Validate the difficulty level
        if difficulty < 0 or difficulty >= len(DIFFICULTY_LEVELS):
            return jsonify({"error": f"Invalid difficulty level. Must be between 0 and {len(DIFFICULTY_LEVELS) - 1}"}), 400

        # Validate the number of questions and answers
        if len(questions) != 5 or len(answers) != 5:
            return jsonify({"error": "There must be exactly 5 questions and 5 answers"}), 400

        # Step-by-step evaluation
        evaluations = []
        correct_count = 0

        for i in range(5):
            question = questions[i]
            user_answer = str(answers[i]).strip()
            
            # Calculate correct answer
            try:
                correct_answer = str(eval(question.replace("x", "*")))
            except:
                correct_answer = "0"  # Fallback if evaluation fails

            # Check if answer is correct (handle empty answers)
            is_correct = False
            if user_answer and user_answer != " ":
                is_correct = (user_answer == correct_answer)

            if is_correct:
                correct_count += 1

            # Add evaluation for this question
            evaluations.append({
                "question": question,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct
            })

        # Adjust difficulty level based on correct answers
        if correct_count >= 4:
            new_difficulty = min(difficulty + 1, len(DIFFICULTY_LEVELS) - 1)
        elif correct_count >= 2:
            new_difficulty = difficulty
        else:
            new_difficulty = max(difficulty - 1, 0)

        # Prepare the response
        response_data = {
            "evaluations": evaluations,
            "correct_count": correct_count,
            "new_difficulty": new_difficulty,
            "message": f"Current difficulty: {DIFFICULTY_LEVELS[new_difficulty]}"
        }

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)