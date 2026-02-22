import os
import random
import psycopg2
import cloudinary
import cloudinary.uploader

from flask import Flask, render_template, request, redirect
from flask_wtf import CSRFProtect
from psycopg2.pool import SimpleConnectionPool
from flask import url_for

# =========================
# Flask 설정
# =========================

app = Flask(__name__,
            static_folder='static',
            template_folder='templates')
app.secret_key = "super_secret_key"

app.config['WTF_CSRF_ENABLED'] = False
csrf = CSRFProtect(app)

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=DATABASE_URL
)

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET")
)


# =========================
# DB 연결
# =========================

def get_connection():
    try:
        return db_pool.getconn()
    except Exception as e:
        print("DB pool error:", e)
        return None

# =========================
# Hero 자동 선택 (페이지별 폴더 지원)
# =========================

def get_random_hero(page, fallback_url=None):

    hero_folder = os.path.join(app.static_folder, "hero", page)

    # 1순위: static/hero/page/
    if os.path.exists(hero_folder):

        files = [
            f for f in os.listdir(hero_folder)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        ]

        if files:
            selected = random.choice(files)

            # 중요: static/ 제거하고 반환
            return url_for('static', filename=f'hero/{page}/{selected}')

    # 2순위: fallback URL
    return fallback_url


# =========================
# HOME
# =========================

@app.route("/")
def home():
    try:
        hero_image = get_random_hero(
            "about",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?q=80&w=1600"
        )
    except Exception as e:
        print("get_random_hero error:", e)
        hero_image = "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?q=80&w=1600"

    try:
        return render_template(
            "index.html",
            hero_image=hero_image
        )
    except Exception as e:
        print("Template error:", e)
        return f"Template error: {e}"


# =========================
# ABOUT
# =========================

@app.route("/about")
def about():

    hero_image = get_random_hero(
        "about",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?q=80&w=1600"
    )

    conn = get_connection()
    if not conn:
        return render_template("about.html")

    cur = conn.cursor()

    cur.execute("SELECT id, image_url FROM portfolio ORDER BY id DESC")

    images = cur.fetchall()

    cur.close()
    db_pool.putconn(conn)

    return render_template(
        "about.html",
        images=images,
        hero_image=hero_image
    )


# =========================
# CONSTRUCTION
# =========================

@app.route("/construction")
def construction():

    hero_image = get_random_hero(
        "construction",
        "https://images.unsplash.com/photo-1600566752355-35792bedcfea?q=80&w=1600"
    )

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, image_url FROM portfolio ORDER BY id DESC")

    images = cur.fetchall()

    cur.close()
    db_pool.putconn(conn)

    return render_template(
        "construction.html",
        images=images,
        hero_image=hero_image
    )

# =========================
# PORTFOLIO (시공 사례 페이지)
# =========================

@app.route("/portfolio")
def portfolio():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, image_url, date, location, category, type
        FROM portfolio
        ORDER BY id DESC
    """)

    images = cur.fetchall()

    cur.close()
    db_pool.putconn(conn)

    return render_template(
        "portfolio.html",
        images=images,
        is_admin=False
    )

# =========================
# INQUIRIES (문의 목록 페이지)
# =========================

@app.route("/inquiries")
def inquiries():

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str)

    per_page = 10
    offset = (page - 1) * per_page

    conn = get_connection()
    cur = conn.cursor()

    # 검색 조건
    if search:
        cur.execute("""
            SELECT COUNT(*)
            FROM inquiries
            WHERE message ILIKE %s
        """, ("%" + search + "%",))
    else:
        cur.execute("SELECT COUNT(*) FROM inquiries")

    total = cur.fetchone()[0]

    total_pages = (total + per_page - 1) // per_page


    # 목록 조회
    if search:
        cur.execute("""
            SELECT id, name, phone, message, image, status, created_at
            FROM inquiries
            WHERE message ILIKE %s
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """, ("%" + search + "%", per_page, offset))
    else:
        cur.execute("""
            SELECT id, name, phone, message, image, status, created_at
            FROM inquiries
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))

    inquiries = cur.fetchall()

    cur.close()
    db_pool.putconn(conn)

    return render_template(
        "inquiries.html",
        inquiries=inquiries,
        page=page,
        total_pages=total_pages,
        search=search
    )

# =========================
# 문의 등록
# =========================

@app.route("/contact", methods=["POST"])
def contact():

    name = request.form.get("name")
    phone = request.form.get("phone")
    message = request.form.get("message")

    file = request.files.get("image")

    image_url = None

    if file and file.filename:

        result = cloudinary.uploader.upload(file)

        image_url = result["secure_url"]

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO inquiries (name, phone, message, image)
    VALUES (%s, %s, %s, %s)
    """,(name, phone, message, image_url))

    conn.commit()

    cur.close()
    db_pool.putconn(conn)

    return redirect("/")

@app.route("/debug_hero/<page>")
def debug_hero(page):
    import os

    hero_folder = f"static/hero/{page}"

    result = f"<h2>Checking hero folder: {hero_folder}</h2>"

    if os.path.exists(hero_folder):
        files = os.listdir(hero_folder)
        result += f"<p>Files found: {files}</p>"
    else:
        result += "<p>Folder does not exist</p>"

    return result

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    print("Starting Flask on port", port)

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )

