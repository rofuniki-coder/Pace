import os
import sys

# Redirect stdout/stderr to null if running without console to prevent crashes
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# Suppress HuggingFace symlink warnings on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Add NVIDIA libs to PATH for ctranslate2 (GPU support)
try:
    import nvidia.cublas.lib
    import nvidia.cudnn.lib
    os.add_dll_directory(os.path.dirname(nvidia.cublas.lib.__file__))
    os.add_dll_directory(os.path.dirname(nvidia.cudnn.lib.__file__))
except Exception as e:
    # If not installed or not on Windows, just ignore
    pass

# Attempt to load ZLIB wapi if present (fix for some cuDNN versions)
# This is a common missing dependency for cuDNN on Windows
zlib_path = os.path.join(os.getcwd(), "venv", "Scripts", "zlibwapi.dll")
if os.path.exists(zlib_path):
    try:
        os.add_dll_directory(os.path.dirname(zlib_path))
    except:
        pass

import time
import threading
import json
import logging
import winsound
import pyautogui
import keyboard
from flask import Flask, request, jsonify
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download
import pyaudio
import wave
import pyperclip
import numpy as np
from deep_translator import GoogleTranslator
import tqdm.auto
import tqdm.std
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
from ctypes import cast, POINTER
import pythoncom # Required for COM in threads

# Monkey patch tqdm to capture progress
download_progress = 0
current_max_total = 0
original_tqdm = tqdm.auto.tqdm

class DownloadProgressBar(original_tqdm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global current_max_total
        # If this bar is larger than any we've seen, it's likely the main model file
        if self.total and self.total > current_max_total:
            current_max_total = self.total
            
    def update(self, n=1):
        super().update(n)
        global download_progress, current_max_total, model_status
        # Only update progress for the largest file (model.bin)
        if self.total and self.total >= current_max_total and self.total > 10 * 1024 * 1024:
             download_progress = int((self.n / self.total) * 100)
             # Force status to downloading if we see active progress
             if model_status != "downloading":
                 model_status = "downloading"

# Apply patch
tqdm.auto.tqdm = DownloadProgressBar
tqdm.std.tqdm = DownloadProgressBar

import argparse

# Parse command line args
parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", help="Directory for storing models and history", default=os.getcwd())
args = parser.parse_args()

DATA_DIR = args.data_dir
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Configuration
# "medium" offers a good balance of speed and accuracy (requires ~1.5GB RAM)
MODEL_SIZE = "tiny.en" 
# Force CPU INT8 for speed and stability
DEVICE = "cpu" 
COMPUTE_TYPE = "int8" 

logging.info(f"Device selected: {DEVICE} ({COMPUTE_TYPE})")

RECORD_FOLDER = os.path.join(DATA_DIR, "recordings")
if not os.path.exists(RECORD_FOLDER):
    os.makedirs(RECORD_FOLDER)

# Logging Setup
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) 

model = None
model_status = "initializing" 
# download_progress is already global from tqdm patch
is_recording = False
is_processing = False
frames = []
stream = None
audio = pyaudio.PyAudio()

# Global config
source_language = "auto" 
target_language = "none" 
sound_enabled = True
formatting_mode = "standard" # standard | raw
smart_polish = False # True | False
gen_z_mode = False # True | False
input_device_index = None
sound_start_path = "start.wav"
sound_stop_path = "stop.wav"
transcription_history = []
update_reminder_ts = 0
MAX_HISTORY = 20 
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

def load_config():
    global update_reminder_ts, source_language, formatting_mode, smart_polish, gen_z_mode, input_device_index, MODEL_SIZE, sound_start_path, sound_stop_path
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if 'update_reminder_ts' in config:
                    update_reminder_ts = config['update_reminder_ts']
                if 'source_language' in config:
                    source_language = config['source_language']
                if 'formatting_mode' in config:
                    formatting_mode = config['formatting_mode']
                if 'smart_polish' in config:
                    smart_polish = config['smart_polish']
                if 'gen_z_mode' in config:
                    gen_z_mode = config['gen_z_mode']
                if 'input_device_index' in config:
                    input_device_index = config['input_device_index']
                if 'model_size' in config:
                    MODEL_SIZE = config['model_size']
                if 'sound_start_path' in config:
                    sound_start_path = config['sound_start_path']
                if 'sound_stop_path' in config:
                    sound_stop_path = config['sound_stop_path']
        except Exception as e:
            logging.error(f"Failed to load config: {e}")

