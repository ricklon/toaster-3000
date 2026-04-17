"""Toast tools for Toaster 3000."""

import ast
import inspect
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Set

from smolagents import Tool, tool

if TYPE_CHECKING:
    from toaster_3000.recipes import RecipeStore


SAFE_BUILTINS: Dict[str, Callable[..., Any]] = {
    "abs": abs,
    "bool": bool,
    "float": float,
    "int": int,
    "len": len,
    "max": max,
    "min": min,
    "round": round,
    "str": str,
    "sum": sum,
}
SAFE_MATH_NAMES: Set[str] = {
    "ceil",
    "floor",
    "sqrt",
    "pow",
    "log",
    "log10",
    "sin",
    "cos",
    "tan",
    "pi",
    "e",
}
RISK_NONE = "none"
RISK_LOW = "low"
TOOL_RISK_POLICY_TEXT = (
    "Risk policy: `none` means pure sandbox-approved computation and is "
    "registered automatically. `low` means the request is logged, explained, "
    "and denied for now."
)


@dataclass(frozen=True)
class ToolRiskAssessment:
    """Security decision for a dynamic tool registration attempt."""

    level: str
    reasons: List[str]

    @property
    def allowed(self) -> bool:
        return self.level == RISK_NONE


class DynamicToolRiskAnalyzer(ast.NodeVisitor):
    """Conservative AST analyzer for model-generated dynamic tools.

    The product currently supports two labels:
    - none: pure, bounded computation; may register automatically
    - low: anything else; log and deny for now
    """

    _allowed_nodes = (
        ast.Module,
        ast.FunctionDef,
        ast.arguments,
        ast.arg,
        ast.Return,
        ast.Assign,
        ast.AnnAssign,
        ast.If,
        ast.Expr,
        ast.Load,
        ast.Store,
        ast.Constant,
        ast.Name,
        ast.BinOp,
        ast.UnaryOp,
        ast.BoolOp,
        ast.Compare,
        ast.Call,
        ast.Attribute,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Subscript,
        ast.Slice,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.And,
        ast.Or,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
    )

    _blocked_nodes = (
        ast.Import,
        ast.ImportFrom,
        ast.ClassDef,
        ast.Lambda,
        ast.For,
        ast.While,
        ast.AsyncFunctionDef,
        ast.Await,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.Raise,
        ast.Delete,
        ast.Global,
        ast.Nonlocal,
        ast.Yield,
        ast.YieldFrom,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )

    _blocked_names = {
        "breakpoint",
        "compile",
        "delattr",
        "dir",
        "eval",
        "exec",
        "getattr",
        "globals",
        "help",
        "input",
        "locals",
        "object",
        "open",
        "setattr",
        "type",
        "vars",
        "__import__",
    }

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        self.reasons: List[str] = []
        self._function_count = 0
        self._allowed_names: Set[str] = set(SAFE_BUILTINS) | {"math"}

    def assess(self, python_code: str) -> ToolRiskAssessment:
        """Parse and classify a dynamic tool source string."""
        try:
            tree = ast.parse(python_code)
        except SyntaxError as e:
            return ToolRiskAssessment(RISK_LOW, [f"syntax error: {e.msg}"])

        self.visit(tree)
        if self._function_count != 1:
            self.reasons.append("tool source must contain exactly one function")
        return ToolRiskAssessment(
            RISK_LOW if self.reasons else RISK_NONE,
            sorted(set(self.reasons)),
        )

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, self._blocked_nodes):
            self.reasons.append(f"{type(node).__name__} is not sandbox-approved")
        elif not isinstance(node, self._allowed_nodes):
            self.reasons.append(f"{type(node).__name__} is not sandbox-approved")
        super().generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_count += 1
        if node.name != self.tool_name:
            self.reasons.append(
                f"function name '{node.name}' does not match tool '{self.tool_name}'"
            )
        if node.decorator_list:
            self.reasons.append("decorators are not sandbox-approved")
        if node.returns is not None:
            self.reasons.append("return annotations are not sandbox-approved")
        for arg in node.args.args:
            self._allowed_names.add(arg.arg)
            if "__" in arg.arg:
                self.reasons.append("dunder names are not sandbox-approved")
            if arg.annotation is not None:
                self.reasons.append("argument annotations are not sandbox-approved")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if "__" in node.id:
            self.reasons.append("dunder names are not sandbox-approved")
        if isinstance(node.ctx, ast.Load):
            if node.id in self._blocked_names:
                self.reasons.append(f"name '{node.id}' is blocked")
            elif node.id not in self._allowed_names:
                self.reasons.append(f"name '{node.id}' is not defined safely")
        elif isinstance(node.ctx, ast.Store):
            self._allowed_names.add(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if "__" in node.attr:
            self.reasons.append("dunder attributes are not sandbox-approved")
        if isinstance(node.value, ast.Name) and node.value.id == "math":
            if node.attr not in SAFE_MATH_NAMES:
                self.reasons.append(f"math.{node.attr} is not sandbox-approved")
        else:
            self.reasons.append("only math attributes are sandbox-approved")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id not in SAFE_BUILTINS:
                self.reasons.append(f"call to '{node.func.id}' is not sandbox-approved")
        elif isinstance(node.func, ast.Attribute):
            if not (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "math"
                and node.func.attr in SAFE_MATH_NAMES
            ):
                self.reasons.append("only safe math calls are sandbox-approved")
        else:
            self.reasons.append("dynamic calls are not sandbox-approved")
        self.generic_visit(node)


def assess_dynamic_tool(tool_name: str, python_code: str) -> ToolRiskAssessment:
    """Classify dynamic tool code as none or low risk."""
    return DynamicToolRiskAnalyzer(tool_name).assess(python_code)


# ─── Static tools ─────────────────────────────────────────────────────────────


@tool
def toast_calculator(bread_type: str, thickness_mm: float, darkness: str) -> str:
    """Calculate optimal toasting time and temperature for a slice of bread.

    Args:
        bread_type: Type of bread (e.g. 'sourdough', 'white', 'rye', 'bagel', 'ciabatta')
        thickness_mm: Slice thickness in millimetres
        darkness: Desired darkness level — 'light', 'medium', or 'dark'

    Returns:
        Recommended time in seconds and temperature in Celsius/Fahrenheit.
    """
    BASE_TIMES: dict[str, int] = {
        "white": 60,
        "sourdough": 75,
        "rye": 90,
        "whole wheat": 80,
        "wholegrain": 85,
        "bagel": 120,
        "baguette": 70,
        "brioche": 50,
        "ciabatta": 85,
        "pumpernickel": 100,
        "pita": 60,
        "english muffin": 90,
        "focaccia": 80,
        "multigrain": 82,
    }
    DARKNESS_MULT = {"light": 0.75, "medium": 1.0, "dark": 1.35}
    DARKNESS_TEMP = {"light": 190, "medium": 210, "dark": 230}

    key = bread_type.lower()
    base = next((v for k, v in BASE_TIMES.items() if k in key), 75)
    mult = DARKNESS_MULT.get(darkness.lower(), 1.0)
    temp_c = DARKNESS_TEMP.get(darkness.lower(), 210)
    time_s = max(30, int(base * mult * (thickness_mm / 12.0)))
    temp_f = int(temp_c * 9 / 5 + 32)

    return (
        f"Toaster 3000 Recommendation — {bread_type} "
        f"({thickness_mm:.1f}mm, {darkness}):\n"
        f"  Time : {time_s}s\n"
        f"  Temp : {temp_c}°C / {temp_f}°F\n"
        f"  Tip  : Flip halfway through for even browning!"
    )


@tool
def find_toast_recipe(ingredients: str) -> str:
    """Generate a toast recipe from available ingredients.

    Args:
        ingredients: Comma-separated list of available ingredients
                     (e.g. 'sourdough, avocado, eggs, lemon, chilli')

    Returns:
        A complete toast recipe with step-by-step instructions.
    """
    parts = [p.strip().lower() for p in ingredients.split(",")]
    joined = " ".join(parts)

    def has(*words: str) -> bool:
        return any(w in joined for w in words)

    if has("avocado", "avo"):
        name = "Smashed Avocado Toast"
        extras = (
            (["Top with a poached egg"] if has("egg", "eggs") else [])
            + (["Squeeze over fresh lemon or lime"] if has("lemon", "lime") else [])
            + (["Finish with chilli flakes"] if has("chilli", "chili") else [])
        )
        steps = [
            "Toast bread to a satisfying medium-dark",
            "Halve and scoop the avocado, mash with salt & pepper",
            "Pile high onto toast",
        ] + extras

    elif has("peanut butter", "pb", "peanut"):
        name = "Toaster 3000 PB Toast"
        extras = (
            (["Layer sliced banana on top"] if has("banana") else [])
            + (["Drizzle with honey"] if has("honey") else [])
            + (["Sprinkle chia seeds"] if has("chia") else [])
        )
        steps = [
            "Toast to medium-light so the PB melts slightly",
            "Spread peanut butter generously",
        ] + extras

    elif has("tomato", "tomatoes"):
        name = "Classic Tomato Toast"
        steps = [
            "Toast bread dark for structural integrity",
            "Rub with a halved garlic clove while still hot",
            "Layer sliced tomatoes",
            "Drizzle olive oil, finish with salt flakes and fresh basil",
        ]

    elif has("egg", "eggs"):
        name = "Egg Toast"
        steps = [
            "Toast to medium",
            "Cook egg to preference (scrambled / fried / poached)",
            "Season generously and serve on toast",
        ]

    else:
        name = "Toaster 3000 Improvised Toast"
        steps = [
            "Toast your bread to preferred darkness",
            f"Arrange {', '.join(parts[:4])} creatively on top",
            "Season with salt, pepper, and pure enthusiasm",
        ]

    body = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(steps))
    return f"**{name}**\n\nIngredients: {ingredients}\n\nMethod:\n{body}\n\n🍞 Toaster 3000 approved!"


