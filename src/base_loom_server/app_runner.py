import argparse
import importlib.resources
import json
import logging
import pathlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import ClassVar

import uvicorn
from fastapi import APIRouter, FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response

from .base_loom_server import DEFAULT_DATABASE_PATH, BaseLoomServer
from .constants import LOG_NAME
from .enums import DirectionControlEnum

PKG_FILES = importlib.resources.files("base_loom_server")


class AppRunner:
    """Run the loom server application.

    This contains the web server's endpoints,
    the lifespan context manager,
    and a method to create the argument parser.

    In order to use this you *must* create an instance on import
    (i.e. at the module level), typically in `main.py'.
    If you defer creation, the web server will not see the endpoints!
    See ``main.py`` for an example.

    Args:
        app: The application, generated with ``app = FastAPI()``
        server_class:  The loom server class (not an instance,
            but the class itself).
        favicon: A 32x32 or so favicon. No favicon if empty.
        app_package_name: The name of the python package for your loom server,
            e.g. "toika_loom_server". This is used by the `run` method,
            as an argument to `uvicorn.run`.
    """

    DirectionControlMap: ClassVar = {item.name.lower(): item for item in DirectionControlEnum}

    def __init__(
        self,
        app: FastAPI,
        server_class: type[BaseLoomServer],
        favicon: bytes,
        app_package_name: str,
    ) -> None:
        self.log = logging.getLogger(LOG_NAME)

        self.server_class = server_class
        self.favicon = favicon
        self.app_package_name = app_package_name
        self.loom_server: BaseLoomServer | None = None

        # Assign enpoints to the app.

        # The only reason we need a router is to set the lifespan
        # but once we have it we may as well use it to add endpoints as well
        router = APIRouter(lifespan=self.lifespan)

        # Normally one would use decorators to specify endpoints
        # but that doesn't work well with methods.
        router.add_api_route("/", self.get, methods=["GET"])

        if self.favicon:
            router.add_api_route(
                "/favicon.ico",
                self.get_favicon,
                methods=["GET"],
                include_in_schema=False,
            )

        router.add_websocket_route("/ws", self.websocket_endpoint)

        app.include_router(router)

    def create_argument_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser.

        Subclasses may override this to add more options.
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("num_shafts", type=int, help="The number of shafts the loom has.")
        parser.add_argument(
            "serial_port",
            help="Serial port connected to the loom, "
            "typically of the form /dev/tty... "
            "Specify 'mock' to run a mock (simulated) loom",
        )
        parser.add_argument(
            "-r",
            "--reset-db",
            action="store_true",
            help="Reset the pattern database, erasing all patterns.",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="Log extra diagnostic information.",
        )
        parser.add_argument(
            "--db-path",
            default=DEFAULT_DATABASE_PATH,
            type=pathlib.Path,
            help="Path for the pattern database. "
            "Specify this if you plan to run more than one loom server on this computer.",
        )
        parser.add_argument(
            "--host",
            default="0.0.0.0",
            help="Server host. 0.0.0.0 is standard. Don't change this unless you know what you are doing.",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8000,
            help="Server port. Specify this if you wish to run more than one web server on this computer.",
        )
        parser.add_argument(
            "--log-level",
            choices=("critical", "error", "warning", "info", "debug", "trace"),
            default="info",
            help="Logging level.",
        )
        return parser

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, FastAPI]:
        """Lifespan context manager for fastAPI.

        Load the translation dict and create the sole instance of
        the loom server class. That loom server instance persists
        for the entire time the web server is running. This is because
        the loom server speaks to one loom and serves at most one user.
        """
        parser = self.create_argument_parser()
        args = parser.parse_args()
        for uvicorn_arg in ("host", "port", "log_level"):
            if getattr(args, uvicorn_arg, None) is not None:
                delattr(args, uvicorn_arg)

        async with self.server_class(**vars(args)) as self.loom_server:
            # Store the server as state for unit tests
            app.state.loom_server = self.loom_server
            yield

    async def get(self) -> HTMLResponse:
        """Endpoint to get the main page."""
        assert self.loom_server is not None  # make mypy happy
        display_html = PKG_FILES.joinpath("display.html").read_text(encoding="utf_8")

        display_css = PKG_FILES.joinpath("display.css").read_text(encoding="utf_8")

        display_js = PKG_FILES.joinpath("display.js").read_text(encoding="utf_8")
        js_translation_str = json.dumps(self.loom_server.translation_dict, indent=4)
        display_js = display_js.replace("{ translation_dict }", js_translation_str)

        display_html = display_html.format(
            display_css=display_css,
            display_js=display_js,
            help_url=self.loom_server.help_url,
            **self.loom_server.translation_dict,
        )

        return HTMLResponse(display_html)

    async def get_favicon(self) -> Response:
        """Endpoint to get the favicon."""
        return Response(content=self.favicon, media_type="image/x-icon")

    async def websocket_endpoint(self, websocket: WebSocket) -> None:
        """Websocket endpoint."""
        assert self.loom_server is not None
        await self.loom_server.run_client(websocket=websocket)

    def run(self) -> None:
        """Parse command-line arguments and run the web server."""
        # Handle the help argument and also catch parsing errors right away
        arg_parser = self.create_argument_parser()
        args = arg_parser.parse_args()

        uvicorn.run(
            self.app_package_name,
            host=args.host,
            port=args.port,
            log_level=args.log_level,
            reload=False,
        )
