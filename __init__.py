# production_system_v2/app/__init__.py
"""
Инициализация приложения с автоматической архивацией и планировщиком задач
"""

from datetime import datetime
import logging
import logging.config
import atexit
import os
import sys

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import config_by_name, Config

from flask_wtf.csrf import CSRFProtect

# Инициализация расширений
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
scheduler = BackgroundScheduler(timezone=Config.SCHEDULER_TIMEZONE)
csrf = CSRFProtect()


def create_app(config_name='default'):
    """
    Фабрика приложения с планировщиком задач
    
    Args:
        config_name: Имя конфигурации ('development', 'testing', 'production', 'default')
        
    Returns:
        Flask: Экземпляр приложения Flask
    """
    app = Flask(__name__)
    
    # Загружаем конфигурацию из объекта
    app.config.from_object(config_by_name[config_name])
    
    # Настройка логирования (ДО инициализации всего остального!)
    configure_logging(app)
    
    # Инициализация расширений
    initialize_extensions(app)
    
    # Регистрация blueprint'ов
    register_blueprints(app)
    
    # Регистрация контекстных процессоров
    register_context_processors(app)
    
    # Инициализация приложения в контексте
    with app.app_context():
        initialize_application(app)
    
    # Регистрируем обработчик завершения приложения
    atexit.register(lambda: stop_scheduler() if scheduler.running else None)
    
    # Регистрация модуля договоров
    try:
        from app.modules.contracts import init_app as init_contracts
        init_contracts(app)
        app.logger.info("Модуль договоров успешно зарегистрирован")
    except ImportError as e:
        app.logger.warning(f"Модуль договоров не загружен: {e}")
    except Exception as e:
        app.logger.error(f"Ошибка при загрузке модуля договоров: {e}")
    
    # Регистрация модуля парсера поставщиков
    try:
        from app.modules import supplier_parser
        app.register_blueprint(supplier_parser.supplier_parser_bp)
        app.logger.info("Модуль парсера поставщиков успешно зарегистрирован")
    except ImportError as e:
        app.logger.warning(f"Модуль парсера поставщиков не загружен: {e}")
    except AttributeError as e:
        app.logger.warning(f"В модуле нет supplier_parser_bp: {e}")
    except Exception as e:
        app.logger.error(f"Ошибка при загрузке модуля парсера поставщиков: {e}")
    
    return app