def save_config_file():
    try:
        config_data = {
            "update_reminder_ts": update_reminder_ts,
            "source_language": source_language,
            "formatting_mode": formatting_mode,
            "smart_polish": smart_polish,
            "gen_z_mode": gen_z_mode,
            "input_device_index": input_device_index,
            "model_size": MODEL_SIZE,
            "sound_start_path": sound_start_path,
            "sound_stop_path": sound_stop_path
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
    except Exception as e:
        logging.error(f"Failed to save config: {e}")

def load_history():
    global transcription_history, last_transcribed_text
    load_config() # Load config as well
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                transcription_history = json.load(f)
                
                # Migration: Convert old string-only history to object format
                if transcription_history and isinstance(transcription_history[0], str):
                    new_hist = []
                    current_ts = time.time()
                    for i, text in enumerate(transcription_history):
                        new_hist.append({
                            "text": text,
                            "timestamp": current_ts - (i * 60), # Fake timestamps for old data
                            "duration": 0
                        })
                    transcription_history = new_hist

                if transcription_history:
                    # Get text from the most recent item (index 0)
                    last_item = transcription_history[0]
                    if isinstance(last_item, dict):
                        last_transcribed_text = last_item.get('text', '')
                    else:
                        last_transcribed_text = str(last_item)
                        
        except Exception as e:
            logging.error(f"Failed to load history: {e}")

def save_history():
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(transcription_history, f)
    except Exception as e:
        logging.error(f"Failed to save history: {e}")

# Load history on startup
load_history()

# Mute Logic - SIMPLIFIED AND ROBUST
def mute_system_audio():
    # Attempt 1: Standard Endpoint Volume (Master)
    try:
        pythoncom.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.EndpointVolume
        interface.SetMute(1, None)
    except Exception as e:
        logging.warning(f"Mute method 1 failed: {e}")
        
    # Attempt 2: SimpleAudioVolume (If available, usually per-app, but fallback)
    # Removing complex session iteration as it causes COM interface errors on some Windows builds

def unmute_system_audio():
    # Attempt 1: Standard Endpoint Volume (Master)
    try:
        pythoncom.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.EndpointVolume
        interface.SetMute(0, None)
    except Exception as e:
        logging.warning(f"Unmute method 1 failed: {e}")

# Sound Effects (Custom WAVs with Fallback)
def play_sound(action):
    if not sound_enabled:
        return
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        
        if action == 'start':
            # Check absolute path or relative to base
            if os.path.isabs(sound_start_path):
                wav_path = sound_start_path
            else:
                wav_path = os.path.join(base_path, sound_start_path)
                
            if os.path.exists(wav_path):
                # Play Synchronously so it finishes BEFORE mute_system_audio() runs
                winsound.PlaySound(wav_path, winsound.SND_FILENAME)
            else:
                winsound.Beep(700, 100)
                
        elif action == 'stop':
            if os.path.isabs(sound_stop_path):
                wav_path = sound_stop_path
            else:
                wav_path = os.path.join(base_path, sound_stop_path)
                
            if os.path.exists(wav_path):
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                winsound.Beep(500, 100)
                
        elif action == 'error':
            winsound.Beep(300, 300)
    except Exception as e:
        logging.warning(f"Sound playback failed: {e}")
        # Fallback
        try:
            if action == 'start': winsound.Beep(700, 100)
            elif action == 'stop': winsound.Beep(500, 100)
        except:
            pass

def download_model_with_progress(repo_id, local_dir):
    # tqdm patch handles progress update
    try:
        logging.info(f"Starting download for {repo_id} to {local_dir}")
        snapshot_download(repo_id=repo_id, local_dir=local_dir, local_dir_use_symlinks=False)
        logging.info("Download complete.")
    except Exception as e:
        logging.error(f"Download failed: {e}")
        raise e

def get_model_path(repo_id, base_local_dir):
    """
    Dynamically finds the correct model directory.
    Checks 'snapshots' for a valid folder containing 'model.bin'.
    Returns ABSOLUTE path to avoid any relative path issues.
    """
    abs_base = os.path.abspath(base_local_dir)
    snapshot_root = os.path.join(abs_base, "snapshots")
    
    if os.path.exists(snapshot_root):
        # Get all subdirectories in snapshots
        snapshots = [
            os.path.join(snapshot_root, d) 
            for d in os.listdir(snapshot_root) 
            if os.path.isdir(os.path.join(snapshot_root, d))
        ]
        
        # Sort by name (hashes usually imply version/date indirectly, but mostly random)
        # However, checking for content is more important.
        for snapshot_dir in snapshots:
            if os.path.exists(os.path.join(snapshot_dir, "model.bin")):
                logging.info(f"Found valid model snapshot: {snapshot_dir}")
                return snapshot_dir
                
    # Fallback to base or check if model.bin is in base (e.g. tiny.en case)
    if os.path.exists(os.path.join(abs_base, "model.bin")):
        return abs_base
        
    logging.warning(f"Could not find model.bin in {abs_base} or snapshots. Returning base.")
    return abs_base

def ensure_vocabulary_file(model_path):
    """
    Workaround for CTranslate2 on Windows sometimes failing to load vocabulary.json
    for Large-v3. If vocabulary.txt is missing but vocabulary.json exists,
    we convert it to the expected text format.
    """
    try:
        json_path = os.path.join(model_path, "vocabulary.json")
        txt_path = os.path.join(model_path, "vocabulary.txt")
        
        if os.path.exists(json_path) and not os.path.exists(txt_path):
            logging.info(f"Converting vocabulary.json to vocabulary.txt in {model_path}")
            with open(json_path, "r", encoding="utf-8") as f:
                vocab_list = json.load(f)
            
            with open(txt_path, "w", encoding="utf-8") as f:
                for token in vocab_list:
                    f.write(token + "\n")
            logging.info("Vocabulary conversion complete.")
    except Exception as e:
        logging.warning(f"Vocabulary conversion failed (this might be fine if not needed): {e}")

def load_model():
    global model, model_status, download_progress, current_max_total
    if model is not None: 
        model_status = "ready"
        return
        
    model_status = "loading" # Internal state, but UI will show "Ready" aggressively
    download_progress = 0
    current_max_total = 0 
    logging.info(f"Status: {model_status} - {MODEL_SIZE} ({COMPUTE_TYPE})...")
    
    try:
        repo_id = f"Systran/faster-whisper-{MODEL_SIZE}"
        local_dir = os.path.join(DATA_DIR, "model_cache", f"models--Systran--faster-whisper-{MODEL_SIZE}")
        
        # SKIP download check if folder exists and has content to be INSTANT and LOCAL
        # Strictly offline mode if files are present
        if os.path.exists(local_dir) and os.listdir(local_dir):
             logging.info("Model files found locally. Skipping online check.")
             model_status = "loading"
        else:
             # Only try download if absolutely missing
             logging.info("Model missing locally. Downloading...")
             model_status = "downloading"
             snapshot_download(repo_id=repo_id, local_dir=local_dir)
             download_progress = 100
             model_status = "loading"
        
        logging.info("Loading model from cache...")
        
        # DYNAMIC PATH RESOLUTION
        final_model_path = get_model_path(repo_id, local_dir)
        logging.info(f"Resolved model path: {final_model_path}")
        
        # FIX VOCABULARY ISSUE
        ensure_vocabulary_file(final_model_path)
        
        # Load silently. UI will just say "Ready" and if user clicks record, it might delay slightly but feels instant.
        # Pass FINAL PATH directly to force local loading
        try:
            logging.info(f"Loading model on {DEVICE}...")
            # Optimization: Set cpu_threads to 4 for faster inference on standard CPUs
            model = WhisperModel(final_model_path, device=DEVICE, compute_type=COMPUTE_TYPE, cpu_threads=4)
        except Exception as e:
            logging.error(f"Failed to load model: {e}")
            raise e
        
        model_status = "ready"
        logging.info("Model loaded successfully.")
    except Exception as e:
        model_status = "error"
        logging.error(f"Error loading model: {e}")
    
# Start loading model immediately in background
threading.Thread(target=load_model, daemon=True).start()

def record_thread():
    global is_recording, frames, stream
    
    # Initialize COM for this thread
    pythoncom.CoInitialize()

    # 1. Play Start Sound
    play_sound('start')
    
    # 2. Mute System Audio (after beep)
    mute_system_audio() # Disabled by user request


    try:
        # Use default input device or selected
        device_index = input_device_index
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, 
                          frames_per_buffer=1024, input_device_index=device_index)
        frames = []
        logging.info("Recording started...")
        
        while is_recording:
            try:
                data = stream.read(1024)
                frames.append(data)
                
                # Check for audio energy (silence detection debug)
                # audio_data = np.frombuffer(data, dtype=np.int16)
                # energy = np.sum(np.abs(audio_data))
                # if energy < 500: logging.debug("Low audio energy detected")
                
            except IOError as e:
                logging.warning(f"Stream read error: {e}")
                continue
                
    except Exception as e:
        logging.error(f"Recording error: {e}")
        play_sound('error')
    finally:
        # 3. Stop Recording
        if stream:
            stream.stop_stream()
            stream.close()
        
        # 4. Unmute System Audio (before stop beep)
        unmute_system_audio() # Disabled by user request


        logging.info("Recording stopped.")
        play_sound('stop')
        
        # Save and transcribe
        if frames:
            threading.Thread(target=save_and_transcribe, daemon=True).start()
        else:
            logging.warning("No audio frames captured.")

