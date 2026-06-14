import json
import os
import threading
import time
from collections import deque

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(PACKAGE_ROOT, "config.json")
SESSION_FILE = os.path.join(PACKAGE_ROOT, "session.json")

MORSE_DICT = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E', '..-.': 'F',
    '--.': 'G', '....': 'H', '..': 'I', '.---': 'J', '-.-': 'K', '.-..': 'L',
    '--': 'M', '-.': 'N', '---': 'O', '.--.': 'P', '--.-': 'Q', '.-.': 'R',
    '...': 'S', '-': 'T', '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X',
    '-.--': 'Y', '--..': 'Z', '-----': '0', '.----': '1', '..---': '2',
    '...--': '3', '....-': '4', '.....': '5', '-....': '6', '--...': '7',
    '---..': '8', '----.': '9'
}

COMMAND_DICT = {
    '........': 'BACKSPACE',
    '.-.-.-': 'ENTER',
    '--.--': 'CLICK',
    '.-.-': 'SHOW_DESKTOP',
    '------': 'AI_MODE',
    '...---...': 'WEB_SEARCH',
    '------...': 'EMERGENCY',
    '-...-': 'DELETE_WORD',
    '.--.-.': 'CLEAR_MESSAGE',
    '.-..-': 'DELETE_LAST_MESSAGE',
    '..--..': 'UNDO',
}




PREDICTIVE_CORPUS = {
    "a": ["about", "again", "afternoon"],
    "b": ["bed", "bathroom", "back"],
    "c": ["caregiver", "call", "chair"],
    "d": ["doctor", "document", "door"],
    "e": ["emergency", "email", "eat"],
    "f": ["family", "father", "food"],
    "g": ["good", "go", "glasses"],
    "h": ["hungry", "hurt", "hospital"],
    "i": ["important", "inside", "issue"],
    "j": ["just", "job", "jacket"],
    "k": ["know", "kitchen", "key"],
    "l": ["light", "later", "lunch"],
    "m": ["medicine", "medical", "message"],
    "n": ["nurse", "nutrition", "night"],
    "o": ["outside", "open", "ointment"],
    "p": ["please", "place", "plan"],
    "q": ["question", "quick", "quiet"],
    "r": ["room", "routine", "ready"],
    "s": ["sleep", "sorry", "shower"],
    "t": ["thank you", "thirsty", "therapy"],
    "u": ["understand", "urgent", "upstairs"],
    "v": ["visit", "vaccine", "vitamin"],
    "w": ["water", "wash", "warm"],
    "x": ["x-ray", "xerox", "xbox"],
    "y": ["yes", "yesterday", "year"],
    "z": ["zero", "zipper", "zone"],
}

AI_MODALITIES = ["QUESTION", "CONVERSATION", "COMMAND", "MICROSOFT_FOUNDRY"]

THEMES = {
    "HIGH_CONTRAST": {"bg": "#000000", "text": "#00ff00", "accent": "#ffff00", "panel": "#000000", "font_f": "Courier"},
    "DARK": {"bg": "#1e1e2e", "text": "#cdd6f4", "accent": "#89b4fa", "panel": "#313244", "font_f": "Helvetica"},
    "LIGHT": {"bg": "#eff1f5", "text": "#4c4f69", "accent": "#1e66f5", "panel": "#e6e9ef", "font_f": "Helvetica"}
}

class StateManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.message_history = []
        self.current_message_str = ""
        self.last_input_time = time.time()
        self.is_recording = True
        self.ai_input_buffer = []
        # Buffer of the currently decoded, not-yet-committed Morse character.
        # In TYPE mode, SPACE is the only event that commits into current_message_str.
        self.pending_character = ""
        self.word_accumulator = ""
        self.system_mode = "TYPE"

        self.ai_modality_index = 0
        self.space_dropped = False
        self.type_mode_char_count = 0
        self.active_predictions = []
        self.output_action_history = deque(maxlen=100)
        self.undo_stack = deque(maxlen=100)
        self.search_history = []
        # Ensure always present to avoid UI/save crashes.
        self.conversation_history = []

        self.last_search_query = ""
        self.last_ai_error = ""
        self.ai_status = "🟡 Missing API Key"
        self.theme = THEMES["DARK"]
        self.keystroke_intervals = deque(maxlen=10)
        self.last_keystroke_timestamp = None
        self.dynamic_idle_timeout = 1.6
        self.ANALYTICS = {
            "total_keystrokes": 0,
            "saved_keystrokes": 0,
            "user_words": 0,
            "ai_words": 0,
            "prediction_count": 0,
            "user_generated_characters": 0,
            "ai_generated_characters": 0,
            "start_time": time.time(),
            "last_wpm_user": 0,
            "last_wpm_ai": 0,
        }
        self.current_buffer = ""
        # Debug/UI: track whether input listeners are active and what was last pressed
        self.keyboard_enabled = False
        self.last_morse_key_pressed = ""
        self.last_morse_sequence = ""
        self.root = None
        self.ui_elements = {}


    def stop_recording(self):
        with self.lock:
            self.is_recording = False

    def save_session(self):
        with self.lock:
            try:
                with open(SESSION_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "message_history": self.message_history[-50:],
                        "search_history": self.search_history[-100:],
                        "conversation_history": self.conversation_history[-100:] if hasattr(self, "conversation_history") else [],
                        "last_search_query": self.last_search_query,
                        "last_ai_error": self.last_ai_error,
                        "ai_status": self.ai_status,
                    }, f, ensure_ascii=False, indent=2)
            except OSError:
                pass

    def load_session(self):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.message_history = data.get("message_history", [])[:50]
            self.search_history = data.get("search_history", [])[:100]
            self.conversation_history = data.get("conversation_history", [])[:100]
            self.last_search_query = self.search_history[-1] if self.search_history else ""
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError):
            pass

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            theme_name = cfg.get("theme")
            if theme_name in THEMES:
                self.theme = THEMES[theme_name]
        except FileNotFoundError:
            self.theme = THEMES["DARK"]
        except (json.JSONDecodeError, OSError):
            self.theme = THEMES["DARK"]

    def save_config(self):
        theme_name = next((name for name, t in THEMES.items() if t is getattr(self, "theme", THEMES["DARK"])), "DARK")
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"theme": theme_name}, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def snapshot(self):
        with self.lock:
            return {
                "current_message_str": self.current_message_str,
                "ai_input_buffer": list(self.ai_input_buffer),
                "word_accumulator": self.word_accumulator,
                "pending_character": getattr(self, "pending_character", ""),
                "message_history": list(self.message_history),
                "search_history": list(self.search_history),
                "last_search_query": self.last_search_query,
                "conversation_history": list(self.conversation_history) if hasattr(self, "conversation_history") else [],
                "ai_status": self.ai_status,
                "last_ai_error": self.last_ai_error,
                "system_mode": self.system_mode,
            }


    def restore(self, snapshot):
        with self.lock:
            self.current_message_str = snapshot["current_message_str"]
            self.ai_input_buffer = list(snapshot["ai_input_buffer"])
            self.word_accumulator = snapshot["word_accumulator"]
            self.pending_character = snapshot.get("pending_character", "")

            self.message_history = list(snapshot["message_history"])
            self.search_history = list(snapshot["search_history"])
            self.last_search_query = snapshot["last_search_query"]
            self.conversation_history = list(snapshot["conversation_history"])
            self.ai_status = snapshot["ai_status"]
            self.last_ai_error = snapshot["last_ai_error"]
            self.system_mode = snapshot["system_mode"]


state_manager = StateManager()
