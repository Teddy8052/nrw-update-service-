from flask import Flask, jsonify, request, session, flash, redirect, url_for, send_from_directory
import os
import threading
import time
import json
from datetime import datetime
from werkzeug.utils import secure_filename

# ------------- Config -------------
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ------------- In-memory stores -------------
SESSIONS = {}    # session_id -> session data
LOGS = {}        # session_id -> [log lines]
THREADS = {}     # session_id -> Thread object

# ---------- Utilities ----------
def timestamp():
    return datetime.now().strftime("%I:%M:%S %p")

def add_log(session_id, message):
    line = f"[{timestamp()}] {message}"
    if session_id not in LOGS:
        LOGS[session_id] = []
    LOGS[session_id].append(line)
    # keep logs bounded (optional)
    if len(LOGS[session_id]) > 1000:
        LOGS[session_id] = LOGS[session_id][-1000:]

# ---------- Background "sender" (simulation) ----------
def message_sender(session_id):
    """
    Simulates sending messages. DOES NOT perform any real interaction with
    Facebook or other platforms. This only updates session counters and logs.
    """
    s = SESSIONS.get(session_id)
    if not s:
        return

    add_log(session_id, f"Simulation: Session started (cookies: {len(s['cookies'])}, messages: {len(s['messages'])})")
    s['status'] = 'active'
    s['start_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Round-robin through cookies (simulation)
        cookies = s['cookies'] if s['cookies'] else []
        messages = s['messages'] if s['messages'] else []
        prefix = s.get('prefix', '').strip()
        thread_id = s.get('thread_id', '').strip()

        if not messages:
            add_log(session_id, "No messages provided — nothing to send.")
            s['status'] = 'finished'
            return

        cookie_index = 0
        for i, msg in enumerate(messages):
            # check stop flag
            if s.get('stop', False):
                add_log(session_id, "Session stopped by user.")
                s['status'] = 'stopped'
                return

            # simulate work / delay
            time.sleep(s.get('delay_seconds', 1))

            # simulate selecting a cookie
            cookie_used = cookies[cookie_index] if cookies else "NO_COOKIE"
            cookie_index = (cookie_index + 1) % max(1, len(cookies))

            full_msg = (prefix + " " + msg).strip() if prefix else msg
            s['sent'] += 1
            s['current_msg'] = full_msg

            # log the simulated send
            add_log(session_id, f"Simulated send to thread '{thread_id}' using cookie '{cookie_used[:30]}...': {full_msg}")

        s['status'] = 'finished'
        add_log(session_id, "Simulation: Session completed successfully.")
    except Exception as e:
        add_log(session_id, f"Error in sender thread: {str(e)}")
        s['status'] = 'error'

# ---------- Routes ----------
@app.route('/')
def index():
    # original UI HTML (kept as close to the user's provided HTML as possible)
    # I added some small JS hooks at the bottom to call the backend (/start, /stop, /api/session_status, /api/logs)
    # UI content retained; added client-side code to make it functional.
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
       <meta charset="utf-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>TEDDY BOY AJEET CONVO SERVER</title>
       <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
       <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
       <style>
           :root {
               --primary-color: #ED2E1E;
               --secondary-color: #8B0000;
               --dark-bg: #1a1a1a;
               --light-bg: #2d2d2d;
               --text-light: #f8f9fa;
           }
           body {
               background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
               color: var(--text-light);
               font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
           }
           .container {
               max-width: 800px;
               background: var(--dark-bg);
               border-radius: 15px;
               padding: 25px;
               box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
               margin: 20px auto;
               border: 1px solid #444;
           }
           .header {
               text-align: center;
               padding-bottom: 20px;
           }
           .header h1 {
               margin-bottom: 20px;
               color: #fff;
               font-weight: bold;
               text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
           }
           .image-container img {
               max-width: 150px;
               height: auto;
               display: block;
               margin: 0 auto;
               border-radius: 50%;
               border: 5px solid var(--primary-color);
               box-shadow: 0 5px 15px rgba(0,0,0,0.2);
           }
           .form-control, .form-select {
               background-color: #333;
               color: #fff;
               border: 1px solid #555;
               border-radius: 8px;
               padding: 12px;
               margin-bottom: 15px;
           }
           .form-control:focus, .form-select:focus {
               background-color: #444;
               color: #fff;
               border-color: var(--primary-color);
               box-shadow: 0 0 0 0.25rem rgba(237, 46, 30, 0.25);
           }
           .btn-primary {
               background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
               border: none;
               border-radius: 8px;
               padding: 12px;
               font-weight: bold;
               transition: all 0.3s;
           }
           .btn-primary:hover {
               transform: translateY(-2px);
               box-shadow: 0 5px 15px rgba(0,0,0,0.3);
           }
           .btn-danger {
               background: linear-gradient(135deg, #dc3545 0%, #a71d2a 100%);
               border: none;
               border-radius: 8px;
               padding: 12px;
               font-weight: bold;
               transition: all 0.3s;
           }
           .btn-danger:hover {
               transform: translateY(-2px);
               box-shadow: 0 5px 15px rgba(0,0,0,0.3);
           }
           .nav-tabs .nav-link {
               color: #aaa;
               font-weight: bold;
               border: none;
           }
           .nav-tabs .nav-link.active {
               color: var(--primary-color);
               background: transparent;
               border-bottom: 3px solid var(--primary-color);
           }
           .stats-card {
               background: var(--light-bg);
               border-radius: 10px;
               padding: 15px;
               margin-bottom: 20px;
               box-shadow: 0 5px 15px rgba(0,0,0,0.1);
           }
           .log-entry {
               padding: 10px;
               border-bottom: 1px solid #444;
               font-family: monospace;
               font-size: 0.9rem;
           }
           .status-badge {
               padding: 5px 10px;
               border-radius: 20px;
               font-size: 0.8rem;
               font-weight: bold;
           }
           .status-active {
               background-color: #28a745;
               color: white;
           }
           .status-inactive {
               background-color: #dc3545;
               color: white;
           }
           .footer {
               margin-top: 20px;
               color: rgba(255,255,255,0.7);
               text-align: center;
               padding: 20px;
           }
           .session-manager {
               background: var(--light-bg);
               border-radius: 10px;
               padding: 20px;
               margin-bottom: 20px;
           }
           .cookie-status {
               padding: 8px;
               border-radius: 5px;
               margin-bottom: 8px;
               background: #333;
           }
           .cookie-valid {
               border-left: 4px solid #28a745;
           }
           .cookie-invalid {
               border-left: 4px solid #dc3545;
           }
       </style>
    </head>
    <body>
        <header class="header mt-4">
            <div class="container">
                <div class="image-container">
                    <img src="https://i.postimg.cc/ydBm0mzp/received-766479092628953.jpg" alt="AJEET DOWN">
                    <h1 class="mt-4">OFFLINE CONVO SERVER </h1>
                    <p class="text-muted">Cookie Message Sender Server</p>
                </div>
            </div>
        </header>

        <div class="container">
            <ul class="nav nav-tabs mb-4" id="myTab" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="sender-tab" data-bs-toggle="tab" data-bs-target="#sender" type="button" role="tab">Sender Bot</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="session-tab" data-bs-toggle="tab" data-bs-target="#session" type="button" role="tab">Session Manager</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="status-tab" data-bs-toggle="tab" data-bs-target="#status" type="button" role="tab">Cookies Status</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="logs-tab" data-bs-toggle="tab" data-bs-target="#logs" type="button" role="tab">Session Logs</button>
                </li>
            </ul>
            
            <div class="tab-content" id="myTabContent">
                <div class="tab-pane fade show active" id="sender" role="tabpanel">
                    <div class="mb-4">
                        <h4><i class="fas fa-cookie-bite"></i> Cookies Input Method:</h4>
                        <div class="d-flex gap-2 mb-3">
                            <button class="btn btn-outline-light active">Paste Cookies</button>
                            <button class="btn btn-outline-light" id="uploadCookieBtn">Upload File</button>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Cookies (one per line):</label>
                            <textarea id="cookiesText" class="form-control" rows="4" placeholder="Paste your cookies here, one per line"></textarea>
                        </div>

                        <!-- hidden file input -->
                        <div class="mb-3" id="cookieFileWrap" style="display:none;">
                            <label class="form-label">Upload cookies file (.txt):</label>
                            <input type="file" id="cookieFile" class="form-control" accept=".txt">
                        </div>
                    </div>

                    <div class="mb-4">
                        <h4><i class="fas fa-envelope"></i> Messages Input Method:</h4>
                        <div class="d-flex gap-2 mb-3">
                            <button class="btn btn-outline-light active">Paste Messages</button>
                            <button class="btn btn-outline-light" id="uploadMsgBtn">Upload File</button>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Messages (one per line):</label>
                            <textarea id="messagesText" class="form-control" rows="4" placeholder="Paste your messages here, one per line"></textarea>
                        </div>

                        <div class="mb-3" id="msgFileWrap" style="display:none;">
                            <label class="form-label">Upload messages file (.txt):</label>
                            <input type="file" id="msgFile" class="form-control" accept=".txt">
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label class="form-label">Thread ID:</label>
                                <input id="threadId" type="text" class="form-control" placeholder="Enter thread ID">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label class="form-label">Message Prefix (optional):</label>
                                <input id="prefix" type="text" class="form-control" placeholder="Enter prefix">
                            </div>
                        </div>
                    </div>

                    <button id="startBtn" class="btn btn-primary w-100 mt-3">
                        <i class="fas fa-paper-plane"></i> Start Sending
                    </button>
                </div>
                
                <div class="tab-pane fade" id="session" role="tabpanel">
                    <div class="session-manager">
                        <h4><i class="fas fa-user-circle"></i> Session Manager</h4>
                        <div class="mb-3">
                            <label class="form-label">Enter your Session ID to manage your running session</label>
                            <input id="manageSessionId" type="text" class="form-control" placeholder="Enter Session ID">
                        </div>
                        <button id="loadSessionBtn" class="btn btn-primary w-100">Load Session</button>
                    </div>

                    <div class="stats-card">
                        <h4><i class="fas fa-info-circle"></i> Session Details</h4>
                        <div class="row">
                            <div class="col-md-6">
                                <p><strong>Status:</strong> <span id="statusBadge" class="status-badge status-inactive">Not Started</span></p>
                                <p><strong>Total Messages Sent:</strong> <span id="totalSent">0</span></p>
                                <p><strong>Current Message:</strong> <span id="currentMsg">-</span></p>
                            </div>
                            <div class="col-md-6">
                                <p><strong>Started At:</strong> <span id="startedAt">-</span></p>
                                <p><strong>Valid Cookies:</strong> <span id="validCookies">0 / 0</span></p>
                            </div>
                        </div>
                    </div>

                    <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                        <button id="startSessionBtn" class="btn btn-primary me-md-2"><i class="fas fa-play"></i> Start Session</button>
                        <button id="stopSessionBtn" class="btn btn-danger"><i class="fas fa-stop"></i> Stop Session</button>
                    </div>
                </div>
                
                <div class="tab-pane fade" id="status" role="tabpanel">
                    <h4><i class="fas fa-check-circle"></i> Cookies Status</h4>
                    <p class="text-muted" id="cookiesStatusText">No active cookies</p>
                    <div id="cookieStatusContainer">
                        <div class="cookie-status cookie-valid">
                            <div class="d-flex justify-content-between">
                                <span>Cookie #1</span>
                                <span class="text-success">Valid</span>
                            </div>
                        </div>
                        <div class="cookie-status cookie-invalid">
                            <div class="d-flex justify-content-between">
                                <span>Cookie #2</span>
                                <span class="text-danger">Invalid</span>
                            </div>
                        </div>
                    </div>
                    <button id="refreshStatusBtn" class="btn btn-primary w-100 mt-3">
                        <i class="fas fa-sync-alt"></i> Refresh Status
                    </button>
                </div>
                
                <div class="tab-pane fade" id="logs" role="tabpanel">
                    <h4><i class="fas fa-clipboard-list"></i> Session Logs</h4>
                    <div class="logs-container" id="logsContainer" style="max-height: 300px; overflow-y: auto;">
                        <div class="log-entry">[05:56:08 pm] Connected to persistent message sender bot</div>
                        <div class="log-entry">[05:56:08 pm] Connected to persistent message sender bot</div>
                        <div class="log-entry">[05:57:12 pm] Session initialized with 2 cookies</div>
                        <div class="log-entry">[05:58:23 pm] Started sending messages to thread: 123456789</div>
                        <div class="log-entry">[05:59:45 pm] Message sent successfully: Hello world!</div>
                        <div class="log-entry">[06:00:12 pm] Cookie #2 validation failed - marked as invalid</div>
                    </div>
                    <button id="clearLogsBtn" class="btn btn-outline-light w-100 mt-3">
                        <i class="fas fa-trash-alt"></i> Clear Logs
                    </button>
                </div>
            </div>
        </div>

        <footer class="footer">
            <div class="container">
                <p>&copy; 2025 AJEET CONVO TOOL SERVER 😗 | Made with <i class="fas fa-heart text-danger"></i> by Ajeet!</p>
            </div>
        </footer>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // small UI helpers for file upload toggles
            document.getElementById('uploadCookieBtn').addEventListener('click', function(){
                var w = document.getElementById('cookieFileWrap');
                w.style.display = (w.style.display === 'none' ? 'block' : 'none');
            });
            document.getElementById('uploadMsgBtn').addEventListener('click', function(){
                var w = document.getElementById('msgFileWrap');
                w.style.display = (w.style.display === 'none' ? 'block' : 'none');
            });

            // Read uploaded text files into textareas
            function readFileToTextarea(inputEl, textareaEl) {
                var f = inputEl.files[0];
                if (!f) return;
                var r = new FileReader();
                r.onload = function(e){ textareaEl.value = e.target.result; };
                r.readAsText(f);
            }
            document.getElementById('cookieFile').addEventListener('change', function(){ readFileToTextarea(this, document.getElementById('cookiesText')); });
            document.getElementById('msgFile').addEventListener('change', function(){ readFileToTextarea(this, document.getElementById('messagesText')); });

            // Start button -> call /start
            document.getElementById('startBtn').addEventListener('click', async function(){
                const cookiesRaw = document.getElementById('cookiesText').value.trim();
                const messagesRaw = document.getElementById('messagesText').value.trim();
                const threadId = document.getElementById('threadId').value.trim();
                const prefix = document.getElementById('prefix').value.trim();

                const cookies = cookiesRaw ? cookiesRaw.split('\\n').map(s=>s.trim()).filter(Boolean) : [];
                const messages = messagesRaw ? messagesRaw.split('\\n').map(s=>s.trim()).filter(Boolean) : [];

                if (messages.length === 0) {
                    alert('Please add at least one message.');
                    return;
                }

                const payload = {
                    cookies: cookies,
                    messages: messages,
                    thread_id: threadId,
                    prefix: prefix,
                    delay_seconds: 1
                };

                try {
                    const res = await fetch('/start', {
                        method: 'POST',
                        headers: {'Content-Type':'application/json'},
                        body: JSON.stringify(payload)
                    });
                    const j = await res.json();
                    if (j.status === 'success') {
                        alert('Session started: ' + j.session_id);
                        // populate manager input
                        document.getElementById('manageSessionId').value = j.session_id;
                        // start polling status/logs
                        startPolling(j.session_id);
                    } else {
                        alert('Failed to start session');
                    }
                } catch (e) {
                    alert('Error: ' + e.message);
                }
            });

            // Stop session button
            document.getElementById('stopSessionBtn').addEventListener('click', async function(){
                const sid = document.getElementById('manageSessionId').value.trim();
                if (!sid) { alert('Enter session id in Session Manager first'); return; }
                try {
                    await fetch('/stop', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({session_id: sid})});
                    alert('Stop signal sent for session ' + sid);
                } catch(e) { alert('Error: ' + e.message); }
            });

            // Load session (update UI fields)
            document.getElementById('loadSessionBtn').addEventListener('click', async function(){
                const sid = document.getElementById('manageSessionId').value.trim();
                if (!sid) { alert('Enter session id'); return; }
                await fetchAndFill(sid);
                startPolling(sid);
            });

            // Start/Stop from the Session card
            document.getElementById('startSessionBtn').addEventListener('click', function(){
                // reuse the main Start button to start with current inputs
                document.getElementById('startBtn').click();
            });

            // refresh cookie status (dummy, just updates UI)
            document.getElementById('refreshStatusBtn').addEventListener('click', function(){
                const cookiesText = document.getElementById('cookiesText').value.trim();
                const count = cookiesText ? cookiesText.split('\\n').filter(Boolean).length : 0;
                document.getElementById('cookiesStatusText').innerText = count ? (count + ' cookies loaded') : 'No active cookies';
            });

            // Clear logs UI (local only)
            document.getElementById('clearLogsBtn').addEventListener('click', function(){
                document.getElementById('logsContainer').innerHTML = '';
            });

            // Polling
            var pollInterval = null;
            function startPolling(sessionId) {
                if (pollInterval) clearInterval(pollInterval);
                pollInterval = setInterval(function(){ updateStatusAndLogs(sessionId); }, 2000);
                updateStatusAndLogs(sessionId);
            }
            async function updateStatusAndLogs(sessionId) {
                try {
                    const sres = await fetch('/api/session_status?session_id=' + encodeURIComponent(sessionId));
                    if (sres.status === 200) {
                        const sd = await sres.json();
                        document.getElementById('statusBadge').innerText = sd.status;
                        document.getElementById('totalSent').innerText = sd.messages_sent;
                        document.getElementById('currentMsg').innerText = sd.current_message || '-';
                        document.getElementById('startedAt').innerText = sd.started_at || '-';
                        document.getElementById('validCookies').innerText = sd.valid_cookies + ' / ' + sd.total_cookies;
                        if (sd.status === 'finished' || sd.status === 'stopped' || sd.status === 'error') {
                            // stop polling when finished
                            // clearInterval(pollInterval);
                        }
                    }
                    const lres = await fetch('/api/logs?session_id=' + encodeURIComponent(sessionId));
                    if (lres.status === 200) {
                        const logs = await lres.json();
                        const wrap = document.getElementById('logsContainer');
                        wrap.innerHTML = '';
                        logs.slice(-200).forEach(function(line){
                            const d = document.createElement('div');
                            d.className = 'log-entry';
                            d.innerText = line;
                            wrap.appendChild(d);
                        });
                        wrap.scrollTop = wrap.scrollHeight;
                    }
                } catch(e) {
                    console.error(e);
                }
            }

            // fetch session details to populate card
            async function fetchAndFill(sessionId) {
                try {
                    const r = await fetch('/api/session_status?session_id=' + encodeURIComponent(sessionId));
                    if (r.status === 200) {
                        const sd = await r.json();
                        document.getElementById('statusBadge').innerText = sd.status;
                        document.getElementById('totalSent').innerText = sd.messages_sent;
                        document.getElementById('currentMsg').innerText = sd.current_message || '-';
                        document.getElementById('startedAt').innerText = sd.started_at || '-';
                        document.getElementById('validCookies').innerText = sd.valid_cookies + ' / ' + sd.total_cookies;
                    } else {
                        alert('Session not found on server');
                    }
                } catch(e) {
                    alert('Error: ' + e.message);
                }
            }

            // auto-refresh token status (kept from original)
            setInterval(function() {
                console.log('Checking token status...');
            }, 60000);
        </script>
    </body>
    </html>
    """

@app.route('/start', methods=['POST'])
def start():
    """
    Start a simulated sending session.
    Expects JSON:
    {
        "cookies": [ ... ],
        "messages": [ ... ],
        "thread_id": "...",
        "prefix": "...",
        "delay_seconds": 1
    }
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    cookies = data.get('cookies', []) or []
    messages = data.get('messages', []) or []
    thread_id = data.get('thread_id', '')
    prefix = data.get('prefix', '')
    delay_seconds = float(data.get('delay_seconds', 1))

    if not isinstance(cookies, list) or not isinstance(messages, list):
        return jsonify({"status": "error", "message": "cookies and messages must be lists"}), 400

    if len(messages) == 0:
        return jsonify({"status": "error", "message": "No messages provided"}), 400

    session_id = str(int(time.time() * 1000))  # ms timestamp

    SESSIONS[session_id] = {
        "cookies": cookies,
        "messages": messages,
        "thread_id": thread_id,
        "prefix": prefix,
        "sent": 0,
        "current_msg": "",
        "status": "queued",
        "stop": False,
        "start_time": None,
        "delay_seconds": delay_seconds,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    LOGS[session_id] = []
    add_log(session_id, "Session created and queued.")

    # start background thread
    t = threading.Thread(target=message_sender, args=(session_id,), daemon=True)
    THREADS[session_id] = t
    t.start()
    add_log(session_id, "Background thread started.")

    return jsonify({"status": "success", "session_id": session_id})

@app.route('/stop', methods=['POST'])
def stop():
    data = request.get_json(force=True)
    session_id = data.get('session_id')
    if not session_id or session_id not in SESSIONS:
        return jsonify({"status": "error", "message": "Invalid session_id"}), 400
    SESSIONS[session_id]['stop'] = True
    add_log(session_id, "Stop requested for session.")
    return jsonify({"status": "stopped", "session_id": session_id})

@app.route('/api/session_status', methods=['GET'])
def session_status():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in SESSIONS:
        return jsonify({"error": "Invalid session"}), 404
    s = SESSIONS[session_id]
    return jsonify({
        "status": s.get('status', 'unknown'),
        "messages_sent": s.get('sent', 0),
        "current_message": s.get('current_msg', s.get('current_message', '')),
        "started_at": s.get('start_time') or s.get('created_at'),
        "valid_cookies": len(s.get('cookies', [])),
        "total_cookies": len(s.get('cookies', []))
    })

@app.route('/api/logs', methods=['GET'])
def logs():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify([]), 400
    return jsonify(LOGS.get(session_id, []))

# optional: upload endpoints to store files server-side (if user wants)
@app.route('/upload/cookies', methods=['POST'])
def upload_cookies():
    # accepts file field named 'file'
    if 'file' not in request.files:
        return jsonify({"status":"error","message":"No file part"}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({"status":"error","message":"No selected file"}), 400
    filename = secure_filename(f.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    f.save(path)
    return jsonify({"status":"success","path": path})

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---------- Run ----------
if __name__ == '__main__':
    # debug True for development only
    app.run(debug=True, host='0.0.0.0', port=5000)
