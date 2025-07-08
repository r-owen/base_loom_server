import importlib.resources

from fastapi import FastAPI

from .app_runner import AppRunner
from .example_loom_server import ExampleLoomServer

PKG_NAME = "base_loom_server"
PKG_FILES = importlib.resources.files(PKG_NAME)

app = FastAPI()

app_runner = AppRunner(
    app=app,
    server_class=ExampleLoomServer,
    favicon=PKG_FILES.joinpath("favicon-32x32.png").read_bytes(),
    app_package_name=f"{PKG_NAME}.main:app",
)


def run_example_loom() -> None:
    """Run the example loom."""
    app_runner.run()
