# production_system_v2/app/config.py
"""
Конфигурация новой системы управления производством
"""

import os
from datetime import datetime
from enum import Enum
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()


class OrderStatus(str, Enum):
    """Статусы заказов"""
    NEW = 'new'
    DESIGN = 'design'
    DESIGN_REVIEW = 'design_review'
    CLIENT_APPROVED = 'design_client_approved'
    IN_DESIGN = 'in_design'
    DESIGN_COMPLETED = 'design_completed'
    PURCHASE = 'purchase'
    PURCHASE_COMPLETED = 'purchase_completed'
    MANUFACTURING = 'manufacturing'
    INSTALLATION = 'installation'
    QUALITY_CHECK = 'quality_check'
    RETURN_TO_DESIGN = 'return_to_design'
    READY_FOR_DELIVERY = 'ready_for_delivery'
    DELIVERED = 'delivered'
    COMPLETED = 'completed'
    ARCHIVED = 'archived'
    RECLAMATION = 'reclamation'
    
    @classmethod
    def get_display_name(cls, status):
        if status is None:
            return "Неизвестно"
        
        status_str = str(status)
        
        if status_str.startswith('OrderStatus.'):
            status_key = status_str.split('.')[-1].lower()
        else:
            status_key = status_str.lower()
        
        display_names = {
            'new': 'НОВЫЙ',
            'design': 'Предварительный эскиз',
            'design_review': 'НА СОГЛАСОВАНИИ',
            'design_client_approved': 'Эскиз согласован с клиентом',
            'in_design': 'В разработке',
            'design_completed': 'Разработка завершена',
            'purchase': 'На закупке',
            'purchase_completed': 'Закупка завершена',
            'manufacturing': 'В производстве',
            'installation': 'Монтаж',
            'quality_check': 'Проверка ОТК',
            'return_to_design': 'Вернуть на доработку',
            'ready_for_delivery': 'Готов к отгрузке',
            'delivered': 'Отгружен',
            'completed': 'Завершен',
            'archived': 'АРХИВИРОВАН',
            'reclamation': 'РЕКЛАМАЦИЯ'
        }
        
        return display_names.get(status_key, status_str)
        
    @classmethod
    def get_status_color(cls, status):
        """Получение цвета для статуса - работает с любым форматом"""
        if status is None:
            return 'secondary'
        
        status_str = str(status)
        
        if status_str.startswith('OrderStatus.'):
            status_key = status_str.split('.')[-1].lower()
        else:
            status_key = status_str.lower()
        
        color_map = {
            'new': 'info',
            'design': 'warning',
            'design_review': 'warning',
            'design_client_approved': 'success',
            'in_design': 'primary',
            'design_completed': 'success',
            'purchase': 'info',
            'purchase_completed': 'success',
            'manufacturing': 'warning',
            'installation': 'primary',
            'quality_check': 'warning',
            'return_to_design': 'danger',
            'ready_for_delivery': 'info',
            'delivered': 'success',
            'completed': 'success',
            'archived': 'secondary',
            'reclamation': 'danger'
        }
        
        return color_map.get(status_key, 'secondary')
    
    @classmethod
    def get_all_statuses(cls):
        """Получение списка всех статусов для форм"""
        return [
            ('new', 'НОВЫЙ'),
            ('design', 'Предварительный эскиз'),
            ('design_review', 'НА СОГЛАСОВАНИИ'),
            ('design_client_approved', 'Эскиз согласован с клиентом'),
            ('in_design', 'В разработке'),
            ('design_completed', 'Разработка завершена'),
            ('purchase', 'На закупке'),
            ('purchase_completed', 'Закупка завершена'),
            ('manufacturing', 'В производстве'),
            ('installation', 'Монтаж'),
            ('quality_check', 'Проверка ОТК'),
            ('return_to_design', 'Вернуть на доработку'),
            ('ready_for_delivery', 'Готов к отгрузке'),
            ('delivered', 'Отгружен'),
            ('completed', 'Завершен'),
            ('archived', 'АРХИВИРОВАН'),
            ('reclamation', 'РЕКЛАМАЦИЯ')
        ]


