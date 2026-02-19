import os
import random
import psycopg2
import cloudinary
import cloudinary.uploader

from flask import Flask, render_template, request, redirect
from flask_wtf import CSRFProtect


# =========================
# Flask 설정
# =========================

app = Flask(__name__)
app.secret_key = "super_secret_key"

app.config['WTF_CSRF_ENABLED'] = False
csrf = CSRFProtect(app)

DATABASE_URL = os.getenv("DATABASE_URL")

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET")
)


# =========================
# DB 연결
# =========================

def get_connection():
    return psycopg2.connect(DATABASE_URL)


# =========================
# Hero 자동 선택 (페이지별 폴더 지원)
# =========================

def get_random_hero(page_folder, default_image):

    # 1순위: static/hero/page_folder/
    folder = os.path.join("static", "hero", page_folder)

    if os.path.exists(folder):

        files = [
            f for f in os.listdir(folder)
            if f.lower().endswith((".jpg",".jpeg",".png",".webp"))
        ]

        if files:
            return f"/static/hero/{page_folder}/" + random.choice(files)


    # 2순위: portfolio
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT image_url FROM portfolio")

    images = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()

    if images:
        return random.choice(images)


    # 3순위: 기본 이미지
    return default_image

# =========================
# HOME
# =========================

@app.route("/")
def home():

    hero_image = get_random_hero(
        "about",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?q=80&w=1600"
    )

    return render_template(
        "index.html",
        hero_image=hero_image
    )

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
    cur = conn.cursor()

    cur.execute("SELECT id, image_url FROM portfolio ORDER BY id DESC")

    images = cur.fetchall()

    cur.close()
    conn.close()

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
    conn.close()

    return render_template(
        "construction.html",
        images=images,
        hero_image=hero_image
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
    conn.close()

    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
