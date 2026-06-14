import threading
import time
import webbrowser
from urllib.parse import quote

from accessbridge.core.state import state_manager, AI_MODALITIES
from accessbridge.core.utils import (
    schedule_on_main,
    play_click_async,
    gui_write,
    gui_press,
    gui_click,
    gui_hotkey,
    speak_text_async,
    logger,
)
from accessbridge.morse.decoder import MorseDecoder
from accessbridge.ai.backend import get_ai_response

try:
    import keyboard
except ImportError:
    keyboard = None
    logger.warning("Optional dependency 'keyboard' is not installed. Morse input listeners are disabled.")

KEY_CONFIG = {
    "DIT_KEY": "j",
    "DAH_KEY": "k",
    "SPACE_KEY": "space",
}

# Tracks which morse input keys are currently held down so OS key-repeat doesn't
# flood the morse buffer.
_held_keys = set()

decoder = MorseDecoder()


def _push_undo_snapshot_locked():
    state_manager.undo_stack.append(state_manager.snapshot())


def _restore_undo_snapshot_locked():
    if not state_manager.undo_stack:
        return False
    snapshot = state_manager.undo_stack.pop()
    state_manager.restore(snapshot)
    return True


def _generate_search_suggestions_locked():
    prompt = (
        " ".join(
            state_manager.ai_input_buffer
            + ([state_manager.word_accumulator] if state_manager.word_accumulator else [])
        )
        .strip()
        .lower()
    )
    suggestions = []
    if prompt:
        for entry in reversed(state_manager.search_history):
            if entry.lower().startswith(prompt) and entry not in suggestions:
                suggestions.append(entry)
                if len(suggestions) >= 3:
                    break
    if not suggestions and prompt:
        phrase = prompt.strip()
        if phrase:
            suggestions.append(phrase)
            if len(phrase.split()) == 1:
                suggestions.extend([f"{phrase} tutorial", f"{phrase} examples"])
    return suggestions[:3]


def _append_search_history_locked(query_text: str):
    normalized = query_text.strip()
    if not normalized:
        return
    if not state_manager.search_history or state_manager.search_history[-1] != normalized:
        state_manager.search_history.append(normalized)
        if len(state_manager.search_history) > 100:
            state_manager.search_history.pop(0)
    state_manager.last_search_query = normalized


def _record_conversation_locked(user_text: str, ai_text: str):
    if not hasattr(state_manager, "conversation_history"):
        state_manager.conversation_history = []
    state_manager.conversation_history.append(f"User: {user_text}")
    state_manager.conversation_history.append(f"AI: {ai_text}")
    if len(state_manager.conversation_history) > 100:
        state_manager.conversation_history[:] = state_manager.conversation_history[-100:]


def _record_output_action(action_type: str, text: str = "", count: int = 0):
    state_manager.output_action_history.append(
        {"type": action_type, "text": text, "count": count}
    )


def _undo_external_output():
    if not state_manager.output_action_history:
        return False
    last_action = state_manager.output_action_history.pop()
    if last_action["type"] == "write":
        count = len(last_action["text"] or "")
        if count > 0:
            gui_press("backspace", presses=count)
            return True
    elif last_action["type"] == "press" and last_action.get("count", 0) > 0:
        gui_press("backspace", presses=last_action["count"])
        return True
    return False


