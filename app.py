from flask import Flask, render_template_string
from flask_socketio import SocketIO
import logging

# Vercel doesn't need to run the SocketIO server, but the imports are needed.
# This code will primarily be used for rendering the HTML templates.
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# A placeholder for the signaling server URL.
# YOU MUST REPLACE THIS with your actual Render app URL.
SIGNALING_SERVER_URL = "https://your-signaling-app-name.onrender.com"


STYLE_CSS = """
    :root {
        --background-color: #1a1a1a;
        --container-bg: rgba(35, 35, 35, 0.5);
        --blur-effect: blur(10px);
        --border-color: rgba(255, 255, 255, 0.2);
        --text-color: #f0f0f0;
        --primary-color: #00aaff;
        --primary-hover: #0088cc;
    }
    body {
        background-color: var(--background-color);
        background-image: radial-gradient(circle at 10% 20%, rgba(0, 170, 255, 0.3), transparent 30%),
                          radial-gradient(circle at 80% 90%, rgba(100, 0, 255, 0.3), transparent 30%);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: var(--text-color);
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
        margin: 0;
        padding: 20px;
        box-sizing: border-box;
    }
    .container {
        background: var(--container-bg);
        backdrop-filter: var(--blur-effect);
        -webkit-backdrop-filter: var(--blur-effect);
        border: 1px solid var(--border-color);
        border-radius: 15px;
        padding: 40px;
        width: 100%;
        max-width: 600px;
        text-align: center;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    h1 {
        margin-bottom: 25px;
        font-size: 2.5em;
    }
    p {
        margin-bottom: 30px;
        font-size: 1.1em;
    }
    video {
        width: 100%;
        border-radius: 10px;
        background-color: #000;
        margin-top: 20px;
        border: 1px solid var(--border-color);
    }
    button, input {
        width: 100%;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid var(--border-color);
        background-color: transparent;
        color: var(--text-color);
        font-size: 1em;
        margin-bottom: 15px;
        box-sizing: border-box;
        transition: all 0.3s ease;
    }
    button {
        background-color: var(--primary-color);
        color: white;
        border: none;
        cursor: pointer;
        font-weight: bold;
    }
    button:hover {
        background-color: var(--primary-hover);
        box-shadow: 0 0 15px var(--primary-color);
    }
    input::placeholder {
        color: #aaa;
    }
    input:focus {
        outline: none;
        border-color: var(--primary-color);
        box-shadow: 0 0 10px var(--primary-color);
    }
    #streamCode {
        background-color: rgba(0,0,0,0.3);
        padding: 10px 15px;
        border-radius: 5px;
        font-family: monospace;
        color: var(--primary-color);
    }
"""

