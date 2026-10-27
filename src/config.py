"""LLM client factory + runtime Config (extracted from the notebook).

Same contract as the SME repo: ``build_llm("MODEL_PREMIUM")`` reads the model name
from that environment variable and raises at startup if it is unset.
``LLM_PROVIDER`` picks how the model is reached:

    LLM_PROVIDER=openai      ChatOpenAI → api.openai.com, or any OpenAI-format
                             gateway via OPENAI_API_BASE. Key: OPENAI_API_KEY.
    LLM_PROVIDER=anthropic   ChatAnthropic; ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL.
    LLM_PROVIDER=databricks  a Databricks model serving endpoint (OpenAI format);
                             DATABRICKS_HOST, DATABRICKS_TOKEN. MODEL_* = endpoint name.
    LLM_PROVIDER=databricks_invocations
                             the team's existing Databricks convention:
                             {ANTHROPIC_API_BASE}/{model}/invocations, key from
                             api_key=, OPENAI_API_KEY, DATABRICKS_API_TOKEN or
                             DATABRICKS_TOKEN (a Databricks token, never sk-...).

LLM_PROVIDER unset → ``databricks_invocations`` when ANTHROPIC_API_BASE is set,
otherwise ``openai``. ``api_key=`` (as the team notebooks pass it) overrides the
key from the environment; ``thinking_budget`` is used by Anthropic models only.
"""

import os
from dataclasses import dataclass
from typing import Any

PROVIDERS = ("openai", "anthropic", "databricks", "databricks_invocations")

# What each provider needs, so a missing value is named before any call is made.
_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "databricks": "DATABRICKS_TOKEN",
    "databricks_invocations": "OPENAI_API_KEY",
}
_URL_ENV = {
    "databricks": "DATABRICKS_HOST",
    "databricks_invocations": "ANTHROPIC_API_BASE",
}


def llm_provider() -> str:
    """The provider in use, after the LLM_PROVIDER-unset default."""

    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if not provider:
        provider = "databricks_invocations" if os.getenv("ANTHROPIC_API_BASE") else "openai"
    if provider not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER={provider!r}; expected one of {PROVIDERS}")
    return provider


def _rate_limiter():
    """One limiter shared by every client, from LLM_REQUESTS_PER_MINUTE (0 = off)."""

    per_minute = float(os.getenv("LLM_REQUESTS_PER_MINUTE", "0") or 0)
    if per_minute <= 0:
        return None
    global _SHARED_LIMITER
    try:
        return _SHARED_LIMITER
    except NameError:
        from langchain_core.rate_limiters import InMemoryRateLimiter

        _SHARED_LIMITER = InMemoryRateLimiter(
            requests_per_second=per_minute / 60.0,
            check_every_n_seconds=0.1,
            max_bucket_size=1,
        )
        return _SHARED_LIMITER


def build_llm(
    model_env: str,
    temperature: float = 0.1,
    timeout_env: str = "LLM_TIMEOUT_SECONDS",
    max_tokens_env: str = "LLM_MAX_TOKENS",
    api_key: str | None = None,
    thinking_budget: int = 0,
):
    """Build one chat client from environment variables."""

    model = os.getenv(model_env, "").strip()
    if not model:
        raise ValueError(
            f"{model_env} is not set — os.environ has no {model_env}. Set it in the "
            f"notebook (os.environ[{model_env!r}] = ...) or in a file named exactly "
            f"'.env' next to the notebook (not .env.example), then re-run cell 2"
        )
    provider = llm_provider()
    key = api_key or os.getenv(_KEY_ENV[provider], "")
    if not key and provider == "databricks_invocations":
        # The team notebooks keep the Databricks token under these names.
        key = os.getenv("DATABRICKS_API_TOKEN", "") or os.getenv("DATABRICKS_TOKEN", "")
    missing = [] if key else [_KEY_ENV[provider]]
    url_env = _URL_ENV.get(provider)
    if url_env and not os.getenv(url_env):
        missing.append(url_env)
    if missing:
        raise ValueError(
            f"LLM_PROVIDER={provider} needs {', '.join(missing)} — set it in "
            f".env or in the notebook (dbutils.secrets) before building the config"
        )

    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": 1.0 if thinking_budget and provider == "anthropic" else temperature,
        "timeout": float(os.getenv(timeout_env, "60")),
        "max_retries": int(os.getenv("LLM_CLIENT_MAX_RETRIES", "1")),
        "max_tokens": int(os.getenv(max_tokens_env, "8192")),
        "api_key": key,
    }
    limiter = _rate_limiter()
    if limiter is not None:
        kwargs["rate_limiter"] = limiter

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if os.getenv("ANTHROPIC_BASE_URL"):
            kwargs["base_url"] = os.getenv("ANTHROPIC_BASE_URL")
        if thinking_budget:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
        return ChatAnthropic(**kwargs)

    from langchain_openai import ChatOpenAI

    if provider == "databricks":
        host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
        if not host.startswith("http"):
            host = "https://" + host
        return ChatOpenAI(**kwargs, base_url=f"{host}/serving-endpoints")

    if provider == "databricks_invocations":
        import httpx

        def _rewrite_url(request: httpx.Request) -> None:
            url = str(request.url)
            if "/chat/completions" in url:
                request.url = httpx.URL(url.replace("/chat/completions", "/invocations"))

        base = os.getenv("ANTHROPIC_API_BASE", "").rstrip("/")
        if not base.startswith("http"):
            base = "https://" + base
        if thinking_budget:
            kwargs["model_kwargs"] = {
                "thinking": {"type": "enabled", "budget_tokens": thinking_budget}
            }
            kwargs["temperature"] = 1.0
        return ChatOpenAI(
            **kwargs,
            base_url=f"{base}/{model}",
            http_client=httpx.Client(event_hooks={"request": [_rewrite_url]}),
        )

    return ChatOpenAI(**kwargs, base_url=os.getenv("OPENAI_API_BASE") or None)


@dataclass
class Config:
    """Runtime config for the local notebook workflow."""

    document_llm: Any = None
    # One per BRD item (Corp Income, "Pháp lý doanh nghiệp" 1-4).
    legal_basic_extraction_llm: Any = None
    shareholders_extraction_llm: Any = None
    legal_rep_extraction_llm: Any = None
    liabilities_extraction_llm: Any = None
    # Phụ lục 01: financial statements (mục 3) and the report writer that fills
    # the template's narrative placeholders from the extracted evidence.
    financial_extraction_llm: Any = None
    report_writer_llm: Any = None
    # [BRD 16/10] Optional: left None, these passes use financial_extraction_llm.
    vat_extraction_llm: Any = None
    cic_extraction_llm: Any = None
    plan_extraction_llm: Any = None
    business_model_extraction_llm: Any = None      # [BRD 27/10]
    max_files: int = 50
    max_chars_per_document: int = 120_000
    max_extraction_calls: int = 60
    max_extraction_input_chars: int = 3_000_000
    result_content_char_limit: int = 2_000
    document_classifier_rule_confidence_threshold: float = 0.80
    document_classifier_grouped_confidence_threshold: float = 0.80
    enable_plan_and_execute: bool = True
    enable_self_ask_gap_analysis: bool = True