last_transcribed_text = ""

def save_and_transcribe():
    global is_processing
    is_processing = True

    # WAIT for model to be ready if it's still loading
    wait_start = time.time()
    while model is None or model_status != "ready":
        if time.time() - wait_start > 120: # 2 min timeout
            logging.error("Timeout waiting for model load")
            is_processing = False
            return
        time.sleep(0.5)
    
    timestamp = int(time.time())
    filename = os.path.join(RECORD_FOLDER, f"rec_{timestamp}.wav")
    
    try:
        wf = wave.open(filename, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        # Calculate duration
        # frames is a list of chunks, each chunk is 1024 samples (Int16)
        # Duration = Total Samples / Sample Rate
        duration = (len(frames) * 1024) / 16000.0
        
        transcribe_audio(filename, duration)
        
        # Clean up file immediately after use
        try:
            if os.path.exists(filename):
                os.remove(filename)
                logging.info(f"Deleted temp file: {filename}")
        except Exception as cleanup_e:
            logging.warning(f"Failed to delete temp file: {cleanup_e}")
                
    except Exception as e:
        logging.error(f"Transcription/Processing error: {e}")
    finally:
        is_processing = False

import re

def polish_text(text):
    """
    Simple heuristic-based text polisher.
    Removes common fillers and handles basic self-corrections.
    """
    # 1. Remove fillers
    # Case insensitive
    fillers = [
        r"\bhm+\b", r"\buh+\b", r"\bum+\b", r"\ber+\b", 
        r"\bah+\b", r"\byou know\b", r"\byou know what\b",
        r"\blike\b"
    ]
    
    polished = text
    for f in fillers:
        polished = re.sub(f, "", polished, flags=re.IGNORECASE)
    
    # 2. Handle "nevermind" / "scratch that"
    undo_phrases = [r"\bnevermind\b", r"\bnvm\b", r"\bscratch that\b", r"\bforget it\b"]
    
    for phrase in undo_phrases:
        if re.search(phrase, polished, re.IGNORECASE):
            parts = re.split(phrase, polished, flags=re.IGNORECASE)
            if len(parts) > 1:
                last_part = parts[-1].strip()
                if last_part:
                    polished = last_part
                else:
                    polished = ""
                    
    # Clean up double spaces and punctuation
    polished = re.sub(r"\s+", " ", polished).strip()
    polished = re.sub(r"\s+([,.!?])", r"\1", polished)
    
    return polished

def gen_z_transform(text):
    """
    Transforms text into Gen Z slang (Brainrot mode).
    """
    replacements = {
        r"\b(hello|hi|hey)\b": "yooo",
        r"\b(good|great|nice|excellent)\b": "bussin",
        r"\b(bad|terrible|awful)\b": "mid",
        r"\b(yes|yeah|sure|okay|ok)\b": "bet",
        r"\b(no|nope)\b": "cap",
        r"\b(friend|dude|man|guy)\b": "blud",
        r"\b(funny|hilarious)\b": "sending me",
        r"\b(lie|lying)\b": "cap",
        r"\b(love|like)\b": "simp for",
        r"\b(very|really)\b": "highkey",
        r"\b(kind of|sort of)\b": "lowkey",
        r"\b(cool|awesome)\b": "lit",
        r"\b(crazy|wild)\b": "wild",
        r"\b(understand|get it)\b": "vibe with",
    }
    
    import random
    
    polished = text
    for pattern, replacement in replacements.items():
        if random.random() < 0.7: # 70% chance to replace
            polished = re.sub(pattern, replacement, polished, flags=re.IGNORECASE)
            
    # Random suffixes
    suffixes = [" no cap", " fr fr", " on god", " deadass", " 💀", " 😭", " sheesh"]
    if random.random() < 0.5:
        polished += random.choice(suffixes)
        
    return polished

def transcribe_audio(filename, duration=0):
    global is_processing, model, last_transcribed_text
    # is_processing is True from caller
    try:
        logging.info("Transcribing...")
        
        # Determine language settings
        lang_arg = source_language if source_language != "auto" else None
        
        logging.info(f"Using model: {MODEL_SIZE} on {DEVICE}")
        
        start_time = time.time()
        # Optimization: Reduced beam_size to 1 (Greedy search) for 3-5x speedup
        # Optimization: Enable VAD to skip silence
        segments, info = model.transcribe(
            filename, 
            beam_size=1, 
            language=lang_arg,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False # Optim: Don't look back, faster for short dictation
        )
        
        logging.info("Generator created. Iterating segments...")
        text = " ".join([segment.text for segment in segments]).strip()
        end_time = time.time()
        logging.info(f"Transcription finished in {end_time - start_time:.2f}s. Detected ({info.language}): {text}")
        
        if text:
            # History Management
            history_item = {
                "text": text,
                "timestamp": time.time(),
                "duration": duration
            }
            transcription_history.insert(0, history_item)
            if len(transcription_history) > MAX_HISTORY:
                transcription_history.pop()
            
            save_history()
                
            last_transcribed_text = text
            final_text = text
            
            # Formatting Logic
            if formatting_mode == "raw":
                final_text = final_text.lower().replace(".", "").replace(",", "").replace("?", "")
            
            # Smart Polish
            if smart_polish:
                logging.info(f"Polishing text: '{final_text}'")
                final_text = polish_text(final_text)
                logging.info(f"Polished result: '{final_text}'")
            
            # Gen Z Mode
            if gen_z_mode:
                logging.info(f"Gen Z transforming: '{final_text}'")
                final_text = gen_z_transform(final_text)
                logging.info(f"Gen Z result: '{final_text}'")

            # Translation Logic
            if target_language and target_language != "none" and target_language != info.language:
                logging.info(f"Translating to {target_language}...")
                try:
                    translated = GoogleTranslator(source='auto', target=target_language).translate(text)
                    logging.info(f"Translated: {translated}")
                    final_text = translated
                except Exception as te:
                    logging.error(f"Translation failed: {te}")
            
            logging.info(f"Typing: {final_text}")
            
            # Typing Animation (Vibes)
            # Use clipboard for reliable text transfer, but type character by character?
            # No, that's slow and error prone with modifiers.
            # Best approach for "typing effect":
            # 1. Paste text instantly (reliable)
            # 2. OR pyautogui.write() which types letter by letter.
            
            try:
                # User requested "animation" / "letter by letter"
                # pyautogui.write(text, interval=0.01) types with delay.
                # However, write() doesn't handle unicode/emojis well on Windows sometimes.
                # Hybrid approach: Copy to clipboard (just in case), then try write.
                
                pyperclip.copy(final_text + " ")
                
                # Check if text is simple ascii (safe to type) or complex
                is_complex = any(ord(c) > 127 for c in final_text)
                
                if is_complex:
                     # Fallback to instant paste for complex chars (Chinese, Emojis, etc)
                     pyautogui.hotkey('ctrl', 'v')
                else:
                     # Type it out for the vibes!
                     # interval=0.01 is fast but visible. 0.05 is slower.
                     # User said "as fast as it can" earlier but now "letter by letter for vibes".
                     # Let's do 0.005 - extremely fast but still "typing".
                     pyautogui.write(final_text + " ", interval=0.01)
                     
            except Exception as e:
                logging.error(f"Typing failed: {e}")
        else:
            logging.info("No speech detected.")
                
    except Exception as e:
        logging.error(f"Transcription logic error: {e}")
    finally:
        is_processing = False

def paste_last_text():
    global last_transcribed_text
    if last_transcribed_text:
        try:
            logging.info(f"Pasting last text: {last_transcribed_text}")
            pyperclip.copy(last_transcribed_text + " ")
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            play_sound('start')
        except Exception as e:
            logging.error(f"Paste last failed: {e}")
    else:
        logging.warning("No last text to paste.")
        play_sound('error')

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "model_loaded": model is not None,
        "model_status": model_status,
        "download_progress": download_progress,
        "is_recording": is_recording,
        "is_processing": is_processing
    })

