import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app_config import load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_failed_replace_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'config.json'
            target.write_text('{"link_timeout": 90}', encoding='utf-8')
            with patch('app_config.config_path', return_value=target), patch('app_config.os.replace', side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError):
                    save_config({'link_timeout': 300})
            self.assertEqual(target.read_text(encoding='utf-8'), '{"link_timeout": 90}')
            self.assertEqual(list(Path(folder).iterdir()), [target])

    def test_non_object_config_is_ignored(self):
        with patch('app_config.Path.read_text', return_value='[]'):
            self.assertEqual(load_config(), {})

    def test_invalid_settings_use_defaults(self):
        with patch('app_config.Path.read_text', return_value='{"link_timeout": -1, "date_direction": "bad"}'):
            self.assertEqual(load_config(), {'link_timeout': 180, 'date_direction': 'nearest'})

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'config.json'
            with patch('app_config.config_path', return_value=target):
                save_config({'target_window': {'hwnd': 7, 'pid': 8}})
                self.assertEqual(load_config()['target_window']['pid'], 8)

    def test_invalid_config_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'config.json'; target.write_text('{bad', encoding='utf-8')
            with patch('app_config.config_path', return_value=target): self.assertEqual(load_config(), {})
