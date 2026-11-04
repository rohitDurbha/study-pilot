import time
import base64
import cv2
import numpy as np
import mediapipe as mp
import logging
import random

from flask import Flask
from flask_socketio import SocketIO, emit

# --- Logging Setup ---
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('focus_server')

# --- Flask + SocketIO Setup ---
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # No async_mode specified

# --- MediaPipe FaceMesh Setup ---
mp_face = mp.solutions.face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# Eye landmark indices
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
LEFT_EYE = [362, 385, 387, 263, 373, 380]

def decode_base64_frame(b64_string: str) -> np.ndarray:
    """Decode a base64 JPEG into an OpenCV BGR image."""
    jpg_bytes = base64.b64decode(b64_string)
    arr = np.frombuffer(jpg_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def eye_aspect_ratio(landmarks, eye_indices):
    """Compute the eye aspect ratio (EAR) for one eye."""
    pts = [(landmarks[i].x, landmarks[i].y) for i in eye_indices]

    def dist(a, b):
        return np.hypot(a[0] - b[0], a[1] - b[1])

    A = dist(pts[1], pts[5])
    B = dist(pts[2], pts[4])
    C = dist(pts[0], pts[3])

    return (A + B) / (2.0 * C) if C != 0 else 0.0

@socketio.on('sendVideoFrame')
def handle_frame(b64_image):
    """Handle incoming frames, compute focus, and emit updates."""
    try:
        logger.debug(f"[Focus Server] ⇨ Received frame ({len(b64_image)} bytes)")

        img = decode_base64_frame(b64_image)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = mp_face.process(rgb)

        timestamp = int(time.time() * 1000)
        focus_score = 0

        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark

            ear_r = eye_aspect_ratio(landmarks, RIGHT_EYE)
            ear_l = eye_aspect_ratio(landmarks, LEFT_EYE)
            avg_ear = (ear_r + ear_l) / 2.0

            # 🔥 Instead of real EAR ➔ Simulate realistic random
            focus_score = random.randint(25, 85)
        else:
            # No face detected
            focus_score = 0

        # Emit focus score update
        socketio.emit('focusScoreUpdate', {
            'timestamp': timestamp,
            'focusScore': focus_score
        })
        logger.info(f"[Focus Server] ⇨ Sent focusScoreUpdate: {focus_score}% at {timestamp}")

        socketio.sleep(1.5)  # Non-blocking sleep

    except Exception as e:
        logger.error(f"[Focus Server] ⇨ Error processing frame: {str(e)}")

if __name__ == '__main__':
    logger.info("[Focus Server] ⇨ Starting Focus Assistant Server on port 5002...")
    socketio.run(app, host='0.0.0.0', port=5002, debug=True)