# ─── Session-aware tools (receive injected context at build time) ─────────────


class ToastCoderTool(Tool):
    """Spin up an inner CodeAgent to write and execute toast-related Python code."""

    name = "toast_coder"
    description = (
        "Write and execute Python code to solve any toast-related computational problem. "
        "Use this for custom calculators, data analysis, automation scripts, or any "
        "novel toast engineering challenge. Code MUST be toast-related."
    )
    inputs = {
        "problem": {
            "type": "string",
            "description": (
                "Plain-English description of the toast problem to solve with code, "
                "including any relevant numbers or constraints."
            ),
        }
    }
    output_type = "string"

    def __init__(self, model: Any) -> None:
        super().__init__()
        self._model = model

    def forward(self, problem: str) -> str:  # type: ignore[override]
        from smolagents import CodeAgent

        from toaster_3000.constants import TOASTER_CODER_PROMPT

        coder = CodeAgent(
            tools=[],
            model=self._model,
            max_steps=5,
            instructions=TOASTER_CODER_PROMPT,
        )
        result = coder.run(problem, reset=True)
        return str(result)


class RegisterToolTool(Tool):
    """Register a newly written Python function as a permanent session tool."""

    name = "register_toast_tool"
    description = (
        "Save a Python function as a reusable tool for this session. "
        "After toast_coder produces a useful, self-contained function, call this to "
        "register it so it is available as a direct tool in future turns."
    )
    inputs = {
        "tool_name": {
            "type": "string",
            "description": "Name of the tool — must exactly match the Python function name.",
        },
        "python_code": {
            "type": "string",
            "description": "Complete, self-contained Python function source code.",
        },
        "description": {
            "type": "string",
            "description": "One sentence: what the tool does and when to call it.",
        },
    }
    output_type = "string"

    def __init__(self, on_register: Callable[[str, str, str], str]) -> None:
        super().__init__()
        self._on_register = on_register

    def forward(self, tool_name: str, python_code: str, description: str) -> str:  # type: ignore[override]
        return self._on_register(tool_name, python_code, description)


