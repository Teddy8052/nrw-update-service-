const express = require('express');
const multer = require('multer');
const pino = require('pino');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const { default: makeWASocket, Browsers, delay, useMultiFileAuthState, makeCacheableSignalKeyStore, DisconnectReason } = require("@whiskeysockets/baileys");
const NodeCache = require('node-cache');
const bodyParser = require('body-parser');
const moment = require('moment-timezone');

const app = express();
const upload = multer({
  limits: {
    fileSize: 10 * 1024 * 1024, // 10MB max file size
  }
});

// Improved session management with cleanup
const activeSessions = new Map();
const sessionLogs = new Map();

// Memory management
const MAX_MESSAGES_PER_SESSION = 1000;
const SESSION_CLEANUP_INTERVAL = 5 * 60 * 1000; // Cleanup every 5 minutes

app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json({ limit: '10mb' }));

// Session cleanup interval
setInterval(() => {
  cleanupInactiveSessions();
}, SESSION_CLEANUP_INTERVAL);

function cleanupInactiveSessions() {
  const now = Date.now();
  for (const [sessionKey, session] of activeSessions.entries()) {
    if (session.lastActivity && (now - session.lastActivity > 30 * 60 * 1000)) {
      // Session inactive for 30 minutes, clean it up
      if (session.running) {
        session.running = false;
        addSessionLog(sessionKey, 'Session auto-cleaned due to inactivity', 'info');
      }
      
      const sessionDir = path.join(__dirname, 'sessions', sessionKey);
      if (fs.existsSync(sessionDir)) {
        fs.rmSync(sessionDir, { recursive: true, force: true });
      }
      
      activeSessions.delete(sessionKey);
      sessionLogs.delete(sessionKey);
    }
  }
}

