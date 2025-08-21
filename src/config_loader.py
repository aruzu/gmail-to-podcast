#!/usr/bin/env python3
"""
Configuration loader for Gmail to Podcast

Handles loading configuration from multiple sources with proper precedence:
1. Command line arguments (highest priority)
2. Environment variables
3. Personal config file (config/config.yaml)
4. Default config file (config/default_config.yaml)
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


class ConfigLoader:
    """Loads and manages configuration from multiple sources."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config = self._load_config()
        self.senders = self._load_senders()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration with proper precedence."""
        config = {}
        
        # 1. Load default config
        default_config_path = self.config_dir / "default_config.yaml"
        if default_config_path.exists():
            config = self._read_yaml(default_config_path)
        
        # 2. Load personal config (overrides defaults)
        personal_config_path = self.config_dir / "config.yaml"
        if personal_config_path.exists():
            personal_config = self._read_yaml(personal_config_path)
            config = self._deep_merge(config, personal_config)
        
        # 3. Apply environment variable overrides
        config = self._apply_env_overrides(config)
        
        return config
    
    def _load_senders(self) -> Dict[str, Dict[str, Any]]:
        """Load sender configurations from JSON files."""
        senders = {}
        senders_dir = self.config_dir / "senders"
        
        if not senders_dir.exists():
            return senders
        
        # Load all JSON files in senders directory
        for json_file in senders_dir.glob("*.json"):
            try:
                sender_data = self._read_json(json_file)
                senders.update(sender_data)
            except Exception as e:
                print(f"Warning: Failed to load {json_file}: {e}")
        
        # Create 'all' preset combining all unique senders
        all_senders = set()
        for preset_data in senders.values():
            if isinstance(preset_data, dict) and 'senders' in preset_data:
                all_senders.update(preset_data['senders'])
        
        if all_senders:
            senders['all'] = {
                'description': 'All configured senders',
                'senders': sorted(list(all_senders))
            }
        
        return senders
    
    def get_sender_preset(self, preset_name: str) -> Optional[List[str]]:
        """Get sender list for a specific preset."""
        if preset_name in self.senders:
            preset_data = self.senders[preset_name]
            if isinstance(preset_data, dict) and 'senders' in preset_data:
                return preset_data['senders']
            elif isinstance(preset_data, list):
                # Support legacy format
                return preset_data
        return None
    
    def get_preset_config(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Get complete preset configuration including senders and labels."""
        if preset_name in self.senders:
            return self.senders[preset_name]
        return None
    
    def get_all_presets(self) -> List[str]:
        """Get list of all available preset names."""
        return list(self.senders.keys())
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Example: config.get('podcast.default_duration', 30)
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def _read_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Read YAML file."""
        try:
            with open(file_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return {}
    
    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        """Read JSON file."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return {}
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_overrides(self, config: Dict) -> Dict:
        """Apply environment variable overrides."""
        # Map environment variables to config paths
        env_mappings = {
            'GMAIL_CREDENTIALS_PATH': 'gmail.credentials_path',
            'GMAIL_TOKEN_PATH': 'gmail.token_path',
            'OUTPUT_BASE_DIR': 'output.base_dir',
            'PODCAST_DURATION': 'podcast.default_duration',
            'OPENAI_MODEL': 'models.openai.default_model',
            'GEMINI_MODEL': 'models.gemini.default_model',
        }
        
        for env_var, config_path in env_mappings.items():
            if env_var in os.environ:
                # Set value using dot notation
                keys = config_path.split('.')
                current = config
                
                for i, key in enumerate(keys[:-1]):
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # Convert to appropriate type
                value = os.environ[env_var]
                if value.isdigit():
                    value = int(value)
                elif value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                
                current[keys[-1]] = value
        
        return config


# Singleton instance
_config_instance = None


def get_config() -> ConfigLoader:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader()
    return _config_instance