from mutagen.mp3 import MP3
from mutagen.wave import WAVE
import os

def get_audio_duration(file_path):
    """
    Returns the duration of the audio file in seconds (float).
    Returns 0 if it fails or format is unsupported.
    """
    if not os.path.exists(file_path):
        return 0

    try:
        # Check file extension
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.mp3':
            audio = MP3(file_path)
            return audio.info.length  # Duration in seconds
        
        elif ext == '.wav':
            audio = WAVE(file_path)
            return audio.info.length
            
        else:
            # Fallback for other formats (requires 'mutagen.File')
            from mutagen import File
            audio = File(file_path)
            if audio is not None and audio.info is not None:
                return audio.info.length
            
    except Exception as e:
        print(f"Error reading duration: {e}")
    
    return 0

# --- Helper to make it readable (MM:SS) ---
def format_duration(seconds):
    if not seconds: return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

# --- Usage ---
# duration = get_audio_duration("C:/Music/song.mp3")
# print(format_duration(duration)) # Output: "03:45"