// Serve the HTML form with Kakashi lightning-style UI
app.get('/', (req, res) => {
  const formHtml = `
      <!DOCTYPE html>
      <html lang="en">
      <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>WhatsApp Server | By GoDxDeViL</title>
          <style>
              :root {
                  --electric-blue: #00aaff;
                  --electric-purple: #8844ee;
                  --electric-cyan: #00ffee;
                  --electric-pink: #ff44aa;
                  --electric-yellow: #ffee00;
                  --dark-bg: #0a0a1a;
                  --darker-bg: #050510;
              }
              
              body {
                  font-family: 'Arial', sans-serif;
                  margin: 0;
                  padding: 0;
                  background-color: var(--dark-bg);
                  color: #ffffff;
                  background-image: 
                      radial-gradient(circle at 10% 20%, rgba(0, 170, 255, 0.1) 0%, transparent 20%),
                      radial-gradient(circle at 90% 60%, rgba(136, 68, 238, 0.1) 0%, transparent 20%),
                      radial-gradient(circle at 50% 80%, rgba(0, 255, 238, 0.1) 0%, transparent 20%);
                  min-height: 100vh;
              }
              
              .header {
                  display: flex;
                  justify-content: space-between;
                  align-items: center;
                  padding: 15px 30px;
                  background-color: var(--darker-bg);
                  border-bottom: 1px solid var(--electric-blue);
                  box-shadow: 0 0 15px rgba(0, 170, 255, 0.3);
              }
              
              .logo {
                  font-size: 24px;
                  font-weight: bold;
                  background: linear-gradient(45deg, var(--electric-blue), var(--electric-cyan));
                  -webkit-background-clip: text;
                  -webkit-text-fill-color: transparent;
                  text-shadow: 0 0 10px rgba(0, 170, 255, 0.5);
              }
              
              .header button {
                  background: linear-gradient(45deg, var(--electric-blue), var(--electric-purple));
                  color: white;
                  border: none;
                  padding: 10px 20px;
                  font-size: 16px;
                  cursor: pointer;
                  border-radius: 30px;
                  transition: all 0.3s ease;
                  box-shadow: 0 0 10px rgba(0, 170, 255, 0.5);
              }
              
              .header button:hover {
                  transform: translateY(-2px);
                  box-shadow: 0 0 15px rgba(0, 170, 255, 0.8);
              }
              
              .container {
                  max-width: 800px;
                  margin: 30px auto;
                  padding: 30px;
                  background-color: rgba(10, 10, 26, 0.8);
                  backdrop-filter: blur(10px);
                  border-radius: 15px;
                  box-shadow: 
                      0 0 20px rgba(0, 170, 255, 0.3),
                      0 0 40px rgba(136, 68, 238, 0.2);
                  border: 1px solid rgba(0, 170, 255, 0.2);
              }
              
              h1 {
                  text-align: center;
                  background: linear-gradient(45deg, var(--electric-blue), var(--electric-cyan), var(--electric-purple));
                  -webkit-background-clip: text;
                  -webkit-text-fill-color: transparent;
                  text-shadow: 0 0 15px rgba(0, 170, 255, 0.5);
                  margin-bottom: 30px;
                  font-size: 32px;
              }
              
              form {
                  display: flex;
                  flex-direction: column;
              }
              
              .form-group {
                  margin-bottom: 20px;
                  position: relative;
              }
              
              label {
                  display: block;
                  margin-bottom: 8px;
                  font-weight: bold;
                  color: var(--electric-cyan);
              }
              
              input, textarea, select {
                  width: 100%;
                  padding: 12px 15px;
                  border: 2px solid transparent;
                  border-radius: 8px;
                  font-size: 16px;
                  background-color: rgba(5, 5, 16, 0.8);
                  color: #ffffff;
                  transition: all 0.3s ease;
                  box-sizing: border-box;
              }
              
              input:focus, textarea:focus, select:focus {
                  outline: none;
                  border-color: var(--electric-blue);
                  box-shadow: 0 0 15px rgba(0, 170, 255, 0.5);
              }
              
              /* Unique colors for each input when focused */
              #creds:focus { border-color: var(--electric-blue); box-shadow: 0 0 15px rgba(0, 170, 255, 0.5); }
              #sms:focus { border-color: var(--electric-purple); box-shadow: 0 0 15px rgba(136, 68, 238, 0.5); }
              #targetType:focus { border-color: var(--electric-cyan); box-shadow: 0 0 15px rgba(0, 255, 238, 0.5); }
              #targetNumber:focus { border-color: var(--electric-pink); box-shadow: 0 0 15px rgba(255, 68, 170, 0.5); }
              #hatersName:focus { border-color: var(--electric-yellow); box-shadow: 0 0 15px rgba(255, 238, 0, 0.5); }
              #timeDelay:focus { border-color: var(--electric-blue); box-shadow: 0 0 15px rgba(0, 170, 255, 0.5); }
              #sessionKey:focus { border-color: var(--electric-purple); box-shadow: 0 0 15px rgba(136, 68, 238, 0.5); }
              
              button {
                  padding: 12px 25px;
                  background: linear-gradient(45deg, var(--electric-blue), var(--electric-purple));
                  color: white;
                  border: none;
                  border-radius: 30px;
                  cursor: pointer;
                  font-size: 16px;
                  font-weight: bold;
                  transition: all 0.3s ease;
                  margin-top: 10px;
                  box-shadow: 0 0 15px rgba(0, 170, 255, 0.3);
              }
              
              button:hover {
                  transform: translateY(-2px);
                  box-shadow: 0 0 20px rgba(0, 170, 255, 0.5);
              }
              
              .session-key-display {
                  background: linear-gradient(45deg, var(--electric-blue), var(--electric-purple));
                  padding: 15px;
                  border-radius: 8px;
                  margin-top: 20px;
                  text-align: center;
                  display: none;
                  animation: pulse 2s infinite;
              }
              
              @keyframes pulse {
                  0% { box-shadow: 0 0 10px rgba(0, 170, 255, 0.5); }
                  50% { box-shadow: 0 0 20px rgba(0, 170, 255, 0.8); }
                  100% { box-shadow: 0 0 10px rgba(0, 170, 255, 0.5); }
              }
              
              .session-key-display h3 {
                  margin-top: 0;
                  color: white;
              }
              
              .session-key {
                  font-size: 18px;
                  font-weight: bold;
                  letter-spacing: 1px;
                  background-color: rgba(0, 0, 0, 0.3);
                  padding: 10px;
                  border-radius: 5px;
                  display: inline-block;
              }
              
              .logs-container {
                  margin-top: 30px;
                  background-color: rgba(5, 5, 16, 0.8);
                  border-radius: 8px;
                  padding: 15px;
                  max-height: 300px;
                  overflow-y: auto;
                  font-family: monospace;
                  font-size: 14px;
              }
              
              .log-entry {
                  margin-bottom: 8px;
                  padding: 5px 10px;
                  border-radius: 4px;
              }
              
              .log-time {
                  color: var(--electric-cyan);
                  margin-right: 10px;
              }
              
              .log-success {
                  color: #00ff00;
                  background-color: rgba(0, 255, 0, 0.1);
              }
              
              .log-error {
                  color: #ff0000;
                  background-color: rgba(255, 0, 0, 0.1);
              }
              
              .log-info {
                  color: var(--electric-blue);
              }
              
              .log-warning {
                  color: #ff9900;
                  background-color: rgba(255, 153, 0, 0.1);
              }
              
              footer {
                  text-align: center;
                  margin-top: 40px;
                  padding: 20px;
                  font-size: 14px;
                  color: rgba(255, 255, 255, 0.6);
                  border-top: 1px solid rgba(0, 170, 255, 0.2);
              }
              
              footer a {
                  color: var(--electric-cyan);
                  text-decoration: none;
                  transition: all 0.3s ease;
              }
              
              footer a:hover {
                  text-decoration: underline;
                  text-shadow: 0 0 10px rgba(0, 255, 238, 0.5);
              }
          </style>
      </head>
      <body>
          <div class="header">
              <div class="logo">WHATSAPP SERVER</div>
              <button onclick="window.location.href='https://whatsapp-token-extractor-by-tabbu.onrender.com/tabbuqr'">Get Token</button>
          </div>
          <div class="container">
              <h1>WhatsApp Message Sender</h1>
              <form id="sendForm" action="/send" method="post" enctype="multipart/form-data">
                  <div class="form-group">
                      <label for="creds">Paste Your WhatsApp Token:</label>
                      <textarea name="creds" id="creds" rows="4" required></textarea>
                  </div>
                  
                  <div class="form-group">
                      <label for="sms">Select Message File (TXT):</label>
                      <input type="file" name="sms" id="sms" accept=".txt" required>
                  </div>
                  
                  <div class="form-group">
                      <label for="targetType">Select Target Type:</label>
                      <select name="targetType" id="targetType" required>
                          <option value="inbox">Inbox</option>
                          <option value="group">Group</option>
                      </select>
                  </div>
                  
                  <div class="form-group">
                      <label for="targetNumber">Target WhatsApp number or Group ID:</label>
                      <input type="text" name="targetNumber" id="targetNumber" required>
                  </div>
                  
                  <div class="form-group">
                      <label for="hatersName">Enter Hater's Name:</label>
                      <input type="text" name="hatersName" id="hatersName" required>
                  </div>
                  
                  <div class="form-group">
                      <label for="timeDelay">Time delay between messages (in seconds):</label>
                      <input type="number" name="timeDelay" id="timeDelay" min="1" value="5" required>
                  </div>
                  
                  <button type="submit">Start Sending</button>
              </form>
              
              <div class="session-key-display" id="sessionKeyDisplay">
                  <h3>Your Session Key:</h3>
                  <div class="session-key" id="sessionKeyValue"></div>
                  <p>Use this key to stop the session if needed.</p>
              </div>
              
              <form action="/stop" method="post" id="stopForm">
                  <div class="form-group">
                      <label for="sessionKey">Enter Session Key to Stop:</label>
                      <input type="text" name="sessionKey" id="sessionKey" required>
                  </div>
                  <button type="submit">Stop Sending</button>
              </form>
              
              <div class="logs-container" id="logsContainer">
                  <div class="log-entry log-info">
                      <span class="log-time">[${new Date().toLocaleTimeString()}]</span>
                      System ready. Fill the form to start sending messages.
                  </div>
              </div>
          </div>
          
          <footer>
              <p>Designed by <a href="#">EVIL FORCE</a> | ONLY FOR RCB❤️ | Powered by Kakashi Lightning Jutsu</p>
          </footer>
          
          <script>
              const sendForm = document.getElementById('sendForm');
              const sessionKeyDisplay = document.getElementById('sessionKeyDisplay');
              const sessionKeyValue = document.getElementById('sessionKeyValue');
              const logsContainer = document.getElementById('logsContainer');
              
              // Function to add log entry
              function addLog(message, type = 'info') {
                  const time = new Date().toLocaleTimeString();
                  const logEntry = document.createElement('div');
                  logEntry.className = 'log-entry log-' + type;
                  logEntry.innerHTML = '<span class="log-time">[' + time + ']</span> ' + message;
                  logsContainer.appendChild(logEntry);
                  logsContainer.scrollTop = logsContainer.scrollHeight;
              }
              
              // Handle form submission with AJAX
              sendForm.addEventListener('submit', async (e) => {
                  e.preventDefault();
                  
                  const formData = new FormData(sendForm);
                  
                  try {
                      const response = await fetch('/send', {
                          method: 'POST',
                          body: formData
                      });
                      
                      const result = await response.text();
                      
                      if (response.ok) {
                          // Extract session key from response
                          const match = result.match(/Your session key is: ([a-f0-9]+)/);
                          if (match) {
                              const key = match[1];
                              sessionKeyValue.textContent = key;
                              sessionKeyDisplay.style.display = 'block';
                              document.getElementById('sessionKey').value = key;
                              addLog('Message sending started with session key: ' + key, 'success');
                              
                              // Start polling for logs
                              pollLogs(key);
                          }
                      } else {
                          addLog('Error: ' + result, 'error');
                      }
                  } catch (error) {
                      addLog('Error: ' + error.message, 'error');
                  }
              });
              
              // Handle stop form submission
              document.getElementById('stopForm').addEventListener('submit', async (e) => {
                  e.preventDefault();
                  
                  const formData = new FormData(e.target);
                  
                  try {
                      const response = await fetch('/stop', {
                          method: 'POST',
                          body: new URLSearchParams(formData)
                      });
                      
                      const result = await response.text();
                      
                      if (response.ok) {
                          addLog('Session stopped: ' + result, 'info');
                      } else {
                          addLog('Error: ' + result, 'error');
                      }
                  } catch (error) {
                      addLog('Error: ' + error.message, 'error');
                  }
              });
              
              // Poll for logs
              function pollLogs(sessionKey) {
                  const eventSource = new EventSource('/logs/' + sessionKey);
                  
                  eventSource.onmessage = function(event) {
                      const logData = JSON.parse(event.data);
                      addLog(logData.message, logData.type);
                  };
                  
                  eventSource.onerror = function() {
                      addLog('Log connection closed', 'info');
                      eventSource.close();
                  };
              }
          </script>
      </body>
      </html>
  `;
  res.send(formHtml);
});

