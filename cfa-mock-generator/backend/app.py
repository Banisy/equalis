"""
MockGen - Finance Exam Preparation Tool
Backend Server v3: PDF processing, AI question generation, exam assembly.
"""
import os, sys, json, sqlite3, hashlib, random, time, re, threading
from pathlib import Path
from datetime import datetime

try: import pdfplumber
except ImportError: os.system(f"{sys.executable} -m pip install pdfplumber -q"); import pdfplumber
try: import cohere
except ImportError: os.system(f"{sys.executable} -m pip install cohere -q"); import cohere
try:
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS
except ImportError:
    os.system(f"{sys.executable} -m pip install flask flask-cors -q")
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"; DB_PATH = DATA_DIR / "questions.db"
UPLOAD_DIR = DATA_DIR / "uploads"; FRONTEND_DIR = BASE_DIR / "frontend"
try: DATA_DIR.mkdir(parents=True, exist_ok=True); UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except:
    BASE_DIR = Path.cwd(); DATA_DIR = BASE_DIR/"data"; DB_PATH = DATA_DIR/"questions.db"
    UPLOAD_DIR = DATA_DIR/"uploads"; FRONTEND_DIR = BASE_DIR/"frontend"
    DATA_DIR.mkdir(parents=True, exist_ok=True); UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class TaskManager:
    def __init__(self):
        self._lock = threading.Lock(); self._active = None; self._cancel = False
        self._progress = {"status":"idle","current":0,"total":0,"message":""}; self._result = None
    def try_start(self, name):
        with self._lock:
            if self._active: return False, self._active
            self._active = name; self._cancel = False; self._result = None
            self._progress = {"status":"running","current":0,"total":0,"message":f"Starting {name}..."}
            return True, None
    def finish(self, result=None):
        with self._lock: self._active = None; self._cancel = False; self._result = result; self._progress = {"status":"done","current":0,"total":0,"message":"Complete"}
    def cancel(self):
        with self._lock:
            if self._active: self._cancel = True; return True
            return False
    def is_cancelled(self): return self._cancel
    def update_progress(self, cur, tot, msg=""):
        with self._lock: self._progress = {"status":"running","task":self._active,"current":cur,"total":tot,"message":msg,"percent":round((cur/tot)*100) if tot>0 else 0}
    def get_progress(self):
        with self._lock: return dict(self._progress)
    def get_active_task(self):
        with self._lock: return self._active
    def get_result(self):
        with self._lock: r = self._result; self._result = None; return r

task_mgr = TaskManager()

# Session-specific topic weights (official CFA Level I)
SESSION1_TOPICS = {"Ethical and Professional Standards":{"weight":0.35},"Quantitative Methods":{"weight":0.15},"Economics":{"weight":0.15},"Financial Statement Analysis":{"weight":0.25},"Corporate Issuers":{"weight":0.10}}
SESSION2_TOPICS = {"Equity Investments":{"weight":0.25},"Fixed Income":{"weight":0.25},"Derivatives":{"weight":0.13},"Alternative Investments":{"weight":0.17},"Portfolio Management":{"weight":0.20}}
ALL_TOPICS = {**SESSION1_TOPICS, **SESSION2_TOPICS}

TOPIC_MIN_SCORE = 2
TOPIC_KEYWORDS = {
    "Ethical and Professional Standards":["code of ethics","standards of practice","gips","fiduciary","material nonpublic","insider trading","professional conduct","duty of loyalty","soft dollar","research objectivity","mosaic theory","whistleblowing","suitability","fair dealing","misrepresentation","ethical decision","professionalism","code and standards"],
    "Quantitative Methods":["hypothesis testing","t-test","z-test","standard deviation","variance","correlation","regression","time value of money","present value","future value","annuity","probability distribution","normal distribution","sampling","confidence interval","p-value","bayes","monte carlo","bootstrap","lognormal","kurtosis","skewness"],
    "Economics":["gdp","inflation","monetary policy","fiscal policy","aggregate demand","aggregate supply","exchange rate","trade deficit","central bank","interest rate parity","purchasing power parity","business cycle","unemployment","currency","tariff","comparative advantage","elasticity","geopolitics","oligopoly","monopoly","perfect competition"],
    "Financial Statement Analysis":["income statement","balance sheet","cash flow statement","revenue recognition","depreciation","amortization","inventory","fifo","lifo","ratio analysis","roe","roa","current ratio","quick ratio","debt-to-equity","financial reporting","ifrs","gaap","deferred tax","goodwill","impairment","operating lease","finance lease","earnings quality","accrual","dupont analysis","financial statement","earnings per share"],
    "Corporate Issuers":["capital budgeting","cost of capital","wacc","capital structure","modigliani","miller","dividend policy","share repurchase","corporate governance","board of directors","agency","stakeholder","leverage","breakeven","operating leverage","financial leverage","working capital","cash conversion cycle","business model"],
    "Equity Investments":["equity valuation","stock valuation","market efficiency","efficient market","security market","industry analysis","price-to-earnings","dividend discount","gordon growth","free cash flow to equity","market index","equity risk premium","beta","systematic risk","intrinsic value","relative valuation","margin transaction","short selling","market order","limit order"],
    "Fixed Income":["bond valuation","yield to maturity","duration","modified duration","convexity","coupon","par value","credit risk","credit spread","yield curve","term structure","callable bond","putable bond","securitization","mortgage-backed","asset-backed","sovereign bond","interest rate risk","reinvestment risk","spot rate","forward rate"],
    "Derivatives":["call option","put option","futures contract","forward contract","swap","put-call parity","option pricing","black-scholes","binomial model","payoff diagram","hedging","speculation","interest rate swap","credit default swap","strike price","expiration","arbitrage","replication","cost of carry","moneyness"],
    "Alternative Investments":["hedge fund","private equity","venture capital","real estate","commodity","infrastructure","distressed debt","buyout","real estate investment trust","reit","fund of funds","illiquidity premium","alternative asset","natural resource","digital asset","distributed ledger","farmland","timberland"],
    "Portfolio Management":["portfolio","asset allocation","diversification","efficient frontier","capital asset pricing","capm","security market line","capital market line","risk and return","systematic risk","unsystematic risk","sharpe ratio","treynor ratio","investment policy statement","risk tolerance","strategic asset allocation","tactical asset allocation","behavioral bias","risk management","risk budgeting"],
}

