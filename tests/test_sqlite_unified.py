"""TDD tests: all SQLite DBs should live under data/ by default."""
import inspect
from pathlib import Path

from config import settings


def test_config_has_memory_db_path():
    """config.py exposes memory_db_path pointing to data/memory.db"""
    expected = str(Path(__file__).resolve().parent.parent / "data" / "memory.db")
    assert settings.memory_db_path == expected


def test_dialogue_memory_default_db_path():
    """DialogueMemory.__init__ defaults db_path to config.memory_db_path."""
    from rag.memory import DialogueMemory

    sig = inspect.signature(DialogueMemory.__init__)
    default = sig.parameters["db_path"].default
    assert default == settings.memory_db_path


def test_execution_tracker_default_db_path():
    """ExecutionTracker.__init__ defaults db_path to config.memory_db_path."""
    from rag.tracker import ExecutionTracker

    sig = inspect.signature(ExecutionTracker.__init__)
    default = sig.parameters["db_path"].default
    assert default == settings.memory_db_path
