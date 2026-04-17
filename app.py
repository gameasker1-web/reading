from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import requests
from google import genai

app = Flask(__name__)
# ВАЖНО: CORS позволяет фронтенду общаться с бэкендом
CORS(app)

# Настройки PostgreSQL
DB_CONFIG = {
    "dbname": "reading_challenge",
    "user": "postgres",
    "password": "1212",
    "host": "localhost",
    "port": "5432"
}

# Настройка Gemini (Новая библиотека)
GEMINI_API_KEY = "AQ.Ab8RN6LTsYX7eeSs8Y0eZFNAtbnfO9W0T8SIoImp-a_qTdXU3A"
client = genai.Client(api_key=GEMINI_API_KEY)

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- МАРШРУТЫ ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    if not user:
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id, username", (username, password))
        user = cur.fetchone()
        conn.commit()
    cur.close()
    conn.close()
    return jsonify({"id": user[0], "username": user[1]})

@app.route('/api/books', methods=['POST'])
def add_book():
    data = request.json
    user_id, title, pages = data.get('userId'), data.get('title'), data.get('pages')
    review = data.get('review', '')
    if not title or not pages or int(pages) <= 0:
        return jsonify({"error": "Data error"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO books (user_id, title, pages_read, review) VALUES (%s, %s, %s, %s)",
                (user_id, title, pages, review))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Success"})

@app.route('/api/recommend', methods=['POST'])
def recommend():
    user_prompt = request.json.get('prompt')
    try:
        gb_res = requests.get(f"https://www.googleapis.com/books/v1/volumes?q={user_prompt}&maxResults=3")
        books_data = gb_res.json().get('items', [])
        raw_info = ""
        for item in books_data:
            v = item.get('volumeInfo', {})
            raw_info += f"Title: {v.get('title')}, Authors: {v.get('authors', 'Unknown')}\n"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"User wants books about {user_prompt}. Here are results from Google Books: {raw_info}. Briefly describe each in one short sentence in Russian."
        )
        return jsonify({"text": response.text})
    except Exception as e:
        return jsonify({"text": "AI Error. Try again."}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)