TOPIC_LOS = {
    "Ethical and Professional Standards": "Explain ethics, role of code of ethics, professions/trust. Compare ethical vs legal standards. Describe ethical decision-making framework. Describe CFA Institute Professional Conduct Program. Identify six Code components and seven Standards. Demonstrate Code/Standards application. Explain GIPS standards. Evaluate practices relative to Code/Standards.",
    "Quantitative Methods": "Interpret interest rates. Calculate return measures (money-weighted, time-weighted, annualized, continuously compounded). Calculate PV of fixed-income/equity instruments. Explain cash flow additivity, no-arbitrage. Calculate central tendency, dispersion, skewness, kurtosis. Interpret correlation. Calculate expected values, variances, standard deviations. Use probability trees and Bayes formula. Calculate portfolio expected value, variance, covariance. Define shortfall risk, safety-first ratio. Describe Monte Carlo simulation and bootstrap. Explain hypothesis testing. Describe simple linear regression, ANOVA. Describe Big Data and ML applications.",
    "Economics": "Determine breakeven/shutdown points. Describe market structures. Explain supply/demand under monopolistic competition and oligopoly. Describe business cycle phases, credit cycles. Compare monetary/fiscal policy. Describe central bank roles. Describe geopolitics, international trade. Describe FX market, exchange rate regimes. Calculate currency cross-rates, forward rates.",
    "Financial Statement Analysis": "Describe FSA framework. Describe revenue/expense recognition. Calculate basic/diluted EPS. Explain reporting for intangibles, goodwill. Describe cash flow statement linkages. Contrast IFRS/US GAAP. Calculate FCFF, FCFE. Describe inventory measurement. Explain lease reporting, pension plans. Explain deferred tax. Calculate activity, liquidity, solvency, profitability ratios. Apply DuPont analysis.",
    "Corporate Issuers": "Compare organizational forms. Describe corporate issuer features. Describe stakeholder groups and ESG factors. Describe principal-agent conflicts. Explain cash conversion cycle. Calculate NPV, IRR, ROIC. Calculate WACC. Explain Modigliani-Miller. Describe business models.",
    "Equity Investments": "Explain financial system functions. Calculate leverage ratio, margin return, margin call. Compare order types. Describe market indexes, weighting methods. Describe market efficiency forms. Describe equity security characteristics. Describe industry analysis with Porter's Five Forces. Calculate Gordon growth DDM. Calculate P/E, P/CF, P/S, P/B multiples. Describe enterprise value multiples.",
    "Fixed Income": "Describe fixed-income features, covenants. Compare FI market segments. Calculate bond price from YTM. Calculate yield/spread measures. Define spot/par/forward rates. Calculate modified duration, PVBP, convexity. Explain effective duration for embedded options. Describe credit risk. Explain securitization, ABS/MBS.",
    "Derivatives": "Define derivatives. Define forwards, futures, swaps, options. Determine option value/profit at expiration. Explain arbitrage/replication. Explain cost of carry. Explain forward contract valuation. Compare forward/futures prices. Explain put-call parity. Explain binomial model.",
    "Alternative Investments": "Describe alternative investment features. Compare investment methods. Calculate returns before/after fees. Explain private equity/debt. Describe real estate/infrastructure. Explain hedge fund features. Describe digital assets.",
    "Portfolio Management": "Explain risk aversion. Calculate portfolio standard deviation. Describe efficient frontiers. Explain CAPM and SML. Calculate Sharpe ratio, Treynor ratio, Jensen's alpha. Describe IPS components. Compare cognitive errors/emotional biases. Define risk management.",
}

