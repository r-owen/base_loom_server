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
from .enums import DirectionControlEnum

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

    Args:
        app: The application, generated with ``app = FastAPI()``
        server_class:  The loom server class (not an instance,
            but the class itself).
        favicon: A 32x32 or so favicon. No favicon if empty.
        app_package_name: The name of the python package for your loom server,
            e.g. "toika_loom_server". This is used by the `run` method,
            as an argument to `uvicorn.run`.
    """

    DirectionControlMap = {item.name.lower(): item for item in DirectionControlEnum}

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
        self.html_lang_value: str = "en"
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
            "num_shafts", type=int, help="The number of shafts the loom has."
        )
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
        self.html_lang_value, self.translation_dict = self.get_translation_info()

        parser = self.create_argument_parser()
        args = parser.parse_args()
        for uvicorn_arg in ("host", "port", "log_level"):
            if getattr(args, uvicorn_arg, None) is not None:
                delattr(args, uvicorn_arg)

        async with self.server_class(
            **vars(args),
            translation_dict=self.translation_dict,
        ) as self.loom_server:
            # Store the server as state for unit tests
            app.state.loom_server = self.loom_server
            yield

    def get_translation_info(self) -> tuple[str, dict[str, str]]:
        """Get the HTML lang value and translation dict for the current
        locale.

        The HTML lang value is the value of the HTML lang tag:
        f"<html lang="{html_lang_value}>"

        Note: HTML lang value is "en" unless a translation file is present.
        If a translation file is present, the value is the short language code
        returned by the locale module. This is because more detail is not
        needed, and because it is is difficult to translate locale names
        return by the locale module to valid HTML lang values.
        """
        # Read a dict of key: None and turn into a dict of key: key
        default_dict = json.loads(
            LOCALE_FILES.joinpath("default.json").read_text(encoding="utf_8")
        )
        translation_dict = {key: key for key in default_dict}

        html_lang_value = "en"
        language_code = locale.getlocale(locale.LC_CTYPE)[0] or ""
        self.log.info(f"Locale: {language_code!r}")
        language_codes = []
        if language_code and language_code != "C":
            language_codes.append(language_code)
            short_language_code = language_code.split("_")[0]
            if short_language_code != language_code:
                language_codes.append(short_language_code)
        for lc in language_codes:
            translation_name = lc + ".json"
            translation_file = LOCALE_FILES.joinpath(translation_name)
            if translation_file.is_file():
                html_lang_value = short_language_code
                self.log.info(f"Loading translation file {translation_name!r}")
                locale_dict = json.loads(translation_file.read_text(encoding="utf_8"))
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
        return html_lang_value, translation_dict

    async def get(self) -> HTMLResponse:
        """Endpoint to get the main page."""
        assert self.loom_server is not None  # make mypy happy
        display_html = PKG_FILES.joinpath("display.html").read_text(encoding="utf_8")

        display_css = PKG_FILES.joinpath("display.css").read_text(encoding="utf_8")

        display_js = PKG_FILES.joinpath("display.js").read_text(encoding="utf_8")
        js_translation_str = json.dumps(self.translation_dict, indent=4)
        display_js = display_js.replace("{ translation_dict }", js_translation_str)

        display_html = display_html.format(
            lang_str=self.html_lang_value,
            display_css=display_css,
            display_js=display_js,
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
