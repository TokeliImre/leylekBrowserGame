from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, session, send_from_directory
import time
import sqlite3

app = Flask(__name__)
app.secret_key = "gizli_anahtar"  # session için gerekli

# Ana sayfa
@app.route("/")
def index():
    # Kullanıcı giriş yapmadıysa login sayfasına yönlendir
    if "user" not in session:
        return redirect(url_for("login"))

    # DB bağlantısı (örnek, veri çekebilirsin)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    current_user = session["user"]  # oturumdaki kullanıcı bilgisi

    return render_template("index.html", user=current_user)

# Login sayfası
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Kullanıcıyı veritabanında kontrol et
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM login WHERE username = ?", (username,)).fetchone()
        conn.close()
        if not user:
            flash("Kullanıcı adı bulunamadı!")
            return redirect(url_for("login"))
        
        if password.strip() != user[2].strip():  # boşlukları kaldır
            flash("Yanlış şifre!")
            return redirect(url_for("login"))

        session["user"] = user[1]  # session kaydet
        flash("Başarıyla giriş yapıldı!")
        return redirect(url_for("index"))
        
    return render_template("login.html")


@app.route("/register",methods=["GET", "POST"])
def register():
    session.clear()  # session temizle
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO login (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        flash("Kayıt başarılı! Giriş yapabilirsiniz.")
        return redirect(url_for("login"))
    return render_template("register.html")
        

@app.route("/logout",methods=["GET", "POST"]) 
def logout():
    session.clear()  # session temizle
    flash("Başarıyla çıkış yapıldı!")
    return redirect(url_for("login"))  




@app.route("/scores",methods=["GET", "POST"])
def scores():
    if "user" not in session:
        return redirect(url_for("login"))
    current_user = session["user"]
    conn = sqlite3.connect("database.db", timeout=10)
    cursor = conn.cursor()
    topScores = cursor.execute("SELECT username, score, timestamp FROM scores ORDER BY score DESC Limit 10").fetchall()
    conn.close()
    return render_template("scores.html", user=current_user, topScores=topScores)


@app.route('/game')
def serve_game():
    if "user" not in session:
        flash("Oyunu oynamak için önce giriş yapmalısınız.", "info")
        return redirect(url_for("login"))
        
    
    return render_template("game.html")

@app.route('/submit_score', methods=['POST'])
def submit_score():
    if "user" not in session:
        return jsonify({"success": False, "message": "Giriş yapılmamış."}), 401

    try:
        # JSON alınması (Content-Type bazen eksik olursa hata olmaması için)
        data = request.get_json(silent=True) or {}
        print("submit_score received JSON:", data, "session user:", session.get("user"))

        if 'gamePoint' in data:
            score = data['gamePoint']
        elif 'score' in data:
            score = data['score']
        else:
            score = None

        try:
            score = int(score)
        except (TypeError, ValueError):
            print("submit_score: invalid score:", score)
            return jsonify({"success": False, "message": "Geçersiz skor formatı."}), 400

        # hızlı duplicate koruması (session)
        last_time = session.get('last_submit_time', 0)
        last_score = session.get('last_submit_score', None)
        now = time.time()
        if last_score == score and (now - last_time) < 3.0:
            print(f"submit_score: duplicate ignored (session) for user {session.get('user')} score {score}")
            return jsonify({"success": True, "message": "Duplicate ignored."})

        username = session['user']

        # DB bağlantısı
        conn = sqlite3.connect("database.db", timeout=10)
        cursor = conn.cursor()

        # DB'den son kayıt kontrolü (mevcut şema ile uyumlu)
        try:
            cursor.execute("SELECT score FROM scores WHERE username = ? ORDER BY rowid DESC LIMIT 1", (username,))
            last_db = cursor.fetchone()
            if last_db is not None and last_db[0] == score:
                # opsiyonel: session zamanını güncelle, tekrar gönderimleri engelle
                session['last_submit_time'] = now
                session['last_submit_score'] = score
                session['last_score'] = score
                conn.close()
                print(f"submit_score: duplicate ignored (db) for user {username} score {score}")
                return jsonify({"success": True, "message": "Duplicate ignored (db)."})
        except sqlite3.Error as e:
            # DB'de tablo yoksa veya hata varsa devam etmeye çalış (hata logla)
            print("submit_score: DB select last error:", e)

        # kayıt yap
        cursor.execute("INSERT INTO scores (username, score) VALUES (?, ?)", (username, score))
        conn.commit()
        conn.close()

        # session'a kayıt zamanı ve değerini kaydet
        session['last_submit_time'] = now
        session['last_submit_score'] = score
        session['last_score'] = score

        print(f"submit_score: saved score {score} for user {username}")
        return jsonify({"success": True, "message": "Skor kaydedildi."})

    except Exception as e:
        print("submit_score exception:", e)
        return jsonify({"success": False, "message": "Sunucu hatası."}), 500



@app.route("/profile",methods=["GET", "POST"]) 
def profile():
    if "user" not in session:
        return redirect(url_for("login"))
    current_user = session["user"]
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    tenScores=cursor.execute("SELECT * FROM scores WHERE username = ? ORDER BY score DESC Limit 10", (current_user,)).fetchall()
    conn.close()

    # tek gösterimlik: oku ve session'dan sil
    last_score = session.pop("last_score", None)

    return render_template("profile.html", user=current_user, last_score=last_score, tenScores=tenScores)


@app.route("/aboutMe",methods=["GET", "POST"]) 
def aboutMe():
    if "user" not in session:
        return redirect(url_for("login"))
    current_user = session["user"]
    return render_template("aboutMe.html", user=current_user)

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