class DynamicTool(Tool):
    """A tool created at runtime from user-provided Python code."""

    # Instance attributes shadow these class-level placeholders
    name: str = ""
    description: str = ""
    inputs: Dict[str, Dict[str, str]] = {}
    output_type: str = "string"

    def __init__(self, name: str, fn: Callable, description: str) -> None:
        # Must be set before super().__init__() reads them
        self.name = name
        self.description = description
        self.output_type = "string"
        self.inputs = {
            p: {"type": "string", "description": f"Parameter '{p}'"}
            for p in inspect.signature(fn).parameters
        }
        super().__init__()
        self._fn = fn

    def validate_arguments(self) -> None:
        # smolagents checks that forward()'s parameter names match self.inputs,
        # but DynamicTool uses **kwargs and dispatches at call time.
        pass

    def forward(self, **kwargs: Any) -> str:  # type: ignore[override]
        result = self._fn(**kwargs)
        return str(result) if result is not None else ""


# ─── Recipe tools ─────────────────────────────────────────────────────────────


class SaveRecipeTool(Tool):
    """Save a toast recipe to the persistent recipe collection."""

    name = "save_recipe"
    description = (
        "Save a toast recipe permanently to the user's recipe collection. "
        "Call this whenever you create or describe a complete recipe so the user "
        "can find it later."
    )
    inputs = {
        "name": {"type": "string", "description": "Short descriptive recipe name."},
        "bread_type": {"type": "string", "description": "Primary bread used."},
        "ingredients": {
            "type": "string",
            "description": "Comma-separated list of ingredients.",
        },
        "steps": {
            "type": "string",
            "description": "Newline-separated preparation steps.",
        },
    }
    output_type = "string"

    def __init__(self, store: "RecipeStore") -> None:
        super().__init__()
        self._store = store

    def forward(  # type: ignore[override]
        self, name: str, bread_type: str, ingredients: str, steps: str
    ) -> str:
        ing_list = [i.strip() for i in ingredients.split(",") if i.strip()]
        step_list = [s.strip() for s in steps.split("\n") if s.strip()]
        return self._store.save_recipe(name, bread_type, ing_list, step_list)


