import json
import os
import tempfile
from pathlib import Path
from PySide6.QtCore import QStandardPaths


def config_path():
    return Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)) / 'config.json'


def load_config():
    try:
        data = json.loads(config_path().read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {}
        if data.get('date_direction') not in ('nearest', 'previous', 'next'):
            data['date_direction'] = 'nearest'
        timeout = data.get('link_timeout', 180)
        data['link_timeout'] = timeout if type(timeout) is int and 30 <= timeout <= 900 else 180
        return data
    except (OSError, ValueError):
        return {}


def save_config(data):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='config-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