QUESTION_STYLE_RULES = """FORMAT RULES (official Level I exam format - follow exactly):
1. STEM (question/statement) + THREE choices (A, B, C)
2. Two formats: sentence completion OR question - both with 3 unique choices
3. DO NOT use 'except', 'true', 'false'. AVOID 'not'
4. Use qualifiers: 'most likely', 'least likely', 'best described', 'most appropriate', 'most accurate'
5. NEVER use: 'all of the above', 'none of the above', 'A and B only', 'cannot determine'
6. Word choices: shortest to longest. Numbers: smallest to largest
7. Common language in stem, not repeated in choices
8. All choices plausible and grammatically consistent
9. Test understanding, application, analysis - not recall
10. Include calculations where material supports it"""

def init_db():
    conn = sqlite3.connect(str(DB_PATH)); conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL, file_hash TEXT UNIQUE NOT NULL, pages INTEGER, uploaded_at TEXT DEFAULT (datetime('now')), processed INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL, topic TEXT NOT NULL, subtopic TEXT DEFAULT '', content TEXT NOT NULL, page_start INTEGER, page_end INTEGER, questions_generated INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, chunk_id INTEGER, topic TEXT NOT NULL, subtopic TEXT DEFAULT '', difficulty TEXT DEFAULT 'medium', question_text TEXT NOT NULL, choice_a TEXT NOT NULL, choice_b TEXT NOT NULL, choice_c TEXT NOT NULL, correct_answer TEXT NOT NULL, explanation TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now')), times_shown INTEGER DEFAULT 0, times_correct INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS exams (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, created_at TEXT DEFAULT (datetime('now')), completed_at TEXT, score REAL, total_questions INTEGER DEFAULT 180, session1_json TEXT, session2_json TEXT, session1_completed INTEGER DEFAULT 0, session2_completed INTEGER DEFAULT 0, difficulty INTEGER DEFAULT 75);
        CREATE TABLE IF NOT EXISTS exam_answers (id INTEGER PRIMARY KEY AUTOINCREMENT, exam_id INTEGER NOT NULL, question_id INTEGER NOT NULL, session INTEGER DEFAULT 1, user_answer TEXT, is_correct INTEGER, flagged INTEGER DEFAULT 0, time_spent_seconds INTEGER DEFAULT 0);
    """)
    conn.commit(); conn.close()

def get_db():
    conn = sqlite3.connect(str(DB_PATH)); conn.row_factory = sqlite3.Row; return conn

def get_api_key():
    key = os.environ.get("COHERE_API_KEY","")
    if not key:
        cp = DATA_DIR/"config.json"
        if cp.exists():
            with open(cp) as f: key = json.load(f).get("cohere_api_key","")
    return key

def require_api_key():
    if not get_api_key(): return jsonify({"error":"API key not set. Go to Settings first.","needs_api_key":True}), 403
    return None

def compute_file_hash(fp):
    h = hashlib.sha256()
    with open(fp,"rb") as f:
        for c in iter(lambda: f.read(8192), b""): h.update(c)
    return h.hexdigest()

def detect_topic(text):
    tl = text.lower(); scores = {}
    for topic, kws in TOPIC_KEYWORDS.items():
        s = sum(tl.count(kw) for kw in kws)
        if s >= TOPIC_MIN_SCORE: scores[topic] = s
    return max(scores, key=scores.get) if scores else "General"

def extract_and_chunk_pdf(filepath, source_id):
    chunks = []; cur = ""; cur_topic = None; cur_start = 0
    with pdfplumber.open(filepath) as pdf:
        tp = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            if task_mgr.is_cancelled(): return chunks
            task_mgr.update_progress(i+1, tp, f"Reading page {i+1}/{tp}...")
            text = page.extract_text()
            if not text or len(text.strip()) < 30: continue
            det = detect_topic(text)
            if (cur_topic and det != cur_topic and det != "General" and len(cur) > 300) or len(cur) > 3000:
                if cur.strip() and len(cur.strip()) >= 300:
                    ft = cur_topic if cur_topic and cur_topic != "General" else det
                    chunks.append({"source_id":source_id,"topic":ft,"content":cur.strip(),"page_start":cur_start,"page_end":i})
                cur = ""; cur_start = i+1
            if det != "General": cur_topic = det
            cur += f"\n\n--- Page {i+1} ---\n\n{text}"
    if cur.strip() and len(cur.strip()) >= 300:
        chunks.append({"source_id":source_id,"topic":cur_topic or "General","content":cur.strip(),"page_start":cur_start,"page_end":0})
    task_mgr.update_progress(tp, tp, "Saving chunks...")
    conn = get_db()
    for c in chunks: conn.execute("INSERT INTO chunks (source_id,topic,content,page_start,page_end) VALUES (?,?,?,?,?)",(c["source_id"],c["topic"],c["content"],c["page_start"],c["page_end"]))
    conn.commit(); conn.close()
    return chunks

def get_cohere_client():
    key = get_api_key()
    if not key: raise ValueError("No API key")
    return cohere.ClientV2(api_key=key)

def build_prompt(topic, content, n):
    los = TOPIC_LOS.get(topic,"")
    los_s = f"\nLEARNING OUTCOMES for {topic} (align questions to these):\n{los}\n" if los else ""
    return f"""You are an expert Level I finance exam question writer for {topic}.