// Function to add log to a session
function addSessionLog(sessionKey, message, type = 'info') {
  const timestamp = moment().tz('Asia/Kolkata').format('YYYY-MM-DD HH:mm:ss');
  const logEntry = { 
      message: `[${timestamp}] ${message}`,
      type 
  };
  
  // Store log (limit to prevent memory issues)
  if (!sessionLogs.has(sessionKey)) {
      sessionLogs.set(sessionKey, []);
  }
  
  const logs = sessionLogs.get(sessionKey);
  if (logs.length > 100) {
      logs.shift(); // Remove oldest log if exceeding limit
  }
  logs.push(logEntry);
  
  // Send to all connected clients
  if (activeSessions.has(sessionKey)) {
      const session = activeSessions.get(sessionKey);
      if (session.clients) {
          session.clients.forEach(client => {
              if (!client.finished) {
                  client.write(`data: ${JSON.stringify(logEntry)}\n\n`);
              }
          });
      }
  }
}

// SSE endpoint for live logs
app.get('/logs/:sessionKey', (req, res) => {
  const sessionKey = req.params.sessionKey;
  
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('Access-Control-Allow-Origin', '*');
  
  // Send existing logs
  if (sessionLogs.has(sessionKey)) {
      const logs = sessionLogs.get(sessionKey);
      logs.forEach(log => {
          res.write(`data: ${JSON.stringify(log)}\n\n`);
      });
  }
  
  // Store the response object to send future logs
  if (!activeSessions.has(sessionKey)) {
      activeSessions.set(sessionKey, { 
          running: true, 
          clients: [] 
      });
  }
  
  const session = activeSessions.get(sessionKey);
  if (!session.clients) {
      session.clients = [];
  }
  
  session.clients.push(res);
  
  // Remove client when connection closes
  req.on('close', () => {
      if (activeSessions.has(sessionKey)) {
          const session = activeSessions.get(sessionKey);
          if (session.clients) {
              const index = session.clients.indexOf(res);
              if (index !== -1) {
                  session.clients.splice(index, 1);
              }
          }
      }
  });
});

