"""Shared test fixtures.

All three services have a file called main.py, so they cannot be imported
with a normal `import main`. `load_module` imports a file by path under a
unique name instead.
"""

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent

Handler = Callable[[httpx.Request], httpx.Response]


def load_module(name: str, relative_path: str) -> ModuleType:
    """Import a Python file by path as a module called `name`."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def mock_client(handler: Handler) -> httpx.AsyncClient:
    """An httpx client whose requests are answered by `handler`, not the network."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def gateway() -> ModuleType:
    return load_module("gateway_main", "services/gateway/main.py")


@pytest.fixture
def orders() -> ModuleType:
    return load_module("orders_main", "services/orders/main.py")


@pytest.fixture
def payments() -> ModuleType:
    return load_module("payments_main", "services/payments/main.py")


@pytest.fixture
def loadgen() -> ModuleType:
    return load_module("loadgen_main", "loadgen/loadgen.py")


@pytest.fixture
def sink() -> ModuleType:
    return load_module("alert_sink", "alert-sink/sink.py")
