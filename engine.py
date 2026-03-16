
import sys
import os
import threading
import time
import numpy as np
import pyaudio
import keyboard
import pygame
import json
import pyperclip
from faster_whisper import WhisperModel
import hashlib
import ctypes
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL

# --- CONFIG ---
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
DEFAULT_MODEL_SIZE = "tiny.en"
CONSOLE_TITLE = "PaceEngine"

class PaceEngine:
    def __init__(self):
        # 1. Name the process for the Electron killer
        if sys.platform == 'win32':
            ctypes.windll.kernel32.SetConsoleTitleW(CONSOLE_TITLE)

        self.lock = threading.Lock()
        self.is_recording = False
        self.pa = pyaudio.PyAudio()
        self.last_audio_hash = None
        self.last_sound_time = 0
        self.last_typed_text = ""
        self.last_typed_time = 0
        self.model_size = DEFAULT_MODEL_SIZE
        
        # Audio Feedback
        pygame.mixer.init()
        try:
            # Use relative paths for portability and privacy
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.start_snd = pygame.mixer.Sound(os.path.join(base_dir, "start.mp3"))
            self.stop_snd = pygame.mixer.Sound(os.path.join(base_dir, "stop.mp3"))
        except:
            self.start_snd = self.stop_snd = None

        self.model = self._load_model()
        self.volume_interface = self._init_volume()
        self.pre_mute_state = False

    def _init_volume(self):
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        except:
            return None

    def mute_pc(self, mute=True):
        if not self.volume_interface: return
        try:
            if mute:
                self.pre_mute_state = self.volume_interface.GetMute()
                self.volume_interface.SetMute(1, None)
            else:
                self.volume_interface.SetMute(self.pre_mute_state, None)
        except:
            pass

    def _load_model(self):
        self.log("status", {"text": f"Pace AI Warming Up ({self.model_size})..."})
        
        # Use a persistent path for models (appdata on windows)
        if sys.platform == 'win32':
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            path = os.path.join(appdata, "Pace", "models")
        else:
            path = os.path.join(os.path.expanduser('~'), ".pace", "models")
            
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            
        model = WhisperModel(self.model_size, device="cpu", compute_type="int8", download_root=path, cpu_threads=4)
        # Warmup
        list(model.transcribe(np.zeros(16000, dtype=np.float32), beam_size=1))
        self.log("engine_ready", {"model": self.model_size})
        return model

    def switch_model(self, size):
        if size == self.model_size: return
        self.model_size = size
        self.model = self._load_model()

    def log(self, msg_type, data):
        print(json.dumps({"type": msg_type, **data}))
        sys.stdout.flush()

    def play_snd(self, snd):
        if not snd: return
        now = time.time()
        if now - self.last_sound_time < 0.3: return # 300ms cooldown
        self.last_sound_time = now
        snd.play()

    def run_session(self):
        # ATOMIC LOCK: Only one session can EVER run at a time
        if not self.lock.acquire(blocking=False):
            return

        session_id = int(time.time() * 1000)
        
        try:
            self.is_recording = True
            self.log("status", {"isRecording": True, "sessionId": session_id})
            self.play_snd(self.start_snd)
            self.mute_pc(True)

            # Fresh stream for every session
            stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE, input=True, frames_per_buffer=CHUNK_SIZE)
            buffer = []

            # RECORDING LOOP
            while self.is_recording:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                buffer.append(data)
                
                # Level for UI (throttled)
                samples = np.frombuffer(data, dtype=np.int16)
                rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
                self.log("level", {"level": float(rms / 1200.0)})

            # STOPPING
            stream.stop_stream()
            stream.close()
            self.mute_pc(False)
            self.play_snd(self.stop_snd)
            self.log("status", {"isRecording": False})

            # TRANSCRIBING
            if len(buffer) > 15:
                raw_data = b"".join(buffer)
                
                # Binary Hash Check: If audio is identical to last time, it's a driver cache leak
                current_hash = hashlib.md5(raw_data).hexdigest()
                if current_hash == self.last_audio_hash:
                    return
                self.last_audio_hash = current_hash

                audio_np = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                segments, _ = self.model.transcribe(audio_np, beam_size=1, vad_filter=True)
                text = " ".join([s.text for s in segments]).strip()

                if text:
                    now = time.time()
                    # FINAL TEXT GUARD: Don't type same text twice within 2 seconds
                    if text == self.last_typed_text and (now - self.last_typed_time) < 2.0:
                        print(f"DEBUG: Blocking duplicate text: '{text}'", file=sys.stderr)
                        return

                    print(f"DEBUG: Result {session_id}: '{text}'", file=sys.stderr)
                    self.last_typed_text = text
                    self.last_typed_time = now
                    
                    # DIRECT TYPING
                    time.sleep(0.05)
                    keyboard.write(text, delay=0)
                    self.log("transcription", {"text": text, "id": session_id})

        finally:
            self.is_recording = False
            self.lock.release()

def hotkey_monitor(engine):
    hotkey_ready = True
    
    # Windows Virtual Key Codes
    VK_CONTROL = 0x11
    VK_MENU = 0x12 # ALT key
    
    def is_pressed(vk):
        # Direct Windows API call for physical key state
        # 0x8000 is the bitmask for "currently held down"
        return (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0

    print("Hotkey loop started (Low-Level Windows API).", file=sys.stderr)

    while True:
        try:
            # Check physical state directly from Windows hardware buffer
            ctrl = is_pressed(VK_CONTROL)
            alt = is_pressed(VK_MENU)
            is_held = ctrl and alt
            
            # START logic
            if is_held and not engine.is_recording and hotkey_ready:
                hotkey_ready = False
                print("DEBUG: Hotkey Triggered START", file=sys.stderr)
                threading.Thread(target=engine.run_session, daemon=True).start()
            
            # STOP logic
            if not is_held and engine.is_recording:
                print("DEBUG: Hotkey Triggered STOP", file=sys.stderr)
                engine.is_recording = False # Signal session to stop
            
            # RESET logic: Ready to trigger again as soon as the COMBO is broken
            if not is_held:
                hotkey_ready = True
                
            time.sleep(0.01) # Ultra-fast polling
        except:
            continue

def command_monitor(engine):
    for line in sys.stdin:
        cmd = line.strip()
        if cmd == "toggle":
            if not engine.is_recording:
                threading.Thread(target=engine.run_session, daemon=True).start()
            else:
                engine.is_recording = False
        elif cmd.startswith("model:"):
            size = cmd.split(":")[1]
            threading.Thread(target=engine.switch_model, args=(size,), daemon=True).start()

def suicide_watch():
    # Kill ourselves if Electron (our parent) dies
    parent_pid = os.getppid()
    while True:
        try:
            if sys.platform == 'win32':
                # Use Windows tasklist to check if parent is still alive
                # This is more robust than getppid() == 1 on Windows
                process_check = os.popen(f'tasklist /FI "PID eq {parent_pid}"').read()
                if str(parent_pid) not in process_check:
                    os._exit(0)
            else:
                if os.getppid() != parent_pid:
                    os._exit(0)
        except:
            pass
        time.sleep(2)

if __name__ == "__main__":
    print(f"PaceEngine PID: {os.getpid()}", file=sys.stderr)
    engine = PaceEngine()
    
    threading.Thread(target=command_monitor, args=(engine,), daemon=True).start()
    threading.Thread(target=suicide_watch, daemon=True).start()
    
    # Run hotkey loop in main thread
    hotkey_monitor(engine)