Generate exactly {n} multiple-choice questions.

{QUESTION_STYLE_RULES}
{los_s}
RULES:
- Base questions ONLY on the study material below
- Questions must be about {topic}
- If material is filler (TOC, index, copyright), return: []
- If limited content, generate fewer (quality over quantity)
- Each question tests a DIFFERENT concept
- Include calculation questions where possible

DIFFICULTY: "easy"=recall, "medium"=application, "hard"=analysis/multi-step

STUDY MATERIAL:
{content}

Respond ONLY with valid JSON array. No markdown, no backticks.
Each object: {{"question":"...","choice_a":"...","choice_b":"...","choice_c":"...","correct_answer":"A/B/C","explanation":"...","difficulty":"easy/medium/hard","subtopic":"..."}}
If insufficient: []"""

def generate_questions_from_chunk(chunk_id, num_q=5):
    conn = get_db()
    try:
        chunk = conn.execute("SELECT * FROM chunks WHERE id=?",(chunk_id,)).fetchone()
        if not chunk: return []
        if chunk["topic"] == "General":
            conn.execute("UPDATE chunks SET questions_generated=-1 WHERE id=?",(chunk_id,)); conn.commit(); return []
        co = get_cohere_client()
        prompt = build_prompt(chunk["topic"], chunk["content"][:8000], num_q)
        resp = co.chat(model="command-a-03-2025", messages=[{"role":"user","content":prompt}], temperature=0.3)
        rt = resp.message.content[0].text.strip()
        if rt.startswith("```"): rt = re.sub(r'^```(?:json)?\n?','',rt); rt = re.sub(r'\n?```$','',rt)
        qs = json.loads(rt)
        if not qs:
            conn.execute("UPDATE chunks SET questions_generated=-1 WHERE id=?",(chunk_id,)); conn.commit(); return []
        stored = []
        for q in qs:
            if not all(k in q for k in ["question","choice_a","choice_b","choice_c","correct_answer","explanation"]): continue
            cur = conn.execute("INSERT INTO questions (chunk_id,topic,subtopic,difficulty,question_text,choice_a,choice_b,choice_c,correct_answer,explanation) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (chunk_id,chunk["topic"],q.get("subtopic",""),q.get("difficulty","medium"),q["question"],q["choice_a"],q["choice_b"],q["choice_c"],q["correct_answer"].upper(),q["explanation"]))
            stored.append(cur.lastrowid)
        conn.execute("UPDATE chunks SET questions_generated=? WHERE id=?",(len(stored),chunk_id)); conn.commit()
        return stored
    except json.JSONDecodeError:
        try: conn.execute("UPDATE chunks SET questions_generated=-1 WHERE id=?",(chunk_id,)); conn.commit()
        except: pass
        return []
    except Exception as e:
        print(f"Error chunk {chunk_id}: {e}"); return []
    finally:
        conn.close()

def generate_questions_threaded(topics, target, qpc=5, delay=1.0):
    conn = get_db()
    ph = ",".join("?"*len(topics))
    chunks = conn.execute(f"SELECT id,topic FROM chunks WHERE questions_generated=0 AND topic IN ({ph}) ORDER BY RANDOM()",topics).fetchall()
    conn.close()
    tw = {}; total_w = 0
    for t in topics: w = ALL_TOPICS.get(t,{}).get("weight",0.05); tw[t] = w; total_w += w
    tt = {t: max(5,round(target*(tw[t]/total_w))) for t in topics}
    tcn = {t: max(1,(tt[t]+qpc-1)//qpc) for t in topics}
    to_proc = []; tcc = {}
    for c in chunks:
        t = c["topic"]; tcc[t] = tcc.get(t,0)+1
        if tcc[t] <= tcn.get(t,999): to_proc.append(c)
    total = len(to_proc); gen = 0
    for i, c in enumerate(to_proc):
        if task_mgr.is_cancelled(): break
        task_mgr.update_progress(i+1,total,f"Chunk {i+1}/{total} - {c['topic']} - {gen} questions so far")
        ids = generate_questions_from_chunk(c["id"],qpc)
        gen += len(ids)
        if gen >= target: break
        time.sleep(delay)
    task_mgr.finish({"questions_generated":gen})

def get_diff_dist(d):
    t = (d-50)/50; e = max(0.05,0.60-0.55*t); h = max(0.05,0.05+0.55*t); return {"easy":e,"medium":1-e-h,"hard":h}

def assemble_exam(qps=90, difficulty=75):
    conn = get_db()
    try:
        tc = {}
        for r in conn.execute("SELECT topic,COUNT(*) as cnt FROM questions GROUP BY topic"): tc[r["topic"]] = r["cnt"]
        dd = get_diff_dist(difficulty)
        def select_session(stopic, target):
            targets = {}
            for topic, info in stopic.items():
                t = round(target * info["weight"]); a = tc.get(topic,0); targets[topic] = min(t,a)
            assigned = sum(targets.values()); rem = target - assigned
            if rem > 0:
                for topic in sorted(stopic.keys(), key=lambda t: tc.get(t,0), reverse=True):
                    if rem <= 0: break
                    a = tc.get(topic,0) - targets.get(topic,0); add = min(rem,a); targets[topic] = targets.get(topic,0)+add; rem -= add
            sq = []
            for topic, count in targets.items():
                if count <= 0: continue
                for dl, ratio in dd.items():
                    n = max(1,round(count*ratio))
                    rows = conn.execute("SELECT id FROM questions WHERE topic=? AND difficulty=? ORDER BY times_shown ASC, RANDOM() LIMIT ?",(topic,dl,n)).fetchall()
                    sq.extend([r["id"] for r in rows])
            sq = list(dict.fromkeys(sq))[:target]
            if len(sq) < target:
                existing = set(sq); tl = list(stopic.keys()); ph = ",".join("?"*len(tl))
                ex_str = ",".join(str(x) for x in existing) if existing else "0"
                fill = conn.execute(f"SELECT id FROM questions WHERE topic IN ({ph}) AND id NOT IN ({ex_str}) ORDER BY times_shown ASC, RANDOM() LIMIT ?", tl+[target-len(sq)]).fetchall()
                sq.extend([r["id"] for r in fill])
            random.shuffle(sq); return sq
        s1 = select_session(SESSION1_TOPICS, qps)
        s2 = select_session(SESSION2_TOPICS, qps)
        total = len(s1)+len(s2)
        if total < 10: return None
        name = f"Mock Exam - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        cur = conn.execute("INSERT INTO exams (name,total_questions,session1_json,session2_json,difficulty) VALUES (?,?,?,?,?)",(name,total,json.dumps(s1),json.dumps(s2),difficulty))
        eid = cur.lastrowid
        for qid in s1+s2: conn.execute("UPDATE questions SET times_shown=times_shown+1 WHERE id=?",(qid,))
        conn.commit()
        return {"exam_id":eid,"name":name,"total_questions":total,"session1_count":len(s1),"session2_count":len(s2),"difficulty":difficulty}
    finally:
        conn.close()

# ============================================================
# FLASK APP
# ============================================================
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)

@app.route("/")
def serve_index(): return send_from_directory(str(FRONTEND_DIR), "index.html")
@app.route("/<path:path>")
def serve_static(path): return send_from_directory(str(FRONTEND_DIR), path)

@app.route("/api/task/status")
def task_status():
    return jsonify({"active_task":task_mgr.get_active_task(),"progress":task_mgr.get_progress(),"result":task_mgr.get_result()})

@app.route("/api/task/cancel", methods=["POST"])
def task_cancel(): return jsonify({"status":"cancel_requested" if task_mgr.cancel() else "no_active_task"})

@app.route("/api/config", methods=["GET","POST"])
def config():
    cp = DATA_DIR/"config.json"
    if request.method == "POST":
        cfg = {}
        if cp.exists():
            with open(cp) as f: cfg = json.load(f)
        cfg["cohere_api_key"] = request.json.get("cohere_api_key","")
        with open(cp,"w") as f: json.dump(cfg,f)
        return jsonify({"status":"ok"})
    else:
        if cp.exists():
            with open(cp) as f: cfg = json.load(f)
            key = cfg.get("cohere_api_key",""); masked = key[:8]+"..."+key[-4:] if len(key)>12 else ("set" if key else "")
            return jsonify({"cohere_api_key":masked,"is_set":bool(key)})
        return jsonify({"cohere_api_key":"","is_set":False})

@app.route("/api/upload", methods=["POST"])
def upload_pdf():
    check = require_api_key()
    if check: return check
    if task_mgr.get_active_task(): return jsonify({"error":"A task is running. Please wait."}), 409
    if "file" not in request.files: return jsonify({"error":"No file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"): return jsonify({"error":"Only PDFs"}), 400
    fp = UPLOAD_DIR / file.filename; file.save(str(fp)); fh = compute_file_hash(str(fp))
    conn = get_db()
    try:
        if conn.execute("SELECT id FROM sources WHERE file_hash=?",(fh,)).fetchone():
            os.remove(str(fp)); return jsonify({"error":"File already uploaded"}), 409
        with pdfplumber.open(str(fp)) as pdf: np = len(pdf.pages)
        cur = conn.execute("INSERT INTO sources (filename,file_hash,pages) VALUES (?,?,?)",(file.filename,fh,np))
        sid = cur.lastrowid; conn.commit()
        return jsonify({"source_id":sid,"filename":file.filename,"pages":np})
    finally: conn.close()

@app.route("/api/process/<int:sid>", methods=["POST"])
def process_pdf(sid):
    check = require_api_key()
    if check: return check
    conn = get_db()
    try:
        src = conn.execute("SELECT * FROM sources WHERE id=?",(sid,)).fetchone()
        if not src: return jsonify({"error":"Not found"}), 404
        if src["processed"]: return jsonify({"error":"Already processed"}), 409
    finally: conn.close()
    fp = UPLOAD_DIR/src["filename"]
    if not fp.exists(): return jsonify({"error":"File missing"}), 404
    ok, bl = task_mgr.try_start("processing")
    if not ok: return jsonify({"error":f"'{bl}' is running"}), 409
    def run():
        try:
            extract_and_chunk_pdf(str(fp), sid)
            if not task_mgr.is_cancelled():
                c = get_db(); c.execute("UPDATE sources SET processed=1 WHERE id=?",(sid,)); c.commit(); c.close()
        except Exception as e: print(f"Error: {e}")
        finally: task_mgr.finish()
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status":"started"})

@app.route("/api/process-all", methods=["POST"])
def process_all():
    check = require_api_key()
    if check: return check
    ok, bl = task_mgr.try_start("processing")
    if not ok: return jsonify({"error":f"'{bl}' is running"}), 409
    def run():
        try:
            conn = get_db(); unp = conn.execute("SELECT * FROM sources WHERE processed=0 ORDER BY id").fetchall(); conn.close()
            for idx, src in enumerate(unp):
                if task_mgr.is_cancelled(): break
                task_mgr.update_progress(idx, len(unp), f"Processing {src['filename']} ({idx+1}/{len(unp)})...")
                fp = UPLOAD_DIR/src["filename"]
                if fp.exists():
                    extract_and_chunk_pdf(str(fp), src["id"])
                    c = get_db(); c.execute("UPDATE sources SET processed=1 WHERE id=?",(src["id"],)); c.commit(); c.close()
        except Exception as e: print(f"Error: {e}")
        finally: task_mgr.finish()
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status":"started"})

@app.route("/api/sources/<int:sid>", methods=["DELETE"])
def delete_source(sid):
    if task_mgr.get_active_task(): return jsonify({"error":"Task running"}), 409
    conn = get_db()
    try:
        src = conn.execute("SELECT * FROM sources WHERE id=?",(sid,)).fetchone()
        if not src: return jsonify({"error":"Not found"}), 404
        cids = [r["id"] for r in conn.execute("SELECT id FROM chunks WHERE source_id=?",(sid,)).fetchall()]
        for cid in cids: conn.execute("DELETE FROM questions WHERE chunk_id=?",(cid,))
        conn.execute("DELETE FROM chunks WHERE source_id=?",(sid,))
        conn.execute("DELETE FROM sources WHERE id=?",(sid,))
        conn.commit()
    finally: conn.close()
    fp = UPLOAD_DIR/src["filename"]
    if fp.exists(): os.remove(str(fp))
    return jsonify({"status":"deleted"})

@app.route("/api/reset-database", methods=["POST"])
def reset_database():
    if task_mgr.get_active_task(): return jsonify({"error":"Task running"}), 409
    conn = get_db()
    try:
        for t in ["exam_answers","exams","questions","chunks","sources"]: conn.execute(f"DELETE FROM {t}")
        conn.commit()
    finally: conn.close()
    for f in UPLOAD_DIR.iterdir():
        if f.is_file(): os.remove(str(f))
    return jsonify({"status":"reset"})

@app.route("/api/generate", methods=["POST"])
def generate():
    check = require_api_key()
    if check: return check
    ok, bl = task_mgr.try_start("generating")
    if not ok: return jsonify({"error":f"'{bl}' is running"}), 409
    data = request.json or {}
    topics = data.get("topics",[]); target = data.get("target_questions",200)
    qpc = data.get("questions_per_chunk",5); delay = data.get("delay",1.0)
    if not topics: task_mgr.finish(); return jsonify({"error":"No topics selected"}), 400
    def run(): generate_questions_threaded(topics, target, qpc, delay)
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status":"started"})

@app.route("/api/stats")
def stats():
    conn = get_db()
    try:
        s = conn.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(pages),0) as pages FROM sources").fetchone()
        ch = conn.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()
        q = conn.execute("SELECT COUNT(*) as cnt FROM questions").fetchone()
        uc = conn.execute("SELECT COUNT(*) as cnt FROM chunks WHERE questions_generated=0 AND topic!='General'").fetchone()
        td = {}
        for r in conn.execute("SELECT topic,COUNT(*) as cnt FROM questions GROUP BY topic ORDER BY cnt DESC"): td[r["topic"]] = r["cnt"]
        cd = {}
        for r in conn.execute("SELECT topic,COUNT(*) as cnt FROM chunks WHERE questions_generated=0 AND topic!='General' GROUP BY topic ORDER BY cnt DESC"): cd[r["topic"]] = r["cnt"]
        ex = conn.execute("SELECT COUNT(*) as cnt FROM exams").fetchone()
        us = conn.execute("SELECT COUNT(*) as cnt FROM sources WHERE processed=0").fetchone()
        return jsonify({"sources":s["cnt"],"total_pages":s["pages"],"chunks":ch["cnt"],"unprocessed_chunks":uc["cnt"],"questions":q["cnt"],"topic_distribution":td,"chunk_distribution":cd,"exams_taken":ex["cnt"],"can_generate_exam":q["cnt"]>=10,"api_key_set":bool(get_api_key()),"unprocessed_sources":us["cnt"]})
    finally: conn.close()

@app.route("/api/sources")
def list_sources():
    conn = get_db()
    try: return jsonify([dict(r) for r in conn.execute("SELECT * FROM sources ORDER BY uploaded_at DESC").fetchall()])
    finally: conn.close()

@app.route("/api/question-bank")
def question_bank():
    conn = get_db()
    try:
        topic = request.args.get("topic",""); diff = request.args.get("difficulty","")
        page = int(request.args.get("page",1)); pp = int(request.args.get("per_page",50))
        w = ["1=1"]; p = []
        if topic: w.append("topic=?"); p.append(topic)
        if diff: w.append("difficulty=?"); p.append(diff)
        ws = " AND ".join(w)
        total = conn.execute(f"SELECT COUNT(*) as cnt FROM questions WHERE {ws}",p).fetchone()["cnt"]
        rows = conn.execute(f"SELECT * FROM questions WHERE {ws} ORDER BY topic,id LIMIT ? OFFSET ?",p+[pp,(page-1)*pp]).fetchall()
        return jsonify({"questions":[{"id":r["id"],"topic":r["topic"],"subtopic":r["subtopic"],"difficulty":r["difficulty"],"question_text":r["question_text"],"choice_a":r["choice_a"],"choice_b":r["choice_b"],"choice_c":r["choice_c"],"correct_answer":r["correct_answer"],"explanation":r["explanation"],"times_shown":r["times_shown"],"times_correct":r["times_correct"]} for r in rows],"total":total,"page":page,"per_page":pp})
    finally: conn.close()

@app.route("/api/exam/create", methods=["POST"])
def create_exam():
    check = require_api_key()
    if check: return check
    if task_mgr.get_active_task(): return jsonify({"error":"Task running"}), 409
    data = request.json or {}
    qps = data.get("questions_per_session",90); diff = data.get("difficulty",75)
    result = assemble_exam(qps, diff)
    if not result: return jsonify({"error":"Not enough questions. Generate more first."}), 400
    return jsonify(result)

@app.route("/api/exam/<int:eid>")
def get_exam(eid):
    conn = get_db()
    try:
        exam = conn.execute("SELECT * FROM exams WHERE id=?",(eid,)).fetchone()
        if not exam: return jsonify({"error":"Not found"}), 404
        s1ids = json.loads(exam["session1_json"]) if exam["session1_json"] else []
        s2ids = json.loads(exam["session2_json"]) if exam["session2_json"] else []
        def load_qs(ids):
            qs = []
            for qid in ids:
                q = conn.execute("SELECT * FROM questions WHERE id=?",(qid,)).fetchone()
                if q: qs.append({"id":q["id"],"topic":q["topic"],"subtopic":q["subtopic"],"difficulty":q["difficulty"],"question_text":q["question_text"],"choice_a":q["choice_a"],"choice_b":q["choice_b"],"choice_c":q["choice_c"]})
            return qs
        answers = {}
        for r in conn.execute("SELECT * FROM exam_answers WHERE exam_id=?",(eid,)):
            answers[str(r["question_id"])] = {"user_answer":r["user_answer"],"flagged":r["flagged"],"session":r["session"]}
        return jsonify({"exam_id":exam["id"],"name":exam["name"],"total_questions":exam["total_questions"],"session1":load_qs(s1ids),"session2":load_qs(s2ids),"session1_completed":exam["session1_completed"],"session2_completed":exam["session2_completed"],"completed":exam["completed_at"] is not None,"score":exam["score"],"answers":answers,"difficulty":exam["difficulty"]})
    finally: conn.close()

@app.route("/api/exam/<int:eid>/answer", methods=["POST"])
def save_answer(eid):
    data = request.json; qid = data["question_id"]; ans = data.get("answer"); fl = data.get("flagged",0); ses = data.get("session",1)
    conn = get_db()
    try:
        q = conn.execute("SELECT correct_answer FROM questions WHERE id=?",(qid,)).fetchone()
        ic = 1 if q and ans and ans.upper()==q["correct_answer"] else 0
        ex = conn.execute("SELECT id FROM exam_answers WHERE exam_id=? AND question_id=?",(eid,qid)).fetchone()
        if ex: conn.execute("UPDATE exam_answers SET user_answer=?,is_correct=?,flagged=?,session=? WHERE id=?",(ans,ic,fl,ses,ex["id"]))
        else: conn.execute("INSERT INTO exam_answers (exam_id,question_id,user_answer,is_correct,flagged,session,time_spent_seconds) VALUES (?,?,?,?,?,?,0)",(eid,qid,ans,ic,fl,ses))
        conn.commit(); return jsonify({"status":"ok"})
    finally: conn.close()

@app.route("/api/exam/<int:eid>/complete-session", methods=["POST"])
def complete_session(eid):
    ses = (request.json or {}).get("session",1)
    conn = get_db()
    try:
        conn.execute(f"UPDATE exams SET session{ses}_completed=1 WHERE id=?",(eid,)); conn.commit()
        return jsonify({"status":"ok"})
    finally: conn.close()

@app.route("/api/exam/<int:eid>/submit", methods=["POST"])
def submit_exam(eid):
    conn = get_db()
    try:
        exam = conn.execute("SELECT * FROM exams WHERE id=?",(eid,)).fetchone()
        if not exam: return jsonify({"error":"Not found"}), 404
        answers = conn.execute("SELECT is_correct FROM exam_answers WHERE exam_id=?",(eid,)).fetchall()
        correct = sum(1 for a in answers if a["is_correct"]); total = exam["total_questions"]
        score = round((correct/total)*100,1) if total>0 else 0
        conn.execute("UPDATE exams SET completed_at=datetime('now'),score=?,session1_completed=1,session2_completed=1 WHERE id=?",(score,eid))
        for r in conn.execute("SELECT question_id,is_correct FROM exam_answers WHERE exam_id=?",(eid,)):
            conn.execute("UPDATE questions SET times_correct=times_correct+? WHERE id=?",(r["is_correct"],r["question_id"]))
        conn.commit(); return jsonify({"score":score,"correct":correct,"total":total})
    finally: conn.close()

@app.route("/api/exam/<int:eid>/review")
def review_exam(eid):
    conn = get_db()
    try:
        exam = conn.execute("SELECT * FROM exams WHERE id=?",(eid,)).fetchone()
        if not exam: return jsonify({"error":"Not found"}), 404
        s1ids = json.loads(exam["session1_json"]) if exam["session1_json"] else []
        s2ids = json.loads(exam["session2_json"]) if exam["session2_json"] else []
        results = []
        for idx, qid in enumerate(s1ids+s2ids):
            q = conn.execute("SELECT * FROM questions WHERE id=?",(qid,)).fetchone()
            a = conn.execute("SELECT * FROM exam_answers WHERE exam_id=? AND question_id=?",(eid,qid)).fetchone()
            if q: results.append({"id":q["id"],"topic":q["topic"],"subtopic":q["subtopic"],"difficulty":q["difficulty"],"question_text":q["question_text"],"choice_a":q["choice_a"],"choice_b":q["choice_b"],"choice_c":q["choice_c"],"correct_answer":q["correct_answer"],"explanation":q["explanation"],"user_answer":a["user_answer"] if a else None,"is_correct":a["is_correct"] if a else None,"flagged":a["flagged"] if a else 0,"session":1 if idx<len(s1ids) else 2})
        tb = {}
        for r in results:
            t = r["topic"]
            if t not in tb: tb[t] = {"correct":0,"total":0}
            tb[t]["total"] += 1
            if r["is_correct"]: tb[t]["correct"] += 1
        return jsonify({"exam_id":eid,"score":exam["score"],"session1_count":len(s1ids),"session2_count":len(s2ids),"questions":results,"topic_breakdown":tb})
    finally: conn.close()

@app.route("/api/exams")
def list_exams():
    conn = get_db()
    try: return jsonify([dict(r) for r in conn.execute("SELECT id,name,created_at,completed_at,score,total_questions,session1_completed,session2_completed,difficulty FROM exams ORDER BY created_at DESC").fetchall()])
    finally: conn.close()

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT",5000))
    print(f"\n{'='*60}\n  MockGen - Finance Exam Preparation Tool\n  http://localhost:{port}\n{'='*60}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
