"""LLM provider resolution: Cloudera AI Inference (CAII) or OpenAI.

Every LLM call site (CrewAI agents, follow-up streaming) goes through this module.
Provider is chosen from environment variables so the same code runs:

  * on Cloudera AI against an open-weight model endpoint (LLM_PROVIDER=caii)
  * on a laptop against OpenAI (LLM_PROVIDER=openai, the default)

Environment variables
---------------------
LLM_PROVIDER      caii | openai  (default: caii if LLM_BASE_URL is set, else openai)
LLM_BASE_URL      OpenAI-compatible base URL, e.g.
                  https://<caii-domain>/namespaces/serving-default/endpoints/<name>/v1
LLM_MODEL         model id as reported by <base_url>/models (e.g. meta/llama-3.1-8b-instruct)
LLM_API_KEY       explicit bearer token (highest precedence)
CDP_TOKEN         long-lived Cloudera workload token / Knox API key (second)
CML_JWT_PATH      path of the JWT file CML injects into pods (default /tmp/jwt)
LLM_TEMPERATURE   agent temperature (default 0.3)
LLM_MAX_TOKENS    completion cap; NIM endpoints need an explicit value (default 2048)
OPENAI_API_KEY    used when provider is openai
OPENAI_MODEL_NAME legacy model override for the openai provider (default gpt-4o-mini)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

_WARNED_EXPIRY = False


def provider() -> str:
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit in ("caii", "openai"):
        return explicit
    return "caii" if os.getenv("LLM_BASE_URL") else "openai"


def jwt_expiry(token: str | None) -> float | None:
    """Return the `exp` claim (epoch seconds) of a JWT, or None if not decodable."""
    if not token or token.count(".") < 2:
        return None
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        exp = claims.get("exp")
        return float(exp) if exp is not None else None
    except Exception:
        return None


_WARNED_INVALID: set[str] = set()
_LAST_SOURCE = "none"


def _looks_like_jwt(token: str | None) -> bool:
    """Three base64url segments with decodable claims and an unexpired `exp`."""
    if not token or token.count(".") != 2 or any(c.isspace() for c in token):
        return False
    exp = jwt_expiry(token)
    return exp is not None and exp > time.time()


def _read_token_file(path: Path) -> str | None:
    """Read a workload token file (JSON with `access_token`, or a raw JWT).

    Cloudera AI injects `/tmp/jwt` into pods; in some pod types the file holds an
    HTML error page instead of a token, so the content is validated before use.
    Re-read on every call (the file is tiny) so a refreshed token is picked up.
    """
    if not path.exists():
        return None
    try:
        raw = path.read_text().strip()
    except Exception as e:  # pragma: no cover - defensive
        log.warning("Could not read token file %s: %s", path, e)
        return None
    token = None
    if raw.startswith("{"):
        try:
            token = json.loads(raw).get("access_token")
        except ValueError:
            token = None
    else:
        token = raw or None
    if _looks_like_jwt(token):
        return token
    key = str(path)
    if key not in _WARNED_INVALID:
        _WARNED_INVALID.add(key)
        log.error("Token file %s does not contain a valid, unexpired JWT (starts with %r)", path, raw[:80])
    return None


def _read_cml_jwt() -> str | None:
    return _read_token_file(Path(os.getenv("CML_JWT_PATH", "/tmp/jwt")))


def fallback_token_path() -> Path:
    default = Path(__file__).resolve().parents[2] / ".secrets" / "jwt.json"
    return Path(os.getenv("CML_JWT_FALLBACK_PATH", str(default)))


def _read_fallback_jwt() -> str | None:
    return _read_token_file(fallback_token_path())


def resolve_api_key() -> str:
    """Bearer token for the LLM endpoint, checked on every call.

    Order: LLM_API_KEY > CDP_TOKEN > valid CML_JWT_PATH (/tmp/jwt) >
    valid CML_JWT_FALLBACK_PATH (.secrets/jwt.json on project storage, written by
    deploy/save_session_token.py) > OPENAI_API_KEY (openai provider only).
    """
    global _WARNED_EXPIRY, _LAST_SOURCE
    for var in ("LLM_API_KEY", "CDP_TOKEN"):
        val = os.getenv(var)
        if val:
            _LAST_SOURCE = var
            return val
    if provider() == "caii":
        tok, source = _read_cml_jwt(), "cml_jwt"
        if not tok:
            tok, source = _read_fallback_jwt(), "fallback_file"
        if tok:
            _LAST_SOURCE = source
            exp = jwt_expiry(tok)
            if exp is not None:
                remaining_h = (exp - time.time()) / 3600
                if remaining_h < 24 and not _WARNED_EXPIRY:
                    _WARNED_EXPIRY = True
                    log.warning("Cloudera workload token (%s) expires in %.1f h; refresh it with "
                                "deploy/save_session_token.py or set CDP_TOKEN", source, remaining_h)
            return tok
        _LAST_SOURCE = "none"
        log.error("LLM_PROVIDER=caii but no valid token: set LLM_API_KEY/CDP_TOKEN, or provide %s / %s",
                  os.getenv("CML_JWT_PATH", "/tmp/jwt"), fallback_token_path())
        return ""
    _LAST_SOURCE = "OPENAI_API_KEY"
    return os.getenv("OPENAI_API_KEY", "")


def assert_ready() -> None:
    """Raise a clear error when no usable credential exists (called before agent runs)."""
    s = settings()
    if not s["api_key"]:
        raise RuntimeError(
            "No valid Cloudera workload token for the LLM endpoint. The pod's /tmp/jwt is missing or "
            f"invalid and {fallback_token_path()} is absent/expired. From a Workbench session run "
            "`python deploy/save_session_token.py` (or set CDP_TOKEN), then retry."
        )


def settings() -> dict:
    """Resolved provider settings: {provider, model, base_url, api_key}."""
    prov = provider()
    if prov == "caii":
        base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
        model = os.getenv("LLM_MODEL", "")
        if not base_url or not model:
            raise RuntimeError("LLM_PROVIDER=caii requires LLM_BASE_URL and LLM_MODEL")
        return {"provider": prov, "model": model, "base_url": base_url, "api_key": resolve_api_key()}
    return {
        "provider": prov,
        "model": os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
        "base_url": os.getenv("LLM_BASE_URL") or None,
        "api_key": resolve_api_key(),
    }


def crew_llm():
    """A CrewAI LLM bound to the resolved provider (litellm OpenAI-compatible adapter)."""
    from crewai import LLM

    s = settings()
    # CrewAI/litellm internals occasionally consult OPENAI_API_KEY even when an
    # explicit api_key is passed; make sure it is populated for the caii case.
    if s["provider"] == "caii" and s["api_key"]:
        os.environ["OPENAI_API_KEY"] = s["api_key"]
    kwargs = {
        "model": f"openai/{s['model']}",
        "api_key": s["api_key"] or None,
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.3")),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "2048")),
    }
    if s["base_url"]:
        kwargs["base_url"] = s["base_url"]
    return LLM(**kwargs)


def openai_client():
    """An openai.OpenAI client bound to the resolved provider (used for streaming)."""
    from openai import OpenAI

    s = settings()
    return OpenAI(base_url=s["base_url"], api_key=s["api_key"] or "missing")


def describe() -> dict:
    """Non-secret summary for /api/health."""
    try:
        s = settings()
    except Exception as e:
        return {"provider": provider(), "error": str(e)}
    exp = jwt_expiry(s["api_key"])
    out = {
        "provider": s["provider"],
        "model": s["model"],
        "base_url": s["base_url"],
        "token_source": _LAST_SOURCE,
        "token_valid": bool(s["api_key"]) and (s["provider"] != "caii" or _looks_like_jwt(s["api_key"])),
        "has_key": bool(s["api_key"]),
        "fallback_file": str(fallback_token_path()),
        "fallback_file_valid": _read_fallback_jwt() is not None,
    }
    if exp is not None:
        out["token_expires_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp))
        out["token_hours_left"] = round((exp - time.time()) / 3600, 1)
    return out


if __name__ == "__main__":
    print(json.dumps(describe(), indent=2))
    llm = crew_llm()
    print("crew LLM reply:", repr(llm.call("Reply with exactly: REASONING: ok")))
    client = openai_client()
    chunks = client.chat.completions.create(
        model=settings()["model"], stream=True, max_tokens=20,
        messages=[{"role": "user", "content": "Say hello in three words."}],
    )
    print("stream:", "".join((c.choices[0].delta.content or "") for c in chunks if c.choices))
