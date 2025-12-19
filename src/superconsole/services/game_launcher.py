from __future__ import annotations

import subprocess
from pathlib import Path
import os
import configparser

from ..paths import EMULATORS_DIR, ROMS_DIR


def _exe(path: Path) -> Path:
    return path


EMULATOR_PATHS = {
    "nes": _exe(EMULATORS_DIR / "Mesen" / "Mesen_2.1.0_Windows" / "Mesen.exe"),
    "snes": _exe(EMULATORS_DIR / "Bsnes" / "bsnes" / "bsnes.exe"),
    "gba": _exe(EMULATORS_DIR / "mGBA" / "mGBA" / "mGBA.exe"),
    "gb": _exe(EMULATORS_DIR / "mGBA" / "mGBA" / "mGBA.exe"),
    "gbc": _exe(EMULATORS_DIR / "mGBA" / "mGBA" / "mGBA.exe"),
    "n64": _exe(EMULATORS_DIR / "Project64" / "Release" / "Project64.exe"),
    "ps1": _exe(EMULATORS_DIR / "DuckStation" / "Duckstation" / "duckstation-qt-x64-ReleaseLTCG.exe"),
    "ps2": _exe(EMULATORS_DIR / "PCSX2" / "pcsx2-qt.exe"),
    "ps3": _exe(EMULATORS_DIR / "RPCS3" / "rpcs3.exe"),
    "gamecube": _exe(EMULATORS_DIR / "Dolphin" / "Dolphin-x64" / "Dolphin.exe"),
    "wii": _exe(EMULATORS_DIR / "Dolphin" / "Dolphin-x64" / "Dolphin.exe"),
    "wiiu": _exe(EMULATORS_DIR / "Cemu" / "Cemu" / "Cemu.exe"),
    "xbox": _exe(EMULATORS_DIR / "Xemu" / "xemu.exe"),
    "xbox360": _exe(EMULATORS_DIR / "Xenia" / "xenia.exe"),
}

FULLSCREEN_ARGS = {
    "nes": ["--fullscreen"],
    "snes": ["--fullscreen"],
    "gba": ["-f"],
    "gb": ["-f"],
    "gbc": ["-f"],
    "n64": ["--fullscreen"],
    "ps1": ["-fullscreen"],
    "ps2": ["--fullscreen"],
    "ps3": ["--fullscreen"],
    "wiiu": ["-f"],
    "xbox": ["-fullscreen"],
    "xbox360": ["--fullscreen"],
}


def _normalize_platform(platform: str) -> str:
    return platform.strip().lower().replace("-", "")


def get_emulator_exe(platform: str) -> Path:
    p = _normalize_platform(platform)
    if p not in EMULATOR_PATHS:
        raise ValueError(f"Unsupported platform: {platform}")
    return EMULATOR_PATHS[p]


def _resolve_launch_target(launch_target: str) -> Path:
    p = Path(launch_target)
    if not p.is_absolute():
        return ROMS_DIR / p
    return p


def is_wsl() -> bool:
    return bool(os.environ.get("WSL_DISTRO_NAME")) or "microsoft" in Path("/proc/version").read_text().lower()


def _to_windows_path(path: Path) -> str:
    try:
        result = subprocess.run(
            ["wslpath", "-w", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return str(path)


def _build_args(platform: str, launch_target: Path) -> list[str]:
    p = _normalize_platform(platform)
    fs_args = FULLSCREEN_ARGS.get(p, [])

    if p in {"gamecube", "wii"}:
        return [str(EMULATOR_PATHS[p]), "-b", "-e", str(launch_target), *fs_args]

    if p == "wiiu":
        return [str(EMULATOR_PATHS[p]), "-g", str(launch_target), *fs_args]

    # Default: exe + rom path
    return [str(EMULATOR_PATHS[p]), str(launch_target), *fs_args]


def launch_game(platform: str, launch_target: str) -> subprocess.Popen:
    p = _normalize_platform(platform)
    if p not in EMULATOR_PATHS:
        raise ValueError(f"Unsupported platform: {platform}")

    exe = EMULATOR_PATHS[p]
    if not exe.exists():
        raise FileNotFoundError(f"Missing emulator for {platform}: {exe}")

    if p in {"gamecube", "wii"}:
        _ensure_dolphin_fullscreen(exe)

    target_path = _resolve_launch_target(launch_target)
    args = _build_args(platform, target_path)

    # If we're in WSL launching Windows emulators, pass Windows paths for ROMs
    # and use cmd.exe start to hand focus to the Windows shell.
    if is_wsl() and exe.suffix.lower() == ".exe":
        exe_win = _to_windows_path(exe)
        args_win = [
            _to_windows_path(Path(a)) if a.startswith("/") else a
            for a in args[1:]
        ]
        cmd = ["cmd.exe", "/c", "start", "", exe_win, *args_win]
        return subprocess.Popen(cmd)
    return subprocess.Popen(args, cwd=str(exe.parent))


def _ensure_dolphin_fullscreen(exe: Path) -> None:
    # Portable Dolphin keeps config under the exe parent.
    config_dir = exe.parent / "User" / "Config"
    dolphin_ini = config_dir / "Dolphin.ini"
    gfx_ini = config_dir / "GFX.ini"
    if not config_dir.exists():
        return

    _set_ini_value(dolphin_ini, "Interface", "StartFullscreen", "True")
    _set_ini_value(dolphin_ini, "Interface", "Fullscreen", "True")
    _set_ini_value(dolphin_ini, "Display", "Fullscreen", "True")
    _set_ini_value(gfx_ini, "Settings", "Fullscreen", "True")


def _set_ini_value(path: Path, section: str, key: str, value: str) -> None:
    config = configparser.ConfigParser()
    config.optionxform = str
    if path.exists():
        config.read(path, encoding="utf-8")
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        config.write(f)