@app.route('/start', methods=['POST'])
def start_record():
    global is_recording
    # Removed strict model check for instant recording
    # if model_status != "ready":
    #     return jsonify({"status": "error", "message": "Model not ready"}), 400
        
    if not is_recording:
        is_recording = True
        threading.Thread(target=record_thread, daemon=True).start()
    return jsonify({"status": "started"})

@app.route('/config', methods=['GET', 'POST'])
def handle_config():
    global source_language, input_device_index, formatting_mode, MODEL_SIZE, smart_polish, gen_z_mode, sound_start_path, sound_stop_path
    if request.method == 'POST':
        data = request.json
        if 'source_language' in data:
            source_language = data['source_language']
        if 'input_device_index' in data:
            input_device_index = data['input_device_index']
        if 'formatting_mode' in data:
            formatting_mode = data['formatting_mode']
        if 'smart_polish' in data:
            smart_polish = data['smart_polish']
        if 'gen_z_mode' in data:
            gen_z_mode = data['gen_z_mode']
        if 'model_size' in data:
            MODEL_SIZE = data['model_size']
        if 'sound_start_path' in data:
            sound_start_path = data['sound_start_path']
        if 'sound_stop_path' in data:
            sound_stop_path = data['sound_stop_path']
            
        save_config_file()
        return jsonify({"status": "success"})
    else:
        return jsonify({
            "source_language": source_language,
            "input_device_index": input_device_index,
            "formatting_mode": formatting_mode,
            "model_size": MODEL_SIZE,
            "smart_polish": smart_polish,
            "gen_z_mode": gen_z_mode,
            "sound_start_path": sound_start_path,
            "sound_stop_path": sound_stop_path,
            "history": transcription_history
        })


