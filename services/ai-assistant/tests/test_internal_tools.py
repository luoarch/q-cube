"""Tests for council internal tools — unit tests with no DB."""

from q3_ai_assistant.council.tools.internal import ToolResult, get_strategy_definition


class TestToolResult:
    def test_frozen(self):
        r = ToolResult(tool="test", data={"key": "val"})
        try:
            r.tool = "hacked"  # type: ignore[misc]
            assert False, "ToolResult should be frozen"
        except AttributeError:
            pass

    def test_default_error_is_none(self):
        r = ToolResult(tool="test", data={})
        assert r.error is None

    def test_with_error(self):
        r = ToolResult(tool="test", data=None, error="not found")
        assert r.error == "not found"
        assert r.data is None


class TestGetStrategyDefinition:
    def test_magic_formula(self):
        result = get_strategy_definition("magic_formula")
        assert result.error is None
        assert result.data is not None
        assert "Magic Formula" in result.data["name"]
        assert "earnings_yield" in result.data["metrics"]
        assert "roic" in result.data["metrics"]

    def test_unknown_strategy(self):
        result = get_strategy_definition("unknown_strategy")
        assert result.error is not None
        assert result.data is None
        assert "unknown_strategy" in result.error

    def test_tool_name(self):
        result = get_strategy_definition("magic_formula")
        assert result.tool == "get_strategy_definition"
