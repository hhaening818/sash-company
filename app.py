import time
import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session
from flask_wtf import CSRFProtect
from datetime import datetime
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET")
)


app = Flask(__name__)
app.secret_key = "super_secret_key"


csrf = CSRFProtect(app)

LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
LOCK_TIME = 300  # 5분 (초 단위)

DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
print("DATABASE_URL:", DATABASE_URL)
# DB 연결
def get_connection():
    return psycopg2.connect(DATABASE_URL)

# 테이블 자동 생성
def create_table():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS inquiries (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT,
            message TEXT,
            image TEXT,
            created_at TIMESTAMP
        )
    """)

    # 🔥 이미 테이블이 존재할 경우를 대비
    cur.execute("""
        ALTER TABLE inquiries
        ADD COLUMN IF NOT EXISTS image TEXT;
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

    file = request.files.get("image")
    image_url = None

    if file and file.filename != "":
         result = cloudinary.uploader.upload(file)
         image_url = result["secure_url"]


    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO inquiries (name, phone, message, image, created_at) VALUES (%s,%s,%s,%s,%s)",
        (name, phone, message, image_url, now)
    )

    conn.commit()
    cur.close()
    conn.close()

    return "<h2>문의 접수 완료!</h2><a href='/'>돌아가기</a>"


@app.route("/login", methods=["GET", "POST"])
def login():
    ip = request.remote_addr
    current_time = time.time()

    # 잠금 상태 확인
    if ip in LOGIN_ATTEMPTS:
        attempts, last_time = LOGIN_ATTEMPTS[ip]
        if attempts >= MAX_ATTEMPTS and current_time - last_time < LOCK_TIME:
            return render_template("login.html", error="5회 이상 실패. 5분 후 다시 시도하세요.")

    if request.method == "POST":
        password = request.form["password"]

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            LOGIN_ATTEMPTS.pop(ip, None)
            return redirect("/admin")
        else:
            if ip in LOGIN_ATTEMPTS:
                attempts, _ = LOGIN_ATTEMPTS[ip]
                LOGIN_ATTEMPTS[ip] = (attempts + 1, current_time)
            else:
                LOGIN_ATTEMPTS[ip] = (1, current_time)

            return render_template("login.html", error="비밀번호가 틀렸습니다.")

    return render_template("login.html", error=None)


@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()

    # 1️⃣ 문의 목록
    cur.execute("SELECT * FROM inquiries ORDER BY created_at DESC")
    rows = cur.fetchall()

    data = []
    for row in rows:
        row = list(row)
        if row[5]:
             try:
                 row[5] = row[5].strftime('%Y-%m-%d %H:%M')
             except:
                 row[5] = str(row[5])
        data.append(row)


    # 2️⃣ 오늘 문의 수
    today = datetime.now().date()
    cur.execute("""
        SELECT COUNT(*) FROM inquiries
        WHERE DATE(created_at) = %s
    """, (today,))
    today_count = cur.fetchone()[0]

    # 3️⃣ 월별 통계
    cur.execute("""
        SELECT TO_CHAR(created_at, 'YYYY-MM') AS month,
               COUNT(*)
        FROM inquiries
        GROUP BY month
        ORDER BY month
    """)
    results = cur.fetchall()

    months = [row[0] for row in results]
    counts = [row[1] for row in results]

    cur.close()
    conn.close()

    # 🔥 모든 변수 정의 후 render
    return render_template(
        "admin.html",
        inquiries=data,
        today_count=today_count,
        months=months,
        counts=counts
    )


@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):

    if not session.get("admin"):
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM inquiries WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")

import os

if __name__ == "__main__":
    app.run()

