import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
# ВАЖНО: Разрешаем запросы именно с твоего домена GitHub
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL')
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        points INTEGER DEFAULT 0
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS books (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        title TEXT NOT NULL,
        author TEXT,
        review TEXT,
        points INTEGER
    )''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id',
                    (data['username'], data['password']))
        user_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"user_id": user_id, "username": data['username'], "points": 0}), 201
    except:
        return jsonify({"message": "Имя уже занято"}), 400
    finally:
        cur.close()
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, username, points FROM users WHERE username = %s AND password = %s',
                (data['username'], data['password']))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user:
        return jsonify({"user_id": user[0], "username": user[1], "points": user[2]})
    return jsonify({"message": "Неверные данные"}), 401

@app.route('/api/add_book', methods=['POST'])
def add_book():
    data = request.json
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"Оцени отзыв о книге от 10 до 50 баллов. Дай только цифру. Отзыв: {data['review']}"
    try:
        response = model.generate_content(prompt)
        points = int(''.join(filter(str.isdigit, response.text)))
    except:
        points = 15

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO books (user_id, title, author, review, points) VALUES (%s, %s, %s, %s, %s)',
                (data['user_id'], data['title'], data['author'], data['review'], points))
    cur.execute('UPDATE users SET points = points + %s WHERE id = %s RETURNING points', (points, data['user_id']))
    new_points = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"points_earned": points, "new_total": new_points})

@app.route('/api/my_books/<int:user_id>', methods=['GET'])
def get_my_books(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT title, author, points FROM books WHERE user_id = %s ORDER BY id DESC', (user_id,))
    books = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"title": b[0], "author": b[1], "points": b[2]} for b in books])

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT username, points FROM users ORDER BY points DESC LIMIT 10')
    leaders = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"username": l[0], "points": l[1]} for l in leaders])

if __name__ == '__main__':
    app.run()
