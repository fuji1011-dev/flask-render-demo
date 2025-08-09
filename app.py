from flask import Flask, render_template, request, redirect, url_for, session
import random
import statistics
import math
import os
import psycopg2

app = Flask(__name__)
app.secret_key = "秘密のキーをここに入れてください"  # セッションで必須

DATABASE_URL = "postgresql://domannaka_user:nZkwoEaGFeRw7USTWRjrRKEK0oCOmlWq@dpg-d2atllc9c44c73838msg-a.oregon-postgres.render.com:5432/domannaka"

def get_conn():
    return psycopg2.connect(DATABASE_URL)

questions = [
    "たまご10この値段は？",
    "最低限財布に入れておきたい金額は？",
    "自分の顔は何点？",
    "成人済みでお酒を全く飲まない人の割合は何%？",
    "スマホにインストールしているアプリの数は？",
    "スマホに保存されている写真の枚数は？",
    "最初に発売されたたまごっちの値段は？",
    "twitterで万バズした事がある人は何人に一人？",
    "茶碗一杯にご飯をよそったら米粒は何粒？",
    "車のタイヤは一回転で何センチ進む？",
]


def central_average(data, ratio=0.3):
    if not data:
        return None
    data_sorted = sorted(data)
    n = len(data_sorted)
    window_size = max(1, int(n * ratio))
    mid = n // 2
    start = max(0, mid - window_size // 2)
    end = start + window_size
    if end > n:
        end = n
        start = n - window_size
    window_data = data_sorted[start:end]
    return sum(window_data) / len(window_data)


@app.route("/")
def home():
    random_id = random.randint(0, len(questions) - 1)
    return redirect(url_for("question", qid=random_id))


@app.route("/question/<int:qid>", methods=["GET", "POST"])
def question(qid):
    if qid < 0 or qid >= len(questions):
        return "質問がありません", 404

    if request.method == "POST":
        price = request.form.get("price")
        if price and price.isdigit():
            conn = get_conn()
            c = conn.cursor()
            c.execute(
            """
            CREATE TABLE IF NOT EXISTS "Answers" (
                id SERIAL PRIMARY KEY,
                question_id INTEGER,
                price INTEGER
            )
            """
            )
            c.execute(
                'INSERT INTO "Answers" (question_id, price) VALUES (%s, %s)',
                (qid, int(price)),
            )
            conn.commit()
            conn.close()
            # セッションに回答済みフラグをセット
            session[f"answered_{qid}"] = True
            session[f"last_answer_{qid}"] = int(price)
        return redirect(url_for("question", qid=qid))


    # 回答済みかどうかを判定
    answered = session.get(f"answered_{qid}", False)
    your_answer = session.get(f"last_answer_{qid}", None)

    prices = []
    mode = median = mean = central_avg = "まだ回答がありません"
    score = None  # ここで初期化

    if answered:
        conn = get_conn()
        c = conn.cursor()
        c.execute('SELECT price FROM "Answers" WHERE question_id=%s', (qid,))
        rows = c.fetchall()
        conn.close()

        prices = [row[0] for row in rows]
        if prices:
            central_avg = round(central_average(prices), 2)
            
            if central_avg != 0:  # 0除算を防ぐ
                if your_answer > central_avg:
                   score = math.floor((central_avg / your_answer) * 100)
                else:
                    score = math.floor((your_answer / central_avg) * 100)
            

    return render_template(
        "index.html",
        question=questions[qid],
        central_avg=central_avg,
        qid=qid,
        max_qid=len(questions) - 1,
        answered=answered,
        your_answer=your_answer,
        score=score,
    )

if __name__ == "__main__":
    app.run(debug=True)