def _handle_special_command_locked(command_name: str):
    actions = []

    if command_name == "EMERGENCY":
        actions.append(lambda: speak_text_async("Emergency locator triggered."))
        # Avoid typing '*' characters into the target app.
        actions.append(lambda: gui_write("\nEMERGENCY PROTOCOL\n"))

    elif command_name == "BACKSPACE":
        if state_manager.system_mode == "TYPE":
            # Backspace should remove pending first.
            if getattr(state_manager, "pending_character", ""):
                state_manager.pending_character = ""
                # Also clear the active fragment typed for prediction.
                # word_accumulator represents typed fragment; we clear it only if it matches.
                state_manager.word_accumulator = state_manager.word_accumulator[:-1]
                state_manager.space_dropped = False
                actions.append(lambda: gui_press("backspace"))
            elif state_manager.current_message_str:
                state_manager.current_message_str = state_manager.current_message_str[:-1]
                state_manager.ANALYTICS["user_generated_characters"] = max(
                    0, state_manager.ANALYTICS["user_generated_characters"] - 1
                )
                actions.append(lambda: gui_press("backspace"))

        else:
            if state_manager.word_accumulator:
                state_manager.word_accumulator = state_manager.word_accumulator[:-1]
            elif state_manager.ai_input_buffer:
                state_manager.ai_input_buffer.pop()

    elif command_name == "ENTER":
        actions.append(lambda: gui_press("enter"))
        if state_manager.type_mode_char_count > 0:
            state_manager.ANALYTICS["user_words"] += 1
            state_manager.type_mode_char_count = 0
        if state_manager.current_message_str.strip():
            state_manager.message_history.append(state_manager.current_message_str)
            if len(state_manager.message_history) > 50:
                state_manager.message_history.pop(0)
        state_manager.current_message_str = ""

    elif command_name == "CLICK":
        actions.append(gui_click)

    elif command_name == "SHOW_DESKTOP":
        actions.append(lambda: gui_hotkey("win", "d"))

    elif command_name == "DELETE_WORD":
        if state_manager.system_mode == "TYPE":
            # If there is an uncommitted pending character, delete that first.
            if getattr(state_manager, "pending_character", ""):
                state_manager.pending_character = ""
                state_manager.word_accumulator = ""
                state_manager.space_dropped = False
            elif state_manager.current_message_str:
                stripped = state_manager.current_message_str.rstrip(" ")

            last_space_idx = stripped.rfind(" ")
            word_start = last_space_idx + 1
            chars_to_remove = len(state_manager.current_message_str) - word_start
            if chars_to_remove > 0:
                actions.append(
                    lambda n=chars_to_remove: gui_press("backspace", presses=n)
                )
                state_manager.current_message_str = state_manager.current_message_str[:word_start]
                state_manager.ANALYTICS["user_generated_characters"] = max(
                    0,
                    state_manager.ANALYTICS["user_generated_characters"] - chars_to_remove,
                )
        elif state_manager.system_mode == "AI":
            state_manager.word_accumulator = ""
            if state_manager.ai_input_buffer:
                state_manager.ai_input_buffer.pop()

    elif command_name == "CLEAR_MESSAGE":
        if state_manager.system_mode == "TYPE" and state_manager.current_message_str:
            chars_to_remove = len(state_manager.current_message_str)
            actions.append(
                lambda n=chars_to_remove: gui_press("backspace", presses=n)
            )
            state_manager.ANALYTICS["user_generated_characters"] = max(
                0, state_manager.ANALYTICS["user_generated_characters"] - chars_to_remove
            )
            state_manager.current_message_str = ""
        else:
            state_manager.word_accumulator = ""
            state_manager.ai_input_buffer.clear()

    elif command_name == "AI_MODE":
        if state_manager.system_mode == "TYPE":
            state_manager.system_mode = "AI"
            state_manager.ai_input_buffer = []
            state_manager.word_accumulator = ""
        else:
            if not state_manager.ai_input_buffer and not state_manager.word_accumulator:
                state_manager.ai_modality_index = (
                    state_manager.ai_modality_index + 1
                ) % len(state_manager.AI_MODALITIES)
                actions.append(
                    lambda: speak_text_async(
                        f"{state_manager.AI_MODALITIES[state_manager.ai_modality_index]} Mode Active"
                    )
                )
            else:
                if state_manager.word_accumulator.strip():
                    state_manager.ai_input_buffer.append(
                        state_manager.word_accumulator.strip()
                    )
                full_prompt = " ".join(state_manager.ai_input_buffer).strip()
                if full_prompt:
                    actions.append(lambda p=full_prompt: _run_ai_prompt(p))
                state_manager.ai_input_buffer = []
                state_manager.word_accumulator = ""
                state_manager.system_mode = "TYPE"

    elif command_name == "WEB_SEARCH":
        if state_manager.system_mode == "TYPE":
            full_query = state_manager.current_message_str.strip()
        else:
            if state_manager.word_accumulator.strip():
                state_manager.ai_input_buffer.append(state_manager.word_accumulator.strip())
            full_query = " ".join(state_manager.ai_input_buffer).strip()

        if full_query:
            # Keep a separate human-readable query for UI/state.
            human_query = full_query
            # URL-encode only for the outbound search request.
            encoded_query = quote(human_query)

            _append_search_history_locked(human_query)
            state_manager.last_search_query = human_query
            state_manager.ai_status = f"🔵 Searching: {human_query}"

            actions.append(
                lambda eq=encoded_query: webbrowser.open(
                    f"https://www.google.com/search?q={eq}"
                )
            )
            actions.append(lambda q=human_query: speak_text_async(f"Searching for {q}"))

            # Clear only the typing buffers/message (do not write encoded strings back).
            state_manager.ai_input_buffer = []
            state_manager.word_accumulator = ""
            state_manager.current_message_str = ""
            state_manager.system_mode = "TYPE"

        else:
            state_manager.ai_status = "🔴 Search Failed"
            actions.append(lambda: speak_text_async("No search query entered"))

    elif command_name == "DELETE_LAST_MESSAGE":
        if state_manager.message_history:
            state_manager.message_history.pop()

    elif command_name == "UNDO":
        if _restore_undo_snapshot_locked():
            _undo_external_output()
        else:
            actions.append(lambda: speak_text_async("Nothing to undo."))

    return actions


