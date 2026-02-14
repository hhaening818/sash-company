from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sash_secret_key_1234"   # 로그인 암호키 (아무 문자열 가능)

FILE_NAME = "문의목록.txt"
ADMIN_PASSWORD = "1234"   # ★ 여기 비밀번호 바꾸면 됨


# 메인 페이지
@app.route("/")
def home():
    return render_template("index.html")


# 문의 접수
@app.route("/contact", methods=["POST"])
def contact():
    name = request.form["name"]
    phone = request.form["phone"]
    message = request.form["message"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(FILE_NAME, "a", encoding="utf-8") as f:
        f.write(f"{now}|{name}|{phone}|{message}\n")

    return "<h2>문의 접수 완료!</h2><a href='/'>돌아가기</a>"


# 로그인 페이지
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form["password"]

        if pw == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        else:
            return "<h3>비밀번호 틀림!</h3><a href='/login'>다시 시도</a>"

    return render_template("login.html")


# 로그아웃
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")


# 관리자 페이지
@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/login")

    inquiries = []

    try:
        with open(FILE_NAME, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f.readlines()):
                date, name, phone, message = line.strip().split("|")
                inquiries.append({
                    "id": idx,
                    "date": date,
                    "name": name,
                    "phone": phone,
                    "message": message
                })
    except:
        pass

    return render_template("admin.html", inquiries=inquiries)


# 삭제
@app.route("/delete/<int:idx>")
def delete(idx):
    if not session.get("admin"):
        return redirect("/login")

    with open(FILE_NAME, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(FILE_NAME, "w", encoding="utf-8") as f:
        for i, line in enumerate(lines):
            if i != idx:
                f.write(line)

    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)