"""
sources/ - Data source plugin registry.

Auto-discovers all source classes from sources/apis/, sources/scrapers/, sources/feeds/, sources/ats/.
Each source class must inherit from BaseSource and set enabled=True/False.

Usage:
    from sources import get_enabled_sources, get_source, get_all_sources
"""

import importlib
import logging
import pkgutil
from pathlib import Path

from aggregator import config
from sources.base import BaseSource

log = logging.getLogger(__name__)

_registry: dict[str, BaseSource] = {}


def _discover_sources() -> None:
    """Import all subpackages and collect BaseSource subclasses."""
    base_dir = Path(__file__).parent
    for pkg in ('sources.apis', 'sources.scrapers', 'sources.feeds', 'sources.ats'):
        pkg_path = base_dir / pkg.split('.')[1]
        if not pkg_path.exists():
            continue
        for _, mod_name, _ in pkgutil.iter_modules([str(pkg_path)]):
            full = f"{pkg}.{mod_name}"
            try:
                mod = importlib.import_module(full)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseSource)
                        and attr is not BaseSource
                        and attr.name
                    ):
                        instance = attr()
                        _registry[instance.name] = instance
            except Exception as exc:
                log.warning(f"Could not load source module {full}: {exc}")


def _ensure_loaded() -> None:
    if not _registry:
        _discover_sources()


def get_all_sources() -> list[BaseSource]:
    """Return all registered source instances (enabled or not)."""
    _ensure_loaded()
    return list(_registry.values())


def get_enabled_sources() -> list[BaseSource]:
    """Return instances of all enabled sources (respecting config)."""
    _ensure_loaded()
    result = []
    for src in _registry.values():
        cfg = config.get_source_config(src.name)
        if cfg.get('enabled', src.enabled):
            if 'rate_limit' in cfg:
                src.rate_limit = cfg['rate_limit']
            result.append(src)
    return result


def get_source(name: str) -> BaseSource:
    """Return a single source instance by name. Raises KeyError if not found."""
    _ensure_loaded()
    if name not in _registry:
        raise KeyError(f"Unknown source: '{name}'. Available: {list(_registry.keys())}")
    return _registry[name]


def register_source(source_class: type) -> type:
    """Decorator to manually register a source class."""
    instance = source_class()
    _registry[instance.name] = instance
    return source_class