def _run_ai_prompt(prompt_text: str):
    answer, status_msg, error_msg = get_ai_response(prompt_text)
    state_manager.ai_status = status_msg
    state_manager.last_ai_error = error_msg
    _record_conversation_locked(prompt_text, answer)
    state_manager.ANALYTICS["ai_words"] += len(answer.split())
    state_manager.ANALYTICS["saved_keystrokes"] += len(answer)
    state_manager.ANALYTICS["ai_generated_characters"] += len(answer)
    gui_write(f"\n{answer}\n")
    speak_text_async(answer)
    state_manager.save_session()


def _commit_pending_buffer_locked(deferred_actions: list):
    if not state_manager.current_buffer:
        return

    seq = state_manager.current_buffer
    logger.info("Decoder pipeline: committing morse sequence='%s'", seq)

    decoded = decoder.decode(seq)
    if decoded:
        logger.info("Decoder pipeline: decoded '%s' -> '%s'", seq, decoded)

        # Special command handling: commands should execute, not be appended.
        if decoder.is_command(seq):
            logger.info("Decoder pipeline: executing special command for decoded='%s'", decoded)
            actions = []
            with state_manager.lock:
                actions = _handle_special_command_locked(decoded)
            for act in actions:
                deferred_actions.append(lambda a=act: a())
            state_manager.current_buffer = ""
            _update_predictions_locked()
            return

        # Numeric prediction selection: 1-3 pick from active predictions.
        if state_manager.active_predictions and decoded in ("1", "2", "3"):
            idx = int(decoded) - 1
            if idx < len(state_manager.active_predictions):
                _apply_prediction_selection(idx, deferred_actions)
        else:
            if state_manager.system_mode == "TYPE":
                _apply_type_character(decoded.lower(), deferred_actions)
            else:
                state_manager.word_accumulator += decoded.lower()

    else:
        logger.warning(
            "Decoder pipeline: invalid morse sequence '%s'", state_manager.current_buffer
        )
        deferred_actions.append(lambda: speak_text_async("Invalid Morse sequence"))

    state_manager.current_buffer = ""
    state_manager.last_input_time = time.time()
    state_manager.space_dropped = False
    _update_predictions_locked()


def _update_predictions_locked():
    prefix = state_manager.word_accumulator.strip().lower()
    state_manager.active_predictions = decoder.get_predictions(prefix)
    state_manager.ANALYTICS["prediction_count"] = len(state_manager.active_predictions)


def _apply_type_character(char_to_write: str, deferred_actions: list):
    state_manager.current_message_str += char_to_write
    state_manager.word_accumulator += char_to_write
    state_manager.type_mode_char_count += 1
    state_manager.ANALYTICS["user_generated_characters"] += 1
    deferred_actions.append(lambda c=char_to_write: gui_write(c))