HOST_HTML = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Host Screen</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{STYLE_CSS}</style>
</head>
<body>
    <div class="container">
        <h1>Host Stream</h1>
        <p>Start your screen share to begin streaming with internal audio.</p>
        <button id="startStream">Start Stream</button>
        <p>Your Stream Code: <b id="streamCode">Not Started</b></p>
        <video id="localVideo" autoplay muted playsinline></video>
    </div>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", () => {{
            // IMPORTANT: Connect to your signaling server on Render
            const socket = io("{SIGNALING_SERVER_URL}", {{transports: ['websocket']}});

            const startStreamButton = document.getElementById('startStream');
            const localVideo = document.getElementById('localVideo');
            const streamCodeDisplay = document.getElementById('streamCode');
            let localStream;
            const peerConnections = {{}};

            startStreamButton.onclick = async () => {{
                try {{
                    localStream = await navigator.mediaDevices.getDisplayMedia({{
                        video: true,
                        audio: {{ echoCancellation: false, noiseSuppression: false, autoGainControl: false }}
                    }});
                    localVideo.srcObject = localStream;
                    socket.emit('start_stream');
                    console.log("Stream capture started.");
                }} catch (error) {{
                    console.error("Failed to start stream: ", error);
                    alert("Could not start stream. Ensure you are on HTTPS and have granted permissions.");
                }}
            }};

            socket.on('connect', () => console.log("Connected to signaling server."));
            socket.on('stream_started', (data) => {{
                streamCodeDisplay.textContent = data.stream_code;
                console.log(`Stream started with code: ${{data.stream_code}}`);
            }});
            socket.on('viewer_joined', (data) => {{
                const viewerId = data.viewer_id;
                console.log(`Viewer ${{viewerId}} joined, creating peer connection.`);
                const peerConnection = new RTCPeerConnection({{{{ iceServers: [{{ urls: 'stun:stun.l.google.com:19302' }}] }}}});
                peerConnections[viewerId] = peerConnection;
                localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
                peerConnection.onicecandidate = (event) => {{
                    if (event.candidate) socket.emit('ice_candidate', {{ 'to': viewerId, 'candidate': event.candidate }});
                }};
                peerConnection.createOffer()
                    .then(offer => peerConnection.setLocalDescription(offer))
                    .then(() => socket.emit('offer', {{ 'to': viewerId, 'offer': peerConnection.localDescription }}));
            }});
            socket.on('answer', (data) => {{
                console.log(`Received answer from ${{data.from}}`);
                peerConnections[data.from].setRemoteDescription(new RTCSessionDescription(data.answer));
            }});
            socket.on('ice_candidate', (data) => peerConnections[data.from].addIceCandidate(new RTCIceCandidate(data.candidate)));
            socket.on('viewer_left', (data) => {{
                if (peerConnections[data.viewer_id]) {{
                    peerConnections[data.viewer_id].close();
                    delete peerConnections[data.viewer_id];
                    console.log(`Viewer ${{data.viewer_id}} left.`);
                }}
            }});
        }});
    </script>
</body>
</html>
"""

VIEWER_HTML = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Viewer Screen</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{STYLE_CSS}</style>
</head>
<body>
    <div class="container">
        <h1>Join a Stream</h1>
        <p>Enter the code from the host to start watching the stream.</p>
        <input type="text" id="streamCodeInput" placeholder="Enter Stream Code">
        <button id="joinStream">Join Stream</button>
        <video id="remoteVideo" autoplay playsinline></video>
    </div>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", () => {{
            // IMPORTANT: Connect to your signaling server on Render
            const socket = io("{SIGNALING_SERVER_URL}", {{transports: ['websocket']}});

            const joinStreamButton = document.getElementById('joinStream');
            const streamCodeInput = document.getElementById('streamCodeInput');
            const remoteVideo = document.getElementById('remoteVideo');
            let peerConnection;

            joinStreamButton.onclick = () => {{
                const streamCode = streamCodeInput.value;
                if (streamCode) socket.emit('join_stream', {{ 'stream_code': streamCode }});
            }};
            
            socket.on('connect', () => console.log("Connected to signaling server."));
            socket.on('offer', (data) => {{
                const hostId = data.from;
                console.log("Received offer, creating peer connection.");
                peerConnection = new RTCPeerConnection({{{{ iceServers: [{{ urls: 'stun:stun.l.google.com:19302' }}] }}}});
                peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
                peerConnection.createAnswer()
                    .then(answer => peerConnection.setLocalDescription(answer))
                    .then(() => socket.emit('answer', {{ 'to': hostId, 'answer': peerConnection.localDescription }}));
                peerConnection.ontrack = (event) => remoteVideo.srcObject = event.streams[0];
                peerConnection.onicecandidate = (event) => {{
                    if (event.candidate) socket.emit('ice_candidate', {{ 'to': hostId, 'candidate': event.candidate }});
                }};
            }});
            socket.on('ice_candidate', (data) => peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate)));
            socket.on('stream_ended', (data) => {{
                alert(`Stream ${{data.stream_code}} has ended.`);
                remoteVideo.srcObject = null;
                if (peerConnection) peerConnection.close();
            }});
            socket.on('error', (data) => alert(data.message));
        }});
    </script>
</body>
</html>
"""

@app.route('/host')
def host():
    return render_template_string(HOST_HTML)

@app.route('/viewer')
def viewer():
    return render_template_string(VIEWER_HTML)

@app.route('/')
def index():
    return "Welcome! Use /host or /viewer."
if __name__ == '__main__':
    # The application is run with eventlet as the web server.
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
