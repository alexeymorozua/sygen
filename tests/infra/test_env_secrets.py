"""Tests for centralised .env secret loading."""

from __future__ import annotations

from pathlib import Path

from ductor_bot.infra.env_secrets import clear_cache, load_env_secrets


def test_parse_simple_key_value(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nBAZ=123\n")

    clear_cache()
    result = load_env_secrets(env_file)

    assert result == {"FOO": "bar", "BAZ": "123"}


def test_parse_quoted_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('SINGLE=\'hello\'\nDOUBLE="world"\n')

    clear_cache()
    result = load_env_secrets(env_file)

    assert result == {"SINGLE": "hello", "DOUBLE": "world"}


def test_parse_export_prefix(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("export MY_KEY=secret\n")

    clear_cache()
    result = load_env_secrets(env_file)

    assert result == {"MY_KEY": "secret"}


def test_skip_comments_and_blanks(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# This is a comment\n\nKEY=val\n  # indented comment\n")

    clear_cache()
    result = load_env_secrets(env_file)

    assert result == {"KEY": "val"}


def test_inline_comment_stripped(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("API_KEY=sk-abc123  # my key\n")

    clear_cache()
    result = load_env_secrets(env_file)

    assert result == {"API_KEY": "sk-abc123"}


def test_inline_comment_preserved_in_quotes(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('MSG="hello # world"\n')

    clear_cache()
    result = load_env_secrets(env_file)

    assert result == {"MSG": "hello # world"}


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    clear_cache()
    result = load_env_secrets(tmp_path / ".env")

    assert result == {}


def test_empty_file_returns_empty(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("")

    clear_cache()
    result = load_env_secrets(env_file)

    assert result == {}


def test_caching(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\n")

    clear_cache()
    first = load_env_secrets(env_file)
    assert first == {"A": "1"}

    # Modify file — cached result should persist.
    env_file.write_text("A=2\nB=3\n")
    second = load_env_secrets(env_file)
    assert second is first  # Same object (cached).

    # After clearing cache, new values are read.
    clear_cache()
    third = load_env_secrets(env_file)
    assert third == {"A": "2", "B": "3"}


def test_line_without_equals_skipped(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("NOVALUE\nGOOD=yes\n")

    clear_cache()
    result = load_env_secrets(env_file)

    assert result == {"GOOD": "yes"}


def test_empty_value_preserved(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("EMPTY=\n")

    clear_cache()
    result = load_env_secrets(env_file)

    assert result == {"EMPTY": ""}
