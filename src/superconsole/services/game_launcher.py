from __future__ import annotations

import subprocess
from pathlib import Path
import os
import configparser
import logging

from ..paths import EMULATORS_DIR, ROMS_DIR


def _exe(path: Path) -> Path:
    return path


EMULATOR_PATHS = {
    "nes": _exe(EMULATORS_DIR / "Mesen" / "Mesen_2.1.0_Windows" / "Mesen.exe"),
    "snes": _exe(EMULATORS_DIR / "Bsnes" / "bsnes" / "bsnes.exe"),
    "gba": _exe(EMULATORS_DIR / "mGBA" / "mGBA" / "mGBA.exe"),
    "gb": _exe(EMULATORS_DIR / "mGBA" / "mGBA" / "mGBA.exe"),
    "gbc": _exe(EMULATORS_DIR / "mGBA" / "mGBA" / "mGBA.exe"),
    "n64": _exe(EMULATORS_DIR / "Mupen64" / "mupen64plus-ui-console.exe"),
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
    "n64": [],
    "ps1": ["-fullscreen"],
    "ps2": [],
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
        p = ROMS_DIR / p
    try:
        return p.resolve(strict=False)
    except Exception:
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


def _to_windows_path_cmd(path: Path) -> str:
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "wslpath", "-w", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return _to_windows_path(path)


def _build_args(platform: str, launch_target: Path) -> list[str]:
    p = _normalize_platform(platform)
    fs_args = FULLSCREEN_ARGS.get(p, [])

    if p in {"gamecube", "wii"}:
        return [str(EMULATOR_PATHS[p]), "-b", "-e", str(launch_target), *fs_args]

    if p == "n64":
        base_dir = EMULATORS_DIR / "Mupen64"
        return [
            str(EMULATOR_PATHS[p]),
            "--corelib", str(base_dir / "mupen64plus.dll"),
            "--configdir", str(base_dir),
            "--datadir", str(base_dir),
            "--plugindir", str(base_dir),
            "--fullscreen",
            str(launch_target),
        ]

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
    if p == "ps2":
        _ensure_pcsx2_fullscreen(exe)
    if p == "n64":
        _ensure_project64_fullscreen(exe)

    target_path = _resolve_launch_target(launch_target)
    args = _build_args(platform, target_path)

    # If we're in WSL launching Windows emulators, pass Windows paths for ROMs
    # and use cmd.exe start to hand focus to the Windows shell.
    if is_wsl() and exe.suffix.lower() == ".exe":
        exe_win = _to_windows_path_cmd(exe)
        exe_dir_win = _to_windows_path_cmd(exe.parent)
        args_win = [
            _to_windows_path_cmd(Path(a)) if a.startswith("/") else a
            for a in args[1:]
        ]
        cmd = ["cmd.exe", "/c", "start", "", "/D", exe_dir_win, exe_win, *args_win]
        wsl_cwd = EMULATORS_DIR.resolve()
        if not wsl_cwd.exists():
            wsl_cwd = Path("/mnt/c")
        logging.getLogger(__name__).info("Launch (WSL): %s", cmd)
        return subprocess.Popen(cmd, cwd=str(wsl_cwd))
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


def _ensure_project64_fullscreen(exe: Path) -> None:
    config_dir = exe.parent / "Config"
    cfg = config_dir / "Project64.cfg"
    if not config_dir.exists():
        return
    _sanitize_project64_cfg(cfg)
    _set_cfg_value(cfg, "Settings", "Start Full Screen", "1")
    _set_cfg_value(cfg, "Settings", "Start Fullscreen", "1")
    _set_cfg_value(cfg, "Settings", "Fullscreen", "1")
    _set_cfg_value(cfg, "Settings", "Full Screen", "1")
    _set_cfg_value(cfg, "Main Window", "Full Screen", "1")


def _ensure_pcsx2_fullscreen(exe: Path) -> None:
    paths = []
    portable_ini = exe.parent / "portable.ini"
    if portable_ini.exists():
        paths.append(exe.parent / "inis" / "PCSX2.ini")
    else:
        paths.append(exe.parent / "inis" / "PCSX2.ini")

    user_cfg = _default_pcsx2_ini_path()
    if user_cfg:
        paths.append(user_cfg)

    for cfg in paths:
        if cfg and cfg.exists():
            _set_cfg_value(cfg, "UI", "StartFullscreen", "true")
            _set_cfg_value(cfg, "UI", "Fullscreen", "true")
            _set_cfg_value(cfg, "GS", "Fullscreen", "true")
            _set_cfg_value(cfg, "GS", "StartFullscreen", "true")
            return


def _default_pcsx2_ini_path() -> Path | None:
    if not is_wsl():
        profile = os.environ.get("USERPROFILE")
        if not profile:
            return None
        return Path(profile) / "Documents" / "PCSX2" / "inis" / "PCSX2.ini"

    try:
        profile = subprocess.run(
            ["cmd.exe", "/c", "echo", "%USERPROFILE%"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not profile:
            return None
        wsl_path = subprocess.run(
            ["wslpath", "-u", profile],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return Path(wsl_path) / "Documents" / "PCSX2" / "inis" / "PCSX2.ini"
    except Exception:
        return None


def _sanitize_project64_cfg(path: Path) -> None:
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[str] = []
    in_plugin = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_plugin = stripped[1:-1].strip().lower() == "plugin"
            out.append(line)
            continue
        if in_plugin:
            if stripped and "=" not in stripped and not stripped.startswith(";"):
                continue
        out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _set_cfg_value(path: Path, section: str, key: str, value: str) -> None:
    if not path.exists():
        path.write_text(f"[{section}]\n{key}={value}\n", encoding="utf-8")
        return

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[str] = []
    in_section = False
    section_found = False
    key_written = False

    def _emit_key():
        nonlocal key_written
        if not key_written:
            out.append(f"{key}={value}")
            key_written = True

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section:
                _emit_key()
            in_section = stripped[1:-1].strip().lower() == section.lower()
            if in_section:
                section_found = True
            out.append(line)
            continue

        if in_section and stripped and not stripped.startswith(";"):
            k = stripped.split("=", 1)[0].strip()
            if k.lower() == key.lower():
                out.append(f"{key}={value}")
                key_written = True
                continue
        out.append(line)

    if in_section:
        _emit_key()
    if not section_found:
        out.append(f"[{section}]")
        out.append(f"{key}={value}")

    path.write_text("\n".join(out) + "\n", encoding="utf-8")


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
