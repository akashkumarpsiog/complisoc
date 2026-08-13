"""Unit tests for core utility helpers (json_extract, retry).

Improves coverage of under-tested modules.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from complisoc.backend.core.json_extract import extract_json
from complisoc.backend.core.retry import call_with_retry


class TestExtractJson:
    def test_plain_json(self):
        result = extract_json('{"a": 1, "b": 2}')
        assert result == {"a": 1, "b": 2}

    def test_fenced_code_block(self):
        text = "```json\n{\"a\": 1}\n```"
        assert extract_json(text) == {"a": 1}

    def test_fenced_without_lang(self):
        text = "```\n{\"a\": 1}\n```"
        assert extract_json(text) == {"a": 1}

    def test_json_embedded_in_text(self):
        text = 'Some preamble\n{"a": 1, "b": 2}\nSome trailing text'
        assert extract_json(text) == {"a": 1, "b": 2}

    def test_nested_json(self):
        text = '{"outer": {"inner": {"value": 42}}}'
        result = extract_json(text)
        assert result == {"outer": {"inner": {"value": 42}}}

    def test_none_input(self):
        with pytest.raises(json.JSONDecodeError):
            extract_json(None)

    def test_empty_string(self):
        with pytest.raises(json.JSONDecodeError):
            extract_json("")

    def test_garbage_with_no_braces(self):
        with pytest.raises(json.JSONDecodeError):
            extract_json("no json here at all")


class TestRetry:
    @pytest.fixture()
    def no_sleep(self):
        with patch("complisoc.backend.core.retry.time.sleep") as mock_sleep:
            yield mock_sleep

    def test_succeeds_first_try(self, no_sleep):
        calls = []

        def fn():
            calls.append(1)
            return "ok"

        assert call_with_retry(fn) == "ok"
        assert len(calls) == 1

    def test_retries_on_failure(self, no_sleep):
        state = {"count": 0}

        def fn():
            state["count"] += 1
            if state["count"] < 3:
                raise RuntimeError("transient")
            return "ok"

        result = call_with_retry(fn, attempts=3, backoff=0)
        assert result == "ok"
        assert state["count"] == 3

    def test_give_up_on_specific_exception(self, no_sleep):
        calls = []

        def fn():
            calls.append(1)
            raise ValueError("fatal")

        with pytest.raises(ValueError):
            call_with_retry(fn, attempts=5, backoff=0, give_up_on=lambda e: isinstance(e, ValueError))
        assert len(calls) == 1

    def test_exhausts_attempts(self, no_sleep):
        calls = []

        def fn():
            calls.append(1)
            raise RuntimeError("always")

        with pytest.raises(RuntimeError):
            call_with_retry(fn, attempts=3, backoff=0)
        assert len(calls) == 3

    def test_max_delay_caps_backoff(self, no_sleep):
        state = {"count": 0}

        def fn():
            state["count"] += 1
            if state["count"] < 2:
                raise RuntimeError("retry")
            return "ok"

        result = call_with_retry(fn, attempts=3, backoff=100, max_delay=0)
        assert result == "ok"
