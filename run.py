#!/usr/bin/env python
# production_system_v2/run.py
"""
Простой запуск приложения без сложных импортов
"""

import os
import sys
from pathlib import Path

# Добавляем текущую папку в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app
    print("✅ Модуль app найден")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print(f"   Текущая директория: {os.getcwd()}")
    print(f"   PYTHONPATH: {sys.path}")
    
    # Пробуем альтернативный импорт
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "app", 
            os.path.join(os.path.dirname(__file__), "app", "__init__.py")
        )
        app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_module)
        create_app = app_module.create_app
        print("✅ Модуль app загружен через прямой импорт")
    except Exception as e2:
        print(f"❌ Альтернативный импорт тоже не сработал: {e2}")
        sys.exit(1)

# Загружаем .env если есть
try:
    from dotenv import load_dotenv
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"✅ Загружен .env: {env_file}")
except ImportError:
    print("⚠️ python-dotenv не установлен, используем системные переменные")
    pass

# Определяем режим запуска
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'false'
PORT = int(os.environ.get('PORT', 5001))
HOST = os.environ.get('HOST', '0.0.0.0')

# Маппинг конфигураций
config_map = {
    'development': 'development',
    'dev': 'development',
    'testing': 'testing',
    'test': 'testing',
    'production': 'production',
    'prod': 'production'
}

config_name = config_map.get(FLASK_ENV.lower(), 'development')

# Создаем приложение
try:
    app = create_app(config_name)
    print(f"✅ Приложение создано в режиме: {config_name}")
except Exception as e:
    print(f"❌ Ошибка создания приложения: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Проверяем обязательные настройки
if not app.config.get('SECRET_KEY'):
    print("⚠️ SECRET_KEY не задан, использую временный ключ для разработки")
    app.config['SECRET_KEY'] = 'dev-temporary-key-12345'

if not app.config.get('SQLALCHEMY_DATABASE_URI'):
    print("⚠️ DATABASE_URL не задан, использую SQLite")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///production_v2.db'

# Запуск
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 PRODUCTION SYSTEM V2".center(50))
    print("="*50)
    print(f"Режим:      {config_name.upper()}")
    print(f"URL:        http://{HOST}:{PORT}")
    print(f"Debug:      {DEBUG}")
    print(f"База данных: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print("="*50 + "\n")
    
    try:
        app.run(debug=DEBUG, host=HOST, port=PORT, threaded=True)
    except KeyboardInterrupt:
        print("\n🛑 Приложение остановлено")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")