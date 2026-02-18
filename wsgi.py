# production_system_v2/wsgi.py
"""
WSGI entry point for production servers
Создан для совместимости, но можно использовать run.py для разработки
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app

# Определяем конфигурацию
config_name = os.environ.get('FLASK_ENV', 'production')
if config_name in ['dev', 'development']:
    config_name = 'development'
elif config_name in ['prod', 'production']:
    config_name = 'production'

# Создаем приложение
app = create_app(config_name)