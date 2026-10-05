import os
import re
import sys
import time
import threading
import subprocess
import webbrowser
import shutil
from pathlib import Path
from urllib.parse import quote_plus

import tkinter as tk
from tkinter import ttk, messagebox
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

try:
    import cv2
except Exception:
    cv2 = None

try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except Exception:
    pyautogui = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import sounddevice as sd
except Exception:
    sd = None

APP_NAME = "Virtual Computer Control"
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "hand_landmarker.task"


class ComputerController:
    def __init__(self, log_callback):
        self.log = log_callback
        self.last_action = 0

    def say_log(self, text):
        self.log(text)

    def run(self, raw_command):
        command = self.clean_command(raw_command)
        if not command:
            return False

        self.say_log(f"Command: {command}")

        # Search commands - deliberately checked first so natural speech works.
        q = self.extract_search(command)
        if q:
            self.google_search(q)
            return True

        q = self.extract_youtube_search(command)
        if q:
            self.youtube_search(q)
            return True

        m = re.match(r"^(?:play|play song)\s+(.+?)\s+(?:on|in)\s+spotify$", command)
        if m:
            self.spotify_search(m.group(1).strip(), play=True)
            return True

        q = self.extract_youtube_play(command)
        if q:
            self.youtube_search(q, play=True)
            return True

        if command.startswith("type "):
            self.type_text(command[5:])
            return True
        if command.startswith("write "):
            self.type_text(command[6:])
            return True

        if command.startswith("open "):
            return self.open_target(command[5:].strip())
        if command.startswith("launch "):
            return self.open_target(command[7:].strip())
        if command.startswith("start "):
            return self.open_target(command[6:].strip())

        exact = {
            "click": lambda: self.click(),
            "left click": lambda: self.click(),
            "select": lambda: self.click(),
            "double click": lambda: self.click(clicks=2),
            "double-click": lambda: self.click(clicks=2),
            "right click": lambda: self.click(button="right"),
            "right-click": lambda: self.click(button="right"),
            "middle click": lambda: self.click(button="middle"),
            "press enter": lambda: self.press("enter"),
            "enter": lambda: self.press("enter"),
            "press escape": lambda: self.press("esc"),
            "escape": lambda: self.press("esc"),
            "esc": lambda: self.press("esc"),
            "press tab": lambda: self.press("tab"),
            "tab": lambda: self.press("tab"),
            "press space": lambda: self.press("space"),
            "space": lambda: self.press("space"),
            "backspace": lambda: self.press("backspace"),
            "delete": lambda: self.press("delete"),
            "go back": lambda: self.hotkey("alt", "left"),
            "back": lambda: self.hotkey("alt", "left"),
            "go forward": lambda: self.hotkey("alt", "right"),
            "forward": lambda: self.hotkey("alt", "right"),
            "switch window": lambda: self.hotkey("alt", "tab"),
            "next window": lambda: self.hotkey("alt", "tab"),
            "minimize window": lambda: self.hotkey("win", "down"),
            "minimise window": lambda: self.hotkey("win", "down"),
            "minimize": lambda: self.hotkey("win", "down"),
            "minimise": lambda: self.hotkey("win", "down"),
            "maximize window": lambda: self.hotkey("win", "up"),
            "maximise window": lambda: self.hotkey("win", "up"),
            "maximize": lambda: self.hotkey("win", "up"),
            "maximise": lambda: self.hotkey("win", "up"),
            "restore window": lambda: self.hotkey("win", "up"),
            "close window": lambda: self.hotkey("alt", "f4"),
            "close": lambda: self.hotkey("alt", "f4"),
            "show desktop": lambda: self.hotkey("win", "d"),
            "desktop": lambda: self.hotkey("win", "d"),
            "volume up": lambda: self.press("volumeup", 5, 0.04),
            "increase volume": lambda: self.press("volumeup", 5, 0.04),
            "louder": lambda: self.press("volumeup", 5, 0.04),
            "volume down": lambda: self.press("volumedown", 5, 0.04),
            "decrease volume": lambda: self.press("volumedown", 5, 0.04),
            "quieter": lambda: self.press("volumedown", 5, 0.04),
            "mute": lambda: self.press("volumemute"),
            "mute volume": lambda: self.press("volumemute"),
            "play": lambda: self.press("playpause"),
            "pause": lambda: self.press("playpause"),
            "play pause": lambda: self.press("playpause"),
            "next song": lambda: self.press("nexttrack"),
            "next track": lambda: self.press("nexttrack"),
            "previous song": lambda: self.press("prevtrack"),
            "previous track": lambda: self.press("prevtrack"),
            "scroll up": lambda: self.scroll(6),
            "scroll down": lambda: self.scroll(-6),
            "scroll to top": lambda: self.hotkey("ctrl", "home"),
            "scroll to bottom": lambda: self.hotkey("ctrl", "end"),
            "screenshot": self.screenshot,
            "take screenshot": self.screenshot,
            "lock computer": self.lock,
            "lock": self.lock,
        }

        if command in exact:
            exact[command]()
            return True

        m = re.match(r"scroll\s+(\d+)\s+(up|down)", command)
        if m:
            amount = min(int(m.group(1)), 20)
            self.scroll(amount if m.group(2) == "up" else -amount)
            return True

        # Common natural-language commands.
        if "copy" == command or "copy this" == command:
            self.hotkey("ctrl", "c")
            return True
        if command in ("paste", "paste this"):
            self.hotkey("ctrl", "v")
            return True
        if command in ("cut", "cut this"):
            self.hotkey("ctrl", "x")
            return True
        if command in ("select all", "select everything"):
            self.hotkey("ctrl", "a")
            return True
        if command in ("refresh", "reload", "refresh page"):
            self.hotkey("ctrl", "r")
            return True
        if command in ("new tab", "open new tab"):
            self.hotkey("ctrl", "t")
            return True
        if command in ("close tab", "close this tab"):
            self.hotkey("ctrl", "w")
            return True

        # If the user says a website/domain, open it.
        if ".com" in command or command.startswith("www."):
            target = command if command.startswith("http") else "https://" + command
            webbrowser.open(target)
            return True

        self.say_log("I could not map that command. I can search Google automatically: try 'search ...'.")
        return False

    def clean_command(self, text):
        text = str(text or "").lower().strip()
        text = re.sub(r"[.!?,]+$", "", text)
        text = re.sub(r"\s+", " ", text)
        # Recognition commonly adds these filler prefixes.
        text = re.sub(r"^(please|hey computer|computer|assistant)\s+", "", text)
        return text.strip()

    def extract_search(self, command):
        patterns = [
            r"^(?:search|google search|search google)\s+(?:for\s+)?(.+)$",
            r"^(?:search|google)\s+(.+)$",
            r"^(?:look up|look for|find)\s+(.+?)\s+(?:on google|in google)$",
            r"^(?:find|look up)\s+(.+)$",
        ]
        for p in patterns:
            m = re.match(p, command)
            if m:
                q = m.group(1).strip()
                if q and q not in ("google", "google search"):
                    return q
        return None

    def extract_youtube_search(self, command):
        patterns = [
            r"^(?:search youtube|youtube search|search on youtube)\s+(?:for\s+)?(.+)$",
            r"^(?:find|look for)\s+(.+?)\s+on youtube$",
        ]
        for p in patterns:
            m = re.match(p, command)
            if m:
                return m.group(1).strip()
        return None

    def extract_youtube_play(self, command):
        patterns = [
            r"^play\s+(.+?)\s+(?:on youtube|in youtube)$",
            r"^play youtube\s+(.+)$",
            r"^play song\s+(.+)$",
            r"^play\s+(.+)$",
        ]
        for p in patterns:
            m = re.match(p, command)
            if m:
                q = m.group(1).strip()
                if q and q not in ("music", "song", "youtube", "spotify"):
                    return q
        return None

    def spotify_search(self, query, play=False):
        self.say_log(f"Spotify search: {query}")
        webbrowser.open("https://open.spotify.com/search/" + quote_plus(query))
        if play:
            self.say_log("Spotify search opened. Select the first track if autoplay is not enabled by Spotify.")

    def google_search(self, query):
        self.say_log(f"Google search: {query}")
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))

    def youtube_search(self, query, play=False):
        self.say_log(f"YouTube: {query}" + (" [auto-play]" if play else ""))
        if play:
            # yt-dlp resolves the first YouTube result to a real watch URL.
            # It does not download the video.
            try:
                ytdlp = shutil.which("yt-dlp")
                if ytdlp:
                    result = subprocess.run(
                        [ytdlp, "ytsearch1:" + query, "--get-id", "--no-playlist", "--skip-download"],
                        capture_output=True, text=True, timeout=20
                    )
                    video_id = ""
                    for line in result.stdout.splitlines():
                        line = line.strip()
                        if re.fullmatch(r"[A-Za-z0-9_-]{11}", line):
                            video_id = line
                            break
                    if video_id:
                        webbrowser.open("https://www.youtube.com/watch?v=" + video_id)
                        return
                    self.say_log("Could not resolve a YouTube video; opening search instead.")
            except Exception as exc:
                self.say_log(f"YouTube resolver error: {exc}")
        webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(query))

    def open_target(self, target):
        target = target.strip()
        aliases = {
            "chrome": "https://www.google.com",
            "google chrome": "https://www.google.com",
            "edge": "https://www.microsoft.com/edge",
            "microsoft edge": "https://www.microsoft.com/edge",
            "youtube": "https://www.youtube.com",
            "spotify": "https://open.spotify.com",
            "gmail": "https://mail.google.com",
            "google": "https://www.google.com",
            "github": "https://github.com",
            "whatsapp": "https://web.whatsapp.com",
            "google drive": "https://drive.google.com",
            "google maps": "https://maps.google.com",
        }
        if target in aliases:
            webbrowser.open(aliases[target])
            return True

        if target.startswith("http://") or target.startswith("https://"):
            webbrowser.open(target)
            return True

        # Windows Start-menu search. This handles installed applications by name.
        if sys.platform.startswith("win"):
            try:
                ps = (
                    "$q=" + repr(target) + "; "
                    "$a=Get-StartApps | Where-Object {$_.Name -like ('*'+$q+'*')} | Select-Object -First 1; "
                    "if($a){Start-Process ('shell:AppsFolder\\'+$a.AppID)} else {Start-Process $q}"
                )
                subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps])
                self.say_log(f"Opening: {target}")
                return True
            except Exception as exc:
                self.say_log(f"Could not open {target}: {exc}")
                return False
        return False

    def available(self):
        if pyautogui is None:
            self.say_log("PyAutoGUI is unavailable. Run setup.bat again.")
            return False
        return True

    def click(self, button="left", clicks=1):
        if self.available():
            pyautogui.click(button=button, clicks=clicks, interval=0.1)

    def type_text(self, text):
        if self.available():
            pyautogui.write(text, interval=0.015)

    def press(self, key, presses=1, interval=0.1):
        if self.available():
            pyautogui.press(key, presses=presses, interval=interval)

    def hotkey(self, *keys):
        if self.available():
            pyautogui.hotkey(*keys)

    def scroll(self, amount):
        if self.available():
            pyautogui.scroll(amount)

    def screenshot(self):
        if self.available():
            folder = Path.home() / "Pictures" / "VirtualComputerControl"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / time.strftime("screenshot_%Y%m%d_%H%M%S.png")
            pyautogui.screenshot(str(path))
            self.say_log(f"Screenshot saved: {path}")

    def lock(self):
        if sys.platform.startswith("win"):
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])