def configure_logging(app):
    """Настройка логирования с использованием DictConfig (ПРОФЕССИОНАЛЬНЫЙ ПОДХОД)"""
    log_level = app.config.get('LOG_LEVEL', logging.INFO)
    log_file = app.config.get('LOG_FILE', 'app_scheduler.log')
    
    # Создаем директорию для логов если её нет
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Определяем уровень для access логов (запросов)
    # В продакшене можно отключить, в разработке оставить для отладки
    access_log_level = logging.INFO if app.debug else logging.WARNING
    
    # Конфигурация логирования - DictConfig
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'detailed': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s:%(lineno)d - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'access': {
                'format': '%(asctime)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout',
                'formatter': 'standard',
                'level': log_level,
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_file,
                'maxBytes': app.config.get('LOG_MAX_BYTES', 10 * 1024 * 1024),
                'backupCount': app.config.get('LOG_BACKUP_COUNT', 5),
                'encoding': 'utf-8',
                'formatter': 'detailed',
                'level': log_level,
            },
            'access_file': {  # Отдельный файл для access логов
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': 'access.log',
                'maxBytes': 10 * 1024 * 1024,
                'backupCount': 3,
                'encoding': 'utf-8',
                'formatter': 'access',
                'level': logging.INFO,
            },
            'error_file': {  # Отдельный файл только для ошибок
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': 'error.log',
                'maxBytes': 10 * 1024 * 1024,
                'backupCount': 3,
                'encoding': 'utf-8',
                'formatter': 'detailed',
                'level': logging.ERROR,
            },
        },
        'root': {
            'level': logging.WARNING,  # Корневой логгер только WARNING+
            'handlers': ['console', 'file'],
        },
        'loggers': {
            # Логгер приложения - ВСЕ уровни
            'app': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False,
            },
            
            # Если хотите оставить только ошибки:
            'werkzeug': {
                'level': logging.ERROR,  # 400, 500 ошибки будут видны
                'handlers': ['console'],  # Только в консоль
                'propagate': False,
            },            
            
            # Логгер для задач
            'app.tasks': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False,
            },
            # Логгер для парсера поставщиков
            'app.modules.supplier_parser': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False,
            },
            # Логгер для сервисов
            'app.services': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False,
            },
            # 🚀 ОПТИМАЛЬНАЯ НАСТРОЙКА ДЛЯ WERKZEUG
            'werkzeug': {
                'level': access_log_level,  # INFO в dev, WARNING в prod
                'handlers': ['console', 'access_file'],  # Только консоль и access.log
                'propagate': False,
            },
            # SQLAlchemy - только предупреждения
            'sqlalchemy.engine': {
                'level': logging.WARNING,
                'handlers': ['file', 'error_file'],
                'propagate': False,
            },
            # APScheduler - только ошибки
            'apscheduler': {
                'level': logging.ERROR,
                'handlers': ['file', 'error_file'],
                'propagate': False,
            },
            # Отключаем лишние логи
            'urllib3': {
                'level': logging.WARNING,
                'handlers': ['file'],
                'propagate': False,
            },
            'requests': {
                'level': logging.WARNING,
                'handlers': ['file'],
                'propagate': False,
            },
        }
    }
    
    # Применяем конфигурацию
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Перенаправляем логгер Flask
    app.logger = logging.getLogger('app')
    
    # Логируем успешную настройку
    app.logger.info(f"✅ Логирование настроено профессионально")
    app.logger.info(f"📁 Основной лог: {log_file}")
    app.logger.info(f"📁 Access лог: access.log")
    app.logger.info(f"📁 Ошибки: error.log")
    app.logger.info(f"🔧 Werkzeug уровень: {logging.getLevelName(access_log_level)}")


def initialize_extensions(app):
    """Инициализация всех расширений Flask"""
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    
    # Настройка Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Пожалуйста, войдите в систему.'
    login_manager.login_message_category = 'warning'
    
    app.logger.info("✅ Расширения Flask инициализированы")


def register_blueprints(app):
    """Регистрация всех blueprint'ов приложения"""
    try:
        from app.routes import main as main_blueprint
        from app.auth import auth as auth_blueprint
        from app.admin import admin as admin_blueprint
        from app.notifications import notifications_bp as notifications_blueprint
        
        app.register_blueprint(main_blueprint)
        app.register_blueprint(auth_blueprint, url_prefix='/auth')
        app.register_blueprint(admin_blueprint, url_prefix='/admin')
        app.register_blueprint(notifications_blueprint, url_prefix='/notifications')
        
        app.logger.info("✅ Blueprint'ы зарегистрированы")
    except ImportError as e:
        app.logger.error(f"❌ Ошибка импорта blueprint'ов: {e}")
        raise


def register_context_processors(app):
    """Регистрация контекстных процессоров для шаблонов"""
    
    @app.context_processor
    def inject_globals():
        """Контекст-процессор для добавления глобальных переменных в шаблоны"""
        try:
            from app.services.file_service import FileService
            from app.config import OrderStatus, UserRole
            from app.models import OrderFile, Client
            from app.services.archive_service import ArchiveService
            
            return {
                'FileService': FileService,
                'OrderStatus': OrderStatus,
                'UserRole': UserRole,
                'OrderFile': OrderFile,
                'ArchiveService': ArchiveService,
                'Client': Client,
                'now': datetime.now
            }
        except ImportError as e:
            app.logger.error(f"❌ Ошибка импорта в контекстном процессоре: {e}")
            return {}
    
    @app.context_processor
    def utility_processor():
        """Контекст-процессор с утилитарными функциями"""
        from app.config import OrderStatus, UserRole
        return dict(
            OrderStatus=OrderStatus,
            UserRole=UserRole,
            now=datetime.now
        )


