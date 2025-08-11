from flask import Flask, render_template, request, redirect, url_for, session, flash
import random
import math
import psycopg2
from livereload import Server

app = Flask(__name__)
app.secret_key = "秘密のキーをここに入れてください"
app.config["TEMPLATES_AUTO_RELOAD"] = True

DATABASE_URL = "postgresql://domannaka_user:nZkwoEaGFeRw7USTWRjrRKEK0oCOmlWq@dpg-d2atllc9c44c73838msg-a.oregon-postgres.render.com:5432/domannaka"

questions_cache = []  # グローバルキャッシュ
answers_cache = {}  

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def load_questions():
    global questions_cache
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute('SELECT id, question FROM "Questions" WHERE is_active = TRUE LIMIT 5')
            questions_cache = c.fetchall()

def load_answers():
    global answers_cache
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute('SELECT question_id, answer FROM "Answers"')
            rows = c.fetchall()
    temp = {}
    for qid, ans in rows:
        temp.setdefault(qid, []).append(ans)
    answers_cache = temp
    
initialized = False

@app.before_request
def before_request():
    global initialized
    if not initialized:
        load_questions()
        load_answers()
        initialized = True
        
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
def index():
    # ゲームスタート用のページを表示
    return render_template("index.html") 

@app.route("/game")
def game():
    session.clear()  # セッションのすべてのデータを削除

    keys_to_clear = [key for key in session.keys() if key.startswith("answered_") or key.startswith("last_answer_") or key.startswith("score_")]
    for key in keys_to_clear:
        session.pop(key, None)
        
    if not questions_cache:
        return "お題がありません", 404

    random_id = random.choice([q[0] for q in questions_cache])
    return redirect(url_for("question", qid=random_id))

@app.route("/question/<int:qid>", methods=["GET", "POST"])
def question(qid):
    question_row = next((q for q in questions_cache if q[0] == qid), None)
    if not question_row:
        return "質問がありません", 404
    question_text = question_row[1]

    if request.method == "POST":
        price = request.form.get("price")
        if price and price.isdigit():
            your_answer_int = int(price)
            with get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        'INSERT INTO "Answers" (question_id, answer) VALUES (%s, %s)',
                        (qid, your_answer_int),
                    )
                conn.commit()
            
            answered_list = session.get("answered_questions", [])
            if qid not in answered_list:
                answered_list.append(qid)
            session["answered_questions"] = answered_list

            answers_cache.setdefault(qid, []).append(your_answer_int)

            session[f"answered_{qid}"] = True
            session[f"last_answer_{qid}"] = your_answer_int

            prices = answers_cache.get(qid, [])
            central_avg_val = math.floor(central_average(prices)) if prices else None
            if central_avg_val and central_avg_val != 0:
                if your_answer_int > central_avg_val:
                    score = math.floor((central_avg_val / your_answer_int) * 100)
                else:
                    score = math.floor((your_answer_int / central_avg_val) * 100)
            else:
                score = 0
            session[f"score_{qid}"] = score

    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute('SELECT answer FROM "Answers" WHERE question_id=%s LIMIT 20', (qid,))
            rows = c.fetchall()
    all_answers = [row[0] for row in rows]

    answered = session.get(f"answered_{qid}", False)
    your_answer = session.get(f"last_answer_{qid}", None)

    prices = []
    central_avg = "まだ回答がありません"
    score = None

    if answered:
        prices = answers_cache.get(qid, [])
        if prices:
            central_avg = math.floor(central_average(prices))
            if central_avg != 0:
                if your_answer > central_avg:
                    score = math.floor((central_avg / your_answer) * 100)
                else:
                    score = math.floor((your_answer / central_avg) * 100)

    unanswered = [q[0] for q in questions_cache if q[0] not in session.get("answered_questions", [])]
    all_answered = len(unanswered) == 0
    next_qid = random.choice(unanswered) if not all_answered else None

    answered_count = len(session.get("answered_questions", []))
    total_questions = 5

    return render_template(
        "game.html",
        question=question_text,
        central_avg=central_avg,
        qid=qid,
        max_qid=max(q[0] for q in questions_cache) if questions_cache else None,
        answered=answered,
        your_answer=your_answer,
        score=score,
        stats={"all_answers": all_answers} if answered else None,
        next_qid=next_qid,
        all_answered=all_answered,
        answered_count=answered_count,
        total_questions=total_questions,
    )

@app.route("/request_question", methods=["GET", "POST"])
def request_question():
    if request.method == "POST":
        req_question = request.form.get("question")
        if req_question:
            with get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        'INSERT INTO "QuestionRequests" (question) VALUES (%s)',
                        (req_question,)
                    )
                conn.commit()
            flash("お題の送信が完了しました！ありがとうございます。")
            return redirect(url_for("request_question"))
    return render_template("request_question.html")

@app.route("/result")
def result():
    answered_list = session.get("answered_questions", [])
    questions_data = []

    for qid in answered_list:
        # 質問文取得
        question_row = next((q for q in questions_cache if q[0] == qid), None)
        if not question_row:
            continue
        question_text = question_row[1]

        # あなたの回答
        your_answer = session.get(f"last_answer_{qid}", None)

        # みんなの回答（キャッシュ）
        all_answers = answers_cache.get(qid, [])

        # ど真ん中（中央値的なもの）
        center_value = math.floor(central_average(all_answers)) if all_answers else None

        # スコア
        score = session.get(f"score_{qid}", 0)

        questions_data.append({
            "question": question_text,
            "your_answer": your_answer,
            "center_value": center_value,
            "score": score,
        })

    if questions_data:
        avg_score = sum(q["score"] for q in questions_data) / len(questions_data)
        total_score = math.floor(avg_score)
    else:
        total_score = 0

    return render_template("result.html",
                           questions=questions_data,
                           total_score=total_score,
                           answered_count=len(answered_list))

if __name__ == "__main__":
    server = Server(app.wsgi_app)
    server.watch("templates/")
    server.watch("static/")
    server.serve(port=5500, debug=True)
