import time
import os
import psycopg2
import bcrypt
from flask import Flask, render_template, request, redirect, url_for, session
from flask_wtf import CSRFProtect
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
from flask import jsonify
from datetime import datetime, timedelta, timezone
import psycopg2.extras
import random
try:
    from coolsms import Message
except:
    Message = None

SMS_API_KEY = "여기 API KEY"
SMS_API_SECRET = "여기 SECRET"
SMS_SENDER = "등록된 발신번호"

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET")
)

app = Flask(__name__)
app.secret_key = "super_secret_key"

verification_codes = {}

app.config['WTF_CSRF_ENABLED'] = False

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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 기본 테이블 생성
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inquiries (
         id SERIAL PRIMARY KEY,
         name TEXT,
         phone TEXT,
         message TEXT,
         image TEXT,
         status TEXT DEFAULT '대기',
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 답변 컬럼
    cur.execute("""
    ALTER TABLE inquiries
    ADD COLUMN IF NOT EXISTS reply TEXT
    """)

    # ⭐ 파일 URL 컬럼 (여기에 추가)
    cur.execute("""
    ALTER TABLE inquiries
    ADD COLUMN IF NOT EXISTS reply_file_url TEXT
    """)

    # 조회수 컬럼
    cur.execute("""
    ALTER TABLE inquiries
    ADD COLUMN IF NOT EXISTS views INTEGER DEFAULT 0
    """)

    # 사용자 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # inquiry_replies 테이블 추가 (conn 닫기 전에!)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inquiry_replies (

        id SERIAL PRIMARY KEY,

        inquiry_id INTEGER REFERENCES inquiries(id) ON DELETE CASCADE,

        reply TEXT,

        file TEXT,

        is_selected BOOLEAN DEFAULT FALSE,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # portfolio 테이블 생성
    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id SERIAL PRIMARY KEY,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        phone TEXT UNIQUE,
        name TEXT,
        ssn TEXT,
        username TEXT UNIQUE,
        password TEXT,
        region TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)    

    conn.commit()
    cur.close()
    conn.close()

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

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["POST"])
def contact():

    name = request.form.get("name")
    phone = request.form.get("phone")
    message = request.form.get("message")

    file = request.files.get("image")

    image_url = None   # ✅ 먼저 None으로 초기화

    # 파일 있는 경우만 업로드
    if file and file.filename != "":
        result = cloudinary.uploader.upload(file)
        image_url = result["secure_url"]

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO inquiries (name, phone, message, image, created_at)
    VALUES (%s, %s, %s, %s, NOW())
    """,(name, phone, message, image_url))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/inquiry")

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
        # created_at 포맷 변환 (index 6)
        # created_at 포맷 변환 (index 4)
        if row[4]:
            try:
                kst_time = row[4] + timedelta(hours=9)
                row[4] = kst_time.strftime('%Y-%m-%d %H:%M')
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

@app.route("/inquiry")
def inquiry_list():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM inquiries
        ORDER BY created_at DESC
    """)

    inquiries = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("inquiry.html", inquiries=inquiries)

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
    session.pop("user", None)

    return redirect("/")

import os