def initialize_application(app):
    """Инициализация приложения: создание БД, папок, планировщика"""
    try:
        # Создание таблиц базы данных
        db.create_all()
        app.logger.info("✅ Таблицы базы данных созданы/проверены")
        
        # Создание необходимых директорий
        create_required_directories(app)
        
        # Создание администратора по умолчанию
        create_default_admin(app)
        
        # Инициализация настроек уведомлений
        initialize_notification_settings(app)
        
        # Инициализация планировщика задач
        init_scheduler(app)
        
        app.logger.info("✅ Приложение успешно инициализировано")
        
    except Exception as e:
        app.logger.error(f"❌ Ошибка при инициализации приложения: {e}")
        raise


def create_required_directories(app):
    """Создание необходимых директорий для загрузки файлов"""
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        # Создаем поддиректории
        os.makedirs(os.path.join(upload_folder, 'orders'), exist_ok=True)
        os.makedirs(os.path.join(upload_folder, 'temp'), exist_ok=True)
        os.makedirs(os.path.join(upload_folder, 'designs'), exist_ok=True)
        
        app.logger.info(f"✅ Директории загрузок созданы: {upload_folder}")
    except Exception as e:
        app.logger.error(f"❌ Ошибка создания директорий загрузок: {e}")
        raise


def create_default_admin(app):
    """Создание администратора по умолчанию"""
    try:
        from app.services.auth_service import AuthService
        AuthService.create_default_admin()
        app.logger.info("✅ Проверка/создание администратора выполнена")
    except Exception as e:
        app.logger.error(f"❌ Ошибка создания администратора: {e}")
        # Не прерываем инициализацию, только логируем


