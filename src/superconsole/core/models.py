from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Game:
    platform: str
    title: str
    game_dir: Path          
    launch_target: Path     
    cover_path: Path        
