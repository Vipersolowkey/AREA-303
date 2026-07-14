"""
Shared LLM client for AREA 303 (no model training).

Backend-agnostic: uses the **OpenAI** API by default (the primary backend), and
can fall back to a local **Ollama** server. Switch with the LLM_BACKEND env var.
No third-party deps — pure urllib — so every feature folder can import it without
extra installs.

Features:
  - dual backend (OpenAI / Ollama), structured JSON output
  - on-disk response cache (re-runs are free + reproducible)
  - concurrency helper (map_concurrent) for fast batch evals
  - 429 / Retry-After aware exponential backoff
  - token + cost usage tracking (usage_report())

Config (env vars, or a `.env` file at the repo root — auto-loaded):
  LLM_BACKEND        "openai" (default) | "ollama"
  LLM_CACHE          "1" (default) | "0" to disable the on-disk cache
  LLM_WORKERS        max concurrent requests (default 8)
  # OpenAI
  OPENAI_API_KEY     required when LLM_BACKEND=openai
  OPENAI_MODEL       default gpt-4o-mini
  OPENAI_EMBED_MODEL default text-embedding-3-small
  OPENAI_BASE_URL    default https://api.openai.com/v1
  # Ollama
  OLLAMA_HOST        default http://localhost:11434
  OLLAMA_CHAT_MODEL  default qwen2.5:7b
  OLLAMA_EMBED_MODEL default bge-m3

Public API:
    ping() / list_models()
    chat(prompt, system=..., fmt=...) -> str
    chat_json(prompt, system=..., schema=...) -> dict
    embed(texts) -> np.ndarray
    map_concurrent(items, fn) -> list        # thread-pooled map for batch work
    usage_report() -> dict / reset_usage()
    CHAT_MODEL, EMBED_MODEL                   # resolved active model names
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from <repo>/.env into os.environ (without overwriting)."""
    for base in (Path(__file__).resolve().parent.parent, Path.cwd()):
        env = base / ".env"
        if not env.exists():
            continue
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break


_load_dotenv()

BACKEND = os.getenv("LLM_BACKEND", "openai").lower()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:7b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

CHAT_MODEL = OPENAI_MODEL if BACKEND == "openai" else OLLAMA_CHAT_MODEL
EMBED_MODEL = OPENAI_EMBED_MODEL if BACKEND == "openai" else OLLAMA_EMBED_MODEL

DEFAULT_OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096}

CACHE_ENABLED = os.getenv("LLM_CACHE", "1").lower() not in ("0", "false", "no")
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "llm"
MAX_WORKERS = int(os.getenv("LLM_WORKERS", "8"))

# USD per 1M tokens (input, output) — for the cost estimate only
_PRICES = {
    "gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.50, 10.00),
    "text-embedding-3-small": (0.02, 0.0), "text-embedding-3-large": (0.13, 0.0),
}
_LOCK = threading.Lock()
_USAGE = {"chat_calls": 0, "cache_hits": 0, "prompt_tokens": 0,
          "completion_tokens": 0, "embed_tokens": 0}


# ---------------------------------------------------------------------------
# usage tracking
# ---------------------------------------------------------------------------
def _record(prompt=0, completion=0, embed=0, cache_hit=False):
    with _LOCK:
        if cache_hit:
            _USAGE["cache_hits"] += 1
            return
        _USAGE["chat_calls"] += bool(prompt or completion)
        _USAGE["prompt_tokens"] += prompt
        _USAGE["completion_tokens"] += completion
        _USAGE["embed_tokens"] += embed


def reset_usage() -> None:
    with _LOCK:
        for k in _USAGE:
            _USAGE[k] = 0


def usage_report() -> dict:
    """Current token counts + estimated USD cost (OpenAI only)."""
    u = dict(_USAGE)
    cin, cout = _PRICES.get(OPENAI_MODEL, (0, 0))
    ein, _ = _PRICES.get(OPENAI_EMBED_MODEL, (0, 0))
    cost = (u["prompt_tokens"] * cin + u["completion_tokens"] * cout
            + u["embed_tokens"] * ein) / 1e6
    u["estimated_usd"] = round(cost, 4) if BACKEND == "openai" else 0.0
    return u


# ---------------------------------------------------------------------------
# on-disk cache
# ---------------------------------------------------------------------------
def _cache_key(*parts) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_read(key: str):
    if not CACHE_ENABLED:
        return None
    p = CACHE_DIR / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


def _cache_write(key: str, value) -> None:
    if not CACHE_ENABLED:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# low-level HTTP + backoff
