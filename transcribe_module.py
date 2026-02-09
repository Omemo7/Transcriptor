import os
import sys
import time
from faster_whisper import WhisperModel

DEVICE = "cuda"
COMPUTE_TYPE = "float16"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

MODEL_DIR = resource_path("models")

# --- GLOBAL MODEL (Prevents Crash) ---
_GLOBAL_MODEL = None

def load_model_globally(status_callback=None):
    global _GLOBAL_MODEL
    if _GLOBAL_MODEL is None:
        if status_callback: status_callback("Loading Model (One-time setup)...")
        # Validate path first
        model_file = os.path.join(MODEL_DIR, "model.bin")
        if not os.path.exists(model_file):
            raise FileNotFoundError(f"CRITICAL: 'model.bin' not found in {MODEL_DIR}")
            
        _GLOBAL_MODEL = WhisperModel(MODEL_DIR, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _GLOBAL_MODEL

def run_transcription(audio_path, progress_callback=None, status_callback=None, check_cancel=None):
    try:
        # 1. Load the persistent model
        model = load_model_globally(status_callback)

        if status_callback: status_callback(f"Transcribing {os.path.basename(audio_path)}...")

        initial_prompt = (
            "هذا التسجيل باللهجة الأردنية العامية. "
            "يرجى كتابة النص كما هو مسموع تماماً. "
            "المصطلحات التقنية تكتب بالإنجليزية."
        )

        segments_generator, info = model.transcribe(
            audio_path,
            language="ar",
            initial_prompt=initial_prompt,
            beam_size=1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False 
        )

        total_duration = info.duration
        
        text_buffer = []
        last_milestone = 0

        for segment in segments_generator:
            if check_cancel and check_cancel(): 
                break

            text_buffer.append(segment.text.strip())
            
            if total_duration > 0:
                current_percent = (segment.end / total_duration) * 100
            else:
                current_percent = 0

            # --- 1% UPDATE LOGIC ---
            # We now update every 1% (much smoother)
            if (current_percent - last_milestone >= 1) or (current_percent >= 99 and last_milestone < 99):
                
                chunk_text = " ".join(text_buffer)
                
                if progress_callback:
                    # Send: (0.XX float, Text Chunk)
                    progress_callback(current_percent / 100.0, chunk_text)
                
                text_buffer = [] # Clear buffer
                last_milestone = current_percent

        # Final flush for any remaining text
        if text_buffer:
            final_chunk = " ".join(text_buffer)
            if progress_callback:
                progress_callback(1.0, final_chunk)

        if status_callback: status_callback("Done!")

    except Exception as e:
        raise e
    
    # CRITICAL: Model stays alive globally.