@app.route("/portfolio")
def portfolio():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, image_url
        FROM portfolio
        ORDER BY id DESC
    """)

    images = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "portfolio.html",
        images=images,
        is_admin=session.get("admin")
    )

@app.route("/admin/upload_portfolio", methods=["POST"])
def upload_portfolio():

    if not session.get("admin"):
        return redirect("/login")

    files = request.files.getlist("image")

    conn = get_connection()
    cur = conn.cursor()

    for file in files:

        if file and file.filename != "":

            result = cloudinary.uploader.upload(file)

            image_url = result["secure_url"]

            cur.execute(
                "INSERT INTO portfolio (image_url) VALUES (%s)",
                (image_url,)
            )

    conn.commit()
    cur.close()
    conn.close()

    return "OK"

@app.route("/admin/update_status/<int:id>", methods=["POST"])
def update_status(id):

    if not session.get("admin"):
        return redirect("/login")

    status = request.form.get("status")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE inquiries
        SET status = %s
        WHERE id = %s
    """, (status, id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")

@app.route("/admin/reply/<int:id>", methods=["POST"])
def reply(id):

    if not session.get("admin"):
        return redirect("/login")

    reply = request.form.get("reply")
    file = request.files.get("reply_file")

    conn = get_connection()
    cur = conn.cursor()

    file_url = None

    # 파일 업로드
    if file and file.filename != "":
        result = cloudinary.uploader.upload(
            file,
            resource_type="auto"
        )
        file_url = result["secure_url"]

    # 기존 대표 답변 해제
    cur.execute("""
        UPDATE inquiry_replies
        SET is_selected = FALSE
        WHERE inquiry_id = %s
    """, (id,))

    # 새 답변 히스토리 저장
    cur.execute("""
        INSERT INTO inquiry_replies
        (inquiry_id, reply, file, is_selected)
        VALUES (%s, %s, %s, TRUE)
    """, (id, reply, file_url))

    # inquiries 테이블 대표 답변 업데이트
    cur.execute("""
        UPDATE inquiries
        SET reply=%s,
            reply_file_url=%s,
            status='완료'
        WHERE id=%s
    """,(reply, file_url, id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")

@app.route("/inquiry/<int:id>")
def inquiry_detail(id):

    conn = get_connection()
    cur = conn.cursor()

    # 먼저 데이터 가져오기
    cur.execute("""
        SELECT *
        FROM inquiries
        WHERE id=%s
    """,(id,))

    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return "존재하지 않는 문의입니다.", 404

    # 조회수 증가 (존재할 때만)
    cur.execute("""
        UPDATE inquiries
        SET views = views + 1
        WHERE id=%s
    """,(id,))

    inquiry = list(row)

    # 날짜 처리
    created_at = inquiry[6]

    if created_at:
        try:
            created_at = created_at + timedelta(hours=9)
            inquiry[6] = created_at.strftime('%Y-%m-%d %H:%M')
        except:
            inquiry[6] = str(created_at)[:16]

    conn.commit()
    cur.close()
    conn.close()

    return render_template(
        "inquiry_detail.html",
        inquiry=inquiry
    )

@app.route("/search_inquiry", methods=["POST"])
def search_inquiry():

    data = request.get_json()

    name = data.get("name")
    phone = data.get("phone")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT message, status, created_at, reply, reply_file_url
    FROM inquiries
    WHERE name=%s AND phone=%s
    ORDER BY created_at DESC
    LIMIT 1
    """,(name,phone))

    rows = cur.fetchall()

    result=[]

    for r in rows:

        created_at = (
             (r[2] + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
             if r[2] else "시간 없음"
        )

        file_url = r[4]

        # Cloudinary 압축 URL 생성
        if file_url and "cloudinary.com" in file_url:
            file_url = file_url.replace(
                "/upload/",
                "/upload/f_auto,q_auto,w_1200/"
            )

        result.append({
            "message": r[0],
            "status": r[1],
            "created_at": created_at,
            "reply": r[3],
            "file": file_url
        })

    cur.close()
    conn.close()

    return jsonify(result)

@app.route("/user_login", methods=["GET","POST"])
def user_login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        SELECT * FROM users
        WHERE username=%s
        """,(username,))

        user = cur.fetchone()

        if user and bcrypt.checkpw(
            password.encode(),
            user[2].encode()
        ):
            session["user"] = username
            return redirect("/")
        else:
            return render_template(
                "user_login.html",
                error="아이디 또는 비밀번호 틀림"
            )

    return render_template("user_login.html", error=None)

@app.route("/admin/replies/<int:inquiry_id>")
def get_replies(inquiry_id):

    if not session.get("admin"):
        return jsonify([])

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, reply, file, is_selected, created_at
        FROM inquiry_replies
        WHERE inquiry_id=%s
        ORDER BY created_at DESC
    """,(inquiry_id,))

    rows = cur.fetchall()

    result = []

    for r in rows:

        created_at = (
            (r[4] + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
            if r[4] else ""
        )

        result.append({
            "id": r[0],
            "reply": r[1],
            "file": r[2],
            "is_selected": r[3],
            "created_at": created_at
        })

    cur.close()
    conn.close()

    return jsonify(result)

@app.route("/admin/select_reply/<int:reply_id>/<int:inquiry_id>", methods=["POST"])
def select_reply(reply_id, inquiry_id):

    if not session.get("admin"):
        return jsonify({"success":False})

    conn = get_connection()
    cur = conn.cursor()

    # 기존 해제
    cur.execute("""
        UPDATE inquiry_replies
        SET is_selected=FALSE
        WHERE inquiry_id=%s
    """,(inquiry_id,))

    # 선택
    cur.execute("""
        UPDATE inquiry_replies
        SET is_selected=TRUE
        WHERE id=%s
    """,(reply_id,))

    # inquiries도 업데이트
    cur.execute("""
        SELECT reply, file
        FROM inquiry_replies
        WHERE id=%s
    """,(reply_id,))

    row = cur.fetchone()

    if row:
        cur.execute("""
            UPDATE inquiries
            SET reply=%s,
                reply_file_url=%s
            WHERE id=%s
        """,(row[0], row[1], inquiry_id))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success":True})

@app.route("/inquiries")
def inquiries():

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str)

    per_page = 10
    offset = (page - 1) * per_page

    conn = get_connection()
    cur = conn.cursor()

    if search:

        cur.execute("""
            SELECT COUNT(*)
            FROM inquiries
            WHERE message ILIKE %s
        """, (f"%{search}%",))

        total = cur.fetchone()[0]

        cur.execute("""
            SELECT *
            FROM inquiries
            WHERE message ILIKE %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (f"%{search}%", per_page, offset))

    else:

        cur.execute("SELECT COUNT(*) FROM inquiries")
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT *
            FROM inquiries
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))

    inquiries = cur.fetchall()

    cur.close()
    conn.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "inquiries.html",
        inquiries=inquiries,
        page=page,
        total_pages=total_pages,
        search=search
    )

