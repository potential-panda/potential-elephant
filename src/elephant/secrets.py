"""
Load API keys from ~/secret/*.keys (INI format) into environment variables.
Existing env vars always take precedence — this only fills gaps.

Mapping: file → section → key  =>  env var
  ai.keys  DEFAULT  SECRET      =>  OPENAI_API_KEY
  ai.keys  ANTHROPIC  SECRET    =>  ANTHROPIC_API_KEY
"""

import configparser
import logging
import os
from pathlib import Path

SECRET_DIR = Path.home() / "secret"

# (filename, section, key) -> env var name
_MAPPINGS = [
    ("ai.keys", "DEFAULT", "SECRET", "OPENAI_API_KEY"),
    ("ai.keys", "ANTHROPIC", "SECRET", "ANTHROPIC_API_KEY"),
]


def load(secret_dir: Path = SECRET_DIR) -> None:
    for filename, section, key, env_var in _MAPPINGS:
        if os.environ.get(env_var):
            continue  # already set — don't overwrite

        path = secret_dir / filename
        if not path.exists():
            continue

        try:
            cfg = configparser.ConfigParser()
            cfg.read(path)
            value = cfg.get(section, key, fallback=None)
            if value and value.strip():
                os.environ[env_var] = value.strip()
                logging.debug(f"Loaded {env_var} from {path}[{section}]")
        except Exception:
            logging.debug(f"Could not read {env_var} from {path}")
