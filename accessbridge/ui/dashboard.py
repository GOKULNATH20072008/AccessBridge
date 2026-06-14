import tkinter as tk
import time
from accessbridge.core.state import state_manager
from accessbridge.core.utils import schedule_on_main, set_gui_root

from accessbridge.core.state import AI_MODALITIES, THEMES

# Adjust this import path to match where handler.py actually lives in your project
# (e.g. accessbridge.morse.handler / accessbridge.input.handler).
from accessbridge.input.handler import register_tk_listeners

class Dashboard:
    def __init__(self, state):
        self.state = state
        self.root = None
        self.ui_elements = {}

    def apply_theme(self):
        theme = self.state.theme
        if not self.root:
            return
        self.root.configure(bg=theme["bg"])
        self.ui_elements["panel_top"].configure(bg=theme["panel"])
        self.ui_elements["lbl_status"].configure(bg=theme["panel"], fg=theme["text"], font=(theme["font_f"], 10, "bold"))
        self.ui_elements["lbl_mode"].configure(bg=theme["panel"], fg=theme["accent"], font=(theme["font_f"], 10, "bold"))
        self.ui_elements["lbl_session"].configure(bg=theme["panel"], fg=theme["text"], font=(theme["font_f"], 10))
        self.ui_elements["lbl_words"].configure(bg=theme["panel"], fg=theme["text"], font=(theme["font_f"], 10))
        self.ui_elements["lbl_saved"].configure(bg=theme["panel"], fg=theme["text"], font=(theme["font_f"], 10))
        self.ui_elements["lbl_buffer"].configure(bg=theme["bg"], fg=theme["text"], font=("Courier", 16, "bold"))
        self.ui_elements["lbl_prediction"].configure(bg=theme["bg"], fg=theme["accent"], font=(theme["font_f"], 11, "italic"))
        self.ui_elements["lbl_msg_preview"].configure(bg=theme["bg"], fg=theme["text"], font=("Courier", 12))
        self.ui_elements["txt_history"].configure(bg=theme["panel"], fg=theme["text"], font=(theme["font_f"], 9), insertbackground=theme["text"])

    def update_hud(self):
        with self.state.lock:
            system_mode = self.state.system_mode
            ai_modality_index = self.state.ai_modality_index
            current_buffer = self.state.current_buffer
            active_predictions = list(self.state.active_predictions)
            analytics = dict(self.state.ANALYTICS)
            current_message_str = self.state.current_message_str
            message_history = list(self.state.message_history[-5:])
            search_history = list(self.state.search_history[-5:])
            conversation_history = list(self.state.conversation_history[-6:]) if hasattr(self.state, "conversation_history") else []
            last_search_query = self.state.last_search_query
            dynamic_idle_timeout = self.state.dynamic_idle_timeout
            current_ai_prompt = " ".join(self.state.ai_input_buffer + ([self.state.word_accumulator] if self.state.word_accumulator else [])).strip()
            ai_status = self.state.ai_status
            keyboard_enabled = getattr(self.state, "keyboard_enabled", False)
            last_key_pressed = getattr(self.state, "last_morse_key_pressed", "")
            last_seq = getattr(self.state, "last_morse_sequence", "")


        elapsed_s = max(0.001, time.time() - analytics["start_time"])
        elapsed_m = int(elapsed_s / 60)
        def wpm(chars):
            minutes = elapsed_s / 60.0
            return 0.0 if minutes <= 0 else (chars / 5.0) / minutes

        self.ui_elements["lbl_status"].config(text=ai_status)
        mode_str = f"Mode: {system_mode}"
        if system_mode == "AI":
            mode_str += f" ({AI_MODALITIES[ai_modality_index]})"
        self.ui_elements["lbl_mode"].config(text=mode_str)
        self.ui_elements["lbl_session"].config(text=f"Time Active: {elapsed_m}m | Idle Cutoff: {dynamic_idle_timeout:.2f}s")
        self.ui_elements["lbl_words"].config(text=f"Words (User/AI): {analytics['user_words']}/{analytics['ai_words']} | WPM(User/AI): {int(wpm(analytics['user_generated_characters']))}/{int(wpm(analytics['ai_generated_characters']))}")
        self.ui_elements["lbl_saved"].config(text=f"Predictions: {analytics['prediction_count']}")
        buf_display = current_buffer if current_buffer else "[Waiting for input]"
        self.ui_elements["lbl_buffer"].config(text=f"Morse Stack: {buf_display}")
        self.ui_elements["lbl_ai_prompt"].config(text=f"AI Prompt: {current_ai_prompt or '[empty]'}")
        # Display-safe: ensure UI never renders URL-encoded '+' separators or odd whitespace.
        display_last_search_query = " ".join((last_search_query or "").replace("+", " ").split())
        self.ui_elements["lbl_search_status"].config(text=f"Last Search: {display_last_search_query or '[none]'} | Search Count: {len(search_history)}")


        if active_predictions:
            pred_lines = " | ".join([f"{i+1}. {word}" for i, word in enumerate(active_predictions)])
            self.ui_elements["lbl_prediction"].config(text=f"🔮 Options: [Type 1-{len(active_predictions)}] -> {pred_lines}")
        else:
            suggestions = []
            if current_ai_prompt:
                suggestions = self.state.search_history[-3:]
            if suggestions:
                self.ui_elements["lbl_prediction"].config(text=f"Search Suggestions: {' | '.join(suggestions)}")
            else:
                self.ui_elements["lbl_prediction"].config(text="System Standing By...")

        normalized_message = " ".join((current_message_str or "").split())
        self.ui_elements["lbl_msg_preview"].config(text=f"✏️  Message: {normalized_message or '[empty]'}")

        from accessbridge.core.utils import logger
        logger.debug(
            "UI refresh: mode=%s current_message_raw='%s' current_message_norm='%s'",
            self.state.system_mode,
            current_message_str,
            normalized_message,
        )



        self.ui_elements["lbl_listeners"].config(
            text=f"⌨️  Morse listeners: {'ON' if keyboard_enabled else 'OFF'}"
        )
        self.ui_elements["lbl_last_input"].config(
            text=f"🧾  Last key: {last_key_pressed or '[none]'} | Sequence buffer: {last_seq or '[empty]'}"
        )

        txt_widget = self.ui_elements["txt_history"]
        txt_widget.configure(state="normal")
        txt_widget.delete("1.0", "end")
        history_lines = []
        if message_history:
            history_lines.append("Recent Messages:")
            history_lines.extend([f"- {msg}" for msg in message_history])
        if search_history:
            history_lines.append("\nRecent Searches:")
            history_lines.extend([f"- {item}" for item in search_history])
        if conversation_history:
            history_lines.append("\nAI Conversation History:")
            history_lines.extend(conversation_history)
        if not history_lines:
            history_lines.append("[No session history yet]")
        txt_widget.insert("1.0", "\n".join(history_lines))
        txt_widget.configure(state="disabled")

        # Keep updating the HUD so UI reflects decoding/state changes.
        if self.root is not None:
            self.root.after(100, self.update_hud)

    def build(self):

        self.root = tk.Tk()
        self.root.title("AccessBridge Dashboard Pro")
        self.root.geometry("700x360+350+20")
        self.root.attributes("-topmost", True)

        panel_top = tk.Frame(self.root, height=35, relief="flat")
        panel_top.pack(fill="x", side="top")
        self.ui_elements["panel_top"] = panel_top
        self.ui_elements["lbl_status"] = tk.Label(panel_top, text="", anchor="w")
        self.ui_elements["lbl_status"].pack(side="left", padx=10)
        self.ui_elements["lbl_mode"] = tk.Label(panel_top, text="", anchor="w")
        self.ui_elements["lbl_mode"].pack(side="left", padx=15)
        self.ui_elements["lbl_saved"] = tk.Label(panel_top, text="")
        self.ui_elements["lbl_saved"].pack(side="right", padx=10)
        self.ui_elements["lbl_words"] = tk.Label(panel_top, text="")
        self.ui_elements["lbl_words"].pack(side="right", padx=10)
        self.ui_elements["lbl_session"] = tk.Label(panel_top, text="")
        self.ui_elements["lbl_session"].pack(side="right", padx=10)

        self.ui_elements["lbl_buffer"] = tk.Label(self.root, text="", anchor="w")
        self.ui_elements["lbl_buffer"].pack(fill="x", padx=15, pady=(10, 2))
        self.ui_elements["lbl_prediction"] = tk.Label(self.root, text="", anchor="w")
        self.ui_elements["lbl_prediction"].pack(fill="x", padx=15, pady=(2, 2))
        self.ui_elements["lbl_ai_prompt"] = tk.Label(self.root, text="", anchor="w", justify="left", wraplength=670)
        self.ui_elements["lbl_ai_prompt"].pack(fill="x", padx=15, pady=(2, 2))
        self.ui_elements["lbl_search_status"] = tk.Label(self.root, text="", anchor="w", justify="left")
        self.ui_elements["lbl_search_status"].pack(fill="x", padx=15, pady=(2, 2))
        self.ui_elements["lbl_msg_preview"] = tk.Label(self.root, text="", anchor="w", wraplength=670, justify="left")
        self.ui_elements["lbl_msg_preview"].pack(fill="x", padx=15, pady=(2, 2))

        self.ui_elements["lbl_listeners"] = tk.Label(self.root, text="", anchor="w")
        self.ui_elements["lbl_listeners"].pack(fill="x", padx=15, pady=(2, 2))

        self.ui_elements["lbl_last_input"] = tk.Label(self.root, text="", anchor="w", justify="left", wraplength=670)
        self.ui_elements["lbl_last_input"].pack(fill="x", padx=15, pady=(2, 2))


        history_frame = tk.Frame(self.root)
        history_frame.pack(fill="both", expand=True, padx=15, pady=(2, 10))
        self.ui_elements["history_frame"] = history_frame
        history_scrollbar = tk.Scrollbar(history_frame)
        history_scrollbar.pack(side="right", fill="y")
        self.ui_elements["txt_history"] = tk.Text(history_frame, height=10, wrap="word", yscrollcommand=history_scrollbar.set, borderwidth=0)
        self.ui_elements["txt_history"].pack(side="left", fill="both", expand=True)
        self.ui_elements["txt_history"].configure(state="disabled")
        history_scrollbar.config(command=self.ui_elements["txt_history"].yview)

        btn_theme = tk.Button(panel_top, text="🔄 Theme", command=self.cycle_theme, font=("Helvetica", 8), bg="#45475a", fg="#ffffff", relief="flat", padx=5)
        btn_theme.pack(side="right", padx=5)

        self.apply_theme()

        # Make this window the GUI root for scheduled main-thread actions.
        set_gui_root(self.root)
        self.root.focus_force()
        self.root.lift()

        # In-window listeners for the morse input keys (j/k/space).
        # Register unconditionally so the app works even when global hooks fail
        # (common on Windows without appropriate permissions).
        register_tk_listeners(self.root)


        self.root.after(100, self.update_hud)
        return self.root

    def cycle_theme(self):
        if self.state.theme == THEMES["DARK"]:
            self.state.theme = THEMES["LIGHT"]
        elif self.state.theme == THEMES["LIGHT"]:
            self.state.theme = THEMES["HIGH_CONTRAST"]
        else:
            self.state.theme = THEMES["DARK"]
        self.apply_theme()
        self.state.save_config()

    def run(self):
        self.root.mainloop()
