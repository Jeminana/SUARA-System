"""Minimal build-time compatibility for CREPE 0.0.12 on Python 3.12+.

CREPE's setup.py uses only imp.load_source, removed from the standard library in
Python 3.12. This shim is placed on PYTHONPATH only while building the upstream
source distribution; it is not installed as an application module.
"""

from importlib.util import module_from_spec, spec_from_file_location


def load_source(name: str, pathname: str, file=None):
    spec = spec_from_file_location(name, pathname)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name!r} from {pathname!r}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
