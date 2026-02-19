import os
import io
import time
import json
import hmac
import base64
import bcrypt
import random
import hashlib
import requests
import psycopg2
import psycopg2.extras
import cloudinary
import cloudinary.uploader

from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect,
    session, jsonify, send_file
)
from flask_wtf import CSRFProtect
from openpyxl import Workbook


# =========================
# Flask 설정
# =========================

app = Flask(__name__)
app.secret_key = "super_secret_key"

app.config['WTF_CSRF_ENABLED'] = False
csrf = CSRFProtect(app)

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

verification_codes = {}

# =========================
# Cloudinary 설정
# =========================

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
# Hero 이미지 자동 선택 함수 (핵심)
# =========================

def get_random_hero(default_image):

    # 1순위: portfolio
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT image_url FROM portfolio")

    portfolio_images = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()

    if portfolio_images:
        return random.choice(portfolio_images)


    # 2순위: static/hero 폴더
    hero_folder = os.path.join("static", "hero")

    if os.path.exists(hero_folder):

        files = [
            f for f in os.listdir(hero_folder)
            if f.lower().endswith((".jpg",".jpeg",".png",".webp"))
        ]

        if files:
            return "/static/hero/" + random.choice(files)


    # 3순위: 기본 이미지
    return default_image


# =========================
# 테이블 생성
# =========================

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
        status TEXT DEFAULT '대기',
        reply TEXT,
        reply_file_url TEXT,
        views INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id SERIAL PRIMARY KEY,
        image_url TEXT,
        date DATE,
        location TEXT,
        category TEXT,
        type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()


with app.app_context():
    create_table()


# =========================
# HOME
# =========================

@app.route("/")
def home():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT image_url FROM portfolio ORDER BY id DESC")

    images = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()

    return render_template("index.html", images=images)


# =========================
# ABOUT (hero 자동 랜덤)
# =========================

@app.route("/about")
def about():

    hero_image = get_random_hero(
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
# CONSTRUCTION (hero 자동 랜덤)
# =========================

@app.route("/construction")
def construction():

    hero_image = get_random_hero(
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