def initialize_notification_settings(app):
    """Инициализация настроек уведомлений по умолчанию"""
    try:
        from app.services.notification_settings_service import NotificationSettingsService
        NotificationSettingsService.init_defaults()
        app.logger.info("✅ Настройки уведомлений инициализированы")
    except Exception as e:
        app.logger.error(f"❌ Ошибка инициализации настроек уведомлений: {e}")
        # Не прерываем инициализацию, только логируем


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя для Flask-Login"""
    try:
        from app.models import User
        return User.query.get(int(user_id))
    except Exception as e:
        logging.getLogger('app').error(f"Ошибка загрузки пользователя {user_id}: {e}")
        return None


def init_scheduler(app):
    """Инициализация и запуск планировщика задач"""
    # Проверяем, не запущен ли уже планировщик
    if scheduler.running:
        app.logger.info("⏰ Планировщик задач уже запущен")
        return
    
    # Проверяем, нужно ли запускать планировщик (в тестах обычно не нужен)
    if app.config.get('TESTING', False):
        app.logger.info("⏰ Планировщик задач не запущен (режим тестирования)")
        return
    
    try:
        # Добавляем задачи в планировщик
        schedule_tasks(app)
        
        # Запускаем планировщик
        scheduler.start()
        app.logger.info("✅ Планировщик задач запущен")
        
        # Логируем все запланированные задачи
        log_scheduled_tasks(app)
        
    except Exception as e:
        app.logger.error(f"❌ Ошибка при запуске планировщика: {str(e)}")


def schedule_tasks(app):
    """Добавление всех задач в планировщик (основные + парсер поставщиков)"""
    from app.tasks import (
        auto_archive_completed_orders,
        cleanup_old_notifications,
        check_overdue_orders,
        check_design_ready_dates,
        send_daily_statistics
    )
    from app.tasks.supplier_parser_tasks import (
        process_pending_specifications,
        cleanup_old_supplier_requests
    )
    
    # Получаем настройки из конфигурации
    archive_hour = app.config.get('AUTO_ARCHIVE_HOUR', 2)
    archive_minute = app.config.get('AUTO_ARCHIVE_MINUTE', 0)
    
    cleanup_day = app.config.get('CLEANUP_NOTIFICATIONS_DAY_OF_WEEK', 'sun')
    cleanup_hour = app.config.get('CLEANUP_NOTIFICATIONS_HOUR', 3)
    
    overdue_hour = app.config.get('CHECK_OVERDUE_HOUR', 9)
    design_hour = app.config.get('CHECK_DESIGN_DATES_HOUR', 10)
    statistics_hour = app.config.get('DAILY_STATISTICS_HOUR', 18)
    
    # --- Основные задачи ---
    # Автоматическая архивация завершённых заказов
    scheduler.add_job(
        func=lambda: run_with_app_context(app, auto_archive_completed_orders),
        trigger=CronTrigger(hour=archive_hour, minute=archive_minute),
        id='auto_archive_job',
        name='Автоматическая архивация завершенных заказов',
        replace_existing=True,
        max_instances=1
    )
    
    # Очистка старых уведомлений (раз в неделю)
    scheduler.add_job(
        func=lambda: run_with_app_context(app, cleanup_old_notifications),
        trigger=CronTrigger(day_of_week=cleanup_day, hour=cleanup_hour, minute=0),
        id='cleanup_notifications_job',
        name='Очистка старых уведомлений',
        replace_existing=True,
        max_instances=1
    )
    
    # Проверка просроченных сроков
    scheduler.add_job(
        func=lambda: run_with_app_context(app, check_overdue_orders),
        trigger=CronTrigger(hour=overdue_hour, minute=0),
        id='check_overdue_job',
        name='Проверка просроченных заказов',
        replace_existing=True,
        max_instances=1
    )
    
    # Проверка сроков готовности чертежей
    scheduler.add_job(
        func=lambda: run_with_app_context(app, check_design_ready_dates),
        trigger=CronTrigger(hour=design_hour, minute=0),
        id='check_design_dates_job',
        name='Проверка сроков готовности чертежей',
        replace_existing=True,
        max_instances=1
    )
    
    # Отправка ежедневной статистики
    scheduler.add_job(
        func=lambda: run_with_app_context(app, send_daily_statistics),
        trigger=CronTrigger(hour=statistics_hour, minute=0),
        id='daily_statistics_job',
        name='Отправка ежедневной статистики',
        replace_existing=True,
        max_instances=1
    )
    
    # --- Задачи парсера поставщиков ---
    # Проверка новых спецификаций (каждые 30 минут)
    scheduler.add_job(
        func=lambda: run_with_app_context(app, process_pending_specifications),
        trigger=CronTrigger(minute='*/30'),
        id='check_specifications_job',
        name='Проверка новых файлов спецификаций',
        replace_existing=True,
        max_instances=1
    )
    
    # Очистка старых заявок поставщикам (раз в неделю)
    scheduler.add_job(
        func=lambda: run_with_app_context(app, cleanup_old_supplier_requests, 30),
        trigger=CronTrigger(day_of_week='sun', hour=4, minute=0),
        id='cleanup_supplier_requests_job',
        name='Очистка старых заявок поставщикам',
        replace_existing=True,
        max_instances=1
    )
    
    app.logger.info(f"📅 Запланировано {len(scheduler.get_jobs())} задач")


def run_with_app_context(app, func, *args, **kwargs):
    """Запуск функции в контексте приложения"""
    with app.app_context():
        try:
            result = func(*args, **kwargs)
            app.logger.info(f"✅ {func.__name__}: {result}")
            return result
        except Exception as e:
            app.logger.error(f"❌ Ошибка в {func.__name__}: {str(e)}")
            return None


def log_scheduled_tasks(app):
    """Логирование запланированных задач"""
    jobs = scheduler.get_jobs()
    app.logger.info(f"📅 Запланировано {len(jobs)} задач:")
    
    # Группируем задачи по времени выполнения
    for job in sorted(jobs, key=lambda j: str(j.next_run_time)):
        next_run = job.next_run_time
        next_run_str = next_run.strftime('%d.%m.%Y %H:%M') if next_run else 'не запланировано'
        app.logger.info(f"  • {job.name}")
        app.logger.info(f"    ID: {job.id}, Следующий запуск: {next_run_str}")


def stop_scheduler():
    """Остановка планировщика задач при завершении работы приложения"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger = logging.getLogger('app')
        logger.info("🛑 Планировщик задач остановлен")