app.post('/send', upload.single('sms'), async (req, res) => {
  const credsEncoded = req.body.creds;
  const smsFile = req.file ? req.file.buffer : null;
  const targetNumber = req.body.targetNumber;
  const targetType = req.body.targetType;
  const timeDelay = parseInt(req.body.timeDelay, 10) * 1000;
  const hatersName = req.body.hatersName;

  if (!smsFile) {
      return res.status(400).send('Message file is required');
  }

  const randomKey = crypto.randomBytes(8).toString('hex'); // Generate a unique key
  const sessionDir = path.join(__dirname, 'sessions', randomKey);

  try {
      // Decode and save creds.json
      const credsDecoded = Buffer.from(credsEncoded, 'base64').toString('utf-8');
      fs.mkdirSync(sessionDir, { recursive: true });
      fs.writeFileSync(path.join(sessionDir, 'creds.json'), credsDecoded);

      // Read SMS content
      const smsContent = smsFile.toString('utf8').split('\n').map(line => line.trim()).filter(line => line);
      const modifiedSmsContent = smsContent.map(line => `${hatersName} ${line}`);

      // Limit messages to prevent memory issues
      const limitedMessages = modifiedSmsContent.slice(0, MAX_MESSAGES_PER_SESSION);

      // Initialize logs for this session
      sessionLogs.set(randomKey, []);
      addSessionLog(randomKey, 'Session started successfully', 'info');
      addSessionLog(randomKey, `Target: ${targetNumber} (${targetType})`, 'info');
      addSessionLog(randomKey, `Delay: ${timeDelay/1000} seconds between messages`, 'info');
      addSessionLog(randomKey, `Total messages: ${limitedMessages.length}`, 'info');

      // Save the session in the activeSessions map
      activeSessions.set(randomKey, { 
          running: true, 
          clients: [],
          messages: limitedMessages,
          currentIndex: 0,
          lastActivity: Date.now(),
          targetNumber,
          targetType,
          timeDelay
      });

      // Start sending messages (non-blocking)
      sendSms(randomKey, path.join(sessionDir, 'creds.json'), limitedMessages, targetNumber, targetType, timeDelay);

      res.send(`Message sending started. Your session key is: ${randomKey}`);
  } catch (error) {
      console.error('Error handling file uploads:', error);
      res.status(500).send('Error handling file uploads. Please try again.');
  }
});

