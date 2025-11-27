from flask import Flask, request, jsonify
import psycopg2
from datetime import datetime
import uuid
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

conn = psycopg2.connect(
    host="localhost",
    database="mini_game_db",
    user="postgres",
    password="1234",
    port=5432
)
cursor = conn.cursor()

@app.post("/api/auth/verify")
def verify_token():
    data = request.get_json()
    token = data.get("token")

    cursor.execute("""
        SELECT users.id, users.username, auth_tokens.expires_at 
        FROM auth_tokens
        JOIN users ON users.id = auth_tokens.user_id
        WHERE token = %s
    """, (token,))
    
    row = cursor.fetchone()

    if not row:
        return jsonify({"success": False, "error": "invalid_token"})

    user_id, username, expires_at = row

    if datetime.now() > expires_at:
        return jsonify({"success": False, "error": "expired_token"})

    # session_id
    session_id = str(uuid.uuid4())

    cursor.execute("""
        INSERT INTO sessions (user_id, session_id)
        VALUES (%s, %s)
    """, (user_id, session_id))
    conn.commit()

    return jsonify({
        "success": True,
        "username": username,
        "session": session_id
    })


@app.get("/api/user")
def get_user():
    session_id = request.args.get("session")

    cursor.execute("""
        SELECT users.username, users.tg_id 
        FROM sessions
        JOIN users ON sessions.user_id = users.id
        WHERE sessions.session_id=%s
    """, (session_id,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"success": False})

    username, tg_id = user
    return jsonify({"success": True, "username": username, "tg_id": tg_id})


if __name__ == "__main__":
    app.run(port=5000)
