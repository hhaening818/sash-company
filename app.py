import time
import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session
from flask_wtf import CSRFProtect
from datetime import datetime
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
from openpyxl import Workbook
from flask import send_file
import io
import requests
import json
import hmac
import hashlib
import time
import base64


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

    # 문의 테이블
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

    # portfolio 테이블 추가 ⭐⭐⭐
    cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id SERIAL PRIMARY KEY,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


create_table()

def send_sms(text):

    api_key = os.getenv("SMS_API_KEY")
    api_secret = os.getenv("SMS_API_SECRET")

    timestamp = str(int(time.time() * 1000))
    salt = os.urandom(16).hex()

    signature_data = timestamp + salt
    signature = hmac.new(
        api_secret.encode(),
        signature_data.encode(),
        hashlib.sha256
    ).digest()

    signature = base64.b64encode(signature).decode()

    headers = {
        "Authorization": f"HMAC-SHA256 apiKey={api_key}, date={timestamp}, salt={salt}, signature={signature}",
        "Content-Type": "application/json"
    }

    data = {
        "message": {
            "to": "010XXXXXXXX",  # 네 번호
            "from": "발신번호등록된번호",
            "text": text
        }
    }

    requests.post(
        "https://api.solapi.com/messages/v4/send",
        headers=headers,
        json=data
    )


@app.route("/")
def home():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT image_url FROM portfolio
        ORDER BY id DESC
    """)

    images = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()

    return render_template("index.html", images=images)


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
    
    send_sms(f"""
    [새 문의 접수]
    이름: {name}
    전화: {phone}
    내용: {message}
    """)


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

    # 문의 목록
    cur.execute("SELECT * FROM inquiries ORDER BY created_at DESC")
    rows = cur.fetchall()

    print(rows[:4])

    data = []
    for row in rows:
        row = list(row)
        if row[4]:
             try:
                 row[4] = row[4].strftime('%Y년 %m월 %d일 %H:%M')
             except:
                 row[4] = str(row[4])
        data.append(row)


    # 오늘 문의 수
    today = datetime.now().date()
    cur.execute("""
        SELECT COUNT(*) FROM inquiries
        WHERE DATE(created_at) = %s
    """, (today,))
    today_count = cur.fetchone()[0]

    # 전체 문의 수 추가
    cur.execute("SELECT COUNT(*) FROM inquiries")
    total_count = cur.fetchone()[0]

    # 이번달 문의 수
    cur.execute("""
    SELECT COUNT(*) FROM inquiries
    WHERE DATE_TRUNC('month', created_at) =
         DATE_TRUNC('month', CURRENT_DATE)
    """)
    month_count = cur.fetchone()[0]

    # 사진 포함 문의 수
    cur.execute("""
    SELECT COUNT(*) FROM inquiries
    WHERE image IS NOT NULL AND image != ''
    """)
    image_count = cur.fetchone()[0]

    # 월별 통계
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
        total_count=total_count,
        month_count=month_count,
        image_count=image_count,
        months=months,
        counts=counts
    )

@app.route("/admin/upload_portfolio", methods=["POST"])
def upload_portfolio():

    if not session.get("admin"):
        return redirect("/login")

    file = request.files.get("image")

    if file and file.filename != "":

        # Cloudinary 업로드
        result = cloudinary.uploader.upload(file)

        image_url = result["secure_url"]

        # DB 저장
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO portfolio (image_url) VALUES (%s)",
            (image_url,)
        )

        conn.commit()
        cur.close()
        conn.close()

    return redirect("/admin")


@app.route("/export")
def export_excel():

    if not session.get("admin"):
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, phone, message, created_at FROM inquiries ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "문의 목록"

    # 헤더
    ws.append(["이름", "전화번호", "내용", "접수시간"])

    # 데이터
    for row in rows:
        ws.append(row)

    # 메모리 파일 생성
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name="문의목록.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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

