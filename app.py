from datetime import datetime
from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, session, send_from_directory
import time
from pymongo import MongoClient
import json 
import os



app = Flask(__name__)
app.secret_key = "gizli_anahtar"  # session için gerekli

client = MongoClient(os.getenv("MONGO_URI"))
db = client["database"]  # kendi veritabanı adını yaz
users_collection = db["login"]
scores_collection = db["scores"]



# Ana sayfa
@app.route("/")
def index():
    # Kullanıcı giriş yapmadıysa login sayfasına yönlendir
    if "user" not in session:
        flash("Giriş yapmalısınız.", "info")
        return redirect(url_for("login"))

    current_user_username = session["user"]  # oturumdaki kullanıcı adı

    # Not: Bu kısımda SQLite3 veri çekme kısmı kaldırılmıştır.
    # Eğer ana sayfada tüm kullanıcıları göstermek istiyorsanız (Genellikle güvenlik riski taşır!)
    # users = users_collection.find()
    # return render_template("index.html", user=current_user_username, users=users)
    
    return render_template("index.html", user=current_user_username)

# Login sayfası
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # MongoDB'de kullanıcı adı VE şifre eşleşmesini kontrol et (DİKKAT: Gerçek uygulamada şifre HASH'lenmelidir!)
        # user = users_collection.find_one({"username": username, "password": password})
        
        # Önce kullanıcıyı bulalım, sonra şifreyi kontrol edelim (Daha iyi hata mesajı için)
        user = users_collection.find_one({"username": username})
        

        if not user:
            flash("Username or Password is wrong !", "danger")
            return redirect(url_for("login"))
        
        # Şifre kontrolü (Şifrelerin düz metin olarak saklanması güvensizdir! Sadece örnek amaçlı)
        # MongoDB'de user["password"] olarak tuttuğunuz varsayılmıştır.
        if password != user.get("password"):
            flash("Username or Password is wrong", "danger")
            return redirect(url_for("login"))

        # Kullanıcı adını oturuma kaydet (ID'sini kaydetmek daha güvenlidir)
        session["user"] = user["username"]
        flash(f"You are successfully logged in as {user['username']}!", "success")
        return redirect(url_for("index"))
        
    return render_template("login.html")


