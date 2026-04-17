"""Persistent recipe store for Toaster 3000."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

DEFAULT_RECIPES_PATH = Path.home() / ".toaster3000" / "recipes.json"


@dataclass
class Recipe:
    name: str
    bread_type: str
    ingredients: List[str]
    steps: List[str]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class RecipeStore:
    """Thread-safe persistent store for toast recipes."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or DEFAULT_RECIPES_PATH
        self._lock = Lock()
        self._recipes: Dict[str, Recipe] = {}
        self._load()

    def save_recipe(
        self,
        name: str,
        bread_type: str,
        ingredients: List[str],
        steps: List[str],
    ) -> str:
        recipe = Recipe(
            name=name,
            bread_type=bread_type,
            ingredients=ingredients,
            steps=steps,
        )
        with self._lock:
            self._recipes[name.lower()] = recipe
            self._persist()
        return f"Recipe '{name}' saved to your collection!"

    def list_recipes(self) -> List[Recipe]:
        with self._lock:
            return list(self._recipes.values())

    def get_recipe(self, name: str) -> Optional[Recipe]:
        with self._lock:
            return self._recipes.get(name.lower())

    def delete_recipe(self, name: str) -> bool:
        with self._lock:
            if name.lower() in self._recipes:
                del self._recipes[name.lower()]
                self._persist()
                return True
            return False

    def count(self) -> int:
        with self._lock:
            return len(self._recipes)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path) as f:
                data = json.load(f)
            self._recipes = {k: Recipe(**v) for k, v in data.items()}
        except Exception as e:
            print(f"RecipeStore: could not load {self._path}: {e}")

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(
                    {k: asdict(v) for k, v in self._recipes.items()},
                    f,
                    indent=2,
                )
        except Exception as e:
            print(f"RecipeStore: could not save {self._path}: {e}")
