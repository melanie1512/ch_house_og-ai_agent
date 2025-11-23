# triage/chat_history.py
import json
from pathlib import Path
from typing import Dict, List, Literal, TypedDict

Role = Literal["user", "assistant"]


class Message(TypedDict):
    role: Role
    content: str


_history: Dict[str, List[Message]] = {}
_MAX_MESSAGES = 20
_CACHE_PATH = Path(__file__).resolve().parent.parent / ".cache" / "chat_history.json"
_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_cache() -> None:
    if _CACHE_PATH.exists():
        try:
            data = json.loads(_CACHE_PATH.read_text())
            if isinstance(data, dict):
                for uid, msgs in data.items():
                    if isinstance(msgs, list):
                        _history[uid] = [
                            {"role": m.get("role", "user"), "content": m.get("content", "")}
                            for m in msgs
                        ]
        except Exception:
            # Best-effort; ignore corrupt cache
            pass


def _persist_cache() -> None:
    try:
        _CACHE_PATH.write_text(json.dumps(_history))
    except Exception:
        # Best-effort; ignore cache write failures
        pass


def get_history(user_id: str) -> List[Message]:
    return _history.get(user_id, [])


def append_message(user_id: str, role: Role, content: str) -> None:
    messages = _history.setdefault(user_id, [])
    messages.append({"role": role, "content": content})
    # Trim to recent N messages to keep prompts small
    if len(messages) > _MAX_MESSAGES:
        _history[user_id] = messages[-_MAX_MESSAGES:]
    _persist_cache()


_load_cache()