def _get_active_fragment_locked() -> str:
    """Return the currently active word fragment used for prediction."""
    if state_manager.system_mode != "TYPE":
        return ""
    return state_manager.word_accumulator or ""


def _find_replacement_range_for_fragment(message: str, fragment: str) -> tuple[int, int]:
    """Find [start,end) range in message to be replaced by fragment with suggestion.

    Expected model: fragment is typically at the end while typing, but we handle
    beginning/middle/end by searching for a word-boundary occurrence of fragment.
    """
    if not fragment:
        return (-1, -1)

    # If message ends with fragment, prefer replacing that tail.
    if message.endswith(fragment):
        start = len(message) - len(fragment)
        # Validate boundary on left (start or preceded by space) and right (end).
        left_ok = (start == 0) or (message[start - 1] == " ")
        right_ok = (len(message) == len(message))  # always true
        if left_ok and right_ok:
            return (start, len(message))

    # Otherwise, try to find last occurrence that looks like a word boundary match.
    # Boundary definition: preceded by start or space, followed by space or end.
    last = (-1, -1)
    idx = message.rfind(fragment)
    while idx != -1:
        start = idx
        end = idx + len(fragment)
        left_ok = (start == 0) or (message[start - 1] == " ")
        right_ok = (end == len(message)) or (message[end] == " ")
        if left_ok and right_ok:
            last = (start, end)
            break
        idx = message.rfind(fragment, 0, idx)

    return last


def _replace_fragment_with_suggestion_locked(completed_word: str, deferred_actions: list):
    fragment = _get_active_fragment_locked()
    logger.info("Prediction replace: fragment detected='%s' suggestion='%s' before_message='%s'", fragment, completed_word, state_manager.current_message_str)

    # Requirement: empty fragment should not corrupt message.
    if not fragment:
        deferred_actions.append(lambda w=completed_word: speak_text_async(w))
        logger.info("Prediction replace aborted: empty fragment. message unchanged='%s'", state_manager.current_message_str)
        return

    # Push undo snapshot before mutating state.
    _push_undo_snapshot_locked()

    message = state_manager.current_message_str
    start, end = _find_replacement_range_for_fragment(message, fragment)

    # Fallback: if we can't find a boundary occurrence, replace the tail if it matches.
    if start == -1:
        if message.endswith(fragment):
            start = len(message) - len(fragment)
            end = len(message)
        else:
            # Do not modify message if we can't safely locate fragment.
            deferred_actions.append(lambda w=completed_word: speak_text_async(w))
            logger.warning("Prediction replace fallback aborted: fragment '%s' not found/bounded in message='%s'", fragment, message)
            return

    # Update internal message state: remove fragment, insert suggestion + trailing space.
    new_message = message[:start] + completed_word + " " + message[end:]
    state_manager.current_message_str = new_message

    # Update prediction typing state.
    state_manager.word_accumulator = ""
    state_manager.active_predictions = []

    # Keep counters roughly consistent with inserted visible chars.
    # (We avoid complex char accounting; undo will restore accurately.)
    inserted_len = len(completed_word) + 1
    state_manager.type_mode_char_count = max(0, state_manager.type_mode_char_count - len(fragment))
    state_manager.type_mode_char_count += inserted_len
    state_manager.ANALYTICS["user_generated_characters"] += inserted_len

    # GUI sync: delete the fragment visually then type replacement + space.
    # Schedule: (1) delete fragment visually, (2) write chosen word + trailing space.
    # Note: returning None from a scheduled action is fine (no further side effects).
    deferred_actions.append(
        lambda n=(end - start): gui_press("backspace", presses=n) if n > 0 else None
    )
    deferred_actions.append(lambda w=completed_word: gui_write(w + " "))


    logger.info("Prediction replace applied: fragment='%s' range=[%d,%d) after_message='%s'", fragment, start, end, state_manager.current_message_str)
    deferred_actions.append(lambda w=completed_word: speak_text_async(w))