# ---------------------------------------------------------------------------
def _request(url: str, payload: dict | None, headers: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _backoff(err: Exception, attempt: int) -> None:
    """Sleep before retry; honor Retry-After and back off harder on 429/5xx."""
    delay = 1.5 * (attempt + 1)
    if isinstance(err, urllib.error.HTTPError):
        ra = err.headers.get("Retry-After") if err.headers else None
        if ra:
            try:
                delay = max(delay, float(ra))
            except ValueError:
                pass
        if err.code in (429, 500, 502, 503):
            delay = max(delay, 2.0 ** attempt)
    time.sleep(min(delay, 30.0))


def _ollama_post(path: str, payload: dict, timeout: int = 600) -> dict:
    return _request(f"{OLLAMA_HOST}{path}", payload,
                    {"Content-Type": "application/json"}, timeout)


def _openai_post(path: str, payload: dict, timeout: int = 120) -> dict:
    return _request(f"{OPENAI_BASE_URL}{path}", payload,
                    {"Content-Type": "application/json",
                     "Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout)


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------
def ping() -> bool:
    try:
        if BACKEND == "openai":
            return bool(OPENAI_API_KEY)
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def list_models() -> list[str]:
    if BACKEND == "openai":
        return [OPENAI_MODEL, OPENAI_EMBED_MODEL]
    with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m["name"] for m in data.get("models", [])]


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------
def chat(prompt: str, system: str | None = None, model: str | None = None,
         options: dict | None = None, fmt: Any = None, retries: int = 4) -> str:
    """Single-turn chat. `fmt` may be 'json' or a JSON schema dict. Cached on disk."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    active = model or (OPENAI_MODEL if BACKEND == "openai" else OLLAMA_CHAT_MODEL)
    key = _cache_key("chat", BACKEND, active, messages, fmt)
    cached = _cache_read(key)
    if cached is not None:
        _record(cache_hit=True)
        return cached

    last = None
    for attempt in range(retries + 1):
        try:
            text = (_chat_openai(messages, model, fmt) if BACKEND == "openai"
                    else _chat_ollama(messages, model, options, fmt))
            _cache_write(key, text)
            return text
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError) as e:
            last = e
            _backoff(e, attempt)
    raise RuntimeError(f"LLM chat failed after {retries + 1} tries: {last}")


def _chat_ollama(messages: list[dict], model: str | None, options: dict | None, fmt: Any) -> str:
    payload: dict = {
        "model": model or OLLAMA_CHAT_MODEL, "messages": messages, "stream": False,
        "options": {**DEFAULT_OPTIONS, **(options or {})},
    }
    if fmt is not None:
        payload["format"] = fmt
    resp = _ollama_post("/api/chat", payload)
    _record(prompt=resp.get("prompt_eval_count", 0), completion=resp.get("eval_count", 0))
    return resp["message"]["content"]


def _chat_openai(messages: list[dict], model: str | None, fmt: Any) -> str:
    payload: dict = {"model": model or OPENAI_MODEL, "messages": messages, "temperature": 0}
    if isinstance(fmt, dict):
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "out", "schema": fmt, "strict": False},
        }
    elif fmt == "json":
        payload["response_format"] = {"type": "json_object"}
    resp = _openai_post("/chat/completions", payload)
    u = resp.get("usage", {}) or {}
    _record(prompt=u.get("prompt_tokens", 0), completion=u.get("completion_tokens", 0))
    return resp["choices"][0]["message"]["content"]


def chat_json(prompt: str, system: str | None = None, schema: dict | None = None,
              model: str | None = None, options: dict | None = None) -> dict:
    """Chat constrained to JSON. Returns a dict."""
    fmt = schema if schema is not None else "json"
    raw = chat(prompt, system=system, model=model, options=options, fmt=fmt)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start:end + 1])
        raise


# ---------------------------------------------------------------------------
# concurrency
# ---------------------------------------------------------------------------
def map_concurrent(items: list, fn: Callable, workers: int | None = None,
                   on_progress: Callable[[int, int], None] | None = None) -> list:
    """Run fn(item) across a thread pool, preserving input order.

    `fn` should handle its own errors (return a value, not raise) for resilience.
    Ideal for LLM batch evals — network-bound, so threads give a big speed-up.
    """
    workers = workers or MAX_WORKERS
    n = len(items)
    out: list = [None] * n
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        for fut in as_completed(futs):
            out[futs[fut]] = fut.result()
            done += 1
            if on_progress:
                on_progress(done, n)
    return out


# ---------------------------------------------------------------------------
# embeddings
# ---------------------------------------------------------------------------
def embed(texts: list[str] | str, model: str | None = None, batch_size: int = 32):
    """Embed text(s). Returns a numpy array (n, dim), or (dim,) for a single string."""
    import numpy as np

    single = isinstance(texts, str)
    items = [texts] if single else list(texts)
    vecs: list[list[float]] = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        last = None
        for attempt in range(4):
            try:
                if BACKEND == "openai":
                    out = _openai_post("/embeddings", {"model": model or OPENAI_EMBED_MODEL, "input": batch})
                    vecs.extend(d["embedding"] for d in out["data"])
                    _record(embed=(out.get("usage", {}) or {}).get("total_tokens", 0))
                else:
                    out = _ollama_post("/api/embed", {"model": model or OLLAMA_EMBED_MODEL, "input": batch})
                    vecs.extend(out["embeddings"])
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError) as e:
                last = e
                _backoff(e, attempt)
        else:
            raise RuntimeError(f"embed failed for batch {i}: {last}")
    arr = np.asarray(vecs, dtype="float32")
    return arr[0] if single else arr


if __name__ == "__main__":
    print(f"Backend: {BACKEND} | chat: {CHAT_MODEL} | embed: {EMBED_MODEL}")
    print(f"Cache: {'on' if CACHE_ENABLED else 'off'} ({CACHE_DIR}) | workers: {MAX_WORKERS}")
    print("Reachable:", ping())
    if ping():
        print("Models:", list_models())
