"""Environment settings and customer-config loading.

Everything that changes per environment is an env var (12-factor). Everything that
changes per customer is a JSON file under config/customers/. No workflow logic here.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from functools import lru_cache

# Repo root = parent of this file's parent (…/fmg_agent)
ROOT = Path(__file__).resolve().parents[1]
CUSTOMERS_DIR = ROOT / "config" / "customers"
PROMPT_PATH = ROOT / "prompts" / "schema_mapping_prompt.md"


class Settings:
    """Runtime settings, all overridable via environment variables."""

    # --- OpenAI ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # Default recommended tier-equivalent of Claude Sonnet for this task.
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
    # Escalation model for ambiguous (low_review) columns.
    OPENAI_ESCALATION_MODEL: str = os.getenv("OPENAI_ESCALATION_MODEL", "gpt-5.6-sol")
    OPENAI_REASONING_EFFORT: str = os.getenv("OPENAI_REASONING_EFFORT", "low")
    # Master switch — when false (or no key), the agent runs the deterministic path only.
    USE_LLM: bool = os.getenv("USE_LLM", "true").lower() == "true"

    # --- Storage (placeholder for Azure Blob wiring) ---
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")  # local | azure_blob
    AZURE_STORAGE_CONNECTION_STRING: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    OUTPUT_CONTAINER: str = os.getenv("OUTPUT_CONTAINER", "outputs")

    # --- Local paths (used by the local storage backend / CLI) ---
    LOCAL_OUTPUT_DIR: str = os.getenv("LOCAL_OUTPUT_DIR", str(ROOT / "_out"))


settings = Settings()


@lru_cache(maxsize=32)
def load_customer_config(customer_id: str = "default") -> dict:
    """Load a customer profile JSON. Falls back to 'default' if the id is unknown."""
    path = CUSTOMERS_DIR / f"{customer_id}.json"
    if not path.exists():
        path = CUSTOMERS_DIR / "default.json"
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    return cfg


def list_customers() -> list[str]:
    return sorted(
        p.stem for p in CUSTOMERS_DIR.glob("*.json") if not p.stem.startswith("_")
    )


def load_prompt() -> str:
    """Return the schema-mapping prompt text (the one created for this project)."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as fh:
        return fh.read()
