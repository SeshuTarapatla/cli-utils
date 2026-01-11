from json import dumps, loads
from os import environ
from pathlib import Path
from typing import Literal, NotRequired, TypedDict
from uuid import uuid4

from click import BadArgumentUsage
from rich.console import Console
from rich.pretty import Pretty
from rich.syntax import Syntax
from rich.table import Table
from typer import Argument, Option, Typer
from yaml import safe_dump

console = Console()


class WtProfile(TypedDict):
    name: str
    guid: str
    commandline: str
    hidden: Literal[False]
    icon: NotRequired[str]


class WtProfilesList(TypedDict):
    list: list[WtProfile]


class WtSettings(TypedDict):
    profiles: WtProfilesList


class WtHandler:
    def __init__(self) -> None:
        self.settings = self.get_settings()

    def __enter__(self) -> "WtHandler":
        return self

    def __exit__(self, *args, **kwargs): ...

    def get_settings(self) -> Path:
        if not (localappdata := environ.get("LOCALAPPDATA")):
            raise Exception("Failed to resolve %LOCALAPPDATA%")
        if not (
            settings := list(
                Path(f"{localappdata}/Packages").glob(
                    "Microsoft.WindowsTerminal_*/LocalState/settings.json"
                )
            )
        ):
            raise Exception("Failed to resolve Windows Terminal settings.json")
        return settings[0]

    def add_profile(self, profile: WtProfile) -> bool:
        if _profile := self.query(profile["commandline"], "commandline"):
            self.remove_profile(_profile["guid"], "guid")
        data = self.data.copy()
        data["profiles"]["list"] = self.profiles + [profile]
        self.settings.write_text(dumps(data, indent=4))
        return True

    def remove_profile(
        self, value: str, field: Literal["guid", "name", "commandline"]
    ) -> WtProfile | None:
        index = None
        for i, profile in enumerate(self.profiles):
            if profile.get(field) == value:
                index = i
                break
        if not index:
            return None
        data = self.data.copy()
        profile = data["profiles"]["list"].pop(index)
        self.settings.write_text(dumps(data, indent=4))
        return profile

    def query(
        self, value: str, field: Literal["guid", "name", "commandline"]
    ) -> WtProfile | None:
        for profile in self.profiles:
            if profile.get(field) == value:
                return profile

    @property
    def data(self) -> WtSettings:
        return loads(self.settings.read_text())

    @property
    def profiles(self) -> list[WtProfile]:
        return self.data["profiles"]["list"]


app = Typer(
    name="wt-profile",
    help="A command line utility to manage windows terminal profiles.",
    no_args_is_help=True,
)


@app.callback()
def callback(): ...


@app.command(
    name="add", help="Add a new windows terminal profile.", no_args_is_help=True
)
def add(
    exe: Path = Option(help="Command line executable for the profile.", exists=True),
    name: str = Argument(help="Name of the profile to add."),
    icon: Path | None = Option(
        default=None, help="Optional icon for the terminal.", exists=True
    ),
):
    entry: WtProfile = {
        "name": name,
        "commandline": str(exe.resolve()),
        "guid": f"{{{uuid4()}}}",
        "hidden": False,
    }
    if icon:
        entry["icon"] = str(icon)
    console.print(Pretty(entry, expand_all=True))
    with WtHandler() as wt:
        wt.add_profile(entry)
    console.print("[bright_green]INFO  [/] - Profile added successfully")


@app.command(
    name="list",
    help="List all current windows terminal profiles.",
)
def list_(format: Literal["json", "yaml", "table"] = Option("yaml", "-o", "--output")):
    with WtHandler() as wt:
        match format:
            case "json":
                console.print(Pretty(wt.profiles, expand_all=True))
            case "yaml":
                yaml_formatted_data = safe_dump(
                    {"profiles": wt.profiles}, sort_keys=False, indent=4
                )
                console.print(
                    Syntax(
                        yaml_formatted_data,
                        "yaml",
                        theme="ansi_dark",
                        line_numbers=False,
                    )
                )
            case "table":
                table = Table(*(WtProfile.__annotations__.keys()))
                table.add_row()
                [
                    table.add_row(
                        *{
                            key: value
                            if isinstance((value := profile.get(key)), str)
                            else dumps(value)
                            for key in WtProfile.__annotations__.keys()
                        }.values()
                    )
                    for profile in wt.profiles
                ]
                console.print(table)


@app.command(
    name="remove",
    help="Remove a given windows terminal profile.",
    epilog="Use either GUID or Name, not both.",
    no_args_is_help=True,
)
def remove(
    guid: str | None = Option(default=None, help="GUID of the profile to delete."),
    name: str | None = Option(default=None, help="Name of the profile to delete."),
):
    if guid and name:
        raise BadArgumentUsage("Have passed both GUID and Name. Use only one.")
    resp = False
    with WtHandler() as wt:
        if guid:
            resp = wt.remove_profile(guid, "guid")
        elif name:
            resp = wt.remove_profile(name, "name")
    if resp:
        console.print(Pretty(resp, expand_all=True))
        console.print("[bright_blue]INFO  [/] - Profile removed successfully.")
    else:
        console.print(
            f"[bright_red]ERROR [/] - No profile to remove with: [bold cyan]{'guid' if guid else 'name'} = {guid or name}[/]"
        )
