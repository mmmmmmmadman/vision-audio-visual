"""
Configuration management
"""

import json
from pathlib import Path
from typing import Any, Dict


class Config:
    """Application configuration manager"""

    DEFAULT_CONFIG = {
        "audio": {
            "sample_rate": 48000,
            "buffer_size": 128,
            "channels": 8,
        },
        "video": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
        },
        "cv": {
            "decay_min": 0.01,
            "decay_max": 10.0,
            "sequence_steps": 16,
        },
        "vision": {
            "camera_id": 0,
            "min_cable_length": 50,
            "max_cables": 32,
            "confidence_threshold": 0.7,
        },
        "diffusion": {
            "model": "stable-diffusion-1.5",
            "steps": 20,
            "guidance_scale": 7.5,
            "strength": 0.5,
        },
    }

    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".vav" / "config.json"
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        """Load configuration from file"""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                loaded = json.load(f)
                self.config.update(loaded)

    def save(self):
        """Save configuration to file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any):
        """Set configuration value"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value

    def get_all(self) -> Dict:
        """Get all configuration"""
        return self.config.copy()
