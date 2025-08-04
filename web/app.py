from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import random
import statistics

app = Flask(__name__)
app.secret_key = "秘密のキーをここに入れてください"  # セッションで必須

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
    return redirect(url_for('question', qid=random_id))

@app.route("/question/<int:qid>", methods=["GET", "POST"])
def question(qid):
    if qid < 0 or qid >= len(questions):
        return "質問がありません", 404

    if request.method == "POST":
        price = request.form.get("price")
        if price and price.isdigit():
            conn = sqlite3.connect('data.db')
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS answers (id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER, price INTEGER)")
            c.execute("INSERT INTO answers (question_id, price) VALUES (?, ?)", (qid, int(price)))
            conn.commit()
            conn.close()
            # セッションに回答済みフラグをセット
            session[f'answered_{qid}'] = True
            session[f'last_answer_{qid}'] = int(price)
        return redirect(url_for('question', qid=qid))

    # 回答済みかどうかを判定
    answered = session.get(f'answered_{qid}', False)
    your_answer = session.get(f'last_answer_{qid}', None)

    prices = []
    mode = median = mean = central_avg = "まだ回答がありません"

    if answered:
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute("SELECT price FROM answers WHERE question_id=?", (qid,))
        rows = c.fetchall()
        conn.close()

        prices = [row[0] for row in rows]
        if prices:
            try:
                mode = statistics.mode(prices)
            except statistics.StatisticsError:
                mode = "複数あり"
            median = statistics.median(prices)
            mean = round(statistics.mean(prices), 2)
            central_avg = round(central_average(prices), 2)

    return render_template("index.html", 
                       question=questions[qid], 
                       mode=mode, 
                       median=median, 
                       mean=mean, 
                       central_avg=central_avg,
                       qid=qid, 
                       max_qid=len(questions) - 1,
                       answered=answered,
                       your_answer=your_answer)

