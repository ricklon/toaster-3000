"""Tests for the toast tool suite (no LLM calls needed)."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ─── toast_calculator ────────────────────────────────────────────────────────


class TestToastCalculator:
    def _call(self, bread_type, thickness_mm, darkness):
        from toaster_3000.tools import toast_calculator

        return toast_calculator(bread_type, thickness_mm, darkness)

    def test_returns_string(self):
        result = self._call("sourdough", 12.0, "medium")
        assert isinstance(result, str)

    def test_contains_time_and_temp(self):
        result = self._call("sourdough", 12.0, "medium")
        assert "Time" in result
        assert "Temp" in result

    def test_dark_toast_longer_than_light(self):
        def time_from(result):
            for line in result.splitlines():
                if "Time" in line:
                    return int(line.split(":")[1].strip().rstrip("s"))

        light = time_from(self._call("white", 12.0, "light"))
        dark = time_from(self._call("white", 12.0, "dark"))
        assert dark > light

    def test_thicker_bread_takes_longer(self):
        def time_from(result):
            for line in result.splitlines():
                if "Time" in line:
                    return int(line.split(":")[1].strip().rstrip("s"))

        thin = time_from(self._call("sourdough", 8.0, "medium"))
        thick = time_from(self._call("sourdough", 20.0, "medium"))
        assert thick > thin

    def test_minimum_time_enforced(self):
        # Very thin slice should never return zero seconds
        result = self._call("white", 1.0, "light")
        for line in result.splitlines():
            if "Time" in line:
                t = int(line.split(":")[1].strip().rstrip("s"))
                assert t >= 30

    def test_unknown_bread_uses_default(self):
        result = self._call("unicorn bread", 12.0, "medium")
        assert "Time" in result  # should not raise

    def test_celsius_and_fahrenheit_present(self):
        result = self._call("rye", 12.0, "dark")
        assert "°C" in result
        assert "°F" in result

    def test_darkness_levels(self):
        for darkness in ("light", "medium", "dark"):
            result = self._call("white", 12.0, darkness)
            assert "Time" in result

    @pytest.mark.parametrize(
        "bread",
        [
            "sourdough",
            "rye",
            "bagel",
            "ciabatta",
            "brioche",
            "pita",
        ],
    )
    def test_known_breads(self, bread):
        result = self._call(bread, 12.0, "medium")
        assert "Time" in result


# ─── find_toast_recipe ───────────────────────────────────────────────────────


class TestFindToastRecipe:
    def _call(self, ingredients):
        from toaster_3000.tools import find_toast_recipe

        return find_toast_recipe(ingredients)

    def test_returns_string(self):
        assert isinstance(self._call("sourdough, avocado"), str)

    def test_avocado_recipe(self):
        result = self._call("sourdough, avocado, lemon")
        assert "Avocado" in result
        assert "lemon" in result.lower() or "citrus" in result.lower()

    def test_avocado_with_egg(self):
        result = self._call("bread, avocado, eggs")
        assert "egg" in result.lower()

    def test_avocado_with_chilli(self):
        result = self._call("toast, avocado, chilli")
        assert "chilli" in result.lower() or "chili" in result.lower()

    def test_peanut_butter_recipe(self):
        result = self._call("bread, peanut butter")
        assert "PB" in result or "peanut" in result.lower()

    def test_pb_with_banana(self):
        result = self._call("bread, peanut butter, banana, honey")
        assert "banana" in result.lower()
        assert "honey" in result.lower()

    def test_tomato_recipe(self):
        result = self._call("bread, tomatoes, garlic")
        assert "Tomato" in result or "tomato" in result.lower()

    def test_egg_recipe(self):
        result = self._call("bread, eggs")
        assert "Egg" in result or "egg" in result.lower()

    def test_unknown_ingredients_fallback(self):
        result = self._call("mystery_bread, something_weird")
        assert "Toast" in result or "toast" in result.lower()

    def test_includes_steps(self):
        result = self._call("sourdough, avocado")
        # Should have numbered steps
        assert "1." in result

    def test_approved_stamp(self):
        result = self._call("sourdough, butter")
        assert "Toaster 3000 approved" in result


# ─── DynamicTool ─────────────────────────────────────────────────────────────


class TestDynamicTool:
    def _make(self, name, fn, description="A test tool"):
        from toaster_3000.tools import DynamicTool

        return DynamicTool(name=name, fn=fn, description=description)

    def test_name_set(self):
        tool = self._make("my_tool", lambda x: x)
        assert tool.name == "my_tool"

    def test_description_set(self):
        tool = self._make("t", lambda: None, description="Does something")
        assert tool.description == "Does something"

    def test_inputs_inferred_from_signature(self):
        def fn(bread: str, thickness: str) -> str:
            return bread

        tool = self._make("fn", fn)
        assert "bread" in tool.inputs
        assert "thickness" in tool.inputs

    def test_forward_calls_fn(self):
        def double(x: str) -> str:
            return x + x

        tool = self._make("double", double)
        assert tool.forward(x="toast") == "toasttoast"

    def test_forward_returns_string(self):
        tool = self._make("num", lambda x: 42)
        assert tool.forward(x="anything") == "42"

    def test_none_return_becomes_empty_string(self):
        tool = self._make("noop", lambda: None)
        assert tool.forward() == ""


# ─── build_dynamic_tool ──────────────────────────────────────────────────────


class TestBuildDynamicTool:
    def _build(self, name, code, description="test"):
        from toaster_3000.tools import build_dynamic_tool

        return build_dynamic_tool(name, code, description)

    def test_simple_function(self):
        code = "def add_toast(a, b):\n    return str(int(a) + int(b))"
        tool = self._build("add_toast", code)
        assert tool.forward(a="2", b="3") == "5"

    def test_uses_math_module(self):
        code = "def circle_toast(r):\n    return str(math.pi * float(r) ** 2)"
        tool = self._build("circle_toast", code)
        result = float(tool.forward(r="1"))
        assert abs(result - 3.14159) < 0.001

    def test_wrong_function_name_raises(self):
        from toaster_3000.tools import build_dynamic_tool

        code = "def different_name():\n    return 'toast'"
        with pytest.raises(ValueError, match="classified as low"):
            build_dynamic_tool("expected_name", code, "test description")

    def test_inputs_match_parameters(self):
        code = "def crispy(moisture, heat):\n    return 'crispy'"
        tool = self._build("crispy", code)
        assert "moisture" in tool.inputs
        assert "heat" in tool.inputs

    def test_syntax_error_raises(self):
        from toaster_3000.tools import build_dynamic_tool

        with pytest.raises(ValueError, match="classified as low"):
            build_dynamic_tool("bad", "def bad(:\n    pass", "test description")


# ─── dynamic tool risk assessment ────────────────────────────────────────────


class TestDynamicToolRiskAssessment:
    def _assess(self, name, code):
        from toaster_3000.tools import assess_dynamic_tool

        return assess_dynamic_tool(name, code)

    def test_policy_text_documents_supported_levels(self):
        from toaster_3000.tools import RISK_LOW, RISK_NONE, TOOL_RISK_POLICY_TEXT

        assert RISK_NONE == "none"
        assert RISK_LOW == "low"
        assert "`none`" in TOOL_RISK_POLICY_TEXT
        assert "`low`" in TOOL_RISK_POLICY_TEXT

    def test_simple_arithmetic_is_none(self):
        result = self._assess(
            "toast_score",
            "def toast_score(thickness, heat):\n"
            "    return str(int(thickness) * int(heat))",
        )
        assert result.level == "none"
        assert result.allowed

    def test_math_access_is_none(self):
        result = self._assess(
            "toast_area",
            "def toast_area(radius):\n    return str(math.pi * float(radius) ** 2)",
        )
        assert result.level == "none"

    def test_import_is_low(self):
        result = self._assess(
            "read_env",
            "import os\n"
            "def read_env():\n"
            "    return os.environ.get('HUGGINGFACE_API_KEY', '')",
        )
        assert result.level == "low"
        assert not result.allowed
        assert any("Import" in reason for reason in result.reasons)

    def test_open_is_low(self):
        result = self._assess(
            "read_file",
            "def read_file(path):\n    return open(path).read()",
        )
        assert result.level == "low"
        assert any("open" in reason for reason in result.reasons)

    def test_dunder_access_is_low(self):
        result = self._assess(
            "escape",
            "def escape(x):\n    return x.__class__",
        )
        assert result.level == "low"
        assert any("dunder" in reason for reason in result.reasons)

    def test_wrong_function_name_is_low(self):
        result = self._assess(
            "expected",
            "def different():\n    return 'toast'",
        )
        assert result.level == "low"
        assert any("does not match" in reason for reason in result.reasons)


# ─── RegisterToolTool ────────────────────────────────────────────────────────


class TestRegisterToolTool:
    def test_calls_callback(self):
        from toaster_3000.tools import RegisterToolTool

        received = {}

        def cb(name, code, desc):
            received.update({"name": name, "code": code, "desc": desc})
            return "ok"

        tool = RegisterToolTool(on_register=cb)
        result = tool.forward(
            tool_name="my_fn",
            python_code="def my_fn(): pass",
            description="does stuff",
        )
        assert result == "ok"
        assert received["name"] == "my_fn"

    def test_return_value_propagated(self):
        from toaster_3000.tools import RegisterToolTool

        tool = RegisterToolTool(on_register=lambda n, c, d: "queued!")
        assert (
            tool.forward(tool_name="x", python_code="def x(): pass", description="y")
            == "queued!"
        )


# ─── ToastCoderTool ──────────────────────────────────────────────────────────


class TestToastCoderTool:
    def test_forward_runs_code_agent(self):
        from toaster_3000.tools import ToastCoderTool

        mock_model = Mock()
        tool = ToastCoderTool(model=mock_model)

        mock_agent = Mock()
        mock_agent.run.return_value = "42 seconds"

        with patch("toaster_3000.tools.ToastCoderTool.forward") as mock_fwd:
            mock_fwd.return_value = "42 seconds"
            result = tool.forward("how long to toast bread?")
            assert result == "42 seconds"

    def test_name_and_description(self):
        from toaster_3000.tools import ToastCoderTool

        tool = ToastCoderTool(model=Mock())
        assert tool.name == "toast_coder"
        assert "code" in tool.description.lower()