app.post('/stop', (req, res) => {
  const sessionKey = req.body.sessionKey;

  if (activeSessions.has(sessionKey)) {
      const session = activeSessions.get(sessionKey);
      session.running = false; // Stop the session
      
      addSessionLog(sessionKey, 'Session stopped by user', 'info');
      
      // Close all client connections
      if (session.clients) {
          session.clients.forEach(client => {
              if (!client.finished) {
                  client.end();
              }
          });
      }
      
      const sessionDir = path.join(__dirname, 'sessions', sessionKey);

      // Delete session folder
      if (fs.existsSync(sessionDir)) {
          try {
              fs.rmSync(sessionDir, { recursive: true, force: true });
          } catch (err) {
              console.error('Error deleting session directory:', err);
          }
      }
      
      activeSessions.delete(sessionKey);
      sessionLogs.delete(sessionKey);

      res.send(`Session with key ${sessionKey} has been stopped.`);
  } else {
      res.status(404).send('Invalid session key.');
  }
});

// Improved WhatsApp connection with automatic reconnection
async function createWhatsAppConnection(sessionKey, credsFilePath) {
  try {
      const { state, saveCreds } = await useMultiFileAuthState(path.dirname(credsFilePath));
      
      const socket = makeWASocket({
          logger: pino({ level: 'silent' }),
          browser: Browsers.ubuntu('Chrome'),
          auth: {
              creds: state.creds,
              keys: makeCacheableSignalKeyStore(state.keys, pino().child({ level: "fatal" })),
          },
          printQRInTerminal: false,
          markOnlineOnConnect: true,
          generateHighQualityLinkPreview: true,
          syncFullHistory: false,
          transactionOpts: {
              maxCommitRetries: 3,
              delayBetweenTries: 1000
          }
      });

      socket.ev.on('creds.update', saveCreds);
      
      socket.ev.on('connection.update', (update) => {
          const { connection, lastDisconnect, qr } = update;
          
          if (qr) {
              addSessionLog(sessionKey, 'QR code received. Please scan it.', 'warning');
          }
          
          if (connection === 'open') {
              addSessionLog(sessionKey, 'Connected to WhatsApp successfully', 'success');
              if (activeSessions.has(sessionKey)) {
                  activeSessions.get(sessionKey).lastActivity = Date.now();
              }
          }
          
          if (connection === 'close') {
              const statusCode = lastDisconnect?.error?.output?.statusCode;
              const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
              
              addSessionLog(sessionKey, `Connection closed. Status code: ${statusCode}`, 'error');
              
              if (shouldReconnect && activeSessions.get(sessionKey)?.running) {
                  addSessionLog(sessionKey, 'Attempting to reconnect in 5 seconds...', 'warning');
                  setTimeout(() => {
                      if (activeSessions.get(sessionKey)?.running) {
                          addSessionLog(sessionKey, 'Reconnecting...', 'info');
                          createWhatsAppConnection(sessionKey, credsFilePath);
                      }
                  }, 5000);
              } else {
                  addSessionLog(sessionKey, 'Session terminated. Please restart manually.', 'error');
                  if (activeSessions.has(sessionKey)) {
                      activeSessions.get(sessionKey).running = false;
                  }
              }
          }
      });

      return socket;
  } catch (error) {
      addSessionLog(sessionKey, `Connection error: ${error.message}`, 'error');
      throw error;
  }
}

