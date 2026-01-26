"""Shared data loading utilities."""
import json
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=1)
def load_teams_data() -> dict:
    """Load teams data from JSON file. Results are cached."""
    teams_path = Path("data/teams.json")
    if teams_path.exists():
        with open(teams_path) as f:
            return json.load(f)
    return {}


@lru_cache(maxsize=1)
def load_athletes_data() -> dict:
    """Load athletes data from JSON file. Results are cached."""
    athletes_path = Path("data/athletes.json")
    if athletes_path.exists():
        with open(athletes_path) as f:
            return json.load(f)
    return {}
