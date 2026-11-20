"""Test bootstrapping.

custom_components/trols/__init__.py imports Home Assistant, which isn't
installed in this environment, so a normal `import custom_components.trols`
(which runs that __init__.py first) fails even though api.py/const.py have
no Home Assistant dependency of their own. To let tests exercise the
scraper in isolation, load const.py and api.py directly from their files
as `custom_components.trols.const` / `.api`, without ever importing the
real package __init__.
"""
import importlib.util
import pathlib
import sys
import types

_ROOT = pathlib.Path(__file__).parent
_PKG_DIR = _ROOT / "custom_components" / "trols"


def _stub_package(name: str, path: pathlib.Path) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


def _load_submodule(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _PKG_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(_ROOT))
_stub_package("custom_components", _ROOT / "custom_components")
_stub_package("custom_components.trols", _PKG_DIR)
_load_submodule("custom_components.trols.const", "const.py")
_load_submodule("custom_components.trols.api", "api.py")