def get_downloaded_models():
    """
    Scans the model_cache directory to find which models are already downloaded.
    Returns a list of model IDs (e.g. ['tiny.en', 'base']).
    """
    downloaded = []
    cache_dir = os.path.join(DATA_DIR, "model_cache")
    
    if not os.path.exists(cache_dir):
        return []
        
    # Standard sizes to check for
    # The directory name format is "models--Systran--faster-whisper-{size}"
    possible_sizes = ["tiny.en", "tiny", "base.en", "base", "small.en", "small", "medium.en", "medium", "large-v2", "large-v3"]
    
    for size in possible_sizes:
        dir_name = f"models--Systran--faster-whisper-{size}"
        model_path = os.path.join(cache_dir, dir_name)
        # Check if directory exists and has content (not empty)
        if os.path.exists(model_path) and os.listdir(model_path):
            # Also check if it has the actual model file (snapshots or root)
            # Simplistic check: if folder is there and not empty, assume downloaded
            downloaded.append(size)
            
    return downloaded

@app.route('/downloaded_models', methods=['GET'])
def list_downloaded_models():
    return jsonify(get_downloaded_models())

@app.route('/model_status', methods=['GET'])
def get_model_status():
    return jsonify({
        "status": model_status,
        "progress": download_progress,
        "current_model": MODEL_SIZE
    })