class UserRole(str, Enum):
    """Роли пользователей"""
    ADMIN = 'admin'
    DIRECTOR = 'director'
    HEAD_DESIGNER = 'head_designer'
    HEAD_PRODUCTION = 'head_production'
    HEAD_SUPPLY = 'head_supply'
    SALON_HEAD = 'salon_head'
    SALON_MANAGER = 'salon_manager'
    DESIGNER = 'designer'
    SUPPLY = 'supply'
    PRODUCTION = 'production'
    QUALITY_CONTROL = 'quality_control'
    CLIENT = 'client'
    
    @classmethod
    def _get_display_names(cls):
        """Внутренний метод для получения словаря отображения"""
        return {
            'admin': 'Администратор',
            'director': 'Директор',
            'head_designer': 'Руководитель конструкторов',
            'head_production': 'Начальник цеха',
            'head_supply': 'Руководитель закупок',
            'salon_head': 'Руководитель салона',
            'salon_manager': 'Магазин',
            'designer': 'Конструктор',
            'supply': 'Специалист закупок',
            'production': 'Рабочий цеха',
            'quality_control': 'ОТК',
            'client': 'Клиент'
        }
    
    @classmethod
    def get_display_name(cls, role):
        """Получение отображаемого имени роли"""
        if role is None:
            return 'Неизвестно'
        
        if isinstance(role, cls):
            role_value = role.value
        else:
            role_value = str(role).strip()
        
        role_lower = role_value.lower()
        
        display_names = cls._get_display_names()
        if role_lower in display_names:
            return display_names[role_lower]
        
        return role_value.title()
    
    @classmethod
    def get_choices_for_form(cls):
        """Получение списка ролей для форм (значение, отображаемое имя)"""
        display_names = cls._get_display_names()
        choices = []
        for member in cls:
            choices.append((member.value, display_names[member.value]))
        return choices
    
    @classmethod
    def get_all_roles(cls):
        """Получение списка всех ролей (значение Enum, отображаемое имя)"""
        display_names = cls._get_display_names()
        return [
            (member, display_names[member.value]) 
            for member in cls
        ]


