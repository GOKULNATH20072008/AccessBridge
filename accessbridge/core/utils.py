import logging
import platform
import sys
import threading
from queue import Queue, Empty

try:
    import pyautogui
except Exception:
    pyautogui = None

# Make logs visible both in console and in accessbridge.log.
# Without a StreamHandler, you can miss callback failures.
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(threadName)s - %(message)s")

_file_handler = logging.FileHandler("accessbridge.log", encoding="utf-8")
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(_formatter)

_stream_handler = logging.StreamHandler()
_stream_handler.setLevel(logging.INFO)
_stream_handler.setFormatter(_formatter)

# Avoid duplicate handlers if modules reload.
if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
    root_logger.addHandler(_file_handler)
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    root_logger.addHandler(_stream_handler)

logger = logging.getLogger(__name__)


gui_task_queue = Queue()
root = None

tts_queue = Queue()

if pyautogui is not None:
    try:
        pyautogui.FAILSAFE = True
    except Exception:
        pass

HAS_TTS = False
tts_engine = None
try:
    import pyttsx3
    HAS_TTS = True
    tts_engine = pyttsx3.init()
    tts_engine.setProperty("rate", 165)
except Exception:
    HAS_TTS = False
    tts_engine = None


def set_gui_root(root_window):
    global root
    root = root_window


def _process_gui_queue():
    while True:
        try:
            action = gui_task_queue.get_nowait()
        except Empty:
            break
        try:
            action()
        except Exception:
            logger.exception("GUI queued action failure")


def schedule_on_main(func, *args, **kwargs):
    try:
        def action():
            func(*args, **kwargs)
        gui_task_queue.put(action)
        if root is not None:
            root.after(0, _process_gui_queue)
        else:
            _process_gui_queue()
    except Exception:
        logger.exception("schedule_on_main failure")


def gui_write(text: str):
    if pyautogui is None:
        return
    pyautogui.write(text)


def gui_press(key: str, presses: int = 1):
    if pyautogui is None:
        return
    pyautogui.press(key, presses=presses)


def gui_hotkey(*keys):
    if pyautogui is None:
        return
    pyautogui.hotkey(*keys)


def gui_click():
    if pyautogui is None:
        return
    pyautogui.click()


def play_click_async(is_dah: bool = False):
    def _beep():
        try:
            if platform.system() == "Windows":
                import winsound
                freq = 600 if is_dah else 950
                duration_ms = 60 if is_dah else 35
                winsound.Beep(freq, duration_ms)
            else:
                sys.stdout.write("\a")
                sys.stdout.flush()
        except Exception:
            logger.exception("Audio feedback failure")

    threading.Thread(target=_beep, daemon=True, name="ClickFeedback").start()


def start_tts_worker_if_needed():
    global HAS_TTS, tts_engine
    if not HAS_TTS:
        return

    if not hasattr(start_tts_worker_if_needed, "worker_started"):
        start_tts_worker_if_needed.worker_started = False

    if not start_tts_worker_if_needed.worker_started:
        start_tts_worker_if_needed.worker_started = True

        def tts_worker():
            while True:
                try:
                    text = tts_queue.get()
                    if text is None:
                        break
                    tts_engine.say(text)
                    tts_engine.runAndWait()
                except Exception:
                    logger.exception("TTS worker failure")

        threading.Thread(target=tts_worker, daemon=True, name="TTS-Worker").start()


def speak_text_async(text_to_speak):
    if not HAS_TTS:
        return
    try:
        start_tts_worker_if_needed()
        # Use the module-level queue (not a function attribute).
        tts_queue.put(str(text_to_speak))

    except Exception:
        logger.exception("Failed to enqueue TTS text")
