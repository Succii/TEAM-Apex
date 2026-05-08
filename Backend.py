from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
import os

load_dotenv()

app = Flask(__name__)

AI_API_ENDPOINT = os.getenv("https://hackathon-1pvb.onrender.com/api/ai-model/v2/chat")
AI_API_KEY = os.getenv("sk_2e33e0a942c3c889eab6de376393829784c37976")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/translate", methods=["POST"])
def translate():
    data = request.get_json()
    user_text = data.get("text", "").strip()

    if not user_text:
        return jsonify({"error": "Please type something first."}), 400

    prompt = f"""
You are the AI translator for an app called "Así Se Dice".

Convert the user's phrase into casual Puerto Rican Spanglish / Puerto Rican slang.

Rules:
- Keep the same meaning.
- Make it sound natural in Puerto Rico.
- Keep it short and fun.
- Do not use offensive language or slurs.
- Return only the translated phrase.

User phrase:
{user_text}
"""

    try:
        response = requests.post(
            AI_API_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": AI_API_KEY
            },
            json={
                "Context": prompt
            },
            timeout=20
        )

        response.raise_for_status()

        ai_data = response.json()

        # This part depends on the exact response format from the API.
        # Try common response keys first.
        translation = (
            ai_data.get("response")
            or ai_data.get("result")
            or ai_data.get("text")
            or ai_data.get("message")
            or str(ai_data)
        )

        return jsonify({
            "original": user_text,
            "translation": translation.strip()
        })

    except requests.exceptions.RequestException as e:
        print("API request error:", e)
        return jsonify({
            "error": "Could not connect to the AI API endpoint."
        }), 500

    except Exception as e:
        print("Unexpected error:", e)
        return jsonify({
            "error": "Something went wrong while translating."
        }), 500


if __name__ == "__main__":
    app.run(debug=True)