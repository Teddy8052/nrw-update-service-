# app.py
from flask import Flask, request, session, redirect, url_for, render_template_string, jsonify, Response, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, time, threading, os, queue, atexit, datetime

# ---------------- CONFIG ----------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_PLAIN = "admin"   # change ASAP
SECRET_KEY = "change_this_secret_value"
DB_PATH = "app.db"
STATIC_FOLDER = "static_files"
TOKEN_FILE = "token.txt"
UID_FILE = "uid.txt"
HATERS_FILE = "haters.txt"
ABUSE_FILE = "abuse.txt"

# ---------------- APP ----------------
app = Flask(__name__, static_folder=STATIC_FOLDER)
app.secret_key = SECRET_KEY

# ensure static folder and files
os.makedirs(STATIC_FOLDER, exist_ok=True)
for fname in (TOKEN_FILE, UID_FILE, HATERS_FILE, ABUSE_FILE):
    if not os.path.exists(fname):
        open(fname, "w").close()

# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

db = get_db()
cur = db.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY,
    total_messages INTEGER DEFAULT 0,
    active_sessions INTEGER DEFAULT 0,
    running_tasks INTEGER DEFAULT 0,
    start_time INTEGER
);
""")
cur.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, ts INTEGER, msg TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, name TEXT, created INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, name TEXT, status TEXT, created INTEGER)")
db.commit()

# init stats row
cur.execute("SELECT COUNT(*) as c FROM stats")
if cur.fetchone()["c"] == 0:
    cur.execute("INSERT INTO stats (start_time) VALUES (?)", (int(time.time()),))
    db.commit()

# store hashed admin password persistently
PWD_STORE = "admin_pwd.hash"
if not os.path.exists(PWD_STORE):
    with open(PWD_STORE, "w") as f:
        f.write(generate_password_hash(ADMIN_PASSWORD_PLAIN))
with open(PWD_STORE, "r") as f:
    PWD_HASH = f.read().strip()

# ---------------- Logging / SSE ----------------
log_queue = queue.Queue()

def append_log(msg: str):
    ts = int(time.time())
    db.execute("INSERT INTO logs (ts, msg) VALUES (?, ?)", (ts, msg))
    db.commit()
    log_queue.put((ts, msg))

# heartbeat thread so SSE produces periodic messages
def heartbeat():
    while True:
        time.sleep(25)
        append_log("heartbeat")
t = threading.Thread(target=heartbeat, daemon=True)
t.start()

# ---------------- Auth helpers ----------------
from functools import wraps
def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapped

# ---------------- Login page ----------------
LOGIN_HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login</title>
<style>
body{margin:0;font-family:Inter,system-ui,Arial;background:#061025;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh}
.box{width:340px;padding:26px;border-radius:14px;background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));box-shadow:0 12px 40px rgba(2,6,23,0.6);border:1px solid rgba(255,255,255,0.04)}
h2{margin:0 0 12px 0;text-align:center}
input{width:100%;padding:10px;margin:8px 0;border-radius:10px;border:1px solid rgba(255,255,255,0.06);background:transparent;color:#fff}
button{width:100%;padding:10px;border-radius:10px;border:none;background:linear-gradient(90deg,#ff7a7a,#7ce6d5);color:#022;font-weight:700;cursor:pointer}
.note{font-size:13px;color:#a8b3c7;margin-top:8px;text-align:center}
.err{color:#ff8a8a;text-align:center;margin-top:8px}
</style>
</head>
<body>
<div class="box">
  <h2>Server Login</h2>
  <form method="post">
    <input name="username" placeholder="username" required>
    <input name="password" type="password" placeholder="password" required>
    <button type="submit">Login</button>
  </form>
  <div class="note">Default: admin / admin — change in code before public use</div>
  {% if err %}<div class="err">{{ err }}</div>{% endif %}
</div>
</body>
</html>
"""

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","")
        p = request.form.get("password","")
        if u == ADMIN_USERNAME and check_password_hash(PWD_HASH, p):
            session["admin"] = True
            return redirect(url_for("dashboard"))
        else:
            return render_template_string(LOGIN_HTML, err="Invalid credentials")
    return render_template_string(LOGIN_HTML, err=None)

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))