@app.route("/register",methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password") # Yeni alan

        # 0. Şifreler Eşleşiyor mu Kontrolü
        if password != confirm_password:
            flash("Şifreler eşleşmiyor. Lütfen tekrar kontrol edin.", "danger")
            return redirect(url_for("register"))

        # 1. Kullanıcının zaten var olup olmadığını kontrol et
        existing_user = users_collection.find_one({"username": username})
        if existing_user:
            flash("Bu kullanıcı adı zaten alınmış. Lütfen başka bir tane deneyin.", "warning")
            return redirect(url_for("register"))

        # 2. Yeni kullanıcıyı MongoDB'ye ekle
        # DİKKAT: Gerçek uygulamada şifre HASH'lenmelidir! (örneğin bcrypt ile)
        new_user = {
            "username": username,
            "password": password,
            "created_at": time.time() # time.time() yerine datetime.datetime.utcnow() kullanmak önerilir
        }
        
        try:
            users_collection.insert_one(new_user)
            flash("Kayıt başarılı! Şimdi giriş yapabilirsiniz.", "success")
            return redirect(url_for("login"))
        except Exception as e:
             flash(f"Kayıt sırasında bir hata oluştu: {e}", "danger")
             return redirect(url_for("register"))

    return render_template("register.html")

        

@app.route("/logout",methods=["GET", "POST"]) 
def logout():
    session.clear()  # session temizle
    flash("Başarıyla çıkış yapıldı!")
    return redirect(url_for("login"))  




@app.route("/scores", methods=["GET", "POST"]) # POST metodu orijinal haliyle bırakıldı
def scores():
    if "user" not in session:
        return redirect(url_for("login"))
        
    current_user = session["user"]
    # SQLite'daki 'topScores' değişken adını koruyoruz.
    topScores = [] 
    
    try:
        # MongoDB karşılığı: find().sort("score", -1).limit(10)
        
        
        topScores = list(
            scores_collection.find({}, 
                # Projeksiyon (Sadece username ve score alanlarını al, _id'yi hariç tut)
                {"username": 1, "score": 1,"Timestamp": 1, "_id": 0} 
            )
            .sort("score", -1) # Azalan sırada sırala
            .limit(10)          # İlk 10 kaydı al
        )
        
    except Exception as e:
        # Eğer bir hata olursa, konsola yazdır ve kullanıcıya bildir
        print(f"MongoDB Skor çekme hatası: {e}")
        flash("Skorlar veritabanından çekilirken bir hata oluştu. Konsolu kontrol edin.", "danger")
        # Hata durumunda 'topScores' boş kalır
        
    # SQLite'da fetchall() bir tuple listesi döndürürken, 
    # MongoDB bir dictionary listesi döndürür. Şablon (scores.html) bunu okumalıdır.
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
        # JSON alınması
        data = request.get_json(silent=True) or {}
        print("submit_score received JSON:", data, "session user:", session.get("user"))

        # Skor değerini 'gamePoint' veya 'score' anahtarından al
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

        # Hızlı duplicate koruması (Session)
        last_time = session.get('last_submit_time', 0)
        last_score = session.get('last_submit_score', None)
        now = time.time()
        if last_score == score and (now - last_time) < 3.0:
            print(f"submit_score: duplicate ignored (session) for user {session.get('user')} score {score}")
            return jsonify({"success": True, "message": "Duplicate ignored."})

        username = session['user']

        # DB'den son kayıt kontrolü (MongoDB)
        try:
            # Kullanıcının son skorunu çek
            last_db_score_doc = scores_collection.find_one(
                {"username": username},
                sort=[("Timestamp", -1)] # En son kayıt için, skorlar Timestamp'e göre sıralanır (varsayılan olarak)
            )
            
            # Eğer son skor mevcut ve gelen skor ile aynıysa duplicate sayılır
            if last_db_score_doc and last_db_score_doc.get('score') == score:
                session['last_submit_time'] = now
                session['last_submit_score'] = score
                session['last_score'] = score
                print(f"submit_score: duplicate ignored (db) for user {username} score {score}")
                return jsonify({"success": True, "message": "Duplicate ignored (db)."})
        
        except Exception as e:
            print("submit_score: DB select last error:", e)
            # Hata varsa, yine de kaydetmeye devam etmeye çalış

        # Yeni skor belgesini oluştur ve kaydet
        score_document = {
            "username": username,
            "score": score,
            "Timestamp": now # MongoDB'de Timestamp (Büyük T) kullanıldığı varsayılmıştır.
        }
        
        scores_collection.insert_one(score_document)

        # Session'a kayıt zamanı ve değerini kaydet
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
    tenScores = []
    
    try:
        # Kullanıcının en iyi 10 skorunu çek (MongoDB)
        tenScores = list(
            scores_collection.find(
                {"username": current_user},
                {"username": 1, "score": 1, "Timestamp": 1, "_id": 0} 
            )
            .sort("score", -1) # Skora göre azalan sırada sırala
            .limit(10)          # İlk 10 kaydı al
        )
    except Exception as e:
        print(f"Profile skor çekme hatası: {e}")
        flash("Profil skorları veritabanından çekilirken bir hata oluştu.", "danger")


    # tek gösterimlik: oku ve session'dan sil
    last_score = session.pop("last_score", None)

    # tenScores (dictionary listesi) ve last_score'u şablona gönder
    return render_template("profile.html", user=current_user, last_score=last_score, tenScores=tenScores)





@app.route("/aboutMe",methods=["GET", "POST"]) 
def aboutMe():
    if "user" not in session:
        return redirect(url_for("login"))
    current_user = session["user"]
    return render_template("aboutMe.html", user=current_user)





@app.template_filter()
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    # ...
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).strftime(format)
    # ...





if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
