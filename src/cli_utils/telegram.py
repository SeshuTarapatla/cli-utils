import asyncio
from os import environ
from shutil import which
from subprocess import DEVNULL, run
from sys import platform
from typing import Literal, NoReturn, cast, overload

from rich.console import Console
from telethon import TelegramClient
from telethon.sessions import StringSession
from typer import Argument, Option, Typer

SETX = which("setx") or ""
console = Console()


def error(msg, code: int = 1) -> NoReturn:
    console.print(f"[bold red]ERROR[/] : {msg}")
    exit(code)


def setx(key: str, value: str | int):
    value = str(value)
    resp = run([SETX, key, value], stdout=DEVNULL)
    if resp.returncode != 0:
        error(f"Failed to perform 'setx' action with args '{key}={value}'.", 3)


class Telegram:
    PHONE_NUMBER: str = "TELEGRAM_NUMBER"
    API_ID: str = "TELEGRAM_API_ID"
    API_HASH: str = "TELEGRAM_API_HASH"
    SESSION: str = "TELEGRAM_SESSION"

    def __init__(self) -> None:
        self.__fetch_session__()

    def __fetch_session__(self):
        self.phone_number: str = environ.get(Telegram.PHONE_NUMBER, "")
        self.api_id: int = int(environ.get(Telegram.API_ID) or 0)
        self.api_hash: str = environ.get(Telegram.API_HASH, "")
        self.session: StringSession = StringSession(environ.get(Telegram.SESSION, ""))
        self.client_: TelegramClient = cast(TelegramClient, None)

        if not self.api_id:
            api_id = console.input("Enter a valid Telegram API-ID: ")
            self.api_id = Telegram.validate(api_id, mode="api_id")
            setx(Telegram.API_ID, self.api_id)

        if not self.api_hash:
            api_hash = console.input("Enter a valid Telegram API Hash: ")
            self.api_hash = Telegram.validate(api_hash, mode="api_hash")
            setx(Telegram.API_HASH, self.api_hash)

    def login(self, phone_number: str):
        if self.verify():
            if phone_number != self.phone_number:
                error(
                    f"Active session found for '{self.phone_number}'. Please logout first (or) use [yellow]-f/--force flag."
                )
            else:
                console.print("Active session already exists.")
        else:
            self.phone_number = self.validate(phone_number, mode="number")
            console.print(f"Starting login procedure for '{self.phone_number}'.")
            setx(Telegram.PHONE_NUMBER, self.phone_number)

            self.client.start(self.phone_number)

            setx(Telegram.SESSION, self.client.session.save())  # type: ignore
            console.print("Logged in successfully and session saved.")

    async def logout(self, reset: bool = False):
        if self.verify():
            await self.client.connect()
            await self.client.log_out()
            setx(Telegram.SESSION, "")
            console.print("Logged out successfully.")
        else:
            error("No active session found", 7)

        if reset:
            setx(Telegram.API_ID, "")
            setx(Telegram.API_HASH, "")

    def verify(self) -> bool:
        if self.session.save():
            return bool(self.client.start())
        return False

    @property
    def client(self) -> TelegramClient:
        self.client_ = self.client_ or TelegramClient(
            self.session, self.api_id, self.api_hash
        )
        return self.client_

    @overload
    @staticmethod
    def validate(value: str, *, mode: Literal["number", "api_hash"]) -> str: ...

    @overload
    @staticmethod
    def validate(value: str, *, mode: Literal["api_id"]) -> int: ...

    @staticmethod
    def validate(
        value: str, *, mode: Literal["number", "api_id", "api_hash"]
    ) -> str | int:
        match mode:
            case "number":
                value = value if value.startswith("+91") else f"+91{value}"
                if len(value) == 13 and value[1:].isdigit():
                    return value
                error(f"'{value}' is not a valid phone number.", 4)
            case "api_id":
                if value.isdigit() and len(value) == 8:
                    return int(value)
                error(f"'{value}' is not a valid API ID.", 5)
            case "api_hash":
                try:
                    if len(bytes.fromhex(value)) == 16:
                        return value
                    else:
                        raise ValueError
                except Exception:
                    error(f"'{value}' is not a valid API Hash.", 6)


def system_check():
    if platform != "win32":
        error("This tool only supports Windows (win32) operating systems.", 1)
    if not SETX:
        error("Required 'setx' utility not found in system PATH.", 2)


system_check()
telegram = Typer(
    name="telegram",
    help="Telegram CLI to manage environment logged in session.",
    no_args_is_help=True,
    add_completion=False,
)


@telegram.command(name="login", help="Login to telegram.")
def login(
    phone_number: str = Argument(None, help="Phone number to login with."),
    force: bool = Option(
        False, "-f", "--force", help="Force login, clearing any existing session."
    ),
):
    """Login to telegram."""
    phone_number = phone_number or environ.get(Telegram.PHONE_NUMBER, "")
    if not phone_number:
        phone_number = console.input("Please enter a valid telegram number (+91): ")
        phone_number = Telegram.validate(phone_number, mode="number")
    if force:
        logout()
    Telegram().login(phone_number)


@telegram.command(name="logout", help="Logout from telegram.")
def logout(reset: bool = Option(False, "-r", "--reset", help="Reset API ID and hash.")):
    """Logout from telegram."""
    asyncio.run(Telegram().logout())


@telegram.command(name="verify", help="Verify current session.")
def verify():
    """Verify current session."""
    tl = Telegram()
    if tl.verify():
        console.print(f"Active session found for '{tl.phone_number}.'")
    else:
        error("No active session found.", 7)


if __name__ == "__main__":
    telegram()