def _apply_prediction_selection(idx: int, deferred_actions: list):
    completed_word = state_manager.active_predictions[idx]

    if state_manager.system_mode == "TYPE":
        _replace_fragment_with_suggestion_locked(completed_word, deferred_actions)
    else:
        # AI mode keeps prior behavior (word_accumulator only).
        state_manager.word_accumulator = completed_word
        state_manager.active_predictions = []
        deferred_actions.append(lambda w=completed_word: speak_text_async(w))



def _handle_morse_symbol_locked(morse_key: str):
    deferred_actions = []

    if morse_key in (KEY_CONFIG["DIT_KEY"], KEY_CONFIG["DAH_KEY"]):
        _push_undo_snapshot_locked()
        is_dah = morse_key == KEY_CONFIG["DAH_KEY"]
        state_manager.current_buffer += "-" if is_dah else "."
        state_manager.ANALYTICS["total_keystrokes"] += 1

        now = time.time()
        if state_manager.last_keystroke_timestamp is not None:
            interval = now - state_manager.last_keystroke_timestamp
            if interval <= state_manager.dynamic_idle_timeout:
                state_manager.keystroke_intervals.append(interval)
                avg_interval = sum(state_manager.keystroke_intervals) / len(state_manager.keystroke_intervals)
                candidate = avg_interval * 3.0
                state_manager.dynamic_idle_timeout = max(1.0, min(2.5, candidate))

        state_manager.last_keystroke_timestamp = now
        state_manager.last_input_time = now
        state_manager.space_dropped = False
        deferred_actions.append(lambda d=is_dah: play_click_async(d))
        return deferred_actions

    if morse_key == KEY_CONFIG["SPACE_KEY"]:
        state_manager.ANALYTICS["total_keystrokes"] += 1

        if state_manager.current_buffer:
            _commit_pending_buffer_locked(deferred_actions)
        else:
            # SPACE pressed with empty buffer -> commit pending character (if any) and add a space.
            if state_manager.system_mode == "TYPE":
                logger.debug(
                    "SPACE pressed: pending_character='%s' message_buffer_before='%s'",
                    getattr(state_manager, "pending_character", ""),
                    state_manager.current_message_str,
                )

                # Character Committed (pending -> message)
                if getattr(state_manager, "pending_character", ""):
                    deferred_actions.append(
                        lambda c=state_manager.pending_character: gui_write(c)
                    )
                    state_manager.current_message_str += state_manager.pending_character
                    state_manager.pending_character = ""

                    # Track typed-visible char count for analytics.
                    state_manager.ANALYTICS["user_generated_characters"] += 1
                    state_manager.type_mode_char_count += 1

                # Now add the space itself.
                state_manager.current_message_str += " "
                state_manager.ANALYTICS["user_generated_characters"] += 1

                # Word boundary bookkeeping.
                if state_manager.type_mode_char_count > 0:
                    state_manager.ANALYTICS["user_words"] += 1
                    state_manager.type_mode_char_count = 0

                state_manager.word_accumulator = ""
                state_manager.space_dropped = True
                deferred_actions.append(lambda: gui_write(" "))

            elif state_manager.word_accumulator:
                state_manager.ai_input_buffer.append(state_manager.word_accumulator)
                state_manager.ANALYTICS["user_words"] += 1
                state_manager.word_accumulator = ""
                state_manager.space_dropped = True

        state_manager.current_buffer = ""
        state_manager.last_input_time = time.time()
        _update_predictions_locked()

    return deferred_actions


def on_morse_key_press(morse_key: str):
    logger.info("Morse pipeline: on_morse_key_press(morse_key=%s)", morse_key)
    try:
        with state_manager.lock:
            before_buffer = state_manager.current_buffer
            deferred_actions = _handle_morse_symbol_locked(morse_key)
            after_buffer = state_manager.current_buffer

            state_manager.last_morse_key_pressed = str(morse_key)
            state_manager.last_morse_sequence = str(after_buffer)

            logger.info(
                "Morse pipeline: buffer update %s -> %s (deferred_actions=%d)",
                before_buffer,
                after_buffer,
                len(deferred_actions),
            )

        for action in deferred_actions:
            schedule_on_main(action)
    except Exception:
        logger.exception("Morse key press handler failure")


