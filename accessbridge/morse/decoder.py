from __future__ import annotations
from typing import Dict, List, Set, Optional

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
    "z": ["zero", "zipper", "zone","zip"],
}

MORSE_DICT = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E', '..-.': 'F',
    '--.': 'G', '....': 'H', '..': 'I', '.---': 'J', '-.-': 'K', '.-..': 'L',
    '--': 'M', '-.': 'N', '---': 'O', '.--.': 'P', '--.-': 'Q', '.-.': 'R',
    '...': 'S', '-': 'T', '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X',
    '-.--': 'Y', '--..': 'Z', '-----': '0', '.----': '1', '..---': '2',
    '...--': '3', '....-': '4', '.....': '5', '-....': '6', '--...': '7',
    '---..': '8', '----.': '9'
}

# Command sequences are mapped from full morse strings.
# Keep this table consistent with accessbridge.core.state.COMMAND_DICT.
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


# Normalize/align command map keys used by COMMAND_DICT in accessbridge.core.state.
# (Core/state also defines COMMAND_DICT and should be identical; if not, inputs won't decode.)



def normalize_prefix(prefix: str) -> str:
    return prefix.lower().strip()


class PredictiveTrie:
    def __init__(self, corpus: Dict[str, List[str]]):
        self.root: Dict[str, Dict] = {}
        self._build_trie(corpus)

    def _build_trie(self, corpus: Dict[str, List[str]]):
        for word_list in corpus.values():
            for word in word_list:
                self.insert(word)

    def insert(self, word: str):
        node = self.root
        normalized = normalize_prefix(word)
        for ch in normalized:
            node = node.setdefault(ch, {})
            node.setdefault("_words", []).append(word)

    def lookup_prefix(self, prefix: str, max_results: int = 3) -> List[str]:
        if not prefix:
            return []
        node = self.root
        normalized = normalize_prefix(prefix)
        for ch in normalized:
            node = node.get(ch)
            if node is None:
                return []
        return node.get("_words", [])[:max_results]


class MorseDecoder:
    def __init__(self, predictive_trie: Optional[PredictiveTrie] = None):
        self.morse_map = MORSE_DICT
        self.command_map = COMMAND_DICT
        self.predictive_trie = predictive_trie or PredictiveTrie(PREDICTIVE_CORPUS)

    def decode(self, sequence: str) -> Optional[str]:
        """Decode a full, dot/dash sequence.

        Note: the timing/classification logic lives in `accessbridge.input.handler`.
        """
        if sequence in self.command_map:
            return self.command_map[sequence]
        return self.morse_map.get(sequence)

    def decode_with_debug(self, sequence: str):
        """Decode and return extra debug info (for reliability investigations)."""
        if sequence in self.command_map:
            return {"sequence": sequence, "decoded": self.command_map[sequence], "type": "command"}
        decoded = self.morse_map.get(sequence)
        return {"sequence": sequence, "decoded": decoded, "type": "morse"}

    def is_command(self, sequence: str) -> bool:
        return sequence in self.command_map

    def get_predictions(self, prefix: str) -> List[str]:
        return self.predictive_trie.lookup_prefix(prefix)