@app.route("/send_sms", methods=["POST"])
def send_sms():

    phone = request.json.get("phone")

    code = str(random.randint(100000,999999))

    verification_codes[phone] = code

    message = Message(SMS_API_KEY, SMS_API_SECRET)

    message.send({
        "to": phone,
        "from": SMS_SENDER,
        "text": f"인증번호: {code}"
    })

    return {"status":"ok"}

@app.route("/verify_sms", methods=["POST"])
def verify_sms():

    phone = request.json.get("phone")
    code = request.json.get("code")

    if verification_codes.get(phone) == code:

        session["verified_phone"] = phone

        return {"status":"ok"}

    return {"status":"fail"}

@app.route("/register", methods=["POST"])
def register():

    data=request.json

    phone=data["phone"]
    name=data["name"]
    ssn=data["ssn"]
    username=data["username"]
    password=data["password"]
    region=data["region"]

    hashed=bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt()
    ).decode()

    conn=get_connection()
    cur=conn.cursor()

    cur.execute("""
    INSERT INTO users
    (phone,name,ssn,username,password,region)
    VALUES (%s,%s,%s,%s,%s,%s)
    """,(phone,name,ssn,username,hashed,region))

    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"status":"ok"})

port = int(os.environ.get("PORT", 10000))

if __name__ == "__main__":
    with app.app_context():
        print("Initializing database...")
        create_table()

    print("Flask starting on port", port)
    app.run(host="0.0.0.0", port=port)