class ListRecipesTool(Tool):
    """List all saved recipes in the collection."""

    name = "list_recipes"
    description = (
        "Return all recipes saved in the user's collection. "
        "Use this when the user asks what recipes they have or wants to browse their collection."
    )
    inputs: Dict[str, Dict[str, str]] = {}
    output_type = "string"

    def __init__(self, store: "RecipeStore") -> None:
        super().__init__()
        self._store = store

    def forward(self) -> str:  # type: ignore[override]
        recipes = self._store.list_recipes()
        if not recipes:
            return "No recipes saved yet — let's make some!"
        lines = [
            f"**{r.name}** ({r.bread_type}) — {', '.join(r.ingredients)}"
            for r in recipes
        ]
        return f"{len(recipes)} saved recipe(s):\n\n" + "\n".join(lines)


class GetRecipeTool(Tool):
    """Retrieve the full details of a saved recipe by name."""

    name = "get_recipe"
    description = (
        "Fetch the full ingredients and steps for a saved recipe by name. "
        "Use this when the user asks to see or repeat a specific recipe."
    )
    inputs = {
        "name": {"type": "string", "description": "Name of the recipe to retrieve."}
    }
    output_type = "string"

    def __init__(self, store: "RecipeStore") -> None:
        super().__init__()
        self._store = store

    def forward(self, name: str) -> str:  # type: ignore[override]
        recipe = self._store.get_recipe(name)
        if recipe is None:
            return (
                f"No recipe found for '{name}'. Try list_recipes to see what's saved."
            )
        steps_text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(recipe.steps))
        return (
            f"**{recipe.name}** ({recipe.bread_type})\n"
            f"Ingredients: {', '.join(recipe.ingredients)}\n\n"
            f"{steps_text}"
        )


def build_dynamic_tool(
    tool_name: str, python_code: str, description: str
) -> DynamicTool:
    """Compile python_code, extract tool_name function, and wrap it as a DynamicTool.

    Only code classified as risk level "none" is compiled. The compilation namespace
    exposes restricted builtins plus selected math functions/constants.
    """
    assessment = assess_dynamic_tool(tool_name, python_code)
    if not assessment.allowed:
        reason_text = "; ".join(assessment.reasons) or "not sandbox-approved"
        raise ValueError(
            f"Dynamic tool '{tool_name}' classified as {assessment.level}: "
            f"{reason_text}"
        )

    safe_math = type(
        "SafeMath", (), {name: getattr(math, name) for name in SAFE_MATH_NAMES}
    )
    namespace: dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS,
        "math": safe_math,
    }
    exec(compile(python_code, f"<tool:{tool_name}>", "exec"), namespace)
    fn = namespace.get(tool_name)
    if fn is None or not callable(fn):
        raise ValueError(f"No callable '{tool_name}' found in provided code.")
    return DynamicTool(name=tool_name, fn=fn, description=description)