class Config:
    """Базовая конфигурация"""
    
    # ========== ОБЯЗАТЕЛЬНЫЕ НАСТРОЙКИ ==========
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        SECRET_KEY = 'dev-secret-key-2026-change-me'
        print("⚠️ SECRET_KEY не найден, используется заглушка для разработки")
    
    CSRF_SECRET_KEY = os.environ.get('CSRF_SECRET_KEY')
    if not CSRF_SECRET_KEY:
        CSRF_SECRET_KEY = 'dev-csrf-key-2026-change-me'
        print("⚠️ CSRF_SECRET_KEY не найден, используется заглушка для разработки")
    
    # ========== CSRF ЗАЩИТА ==========
    WTF_CSRF_ENABLED = True  # Включено для всех окружений
    WTF_CSRF_SECRET_KEY = CSRF_SECRET_KEY  # Используем тот же ключ
    WTF_CSRF_TIME_LIMIT = 3600  # Время жизни токена: 1 час
    WTF_CSRF_SSL_STRICT = False  # Отключаем strict SSL для разработки
    WTF_CSRF_CHECK_DEFAULT = True  # Проверять CSRF для всех POST запросов по умолчанию
    WTF_CSRF_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']  # Методы для проверки
    
    # Базовый URL приложения
    BASE_URL = os.environ.get('BASE_URL')
    if not BASE_URL:
        raise ValueError("BASE_URL не установлен в переменных окружения!")
    
    # База данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("DATABASE_URL не установлен в переменных окружения!")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Папка для загрузок
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(
        os.path.dirname(__file__), '..', 'uploads'
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Настройки загрузки файлов
    FILE_UPLOAD_ALLOW_ALL = os.environ.get('FILE_UPLOAD_ALLOW_ALL', 'false').lower() == 'true'
    
    # Список разрешенных расширений
    ALLOWED_EXTENSIONS = {
        'images': {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'},
        'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'},
        'spreadsheets': {'xls', 'xlsx', 'csv', 'ods'},
        'cad': {'dwg', 'dxf', 'dgn', 'cdw', 'm3d', 'step', 'stp', 'iges', 'igs'},
        'archives': {'zip', 'rar', '7z', 'tar', 'gz', 'bz2'},
        'other': set()
    }
    
    @property
    def ALLOWED_ALL_EXTENSIONS(self):
        """Полный список разрешенных расширений"""
        return set().union(*self.ALLOWED_EXTENSIONS.values())
    
    # ========== НАСТРОЙКИ ПОЧТЫ ==========
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 0))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'false').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    MAIL_SUPPRESS_SEND = False
    MAIL_MAX_EMAILS = None
    MAIL_ASCII_ATTACHMENTS = False
    
    @classmethod
    def validate_mail_settings(cls):
        """Проверка наличия настроек почты"""
        if cls.MAIL_SERVER and cls.MAIL_USERNAME and cls.MAIL_PASSWORD:
            return True
        return False
    
    # ========== НАСТРОЙКИ TELEGRAM ==========
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
    TELEGRAM_NOTIFICATIONS_ENABLED = os.environ.get('TELEGRAM_NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
    
    TELEGRAM_NOTIFICATIONS_DEFAULTS = {
        'telegram_new_orders': True,
        'telegram_status_changes': True,
        'telegram_design_completed': True,
        'telegram_quality_check': True,
        'telegram_ready_for_delivery': True,
        'telegram_return_to_design': True,
        'telegram_errors': True
    }
    
    # ========== НАСТРОЙКИ PUSH-УВЕДОМЛЕНИЙ ==========
    PUSH_NOTIFICATIONS_ENABLED = os.environ.get('PUSH_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
    PUSH_NOTIFICATIONS_TTL = 2419200  # 28 дней в секундах
    
    # VAPID для Web Push уведомлений - СОХРАНЯЕМ ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ!!!
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY') or 'LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JR0hBZ0VBTUJNR0J5cUdTTTQ5QWdFR0NDcUdTTTQ5QXdFSEJHMHdhd0lCQVFRZ0pRYllvNUpFb2JBamVEWm0Kbks3TE8zTzJkRlNDRTFzdEdFWmFLSmN4aTZTaFJBTkNBQVRvU1ZYbmJhZTZBMzROVEZ3aWFBV1RzTjBQbms3TApTL2VlTFVQY2xra0k4Y0QzS2QvZHlLUmlyNzVDNGUyT05UTUw5cGx6MTJRaGwwRVRLazRhNERzVgotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tCg'
    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY') or 'BOhJVedtp7oDfg1MXCJoBZOw3Q-eTstL954tQ9yWSQjxwPcp393IpGKvvkLh7Y41Mwv2mXPXZCGXQRMqThrgOxU'
    VAPID_CLAIMS_EMAIL = os.environ.get('VAPID_CLAIMS_EMAIL') or 'mebel.dm@mail.ru'
    
    @classmethod
    def validate_vapid_settings(cls):
        """Проверка наличия VAPID ключей если push-уведомления включены"""
        if cls.PUSH_NOTIFICATIONS_ENABLED:
            if not all([cls.VAPID_PRIVATE_KEY, cls.VAPID_PUBLIC_KEY, cls.VAPID_CLAIMS_EMAIL]):
                raise ValueError(
                    "Для работы push-уведомлений необходимо установить "
                    "VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY и VAPID_CLAIMS_EMAIL"
                )
        return True
    
    # ========== НАСТРОЙКИ ЛОГИРОВАНИЯ ==========
    LOG_FILE = os.environ.get('LOG_FILE', 'app_scheduler.log')
    LOG_LEVEL = getattr(logging, os.environ.get('LOG_LEVEL', 'INFO'))
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', 10 * 1024 * 1024))
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', 5))
    
    # ========== НАСТРОЙКИ ПЛАНИРОВЩИКА ==========
    SCHEDULER_API_ENABLED = os.environ.get('SCHEDULER_API_ENABLED', 'false').lower() == 'true'
    SCHEDULER_TIMEZONE = os.environ.get('SCHEDULER_TIMEZONE', 'Europe/Moscow')
    
    # Настройки автоматической архивации
    AUTO_ARCHIVE_DAYS = int(os.environ.get('AUTO_ARCHIVE_DAYS', 5))
    AUTO_ARCHIVE_HOUR = int(os.environ.get('AUTO_ARCHIVE_HOUR', 2))
    AUTO_ARCHIVE_MINUTE = int(os.environ.get('AUTO_ARCHIVE_MINUTE', 0))
    
    # Настройки очистки уведомлений
    CLEANUP_NOTIFICATIONS_DAYS = int(os.environ.get('CLEANUP_NOTIFICATIONS_DAYS', 30))
    CLEANUP_NOTIFICATIONS_DAY_OF_WEEK = os.environ.get('CLEANUP_NOTIFICATIONS_DAY_OF_WEEK', 'sun')
    CLEANUP_NOTIFICATIONS_HOUR = int(os.environ.get('CLEANUP_NOTIFICATIONS_HOUR', 3))
    
    # Настройки проверки просроченных заказов
    CHECK_OVERDUE_HOUR = int(os.environ.get('CHECK_OVERDUE_HOUR', 9))
    
    # Настройки проверки сроков чертежей
    CHECK_DESIGN_DATES_HOUR = int(os.environ.get('CHECK_DESIGN_DATES_HOUR', 10))
    DESIGN_DEADLINE_WARNING_DAYS = int(os.environ.get('DESIGN_DEADLINE_WARNING_DAYS', 2))
    
    # Настройки ежедневной статистики
    DAILY_STATISTICS_HOUR = int(os.environ.get('DAILY_STATISTICS_HOUR', 18))
    
    # ========== ПРАВА ДОСТУПА ==========
    STATUS_PERMISSIONS = {
        ('new', 'design'): ['head_designer', 'admin', 'director'],
        ('design', 'design_client_approved'): ['salon_manager', 'admin', 'head_designer', 'director'],
        ('design_client_approved', 'in_design'): ['designer', 'admin', 'head_designer', 'director'],
        ('in_design', 'design_completed'): ['designer', 'admin', 'head_designer', 'director'],
        ('design_completed', 'purchase'): ['head_supply', 'admin', 'head_designer', 'director'],
        ('purchase', 'purchase_completed'): ['head_supply', 'admin', 'director'],
        ('purchase_completed', 'manufacturing'): ['head_production', 'admin', 'director'],
        ('manufacturing', 'installation'): ['head_production', 'admin', 'director'],
        ('installation', 'quality_check'): ['head_production', 'admin', 'director'],
        ('quality_check', 'ready_for_delivery'): ['quality_control', 'admin', 'head_production', 'director'],
        ('quality_check', 'return_to_design'): ['quality_control', 'admin', 'head_production', 'director'],
        ('return_to_design', 'in_design'): ['designer', 'admin', 'director'],
        ('ready_for_delivery', 'delivered'): ['head_production', 'admin', 'director'],
        ('delivered', 'completed'): ['admin', 'head_production', 'director'],
        ('in_design', 'design_review'): ['designer', 'admin', 'director'],
        ('design_review', 'design_client_approved'): ['salon_manager', 'admin', 'director'],
        ('design_review', 'return_to_design'): ['salon_manager', 'admin', 'director'],
        ('design', 'design_review'): ['designer', 'admin', 'head_production', 'head_designer', 'director'],
        ('manufacturing', 'return_to_design'): ['head_production', 'admin', 'director'],
        ('installation', 'return_to_design'): ['head_production', 'admin', 'director'],
        ('return_to_design', 'design_review'): ['designer', 'admin', 'director', 'head_designer'],
        ('completed', 'archived'): ['admin', 'director'],
        ('completed', 'reclamation'): ['admin', 'director'],
        ('archived', 'completed'): ['admin', 'director'],
        ('reclamation', 'completed'): ['admin', 'director'],
        ('reclamation', 'archived'): ['admin', 'director'],
    }
    
    # Настройки парсера поставщиков
    SUPPLIER_PARSER_ENABLED = os.environ.get('SUPPLIER_PARSER_ENABLED', 'true').lower() == 'true'
    SUPPLIER_PARSER_AUTO_PROCESS = os.environ.get('SUPPLIER_PARSER_AUTO_PROCESS', 'true').lower() == 'true'
    SUPPLIER_PARSER_CHECK_INTERVAL = int(os.environ.get('SUPPLIER_PARSER_CHECK_INTERVAL', 30))  # минут
    
    # Автоматические переходы
    AUTO_TRANSITIONS = {
        'design_completed': 'purchase',
        'purchase_completed': 'manufacturing',
        'return_to_design': 'in_design',
    }
    
    # Уведомления для статусов
    STATUS_NOTIFICATIONS = {
        'design': ['salon_manager', 'head_production', 'head_designer'],
        'design_client_approved': ['designer', 'head_production', 'head_designer'],
        'design_completed': ['head_supply', 'head_production', 'head_designer'],
        'purchase_completed': ['head_production', 'head_designer'],
        'return_to_design': ['designer', 'head_production', 'head_designer'],
        'quality_check': ['quality_control', 'head_production', 'head_designer'],
        'ready_for_delivery': ['salon_manager', 'head_production', 'head_designer'],
        'design_review': ['salon_manager', 'head_production', 'head_designer'],
    }
    
    @staticmethod
    def init_logging(app):
        """Инициализация логирования"""
        log_dir = os.path.dirname(Config.LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        handler = RotatingFileHandler(
            Config.LOG_FILE,
            maxBytes=Config.LOG_MAX_BYTES,
            backupCount=Config.LOG_BACKUP_COUNT
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        handler.setLevel(Config.LOG_LEVEL)
        
        app.logger.addHandler(handler)
        app.logger.setLevel(Config.LOG_LEVEL)
        
        if app.debug:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(Config.LOG_LEVEL)
            app.logger.addHandler(console_handler)



class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True
    MAIL_SUPPRESS_SEND = True
    PUSH_NOTIFICATIONS_ENABLED = True  # В разработке тоже включим
    
    # ⚠️ ВРЕМЕННО ОТКЛЮЧАЕМ CSRF ДЛЯ РАЗРАБОТКИ
    WTF_CSRF_ENABLED = True
    WTF_CSRF_CHECK_DEFAULT = False
    
    # В разработке можно использовать SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///production_v2_dev.db'


class TestingConfig(Config):
    """Конфигурация для тестирования"""
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    PUSH_NOTIFICATIONS_ENABLED = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite:///production_v2_test.db'


class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False
    PUSH_NOTIFICATIONS_ENABLED = os.environ.get('PUSH_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
    
    def __init__(self):
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY должен быть не менее 32 символов в продакшене!")
        
        if not self.validate_mail_settings():
            raise ValueError("В продакшене необходимо настроить почту!")
        
        if self.PUSH_NOTIFICATIONS_ENABLED:
            self.validate_vapid_settings()

  # Словарь для выбора конфигурации по окружению
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
