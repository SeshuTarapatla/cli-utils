import ctypes
import winreg
from pathlib import Path
from typing import Annotated

from rich import print
from typer import Argument, BadParameter, run


class WinUserPathEnvVarHandler:
    @staticmethod
    def check_if_exists_in_full_path(path: Path) -> bool:
        path_env_var, _ = WinUserPathEnvVarHandler.read_user_path_reg()
        current_paths = (
            Path(entry) for entry in path_env_var.split(";") if entry.strip()
        )
        return path in current_paths

    @staticmethod
    def validate_path(path: Path) -> Path:
        try:
            resolved = path.resolve()
            resolved.mkdir(exist_ok=True, parents=True)
            return resolved
        except OSError as e:
            raise BadParameter(f"{e}")

    @staticmethod
    def read_user_path_reg() -> tuple[str, int]:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ
        ) as key:
            return winreg.QueryValueEx(key, "Path")

    @staticmethod
    def add_path_to_user_reg(path: Path):
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE
        ) as key:
            current_path, reg_type = WinUserPathEnvVarHandler.read_user_path_reg()
            updated_path = current_path.rstrip(";") + ";" + str(path)
            winreg.SetValueEx(key, "Path", 0, reg_type, updated_path)
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "Environment")


def add_to_path(
    path: Annotated[
        Path,
        Argument(
            help="Path to add to the user's PATH environment variable.",
            callback=WinUserPathEnvVarHandler.validate_path,
        ),
    ],
):
    if not WinUserPathEnvVarHandler.check_if_exists_in_full_path(path):
        WinUserPathEnvVarHandler.add_path_to_user_reg(path)
        print(
            f"[blue]INFO[/] : Added [bold magenta]WindowsPath[/]([green]'{path}'[/]) successfully to the PATH."
        )
    else:
        print("[blue]INFO[/] : Path already exists.")


def _run():
    run(add_to_path)