def handle_special_command(command_name: str):
    try:
        with state_manager.lock:
            actions = _handle_special_command_locked(command_name)
        for act in actions:
            schedule_on_main(act)
    except Exception:
        logger.exception("Special command failure")


def _commit_space_if_idle_timeout():
    """Disabled: commit/auto-space must be SPACE-driven only."""
    while state_manager.is_recording:
        time.sleep(0.5)


def _make_keyboard_press_handler(key_name: str):
    def _handler(_event):
        if key_name in _held_keys:
            return
        _held_keys.add(key_name)
        on_morse_key_press(key_name)

    return _handler


def _make_keyboard_release_handler(key_name: str):
    def _handler(_event):
        _held_keys.discard(key_name)

    return _handler


def register_tk_listeners(root):
    """Bind the morse input keys (DIT/DAH/SPACE) directly to a Tk window."""

    def _press(event):
        keysym = (event.keysym or "").lower()

        if keysym == KEY_CONFIG["DIT_KEY"]:
            target = KEY_CONFIG["DIT_KEY"]
        elif keysym == KEY_CONFIG["DAH_KEY"]:
            target = KEY_CONFIG["DAH_KEY"]
        elif keysym == "space":
            target = KEY_CONFIG["SPACE_KEY"]
        else:
            return None

        if target in _held_keys:
            return "break"

        _held_keys.add(target)
        on_morse_key_press(target)
        return "break"

    def _release(event):
        keysym = (event.keysym or "").lower()
        if keysym == KEY_CONFIG["DIT_KEY"]:
            _held_keys.discard(KEY_CONFIG["DIT_KEY"])
        elif keysym == KEY_CONFIG["DAH_KEY"]:
            _held_keys.discard(KEY_CONFIG["DAH_KEY"])
        elif keysym == "space":
            _held_keys.discard(KEY_CONFIG["SPACE_KEY"])

    def _press_logged(event):
        keysym = (getattr(event, "keysym", "") or "").lower()
        logger.info("Tk KeyPress received: keysym=%s", keysym)
        return _press(event)

    def _release_logged(event):
        keysym = (getattr(event, "keysym", "") or "").lower()
        logger.info("Tk KeyRelease received: keysym=%s", keysym)
        return _release(event)

    root.bind_all("<KeyPress>", _press_logged)
    root.bind_all("<KeyRelease>", _release_logged)

    with state_manager.lock:
        state_manager.keyboard_enabled = True

    logger.info(
        "In-window morse listeners registered for DIT=%s DAH=%s SPACE=%s (Tk focus required).",
        KEY_CONFIG["DIT_KEY"],
        KEY_CONFIG["DAH_KEY"],
        KEY_CONFIG["SPACE_KEY"],
    )


def start_input_listeners():
    """Start global keyboard listeners if available, and always start idle-timeout worker."""

    registered_any = False

    logger.info("Input listeners startup: attempting global keyboard hooks")

    if keyboard is None:
        logger.warning("Keyboard listeners are unavailable because the 'keyboard' package is missing.")
    else:
        for key_name in (KEY_CONFIG["DIT_KEY"], KEY_CONFIG["DAH_KEY"], KEY_CONFIG["SPACE_KEY"]):
            try:
                keyboard.on_press_key(key_name, _make_keyboard_press_handler(key_name))
                keyboard.on_release_key(key_name, _make_keyboard_release_handler(key_name))
                registered_any = True
                logger.info("Global keyboard listener registered for key=%s", key_name)
            except Exception:
                logger.exception("Failed to register global listener for key '%s'", key_name)

    with state_manager.lock:
        state_manager.keyboard_enabled = registered_any

    if not registered_any:
        logger.warning("Global morse-key listeners could not be registered; app will rely on in-window Tk bindings.")

    logger.info("Input listeners startup: keyboard_global_registered=%s", registered_any)
    logger.info("Idle timeout checker thread started")
    threading.Thread(
        target=_commit_space_if_idle_timeout,
        daemon=True,
        name="IdleTimeoutChecker",
    ).start()