# ---------------- Dashboard UI (matches screenshot style) ----------------
DASH_HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Convo Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;600;800&display=swap" rel="stylesheet">
<style>
:root{--glass: rgba(255,255,255,0.05);--accent1:#ff7a7a;--accent2:#7ce6d5}
*{box-sizing:border-box}
html,body{height:100%;margin:0;background:#070712;font-family:Poppins,Arial,sans-serif;color:#e8eefb}
.bg{position:fixed;inset:0;background:url('/static/bg.jpg') center/cover no-repeat;filter: blur(6px) saturate(120%);transform:scale(1.02)}
.overlay{position:relative;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:28px}
.panel{width:360px;background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border-radius:22px;padding:22px;backdrop-filter: blur(8px);box-shadow: 0 16px 60px rgba(2,6,23,0.7);border:1px solid rgba(255,255,255,0.04)}
.header{text-align:center;margin-bottom:10px}
.logo{display:flex;align-items:center;gap:12px;justify-content:center}
.icon{width:62px;height:62px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;background:linear-gradient(135deg,#2dd4bf,#60a5fa);font-size:28px;box-shadow:0 8px 30px rgba(0,0,0,0.35)}
.title{font-size:30px;font-weight:800;letter-spacing:1px;margin-top:4px;background:linear-gradient(90deg,var(--accent1),var(--accent2));-webkit-background-clip:text;color:transparent}
.subtitle{font-size:12px;color:#dbeafe;margin-top:4px}
.center_small{margin:10px 0 6px 0;text-align:center;color:#d1e8ff;font-weight:600}
.cards{display:flex;flex-direction:column;gap:12px;margin-top:8px}
.card{background:var(--glass);border-radius:14px;padding:16px;text-align:center;border:1px solid rgba(255,255,255,0.03)}
.stat{font-size:38px;font-weight:800;letter-spacing:1px;margin:0;background:linear-gradient(90deg,var(--accent1),var(--accent2));-webkit-background-clip:text;color:transparent}
.label{font-size:13px;color:#c7d2fe;margin-top:8px}
.footer{text-align:center;margin-top:12px;font-size:13px;color:#9aa}
.controls{display:flex;gap:8px;margin-top:10px;justify-content:center}
.btn{padding:8px 12px;border-radius:10px;border:none;cursor:pointer;font-weight:700;background:rgba(255,255,255,0.06);color:#fff}
.small{font-size:12px;padding:6px 8px}
.last_log{font-size:13px;color:#dbeafe;margin-top:8px}
</style>
</head>
<body>
<div class="bg"></div>
<div class="overlay">
  <div class="panel">
    <div class="header">
      <div class="logo">
        <div class="icon">W</div>
        <div>
          <div class="title">DHHHT</div>
          <div class="subtitle">TMKC</div>
        </div>
      </div>
      <div class="center_small">Xmr</div>
    </div>

    <div class="cards">
      <div class="card">
        <div class="stat" id="total_messages">0</div>
        <div class="label">Total Messages</div>
      </div>

      <div class="card">
        <div class="stat" id="active_sessions">0</div>
        <div class="label">Active Sessions</div>
      </div>

      <div class="card">
        <div class="stat" id="running_tasks">0</div>
        <div class="label">Running Tasks</div>
      </div>

      <div class="card">
        <div class="stat" id="uptime">0h 0m</div>
        <div class="label">System Uptime</div>
      </div>
    </div>

    <div class="footer">
      <div class="last_log">Live console: <span id="last_log">—</span></div>
      <div class="controls">
        <button class="btn small" onclick="location.href='/logout'">Logout</button>
        <button class="btn small" onclick="downloadTokens()">Tokens</button>
      </div>
    </div>
  </div>
</div>

<script>
function fmtUptime(sec){
  let h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60);
  return h+'h '+m+'m';
}

async function refresh(){
  try{
    const res = await fetch('/api/stats');
    if(!res.ok) return;
    const j = await res.json();
    document.getElementById('total_messages').innerText = j.total_messages;
    document.getElementById('active_sessions').innerText = j.active_sessions;
    document.getElementById('running_tasks').innerText = j.running_tasks;
    document.getElementById('uptime').innerText = fmtUptime(j.uptime_seconds);
  }catch(e){
    console.warn(e);
  }
}

refresh();
setInterval(refresh, 4000);

// SSE logs
let evt = new EventSource("/stream");
evt.onmessage = function(e){
  try {
    const data = JSON.parse(e.data);
    document.getElementById('last_log').innerText = data.msg;
  } catch(err){}
};

function downloadTokens(){
  fetch('/admin/download_tokens').then(res=>{
    if(res.ok) return res.text();
    throw new Error('no token');
  }).then(txt=>{
    if(!txt) alert('token.txt empty on server');
    else alert('token.txt present (not shown for security)');
  }).catch(()=>alert('token.txt missing or download failed'));
}
</script>
</body>
</html>
"""

@app.route("/")
@login_required
def dashboard():
    return render_template_string(DASH_HTML)

# SSE stream
@app.route('/stream')
@login_required
def stream():
    def gen():
        # send last few logs first
        cur = db.execute("SELECT ts,msg FROM logs ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()[::-1]
        for r in rows:
            payload = {"ts": r["ts"], "msg": r["msg"]}
            yield f"data: {jsonify(payload).get_data(as_text=True)}\n\n"
        while True:
            ts, msg = log_queue.get()
            payload = {"ts": ts, "msg": msg}
            yield f"data: {jsonify(payload).get_data(as_text=True)}\n\n"
    return Response(gen(), mimetype='text/event-stream')

# API stats
@app.route("/api/stats")
@login_required
def api_stats():
    st = db.execute("SELECT * FROM stats LIMIT 1").fetchone()
    uptime_seconds = int(time.time()) - (st["start_time"] or int(time.time()))
    return jsonify({
        "total_messages": int(st["total_messages"]),
        "active_sessions": int(st["active_sessions"]),
        "running_tasks": int(st["running_tasks"]),
        "uptime_seconds": uptime_seconds
    })

# simple APIs to update stats (for worker integration)
@app.route("/api/inc_message", methods=["POST"])
@login_required
def inc_message():
    n = int(request.form.get("n", 1))
    db.execute("UPDATE stats SET total_messages = total_messages + ? WHERE id = 1", (n,))
    db.commit()
    append_log(f"Messages +{n}")
    return jsonify({"ok":True})

@app.route("/api/set_sessions", methods=["POST"])
@login_required
def set_sessions():
    n = int(request.form.get("n", 0))
    db.execute("UPDATE stats SET active_sessions = ? WHERE id = 1", (n,))
    db.commit()
    append_log(f"Active sessions set to {n}")
    return jsonify({"ok":True})

@app.route("/api/set_tasks", methods=["POST"])
@login_required
def set_tasks():
    n = int(request.form.get("n", 0))
    db.execute("UPDATE stats SET running_tasks = ? WHERE id = 1", (n,))
    db.commit()
    append_log(f"Running tasks set to {n}")
    return jsonify({"ok":True})

# admin token upload/download
@app.route("/admin/upload_token", methods=["POST"])
@login_required
def upload_token():
    token = request.form.get("token","").strip()
    if not token:
        return jsonify({"ok":False,"error":"empty"}), 400
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    append_log("Token updated (manual)")
    return jsonify({"ok":True})

@app.route("/admin/download_tokens")
@login_required
def download_tokens():
    if os.path.exists(TOKEN_FILE):
        return send_from_directory(".", TOKEN_FILE, as_attachment=False)
    return ("", 404)

# demo endpoints to add sessions/tasks
@app.route("/admin/add_demo_session", methods=["POST"])
@login_required
def add_demo_session():
    name = request.form.get("name","session")
    ts = int(time.time())
    db.execute("INSERT INTO sessions (name, created) VALUES (?, ?)", (name, ts))
    db.execute("UPDATE stats SET active_sessions = active_sessions + 1 WHERE id = 1")
    db.commit()
    append_log(f"Session created: {name}")
    return jsonify({"ok":True})

@app.route("/admin/add_demo_task", methods=["POST"])
@login_required
def add_demo_task():
    name = request.form.get("name","task")
    ts = int(time.time())
    db.execute("INSERT INTO tasks (name, status, created) VALUES (?, ?, ?)", (name, "running", ts))
    db.execute("UPDATE stats SET running_tasks = running_tasks + 1 WHERE id = 1")
    db.commit()
    append_log(f"Task started: {name}")
    return jsonify({"ok":True})

# logs
@app.route("/admin/logs")
@login_required
def view_logs():
    rows = db.execute("SELECT ts,msg FROM logs ORDER BY id DESC LIMIT 200").fetchall()
    return jsonify([{"ts": r["ts"], "msg": r["msg"]} for r in rows])

# static helper
@app.route("/static/<path:p>")
def static_files(p):
    return send_from_directory(STATIC_FOLDER, p)

# create fallback bg.jpg if missing
default_bg = os.path.join(STATIC_FOLDER, "bg.jpg")
if not os.path.exists(default_bg):
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (1200, 2000), "#0b1220")
        draw = ImageDraw.Draw(img)
        # soft blurred gradient-ish
        for i in range(200):
            draw.rectangle([0, i*10, 1200, (i+1)*10], fill=(7+i%30, 18+i%50, 32+i%80))
        img.save(default_bg, quality=80)
    except Exception:
        pass

# graceful shutdown
def close_db():
    try:
        db.close()
    except:
        pass
atexit.register(close_db)

append_log("UI updated - dashboard ready")

if __name__ == "__main__":
    print("Starting app on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
