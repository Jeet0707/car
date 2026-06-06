import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from upstash_redis import Redis

_redis: Optional[Redis] = None
_memory_pending: dict[str, dict[str, Any]] = {}
_memory_state: dict[str, dict[str, Any]] = {}


def storage_mode() -> str:
    if _redis_credentials():
        return "redis"
    return "memory"


def kv_configured() -> bool:
    return _redis_credentials()


def _redis_credentials() -> tuple[str, str] | None:
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return url, token
    return None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        creds = _redis_credentials()
        if not creds:
            raise RuntimeError(
                "Redis not configured. Link Vercel KV or set KV_REST_API_URL + KV_REST_API_TOKEN."
            )
        _redis = Redis(url=creds[0], token=creds[1])
    return _redis


def pending_key(device_id: str) -> str:
    return f"khetix:{device_id}:pending"


def state_key(device_id: str) -> str:
    return f"khetix:{device_id}:state"


def default_state() -> dict[str, Any]:
    return {
        "cutter": False,
        "servoAngle": 90,
        "updatedAt": _now_iso(),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_command_to_state(state: dict[str, Any], command: dict[str, Any]) -> dict[str, Any]:
    updated_at = _now_iso()
    cmd = command.get("cmd")

    if cmd == "1":
        return {**state, "cutter": True, "updatedAt": updated_at}
    if cmd == "2":
        return {**state, "cutter": False, "updatedAt": updated_at}
    if cmd == "servo":
        return {**state, "servoAngle": int(command["angle"]), "updatedAt": updated_at}

    return {**state, "updatedAt": updated_at}


def enqueue_command(device_id: str, command: dict[str, Any]) -> None:
    if _redis_credentials():
        redis = get_redis()
        existing_raw = redis.get(state_key(device_id))
        existing = json.loads(existing_raw) if existing_raw else default_state()
        next_state = apply_command_to_state(existing, command)
        redis.set(pending_key(device_id), json.dumps(command))
        redis.set(state_key(device_id), json.dumps(next_state))
        return

    existing = _memory_state.get(device_id, default_state())
    _memory_state[device_id] = apply_command_to_state(existing, command)
    _memory_pending[device_id] = command


def consume_pending_command(device_id: str) -> Optional[dict[str, Any]]:
    if _redis_credentials():
        redis = get_redis()
        pending_raw = redis.get(pending_key(device_id))
        if not pending_raw:
            return None

        redis.delete(pending_key(device_id))

        state_raw = redis.get(state_key(device_id))
        state = json.loads(state_raw) if state_raw else default_state()
        state["lastPollAt"] = _now_iso()
        redis.set(state_key(device_id), json.dumps(state))

        return json.loads(pending_raw)

    pending = _memory_pending.pop(device_id, None)
    if pending is None:
        return None

    state = _memory_state.get(device_id, default_state())
    state["lastPollAt"] = _now_iso()
    _memory_state[device_id] = state
    return pending


def get_device_state(device_id: str) -> dict[str, Any]:
    if _redis_credentials():
        redis = get_redis()
        state_raw = redis.get(state_key(device_id))
        return json.loads(state_raw) if state_raw else default_state()

    return _memory_state.get(device_id, default_state())


def is_online(state: dict[str, Any], window_ms: int = 5000) -> bool:
    poll_at = state.get("lastPollAt") or state.get("updatedAt")
    if not poll_at:
        return False
    poll_time = datetime.fromisoformat(poll_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    return (now - poll_time).total_seconds() * 1000 <= window_ms
