"""Ollama client: talks to the local Ollama server (default http://127.0.0.1:11434). No cloud, works offline."""
import httpx

from .. import config


class OllamaError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind          # not_running | model_missing | timeout | http_error | bad_reply


def chat(messages: list[dict], client: httpx.Client | None = None) -> str:
    """Send a chat to Ollama and return the reply text. Low temperature keeps answers factual."""
    own = client is None
    client = client or httpx.Client(timeout=config.OLLAMA_TIMEOUT)
    try:
        resp = client.post(f"{config.OLLAMA_URL}/api/chat", json={
            "model": config.OLLAMA_MODEL, "messages": messages, "stream": False, "keep_alive": "10m",
            "options": {"temperature": 0.1, "num_ctx": config.OLLAMA_NUM_CTX, "num_predict": config.OLLAMA_MAX_TOKENS},
        })
        if resp.status_code == 404:
            raise OllamaError("model_missing", f"Model '{config.OLLAMA_MODEL}' is not installed. Run: ollama pull {config.OLLAMA_MODEL}")
        resp.raise_for_status()
        text = (resp.json().get("message") or {}).get("content")
        if not isinstance(text, str):
            raise OllamaError("bad_reply", "Ollama returned an unexpected reply")
        return text.strip()
    except OllamaError:
        raise
    except httpx.ConnectError as exc:
        raise OllamaError("not_running", "Ollama is not running") from exc
    except httpx.TimeoutException as exc:
        raise OllamaError("timeout", "The AI took too long to answer") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaError("http_error", f"Ollama error: {exc}") from exc
    finally:
        if own:
            client.close()


def status(client: httpx.Client | None = None) -> dict:
    """Is Ollama running and is the configured model installed?"""
    own = client is None
    client = client or httpx.Client(timeout=2.5)
    try:
        resp = client.get(f"{config.OLLAMA_URL}/api/tags")
        resp.raise_for_status()
        names = [m.get("name", "") for m in resp.json().get("models", [])]
        want = config.OLLAMA_MODEL
        installed = want in names or (":" not in want and any(n.split(":")[0] == want for n in names))
        return {"running": True, "model": want, "model_installed": installed, "installed_models": names,
                "message": "AI ready" if installed else f"Model not installed. Run: ollama pull {want}"}
    except (httpx.HTTPError, ValueError):
        return {"running": False, "model": config.OLLAMA_MODEL, "model_installed": False, "installed_models": [],
                "message": "Ollama is not running. Start the Ollama app."}
    finally:
        if own:
            client.close()
