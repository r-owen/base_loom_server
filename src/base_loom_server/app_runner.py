import argparse
import importlib.resources
import json
import locale
import logging
import pathlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Type

import uvicorn
from fastapi import APIRouter, FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response

from .base_loom_server import DEFAULT_DATABASE_PATH, BaseLoomServer
from .constants import LOG_NAME

PKG_FILES = importlib.resources.files("base_loom_server")
LOCALE_FILES = PKG_FILES.joinpath("locales")


class AppRunner:
    """Run the loom server application.

    This contains the web server's endpoints,
    the lifespan context manager,
    and a method to create the argument parser.

    In order to use this you *must* create an instance on import
    (i.e. at the module level), typically in `main.py'.
    If you defer creation, the web server will not see the endpoints!
    See ``main.py`` for an example.

    Parameters
    ----------
    app : FastAPI
        The application, generated with ``app = FastAPI()``
    server_class : Type[BaseLoomServer]
        Your loom server class (NOT an instance, but the class itself).
    favicon : bytes
        A 32x32 or so favicon. None if empty.
    app_package_name : the name of the python package for your loom server,
        e.g. "toika_loom_server". This is used by the `run` method,
        as an argument to `uvicorn.run`.
    """

    def __init__(
        self,
        app: FastAPI,
        server_class: Type[BaseLoomServer],
        favicon: bytes,
        app_package_name: str,
    ) -> None:
        """Construct endpoints for FastAPI"""
        self.log = logging.getLogger(LOG_NAME)

        self.server_class = server_class
        self.favicon = favicon
        self.app_package_name = app_package_name
        self.loom_server: BaseLoomServer | None = None
        self.translation_dict: dict[str, str] = {}

        # There must be a better way to do this,
        # but everything I have tried fails,
        # including using an APIRouter with add_api_route

        @asynccontextmanager
        async def lifespan_wrapper(*args):
            async with self.lifespan(app):
                yield

        # The only rason we need a router is to set the lifespan
        # but once we have it we may as well use it to add endpoints as well
        router = APIRouter(lifespan=lifespan_wrapper)

        @router.get("/")
        async def get_wrapper():
            return await self.get()

        if self.favicon:

            @router.get("/favicon.ico", include_in_schema=False)
            async def get_favicon():
                return await self.get_favicon()

        @router.websocket("/ws")
        async def websocket_endpoint_wrapper(websocket: WebSocket):
            return await self.websocket_endpoint(websocket)

        app.include_router(router)

    def create_argument_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser.

        Subclasses may override this to add more options.
        """
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "serial_port",
            help="Serial port connected to the loom, "
            "typically of the form /dev/tty... "
            "Specify 'mock' to run a mock (simulated) loom",
        )
        parser.add_argument(
            "-n",
            "--name",
            help="loom name",
        )
        parser.add_argument(
            "-r",
            "--reset-db",
            action="store_true",
            help="reset pattern database?",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="print diagnostic information to stdout",
        )
        parser.add_argument(
            "--db-path",
            default=DEFAULT_DATABASE_PATH,
            type=pathlib.Path,
            help="Path for pattern database. "
            "Settable so unit tests can avoid changing the real database.",
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
        self.translation_dict = self.get_translation_dict()

        parser = self.create_argument_parser()
        args = parser.parse_args()

        async with self.server_class(
            **vars(args), translation_dict=self.translation_dict
        ) as self.loom_server:
            # Store the server as state for unit tests
            app.state.loom_server = self.loom_server
            yield

    def get_translation_dict(self) -> dict[str, str]:
        """Get the translation dict for the current locale"""
        # Read a dict of key: None and turn into a dict of key: key
        default_dict = json.loads(LOCALE_FILES.joinpath("default.json").read_text())
        translation_dict = {key: key for key in default_dict}

        language_code = locale.getlocale(locale.LC_CTYPE)[0]
        self.log.info(f"Locale: {language_code!r}")
        if language_code is not None:
            short_language_code = language_code.split("_")[0]
            for lc in (short_language_code, language_code):
                translation_name = lc + ".json"
                translation_file = LOCALE_FILES.joinpath(translation_name)
                if translation_file.is_file():
                    self.log.info(f"Loading translation file {translation_name!r}")
                    locale_dict = json.loads(translation_file.read_text())
                    purged_locale_dict = {
                        key: value
                        for key, value in locale_dict.items()
                        if value is not None
                    }
                    if purged_locale_dict != locale_dict:
                        self.log.warning(
                            f"Some entries in translation file {translation_name!r} "
                            "have null entries"
                        )
                    translation_dict.update(purged_locale_dict)
        return translation_dict

    async def get(self) -> HTMLResponse:
        """Endpoint to get the main page."""
        assert self.loom_server is not None  # make mypy happy
        display_html_template = PKG_FILES.joinpath("display.html_template").read_text()

        display_css = PKG_FILES.joinpath("display.css").read_text()

        display_js = PKG_FILES.joinpath("display.js").read_text()
        js_translation_str = json.dumps(self.translation_dict, indent=4)
        js_enable_swd_str = (
            "true" if self.loom_server.enable_software_weave_direction else "false"
        )
        display_js = display_js.replace(
            "{ translation_dict }", js_translation_str
        ).replace("{ enable_software_weave_direction }", js_enable_swd_str)

        assert self.loom_server is not None
        is_mock = self.loom_server.mock_loom is not None
        display_debug_controls = "block" if is_mock else "none"

        display_html = display_html_template.format(
            display_css=display_css,
            display_js=display_js,
            display_debug_controls=display_debug_controls,
            **self.translation_dict,
        )

        return HTMLResponse(display_html)

    async def get_favicon(self) -> Response:
        """Endpoint to get the favicon"""
        return Response(content=self.favicon, media_type="image/x-icon")

    async def websocket_endpoint(self, websocket: WebSocket) -> None:
        """Websocket endpoint."""
        assert self.loom_server is not None
        await self.loom_server.run_client(websocket=websocket)

    def run(self, host="0.0.0.0", port=8000, log_level="info", reload=True) -> None:
        """Parse command-line arguments and run the web server."""
        # Handle the help argument and also catch parsing errors right away
        arg_parser = self.create_argument_parser()
        arg_parser.parse_args()

        uvicorn.run(
            self.app_package_name,
            host=host,
            port=port,
            log_level=log_level,
            reload=reload,
        )
