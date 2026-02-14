import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super_secret_key"

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# DB 연결 함수
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# 테이블 자동 생성
def create_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inquiries (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT,
            message TEXT,
            created_at TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

create_table()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/contact", methods=["POST"])
def contact():
    name = request.form["name"]
    phone = request.form["phone"]
    message = request.form["message"]
    now = datetime.now()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO inquiries (name, phone, message, created_at) VALUES (%s, %s, %s, %s)",
        (name, phone, message, now)
    )
    conn.commit()
    cur.close()
    conn.close()

    return "<h2>문의 접수 완료!</h2><a href='/'>돌아가기</a>"