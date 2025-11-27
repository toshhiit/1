from flask import Flask, request, jsonify
import psycopg2
import os
from urllib.parse import urlparse
from flask_cors import CORS
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing!")

url = urlparse(DATABASE_URL)

conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
cursor = conn.cursor()

@app.post("/api/auth/verify")
def verify():
    data = request.get_json()
    token = data.get("token")

    cursor.execute("""
        SELECT users.id, users.username, auth_tokens.expires_at
        FROM auth_tokens
        JOIN users ON users.id = auth_tokens.user_id
        WHERE token=%s
    """, (token,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"success": False, "error": "invalid"})

    user_id, username, expires_at = row

    if datetime.utcnow() > expires_at:
        return jsonify({"success": False, "error": "expired"})

    session_id = str(uuid.uuid4())

    cursor.execute(
        "INSERT INTO sessions (user_id, session_id) VALUES (%s, %s)",
        (user_id, session_id)
    )
    conn.commit()

    return jsonify({"success": True, "username": username, "session": session_id})


@app.get("/api/user")
def get_user():
    session_id = request.args.get("session")

    cursor.execute("""
        SELECT users.username, users.tg_id
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.session_id=%s
    """, (session_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"success": False})

    username, tg_id = row
    return jsonify({"success": True, "username": username, "tg_id": tg_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
