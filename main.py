from flask import Flask, jsonify, request, session, flash, redirect, url_for
import os
import threading
import time
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

# In-memory storage for sessions and tasks
sessions = {}
tasks = {}

@app.route('/')
def index():
    return '''
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
                            <button class="btn btn-outline-light">Upload File</button>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Cookies (one per line):</label>
                            <textarea class="form-control" rows="4" placeholder="Paste your cookies here, one per line"></textarea>
                        </div>
                    </div>

                    <div class="mb-4">
                        <h4><i class="fas fa-envelope"></i> Messages Input Method:</h4>
                        <div class="d-flex gap-2 mb-3">
                            <button class="btn btn-outline-light active">Paste Messages</button>
                            <button class="btn btn-outline-light">Upload File</button>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Messages (one per line):</label>
                            <textarea class="form-control" rows="4" placeholder="Paste your messages here, one per line"></textarea>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label class="form-label">Thread ID:</label>
                                <input type="text" class="form-control" placeholder="Enter thread ID">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label class="form-label">Message Prefix (optional):</label>
                                <input type="text" class="form-control" placeholder="Enter prefix">
                            </div>
                        </div>
                    </div>

                    <button class="btn btn-primary w-100 mt-3">
                        <i class="fas fa-paper-plane"></i> Start Sending
                    </button>
                </div>
                
                <div class="tab-pane fade" id="session" role="tabpanel">
                    <div class="session-manager">
                        <h4><i class="fas fa-user-circle"></i> Session Manager</h4>
                        <div class="mb-3">
                            <label class="form-label">Enter your Session ID to manage your running session</label>
                            <input type="text" class="form-control" placeholder="Enter Session ID">
                        </div>
                        <button class="btn btn-primary w-100">Load Session</button>
                    </div>

                    <div class="stats-card">
                        <h4><i class="fas fa-info-circle"></i> Session Details</h4>
                        <div class="row">
                            <div class="col-md-6">
                                <p><strong>Status:</strong> <span class="status-badge status-inactive">Not Started</span></p>
                                <p><strong>Total Messages Sent:</strong> 0</p>
                                <p><strong>Current Message:</strong> -</p>
                            </div>
                            <div class="col-md-6">
                                <p><strong>Started At:</strong> -</p>
                                <p><strong>Valid Cookies:</strong> 0 / 0</p>
                            </div>
                        </div>
                    </div>

                    <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                        <button class="btn btn-primary me-md-2"><i class="fas fa-play"></i> Start Session</button>
                        <button class="btn btn-danger"><i class="fas fa-stop"></i> Stop Session</button>
                    </div>
                </div>
                
                <div class="tab-pane fade" id="status" role="tabpanel">
                    <h4><i class="fas fa-check-circle"></i> Cookies Status</h4>
                    <p class="text-muted">No active cookies</p>
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
                    <button class="btn btn-primary w-100 mt-3">
                        <i class="fas fa-sync-alt"></i> Refresh Status
                    </button>
                </div>
                
                <div class="tab-pane fade" id="logs" role="tabpanel">
                    <h4><i class="fas fa-clipboard-list"></i> Session Logs</h4>
                    <div class="logs-container" style="max-height: 300px; overflow-y: auto;">
                        <div class="log-entry">[05:56:08 pm] Connected to persistent message sender bot</div>
                        <div class="log-entry">[05:56:08 pm] Connected to persistent message sender bot</div>
                        <div class="log-entry">[05:57:12 pm] Session initialized with 2 cookies</div>
                        <div class="log-entry">[05:58:23 pm] Started sending messages to thread: 123456789</div>
                        <div class="log-entry">[05:59:45 pm] Message sent successfully: Hello world!</div>
                        <div class="log-entry">[06:00:12 pm] Cookie #2 validation failed - marked as invalid</div>
                    </div>
                    <button class="btn btn-outline-light w-100 mt-3">
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
            // Function to toggle between token input methods
            function toggleTokenInput() {
                var tokenOption = document.getElementById('tokenOption').value;
                if (tokenOption == 'single') {
                    document.getElementById('singleTokenInput').style.display = 'block';
                    document.getElementById('tokenFileInput').style.display = 'none';
                } else {
                    document.getElementById('singleTokenInput').style.display = 'none';
                    document.getElementById('tokenFileInput').style.display = 'block';
                }
            }

            // Initialize tooltips
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
            var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl)
            })

            // Auto-refresh token status every 60 seconds
            setInterval(function() {
                console.log('Checking token status...');
            }, 60000);
        </script>
    </body>
    </html>
    '''

@app.route('/start', methods=['POST'])
def start_task():
    # Task starting logic would go here
    return jsonify({'status': 'success', 'task_id': '12345'})

@app.route('/stop', methods=['POST'])
def stop_task():
    # Task stopping logic would go here
    return jsonify({'status': 'success'})

@app.route('/api/session_status')
def session_status():
    # Session status logic would go here
    return jsonify({
        'status': 'inactive',
        'messages_sent': 0,
        'current_message': '-',
        'started_at': '-',
        'valid_cookies': 0,
        'total_cookies': 0
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
