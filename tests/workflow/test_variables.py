"""Tests for variable resolution and safe expression evaluation."""

from __future__ import annotations

from sygen_bot.workflow.models import StepRun, StepStatus
from sygen_bot.workflow.variables import resolve_variables, safe_eval


class TestResolveSimpleVariable:
    def test_dollar_shorthand(self):
        result = resolve_variables("$greeting", {"greeting": "hello"}, {})
        assert result == "hello"

    def test_variables_prefix(self):
        result = resolve_variables(
            "$variables.greeting", {"greeting": "hello"}, {}
        )
        assert result == "hello"

    def test_embedded_in_text(self):
        result = resolve_variables(
            "Say $greeting world", {"greeting": "hello"}, {}
        )
        assert result == "Say hello world"


class TestResolveStepOutput:
    def test_step_output(self):
        sr = StepRun(step_id="step1", output="result")
        resolved = resolve_variables(
            "$steps.step1.output", {}, {"step1": sr}
        )
        assert resolved == "result"


class TestResolveStepError:
    def test_step_error(self):
        sr = StepRun(step_id="s1", error="oops")
        resolved = resolve_variables(
            "$steps.s1.error", {}, {"s1": sr}
        )
        assert resolved == "oops"


class TestResolveStepStatus:
    def test_step_status(self):
        sr = StepRun(step_id="s1", status=StepStatus.COMPLETED)
        resolved = resolve_variables(
            "$steps.s1.status", {}, {"s1": sr}
        )
        assert resolved == "completed"


class TestMissingVariableUnchanged:
    def test_unknown_var(self):
        result = resolve_variables("$unknown", {}, {})
        assert result == "$unknown"

    def test_unknown_nested(self):
        result = resolve_variables("$variables.missing", {}, {})
        assert result == "$variables.missing"


class TestMissingStepUnchanged:
    def test_missing_step(self):
        result = resolve_variables("$steps.nope.output", {}, {})
        assert result == "$steps.nope.output"


class TestSafeEval:
    def test_string_in(self):
        assert safe_eval("'hello' in 'hello world'") is True

    def test_not_in(self):
        assert safe_eval("'x' not in 'abc'") is True

    def test_equality(self):
        assert safe_eval("'a' == 'a'") is True

    def test_inequality(self):
        assert safe_eval("'a' == 'b'") is False

    def test_lower(self):
        assert safe_eval("'YES'.lower() == 'yes'") is True

    def test_boolean_ops(self):
        assert safe_eval("True and not False") is True

    def test_false_expression(self):
        assert safe_eval("'a' in 'xyz'") is False

    def test_unsafe_import_rejected(self):
        result = safe_eval("__import__('os')")
        assert result is False

    def test_unsafe_getattr_call_rejected(self):
        # getattr() is not in the allowed call list
        result = safe_eval("getattr('', '__class__')")
        assert result is False

    def test_syntax_error_returns_false(self):
        result = safe_eval("not valid python !!!")
        assert result is False
