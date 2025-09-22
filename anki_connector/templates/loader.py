"""Template loader with a Jinja2-based layout.

Structure:
  - Base (shared, not a theme): ``anki_connector/templates/base``
  - Themes (override base): ``anki_connector/templates/themes/<name>``
  - Assets (shared snippets): ``anki_connector/templates/assets``

Each theme provides these files (missing items fall back to base):
  - front.html.j2
  - back.html.j2
  - style.css.j2

Search order for templates: theme -> base -> assets.

Jinja2 uses custom delimiters so Anki's Mustache ``{{Field}}`` placeholders
remain untouched.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

# Import Jinja2 lazily inside functions to avoid hard dependency at import time.


def _build_fs_env(search_paths: list[Path]) -> Any:
    from jinja2 import ChoiceLoader, Environment, FileSystemLoader  # type: ignore

    loaders = [FileSystemLoader(str(p)) for p in search_paths]
    env = Environment(
        loader=ChoiceLoader(loaders),
        autoescape=False,
        # Use custom delimiters to avoid clashing with Anki/Mustache {{...}} and {{#...}} syntax
        variable_start_string="[[",
        variable_end_string="]]",
        block_start_string="[%",
        block_end_string="%]",
        comment_start_string="[#",
        comment_end_string="#]",
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env


def _try_load_jinja_from_dir(dir_path: Path) -> tuple[str, str, str]:
    base = Path(__file__).parent / "base"
    assets = Path(__file__).parent / "assets"
    env = _build_fs_env([dir_path, base, assets])
    front = env.get_template("front.html.j2").render()
    back = env.get_template("back.html.j2").render()
    css = env.get_template("style.css.j2").render()
    return front, back, css


def _try_load_jinja_from_package(name: str) -> tuple[str, str, str]:
    from jinja2 import ChoiceLoader, Environment, PackageLoader  # type: ignore

    # Chain loaders: theme -> base -> assets
    loaders = [
        PackageLoader("anki_connector", f"templates/themes/{name}"),
        PackageLoader("anki_connector", "templates/base"),
        PackageLoader("anki_connector", "templates/assets"),
    ]
    env = Environment(
        loader=ChoiceLoader(loaders),
        autoescape=False,
        variable_start_string="[[",
        variable_end_string="]]",
        block_start_string="[%",
        block_end_string="%]",
        comment_start_string="[#",
        comment_end_string="#]",
        trim_blocks=True,
        lstrip_blocks=True,
    )
    front = env.get_template("front.html.j2").render()
    back = env.get_template("back.html.j2").render()
    css = env.get_template("style.css.j2").render()
    return front, back, css


def _try_load_base_from_package() -> tuple[str, str, str]:
    from jinja2 import ChoiceLoader, Environment, PackageLoader  # type: ignore

    loaders = [
        PackageLoader("anki_connector", "templates/base"),
        PackageLoader("anki_connector", "templates/assets"),
    ]
    env = Environment(
        loader=ChoiceLoader(loaders),
        autoescape=False,
        variable_start_string="[[",
        variable_end_string="]]",
        block_start_string="[%",
        block_end_string="%]",
        comment_start_string="[#",
        comment_end_string="#]",
        trim_blocks=True,
        lstrip_blocks=True,
    )
    front = env.get_template("front.html.j2").render()
    back = env.get_template("back.html.j2").render()
    css = env.get_template("style.css.j2").render()
    return front, back, css


@lru_cache(maxsize=32)
def _load_card_visuals_cached(template: str | None) -> tuple[str, str, str] | None:
    """Load (front, back, css) for the given template spec.

    If ``template`` is None, returns the packaged default theme 'vapor'.

    Supported locations (Jinja only):
      1) A filesystem directory containing front.html.j2/back.html.j2/style.css.j2
      2) A packaged theme name under anki_connector/templates/themes/<name>
    """
    if not template:
        # Default to packaged 'vapor' theme
        try:
            return _try_load_jinja_from_package("vapor")
        except Exception:
            pkg_dir = Path(__file__).parent / "themes" / "vapor"
            if pkg_dir.exists() and pkg_dir.is_dir():
                return _try_load_jinja_from_dir(pkg_dir)
            raise

    path = Path(template)

    # 1) Filesystem directory with Jinja files
    if path.exists() and path.is_dir():
        return _try_load_jinja_from_dir(path)

    # 2) Packaged Jinja theme by name
    try:
        return _try_load_jinja_from_package(template)
    except Exception:
        # Fallback to reading from package directory directly
        pkg_dir = Path(__file__).parent / "themes" / template
        if pkg_dir.exists() and pkg_dir.is_dir():
            return _try_load_jinja_from_dir(pkg_dir)
        raise


def load_card_visuals(template: str | None) -> tuple[str, str, str] | None:
    """Cached loader wrapper.

    Normalizes filesystem paths to absolute strings so the cache key is stable.
    """
    if template:
        p = Path(template)
        if p.exists():
            return _load_card_visuals_cached(str(p.resolve()))
    return _load_card_visuals_cached(template)