class GestureEngine:
    """MediaPipe hand tracking with stable gesture debouncing."""
    def __init__(self, controller, status_callback, preview_callback):
        self.controller = controller
        self.status = status_callback
        self.preview = preview_callback
        self.running = False
        self.thread = None
        self.cap = None
        self.last_gesture = None
        self.gesture_since = 0
        self.last_action = 0
        self.last_move = 0
        self.prev_pinch = False
        self.screen_w, self.screen_h = (1920, 1080)
        if pyautogui:
            try:
                self.screen_w, self.screen_h = pyautogui.size()
            except Exception:
                pass

    def start(self):
        if cv2 is None:
            self.status("OpenCV is missing. Run setup.bat.")
            return
        if mp is None:
            self.status("MediaPipe is missing. Run setup.bat again.")
            return
        if not MODEL_PATH.exists():
            self.status("Hand model missing. Run setup.bat to download it.")
            return
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        self.status("Starting camera...")

    def stop(self):
        self.running = False
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.status("Gesture control stopped")

    def loop(self):
        # Windows webcams may work through different OpenCV backends.
        if sys.platform.startswith("win"):
            candidates = [
                (0, cv2.CAP_MSMF), (0, cv2.CAP_DSHOW), (0, cv2.CAP_ANY),
                (1, cv2.CAP_MSMF), (1, cv2.CAP_DSHOW),
            ]
        else:
            candidates = [(0, cv2.CAP_ANY), (1, cv2.CAP_ANY)]

        self.cap = None
        for index, backend in candidates:
            if not self.running:
                return
            self.status(f"Opening camera {index}...")
            try:
                cap = cv2.VideoCapture(index, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    ok, test_frame = cap.read()
                    if ok and test_frame is not None and test_frame.size > 0:
                        self.cap = cap
                        self.status(f"Camera active - camera {index} connected")
                        break
                try:
                    cap.release()
                except Exception:
                    pass
            except Exception as exc:
                self.status(f"Camera {index} error: {exc}")

        if self.cap is None:
            self.running = False
            self.status("Camera not available. Check Windows Camera permission or close Camera/Teams/Zoom.")
            return

        # MediaPipe 0.10.32+ no longer exposes the old mp.solutions API.
        # Use the supported Hand Landmarker Tasks API instead.
        try:
            BaseOptions = mp.tasks.BaseOptions
            HandLandmarker = mp.tasks.vision.HandLandmarker
            HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
            RunningMode = mp.tasks.vision.RunningMode

            options = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.60,
                min_hand_presence_confidence=0.60,
                min_tracking_confidence=0.60,
            )
            landmarker = HandLandmarker.create_from_options(options)
        except Exception as exc:
            self.running = False
            if self.cap is not None:
                self.cap.release()
            self.cap = None
            self.status(f"Hand tracker failed to start: {exc}")
            return

        self.status("Camera active - show one hand")
        frame_number = 0
        try:
            while self.running:
                ok, frame = self.cap.read()
                if not ok or frame is None:
                    self.status("Waiting for camera frame...")
                    time.sleep(0.05)
                    continue

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = frame_number * 33
                frame_number += 1
                result = landmarker.detect_for_video(mp_image, timestamp_ms)
                gesture = "NO HAND"

                if result.hand_landmarks:
                    hand = result.hand_landmarks[0]
                    self.draw_hand(frame, hand)
                    gesture = self.classify(hand)
                    self.perform(gesture, hand, frame.shape[1], frame.shape[0])

                cv2.putText(frame, f"Gesture: {gesture}", (15, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, "Index=Move | Pinch=Click | 3 Fingers=Right Click | Open Palm=Scroll",
                            (10, frame.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
                self.preview(frame)
                time.sleep(0.005)
        finally:
            try:
                landmarker.close()
            except Exception:
                pass
            if self.cap is not None:
                self.cap.release()
            self.cap = None

    def draw_hand(self, frame, lm):
        # Hand skeleton connections used by the MediaPipe hand model.
        connections = [
            (0,1),(1,2),(2,3),(3,4),
            (0,5),(5,6),(6,7),(7,8),
            (5,9),(9,10),(10,11),(11,12),
            (9,13),(13,14),(14,15),(15,16),
            (13,17),(17,18),(18,19),(19,20),(0,17)
        ]
        h, w = frame.shape[:2]
        points = []
        for p in lm:
            x = int(p.x * w)
            y = int(p.y * h)
            points.append((x, y))
            cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)
        for a, b in connections:
            cv2.line(frame, points[a], points[b], (255, 0, 0), 2)

    def classify(self, lm):
        # Gesture mapping:
        # 1 finger (index) -> mouse movement
        # thumb + index pinch -> left click
        # 2 fingers (index + middle) -> right click
        # 4 fingers (index + middle + ring + pinky) -> scroll up
        # closed fist -> scroll down
        index_up = lm[8].y < lm[6].y
        middle_up = lm[12].y < lm[10].y
        ring_up = lm[16].y < lm[14].y
        pinky_up = lm[20].y < lm[18].y

        pinch_dist = ((lm[4].x - lm[8].x) ** 2 + (lm[4].y - lm[8].y) ** 2) ** 0.5
        if pinch_dist < 0.055:
            return "PINCH CLICK"

        if index_up and not middle_up and not ring_up and not pinky_up:
            return "MOVE"

        if index_up and middle_up and not ring_up and not pinky_up:
            return "RIGHT CLICK"

        if index_up and middle_up and ring_up and pinky_up:
            return "SCROLL UP"

        if not index_up and not middle_up and not ring_up and not pinky_up:
            return "SCROLL DOWN"

        return "NONE"

    def perform(self, gesture, lm, fw, fh):
        now = time.time()

        # One index finger: control the mouse cursor.
        if gesture == "MOVE" and pyautogui and now - self.last_move > 0.025:
            x = max(0, min(self.screen_w - 1, int(lm[8].x * self.screen_w)))
            y = max(0, min(self.screen_h - 1, int(lm[8].y * self.screen_h)))
            pyautogui.moveTo(x, y, duration=0.01)
            self.last_move = now
            return

        # Four fingers: scroll up.
        if gesture == "SCROLL UP" and now - self.last_action > 0.30:
            self.controller.scroll(5)
            self.last_action = now
            return

        # Closed fist: scroll down.
        if gesture == "SCROLL DOWN" and now - self.last_action > 0.30:
            self.controller.scroll(-5)
            self.last_action = now
            return

        # Pinch = left click, two fingers = right click.
        if gesture in ("PINCH CLICK", "RIGHT CLICK") and now - self.last_action > 0.55:
            if gesture == "PINCH CLICK":
                self.controller.click()
            else:
                self.controller.click(button="right")
            self.last_action = now



class VoiceEngine:
    def __init__(self, controller, status_callback):
        self.controller = controller
        self.status = status_callback
        self.running = False
        self.thread = None
        self.recognizer = None

    def start(self):
        if sr is None:
            self.status("SpeechRecognition is missing. Run setup.bat again.")
            return
        try:
            import pyaudio  # noqa: F401
        except Exception:
            self.status("PyAudio is missing. Run setup.bat again.")
            return
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        self.status("Starting microphone...")

    def stop(self):
        self.running = False
        self.status("Voice control stopped")

    def test_microphone(self):
        if sr is None:
            self.status("SpeechRecognition is missing")
            return
        try:
            with sr.Microphone() as source:
                self.status("Microphone connected - speak now")
                r = sr.Recognizer()
                r.adjust_for_ambient_noise(source, duration=0.7)
                audio = r.listen(source, timeout=5, phrase_time_limit=4)
                text = r.recognize_google(audio, language="en-IN")
                self.controller.say_log(f"Microphone test heard: {text}")
                self.status(f"Microphone test OK: {text}")
        except Exception as exc:
            self.controller.say_log(f"Microphone test error: {exc}")
            self.status("Microphone test failed - check Windows microphone permission/device")

    def loop(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.65
        self.recognizer.phrase_threshold = 0.25
        self.recognizer.non_speaking_duration = 0.3
        self.recognizer.energy_threshold = 250

        try:
            mic = sr.Microphone()
        except Exception as exc:
            self.running = False
            self.status("No usable microphone found")
            self.controller.say_log(f"Microphone initialization error: {exc}")
            return

        try:
            with mic as source:
                self.status("Calibrating microphone - stay quiet...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.2)
                self.controller.say_log(f"Microphone ready; energy threshold={int(self.recognizer.energy_threshold)}")
        except Exception as exc:
            self.running = False
            self.status("Microphone calibration failed")
            self.controller.say_log(f"Calibration error: {exc}")
            return

        self.status("Voice control active - say a command")
        while self.running:
            try:
                with mic as source:
                    self.status("Listening...")
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=7)
                text = self.recognizer.recognize_google(audio, language="en-IN")
                self.status(f"Heard: {text}")
                self.controller.run(text)
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                self.status("Could not understand - try again")
            except sr.RequestError as exc:
                self.status("Speech recognition needs an internet connection")
                self.controller.say_log(f"Speech service error: {exc}")
                time.sleep(1)
            except Exception as exc:
                self.controller.say_log(f"Microphone error: {exc}")
                self.status("Microphone error - check Windows input device")
                time.sleep(1)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1000x760")
        self.root.minsize(850, 650)
        self.status_var = tk.StringVar(value="Ready")
        self.controller = ComputerController(self.log)
        self.voice = VoiceEngine(self.controller, self.set_status)
        self.gesture = GestureEngine(self.controller, self.set_status, self.show_frame)
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        ttk.Label(self.root, text=APP_NAME, font=("Segoe UI", 24, "bold")).pack(pady=(14, 2))
        ttk.Label(self.root, text="Hands-free Windows control using gestures + natural voice commands",
                  font=("Segoe UI", 11)).pack(pady=(0, 10))

        buttons = ttk.Frame(self.root)
        buttons.pack(pady=5)
        ttk.Button(buttons, text="Start Gesture Control", command=self.gesture.start).grid(row=0, column=0, padx=4)
        ttk.Button(buttons, text="Stop Gesture Control", command=self.gesture.stop).grid(row=0, column=1, padx=4)
        ttk.Button(buttons, text="Start Voice Control", command=self.voice.start).grid(row=0, column=2, padx=4)
        ttk.Button(buttons, text="Stop Voice Control", command=self.voice.stop).grid(row=0, column=3, padx=4)
        ttk.Button(buttons, text="Test Microphone", command=lambda: threading.Thread(target=self.voice.test_microphone, daemon=True).start()).grid(row=0, column=4, padx=4)

        manual = ttk.LabelFrame(self.root, text="Test any command")
        manual.pack(fill="x", padx=20, pady=10)
        self.command_entry = ttk.Entry(manual, font=("Segoe UI", 11))
        self.command_entry.pack(side="left", fill="x", expand=True, padx=8, pady=8)
        self.command_entry.bind("<Return>", lambda e: self.run_manual())
        ttk.Button(manual, text="Run", command=self.run_manual).pack(side="right", padx=8, pady=8)

        help_text = (
            "Examples: 'search latest Java tutorials in Google' | 'search YouTube for relaxing music' | "
            "'play Believer on YouTube' | 'open Chrome' | 'open calculator' | 'type hello world' | "
            "'click' | 'right click' | 'minimize window' | 'maximize window' | 'close window' | "
            "'copy' | 'paste' | 'select all' | 'new tab' | 'scroll down' | 'screenshot' | "
            "'play Believer' | 'play Believer on Spotify'."
        )
        ttk.Label(self.root, text=help_text, wraplength=930, justify="left").pack(fill="x", padx=25, pady=4)

        self.preview_label = ttk.Label(self.root, text="Camera preview appears here when gesture control is started.", anchor="center")
        self.preview_label.pack(fill="both", expand=True, padx=20, pady=8)

        status = ttk.Frame(self.root)
        status.pack(fill="x", padx=20, pady=5)
        ttk.Label(status, text="Status:", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(status, textvariable=self.status_var).pack(side="left", padx=8)

        self.log_box = tk.Text(self.root, height=8, state="disabled", font=("Consolas", 9))
        self.log_box.pack(fill="x", padx=20, pady=(4, 14))

    def log(self, text):
        self.root.after(0, self._append_log, text)

    def _append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", time.strftime("[%H:%M:%S] ") + text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def show_frame(self, frame):
        if cv2 is None:
            return
        try:
            small = cv2.resize(frame, (640, 480))
            if Image is not None and ImageTk is not None:
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(rgb)
                self.root.after(0, self._update_preview_image, image)
            else:
                ok, encoded = cv2.imencode(".ppm", small)
                if ok:
                    self.root.after(0, self._update_preview, encoded.tobytes())
        except Exception as exc:
            self.set_status(f"Preview error: {exc}")

    def _update_preview_image(self, image):
        try:
            photo = ImageTk.PhotoImage(image=image)
            self.preview_label.configure(image=photo, text="")
            self.preview_label.image = photo
        except Exception:
            pass

    def _update_preview(self, ppm):
        try:
            photo = tk.PhotoImage(data=ppm, format="PPM")
            self.preview_label.configure(image=photo, text="")
            self.preview_label.image = photo
        except Exception:
            pass

    def run_manual(self):
        command = self.command_entry.get().strip()
        if command:
            threading.Thread(target=self.controller.run, args=(command,), daemon=True).start()
            self.command_entry.delete(0, "end")

    def close(self):
        self.voice.stop()
        self.gesture.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