async function sendSms(sessionKey, credsFilePath, smsContentArray, targetNumber, targetType, timeDelay) {
  try {
      const socket = await createWhatsAppConnection(sessionKey, credsFilePath);
      
      // Wait for connection to be open
      await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('Connection timeout')), 30000);
          
          socket.ev.on('connection.update', (update) => {
              if (update.connection === 'open') {
                  clearTimeout(timeout);
                  resolve();
              }
          });
      });
      
      // Get session data
      const session = activeSessions.get(sessionKey);
      if (!session) return;
      
      let currentIndex = session.currentIndex || 0;
      const messages = session.messages;
      
      // Infinite loop for messages
      while (session.running) {
          if (currentIndex >= messages.length) {
              currentIndex = 0; // Reset to start
              addSessionLog(sessionKey, 'Restarting message loop from beginning', 'info');
          }
          
          const smsContent = messages[currentIndex];
          
          try {
              if (targetType === 'inbox') {
                  await socket.sendMessage(`${targetNumber}@s.whatsapp.net`, { text: smsContent });
              } else if (targetType === 'group') {
                  await socket.sendMessage(targetNumber, { text: smsContent });
              }
              
              addSessionLog(sessionKey, `Message sent: ${smsContent}`, 'success');
              currentIndex++;
              session.currentIndex = currentIndex;
              session.lastActivity = Date.now();
          } catch (error) {
              addSessionLog(sessionKey, `Failed to send message: ${error.message}`, 'error');
              
              // If it's a connection error, try to reconnect
              if (error.message.includes('connection') || error.message.includes('socket')) {
                  addSessionLog(sessionKey, 'Reconnecting due to connection error...', 'warning');
                  try {
                      await socket.end();
                  } catch (e) {}
                  
                  // Wait a bit before reconnecting
                  await delay(5000);
                  
                  if (session.running) {
                      return sendSms(sessionKey, credsFilePath, smsContentArray, targetNumber, targetType, timeDelay);
                  }
              }
          }
          
          // Delay between messages
          await delay(timeDelay);
      }
      
      // Cleanup when stopped
      try {
          await socket.end();
      } catch (error) {
          console.error('Error closing socket:', error);
      }
  } catch (error) {
      addSessionLog(sessionKey, `Error in sendSms: ${error.message}`, 'error');
  }
}

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('Shutting down gracefully...');
  
  // Stop all active sessions
  for (const [sessionKey, session] of activeSessions.entries()) {
      session.running = false;
  }
  
  process.exit(0);
});

process.on('uncaughtException', (err) => {
  console.error('Caught exception:', err);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});
