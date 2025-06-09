"""Configuration loading and management for ctxssg."""

import sys
from pathlib import Path
from typing import Dict, Any
import yaml

# TOML support for configuration
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class ConfigLoader:
    """Handles loading and normalizing site configuration."""
    
    def __init__(self, root_path: Path):
        self.root_path = root_path
    
    def load_config(self) -> Dict[str, Any]:
        """Load site configuration from config.toml or config.yaml."""
        # Try TOML first (preferred), then YAML for backward compatibility
        toml_path = self.root_path / "config.toml"
        yaml_path = self.root_path / "config.yaml"
        
        if toml_path.exists():
            with open(toml_path, 'rb') as f:
                config = tomllib.load(f)
                return self._normalize_config(config)
        elif yaml_path.exists():
            with open(yaml_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                return self._normalize_config(config)
        
        return self._get_default_config()
    
    def _normalize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize configuration to internal format."""
        # Handle TOML nested structure vs flat YAML structure
        if 'site' in config:
            # TOML format with sections
            normalized = {}
            # Flatten site section to root
            normalized.update(config.get('site', {}))
            # Add build settings
            normalized.update(config.get('build', {}))
            # Add template settings
            if 'templates' in config:
                normalized['template_config'] = config['templates']
            # Add format-specific settings
            if 'formats' in config:
                normalized['format_config'] = config['formats']
            # Add CSS settings
            if 'css' in config:
                normalized['css'] = config['css']
            return normalized
        else:
            # YAML format (flat) or legacy TOML
            return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when no config file exists."""
        return {
            'title': 'My Site',
            'url': 'http://localhost:8000',
            'description': 'A static site generated with ctxssg',
            'author': 'Your Name',
            'output_dir': '_site',
            'output_formats': ['html'],
        }