@app.route('/download_model', methods=['POST'])
def trigger_download_model():
    global MODEL_SIZE, model, model_status
    data = request.json
    new_size = data.get('model_size')
    
    if new_size and new_size != MODEL_SIZE:
        MODEL_SIZE = new_size
        save_config_file()
        
        # Reset model to trigger reload/download
        model = None
        model_status = "initializing"
        
        # Start loading/downloading in background
        threading.Thread(target=load_model, daemon=True).start()
        
        return jsonify({"status": "started", "model_size": MODEL_SIZE})
    elif new_size == MODEL_SIZE and model_status == "ready":
         return jsonify({"status": "already_ready", "model_size": MODEL_SIZE})
    
    return jsonify({"status": "ignored"})

@app.route('/devices', methods=['GET'])
def get_devices():
    devices = []
    info = audio.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        if (audio.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            name = audio.get_device_info_by_host_api_device_index(0, i).get('name')
            devices.append({"index": i, "name": name})
    return jsonify(devices)


@app.route('/stop', methods=['POST'])
def stop_record():
    global is_recording
    if is_recording:
        is_recording = False
    return jsonify({"status": "stopped"})

@app.route('/paste', methods=['POST'])
def paste_last():
    paste_last_text()
    return jsonify({"status": "pasted"})

def hotkey_loop():
    # Push-to-Talk Logic (Hold Ctrl+Alt)
    global is_recording
    was_pressed = False
    was_paste_pressed = False
    
    while True:
        # Paste Hotkey (Ctrl+Shift+P)
        is_paste_pressed = keyboard.is_pressed('ctrl+shift+p')
        if is_paste_pressed and not was_paste_pressed:
            paste_last_text()
            was_paste_pressed = True
        elif not is_paste_pressed:
            was_paste_pressed = False
            
        # Record Hotkey (Ctrl+Alt)
        # Avoid triggering record if P is also pressed (though less likely with shift now)
        is_record_pressed = keyboard.is_pressed('ctrl+alt')
        
        if is_record_pressed and not was_pressed:
            # Key Down -> Start Recording
            if not is_recording:
                is_recording = True
                threading.Thread(target=record_thread, daemon=True).start()
            was_pressed = True
            
        elif not is_record_pressed and was_pressed:
            # Key Up -> Stop Recording
            if is_recording:
                is_recording = False
            was_pressed = False
            
        time.sleep(0.05)

threading.Thread(target=hotkey_loop, daemon=True).start()

if __name__ == '__main__':
    app.run(port=5000)
