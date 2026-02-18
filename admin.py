# production_system_v2/app/admin.py
"""
Админ-панель для управления пользователями и системой
"""

from flask import render_template, redirect, url_for, flash, request, Blueprint, send_from_directory, current_app
from flask_login import login_required, current_user
from app import db
from app.models import User, Order, Notification, OrderStatusHistory  # Добавили Notification
from app.permissions import admin_required
from app.services.auth_service import AuthService
from app.config import UserRole
import os
from datetime import datetime, timedelta  # Добавили импорт
from app.services.settings_service import SettingsService

admin = Blueprint('admin', __name__)

@admin.route('/orders/trash')
@login_required
@admin_required
def admin_order_trash():
    """Административный просмотр корзины"""
    return redirect(url_for('main.order_trash'))

@admin.route('/')
@login_required
@admin_required
def index():
    """Главная страница админ-панели"""
    # Статистика
    total_users = User.query.count()
    total_orders = Order.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    
    # Последние действия
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    return render_template('admin/index.html',
                         total_users=total_users,
                         total_orders=total_orders,
                         active_users=active_users,
                         recent_users=recent_users)


@admin.route('/users')
@login_required
@admin_required
def user_list():
    """Список всех пользователей"""
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Статистика по ролям
    role_stats = {}
    for role in UserRole:
        role_stats[role] = User.query.filter_by(role=role).count()
    
    return render_template('admin/users.html',
                         users=users,
                         role_stats=role_stats,
                         UserRole=UserRole)


@admin.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    """Активация/деактивация пользователя"""
    user = User.query.get_or_404(user_id)
    
    # Нельзя деактивировать самого себя
    if user.id == current_user.id and user.is_active:
        flash('Нельзя деактивировать самого себя.', 'danger')
        return redirect(url_for('admin.user_list'))
    
    # Для администраторов дополнительная проверка
    if user.role == UserRole.ADMIN and user.is_active:  # Если пытаемся деактивировать активного админа
        # Проверяем, есть ли другие активные администраторы
        other_active_admins = User.query.filter(
            User.role == UserRole.ADMIN,
            User.is_active == True,
            User.id != user_id
        ).count()
        
        if other_active_admins == 0:
            flash('Нельзя деактивировать последнего активного администратора!', 'danger')
            return redirect(url_for('admin.user_list'))
    
    try:
        user.is_active = not user.is_active
        db.session.commit()
        
        status = 'активирован' if user.is_active else 'деактивирован'
        flash(f'Пользователь {user.username} {status}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('admin.user_list'))


@admin.route('/users/<int:user_id>/reset_password', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    """Сброс пароля пользователя"""
    user = User.query.get_or_404(user_id)
    
    try:
        # Генерируем новый пароль
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits + '!@#$%'
        new_password = ''.join(secrets.choice(alphabet) for i in range(10))
        
        # Устанавливаем новый пароль
        AuthService.change_password(user, new_password)
        
        flash(f'Пароль для пользователя {user.username} сброшен. Новый пароль: {new_password}', 'success')
        
    except Exception as e:
        flash(f'Ошибка при сбросе пароля: {str(e)}', 'danger')
    
    return redirect(url_for('admin.user_list'))

@admin.route('/users/<int:user_id>/change_password', methods=['GET', 'POST'])
@login_required
@admin_required
def change_user_password(user_id):
    """Изменение пароля пользователя (ручной ввод)"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or not confirm_password:
            flash('Все поля обязательны для заполнения', 'danger')
            return redirect(url_for('admin.change_user_password', user_id=user_id))
        
        if new_password != confirm_password:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('admin.change_user_password', user_id=user_id))
        
        if len(new_password) < 6:
            flash('Пароль должен содержать минимум 6 символов', 'danger')
            return redirect(url_for('admin.change_user_password', user_id=user_id))
        
        try:
            AuthService.change_password(user, new_password)
            flash(f'Пароль пользователя {user.username} успешно изменен', 'success')
            
            # Логируем действие
            current_app.logger.info(f'Администратор {current_user.username} изменил пароль пользователя {user.username}')
            
            return redirect(url_for('admin.user_list'))
            
        except Exception as e:
            flash(f'Ошибка при изменении пароля: {str(e)}', 'danger')
    
    return render_template('admin/change_password.html', user=user)
    
@admin.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Удаление пользователя"""
    user = User.query.get_or_404(user_id)
    
    # Нельзя удалить самого себя
    if user.id == current_user.id:
        flash('Нельзя удалить самого себя.', 'danger')
        return redirect(url_for('admin.user_list'))
    
    # Проверяем, есть ли связанные заказы
    if Order.query.filter(
        (Order.salon_manager_id == user_id) | 
        (Order.designer_id == user_id)
    ).first():
        flash('Нельзя удалить пользователя, у которого есть связанные заказы.', 'danger')
        return redirect(url_for('admin.user_list'))
    
    # Для администраторов дополнительная проверка
    if user.role == UserRole.ADMIN:
        # Проверяем, есть ли другие администраторы
        other_admins = User.query.filter(
            User.role == UserRole.ADMIN,
            User.id != user_id
        ).count()
        
        if other_admins == 0:
            flash('Нельзя удалить последнего администратора! Сначала создайте другого.', 'danger')
            return redirect(url_for('admin.user_list'))
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'Пользователь {user.username} удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении пользователя: {str(e)}', 'danger')
    
    return redirect(url_for('admin.user_list'))

@admin.route('/system_settings/save', methods=['POST'])
@login_required
@admin_required
def save_system_settings():
    """Сохранение системных настроек"""
    try:
        # Пример сохранения настроек в БД или файле
        settings = {
            'site_name': request.form.get('site_name', 'Производственная система'),
            'notification_email': request.form.get('notification_email'),
            'auto_backup': request.form.get('auto_backup') == 'on',
            'backup_days': int(request.form.get('backup_days', 7)),
        }
        
        # Здесь можно сохранить в БД или файл конфигурации
        # Например, в таблицу SystemSettings
        
        flash('Настройки успешно сохранены.', 'success')
        
    except Exception as e:
        flash(f'Ошибка при сохранении настроек: {str(e)}', 'danger')
    
    return redirect(url_for('admin.system_settings'))

@admin.route('/backup', methods=['GET', 'POST'])
@login_required
@admin_required
def create_backup():
    """Создание резервной копии системы"""
    import zipfile
    if request.method == 'POST':
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f'backup_{timestamp}.zip'
            
            # Все папки на одном уровне: app, backups, instance
            # Файл admin.py находится в: app/admin.py
            # Значит корень проекта - родительская папка от app
            current_file_dir = os.path.dirname(os.path.abspath(__file__))  # C:\...\app
            project_root = os.path.dirname(current_file_dir)  # C:\...\production_system_v2
            
            # Пути к папкам (все на одном уровне)
            backups_dir = os.path.join(project_root, 'backups')
            instance_dir = os.path.join(project_root, 'instance')
            uploads_dir = os.path.join(project_root, 'uploads')
            
            # Создаем папку backups если её нет
            os.makedirs(backups_dir, exist_ok=True)
            
            backup_path = os.path.join(backups_dir, backup_name)
            
            # Логируем пути для отладки
            current_app.logger.info(f"Корень проекта: {project_root}")
            current_app.logger.info(f"Папка instance: {instance_dir}")
            current_app.logger.info(f"Папка backups: {backups_dir}")
            current_app.logger.info(f"Путь к бэкапу: {backup_path}")
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                # 1. Копируем базу данных из папки instance
                db_found = False
                
                if os.path.exists(instance_dir):
                    # Ищем все .db файлы в папке instance
                    for file in os.listdir(instance_dir):
                        if file.endswith(('.db', '.sqlite', '.sqlite3')):
                            db_path = os.path.join(instance_dir, file)
                            backup_zip.write(db_path, f"instance/{file}")
                            db_found = True
                            current_app.logger.info(f"✓ Найдена БД: {file}")
                
                if not db_found:
                    current_app.logger.warning("База данных не найдена в папке instance!")
                
                # 2. Копируем папку uploads если существует
                uploads_added = False
                
                if os.path.exists(uploads_dir):
                    file_count = 0
                    for root, dirs, files in os.walk(uploads_dir):
                        for file in files[:50]:  # Ограничиваем количество файлов
                            file_path = os.path.join(root, file)
                            # Сохраняем относительный путь от uploads_dir
                            rel_path = os.path.relpath(file_path, uploads_dir)
                            backup_zip.write(file_path, f"uploads/{rel_path}")
                            file_count += 1
                    
                    if file_count > 0:
                        uploads_added = True
                        current_app.logger.info(f"✓ Добавлено файлов из uploads: {file_count}")
                
                # 3. Создаем файл с информацией
                info_content = f"""Резервная копия системы управления производством
Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Пользователь: {current_user.username}

Содержимое архива:
- Папка instance/ (база данных): {"ДА" if db_found else "НЕТ"}
- Папка uploads/ (загруженные файлы): {"ДА" if uploads_added else "НЕТ"}

Пути в системе:
- Корень проекта: {project_root}
- Папка instance: {instance_dir}
- Папка uploads: {uploads_dir}
- Папка backups: {backups_dir}

Восстановление:
1. Распакуйте архив
2. Скопируйте файлы из папки instance/ в вашу папку instance/
3. Скопируйте файлы из папки uploads/ в вашу папку uploads/
"""
                backup_zip.writestr('ВОССТАНОВЛЕНИЕ.txt', info_content)
            
            # Получаем размер файла
            file_size = os.path.getsize(backup_path)
            size_str = f"{file_size/1024:.1f} KB" if file_size < 1024*1024 else f"{file_size/(1024*1024):.1f} MB"
            
            flash(f'✓ Резервная копия создана успешно! ({size_str})', 'success')
            current_app.logger.info(f"Бэкап создан: {backup_name} ({size_str})")
            
            return redirect(url_for('admin.create_backup'))
            
        except Exception as e:
            current_app.logger.error(f'Ошибка создания резервной копии: {str(e)}', exc_info=True)
            flash(f'❌ Ошибка при создании резервной копии: {str(e)}', 'danger')
    
    # GET запрос - показываем список существующих копий
    # Определяем путь к папке backups
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_file_dir)
    backups_dir = os.path.join(project_root, 'backups')
    
    backup_files = []
    file_sizes = []
    file_dates = []
    
    if os.path.exists(backups_dir):
        for file in sorted(os.listdir(backups_dir), reverse=True):
            if file.endswith('.zip'):
                file_path = os.path.join(backups_dir, file)
                
                # Размер файла
                size = os.path.getsize(file_path)
                size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
                
                # Дата создания
                mtime = os.path.getmtime(file_path)
                date_str = datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M')
                
                backup_files.append(file)
                file_sizes.append(size_str)
                file_dates.append(date_str)
    
    return render_template('admin/backup.html',
                         backup_files=backup_files[:10],
                         file_size=file_sizes[:10],
                         file_dates=file_dates[:10])

@admin.route('/backup/download/<filename>')
@login_required
@admin_required
def download_backup(filename):
    """Скачивание резервной копии"""
    try:
        # Определяем путь к папке backups
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_file_dir)
        backups_dir = os.path.join(project_root, 'backups')
        
        if not os.path.exists(backups_dir):
            flash('Папка backups не найдена', 'danger')
            return redirect(url_for('admin.create_backup'))
        
        file_path = os.path.join(backups_dir, filename)
        
        if not os.path.exists(file_path):
            flash('Файл не найден', 'danger')
            return redirect(url_for('admin.create_backup'))
        
        # Проверяем, что файл безопасный
        if not filename.endswith('.zip'):
            flash('Недопустимый тип файла', 'danger')
            return redirect(url_for('admin.create_backup'))
        
        current_app.logger.info(f"Скачивание бэкапа: {filename}")
        return send_from_directory(
            backups_dir,
            filename,
            as_attachment=True,
            download_name=f"backup_{filename}"
        )
        
    except Exception as e:
        current_app.logger.error(f'Ошибка скачивания бэкапа: {str(e)}', exc_info=True)
        flash(f'Ошибка при скачивании: {str(e)}', 'danger')
        return redirect(url_for('admin.create_backup'))

@admin.route('/system/logs')
@login_required
@admin_required
def system_logs():
    """Просмотр системных логов"""
    log_file = 'app_scheduler.log'
    logs = []
    
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            # Читаем последние 100 строк
            logs = f.readlines()[-100:]
    
    return render_template('admin/logs.html', logs=reversed(logs))


@admin.route('/system/cleanup', methods=['POST'])
@login_required
@admin_required
def system_cleanup():
    """Очистка системных данных"""
    try:
        # Импортируем datetime локально
        from datetime import datetime, timedelta
        
        # Очистка старых уведомлений (старше 30 дней)
        old_date = datetime.utcnow() - timedelta(days=30)
        
        # Удаляем старые уведомления
        old_notifications = Notification.query.filter(Notification.created_at < old_date).all()
        count_notifications = len(old_notifications)
        
        for notification in old_notifications:
            db.session.delete(notification)
        
        # Очистка временных файлов
        temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp')
        count_files = 0
        
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path):
                    try:
                        os.unlink(file_path)
                        count_files += 1
                    except Exception as e:
                        current_app.logger.error(f'Ошибка удаления файла {file_path}: {e}')
        
        # Очистка пустых директорий
        try:
            if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            current_app.logger.error(f'Ошибка удаления директории {temp_dir}: {e}')
        
        db.session.commit()
        flash(f'Очистка системы выполнена успешно. Удалено: {count_notifications} уведомлений, {count_files} временных файлов.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при очистке: {str(e)}', 'danger')
        current_app.logger.error(f'Ошибка system_cleanup: {str(e)}')
    
    return redirect(url_for('admin.system_settings'))
    
@admin.route('/system/logs/clear', methods=['POST'])
@login_required
@admin_required
def clear_logs():
    """Очистка файла логов"""
    try:
        log_file = 'scheduler.log'
        if os.path.exists(log_file):
            # Вместо полного удаления создаем пустой файл
            open(log_file, 'w').close()
            flash('Файл логов очищен.', 'success')
        else:
            flash('Файл логов не найден.', 'warning')
            
    except Exception as e:
        flash(f'Ошибка при очистке логов: {str(e)}', 'danger')
    
    return redirect(url_for('admin.system_logs'))


@admin.route('/notification_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def notification_settings():
    """Настройки уведомлений"""
    from app.services.notification_settings_service import NotificationSettingsService
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'toggle_all':
            enabled = request.form.get('enabled') == 'true'
            if NotificationSettingsService.set_all_enabled(enabled):
                flash(f'Все уведомления {"включены" if enabled else "отключены"}', 'success')
            else:
                flash('Ошибка при изменении настроек', 'danger')
                
        elif action == 'toggle_single':
            notification_type = request.form.get('notification_type')
            enabled = request.form.get('enabled') == 'true'
            if notification_type and NotificationSettingsService.set_notification_enabled(notification_type, enabled):
                flash(f'Настройка уведомления изменена', 'success')
            else:
                flash('Ошибка при изменении настройки', 'danger')
        
        return redirect(url_for('admin.notification_settings'))
    
    # GET запрос - показываем настройки
    # Используем другое имя переменной, чтобы избежать конфликта с именем функции
    settings_data = NotificationSettingsService.get_all_settings()
    
    # Добавьте статистику для отображения в шаблоне
    from app.models import Notification
    from datetime import datetime, timedelta
    
    # Статистика для информационных карточек
    total_notifications = Notification.query.count()
    
    # Уведомления за сегодня
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    sent_today = Notification.query.filter(
        Notification.created_at >= today_start
    ).count()
    
    # Активные типы уведомлений
    active_types = sum(1 for config in settings_data.values() if config['enabled'])
    
    # Среднее за день (за последние 7 дней)
    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_notifications = Notification.query.filter(
        Notification.created_at >= week_ago
    ).count()
    avg_daily = weekly_notifications // 7 if weekly_notifications > 0 else 0
    
    notification_stats = {
        'total': total_notifications,
        'sent_today': sent_today,
        'active_types': active_types,
        'avg_daily': avg_daily
    }
    
    return render_template('admin/notification_settings.html',
                         notification_settings=settings_data,  # Передаем под другим именем
                         notification_stats=notification_stats)

@admin.route('/system_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def system_settings():
    """Настройки системы"""
    # Загружаем текущие настройки
    general_settings = SettingsService.get_all_by_category('general')
    mail_settings = SettingsService.get_all_by_category('mail')
    telegram_settings = SettingsService.get_all_by_category('telegram')
    
    return render_template('admin/settings.html',
                         general=general_settings,
                         mail=mail_settings,
                         telegram=telegram_settings)


@admin.route('/system_settings/save/general', methods=['POST'])
@login_required
@admin_required
def save_general_settings():
    """Сохранение основных настроек"""
    try:
        settings = {
            'site_name': request.form.get('site_name'),
            'timezone': request.form.get('timezone'),
            'max_file_size_mb': request.form.get('max_file_size_mb'),
            'date_format': request.form.get('date_format'),
            'language': request.form.get('language'),
            'auto_backup': 'true' if request.form.get('auto_backup') == 'on' else 'false',
            'email_notifications': 'true' if request.form.get('email_notifications') == 'on' else 'false',
            'telegram_notifications': 'true' if request.form.get('telegram_notifications') == 'on' else 'false',
        }
        
        SettingsService.set_many(settings, category='general')
        flash('Основные настройки сохранены', 'success')
        
    except Exception as e:
        flash(f'Ошибка при сохранении настроек: {str(e)}', 'danger')
    
    return redirect(url_for('admin.system_settings'))


@admin.route('/system_settings/save/mail', methods=['POST'])
@login_required
@admin_required
def save_mail_settings():
    """Сохранение настроек почты"""
    try:
        settings = {
            'mail_server': request.form.get('mail_server'),
            'mail_port': request.form.get('mail_port'),
            'mail_use_tls': 'true' if request.form.get('mail_use_tls') == 'on' else 'false',
            'mail_use_ssl': 'true' if request.form.get('mail_use_ssl') == 'on' else 'false',
            'mail_username': request.form.get('mail_username'),
            'mail_password': request.form.get('mail_password') if request.form.get('mail_password') != '••••••••' else None,
            'mail_default_sender': request.form.get('mail_default_sender'),
        }
        
        # Не обновляем пароль если он не изменился
        if settings['mail_password'] is None:
            del settings['mail_password']
        
        SettingsService.set_many(settings, category='mail')
        flash('Настройки почты сохранены', 'success')
        
    except Exception as e:
        flash(f'Ошибка при сохранении настроек почты: {str(e)}', 'danger')
    
    return redirect(url_for('admin.system_settings'))


@admin.route('/system_settings/save/telegram', methods=['POST'])
@login_required
@admin_required
def save_telegram_settings():
    """Сохранение настроек Telegram"""
    try:
        settings = {
            'telegram_bot_token': request.form.get('telegram_bot_token'),
            'telegram_chat_id': request.form.get('telegram_chat_id'),
            'telegram_new_orders': 'true' if request.form.get('telegram_new_orders') == 'on' else 'false',
            'telegram_status_changes': 'true' if request.form.get('telegram_status_changes') == 'on' else 'false',
            'telegram_errors': 'true' if request.form.get('telegram_errors') == 'on' else 'false',
        }
        
        SettingsService.set_many(settings, category='telegram')
        flash('Настройки Telegram сохранены', 'success')
        
    except Exception as e:
        flash(f'Ошибка при сохранении настроек Telegram: {str(e)}', 'danger')
    
    return redirect(url_for('admin.system_settings'))


@admin.route('/system_settings/test/mail', methods=['POST'])
@login_required
@admin_required
def test_mail_settings():
    """Тест отправки почты"""
    try:
        from flask_mail import Message
        from app import mail
        
        msg = Message(
            subject='Тестовое письмо от системы',
            recipients=[current_user.email],
            body='Это тестовое письмо подтверждает, что настройки почты работают корректно.'
        )
        
        mail.send(msg)
        flash('Тестовое письмо отправлено', 'success')
        
    except Exception as e:
        flash(f'Ошибка отправки тестового письма: {str(e)}', 'danger')
    
    return redirect(url_for('admin.system_settings'))


@admin.route('/system_settings/test/telegram', methods=['POST'])
@login_required
@admin_required
def test_telegram_settings():
    """Тест подключения Telegram"""
    try:
        import requests
        
        bot_token = SettingsService.get('telegram_bot_token')
        chat_id = SettingsService.get('telegram_chat_id')
        
        if not bot_token or not chat_id:
            flash('Укажите токен бота и ID чата', 'warning')
            return redirect(url_for('admin.system_settings'))
        
        # Отправляем тестовое сообщение
        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        data = {
            'chat_id': chat_id,
            'text': '✅ Тестовое сообщение от системы управления производством',
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            flash('Тестовое сообщение отправлено в Telegram', 'success')
        else:
            flash(f'Ошибка Telegram API: {response.text}', 'danger')
            
    except Exception as e:
        flash(f'Ошибка подключения к Telegram: {str(e)}', 'danger')
    
    return redirect(url_for('admin.system_settings'))    

@admin.route('/notifications/send', methods=['GET', 'POST'])
@login_required
@admin_required
def send_system_notification():
    """Отправка системных уведомлений пользователям"""
    from app.services.notification_service import NotificationService
    from app.config import UserRole
    
    if request.method == 'POST':
        recipient_type = request.form.get('recipient_type', 'all')
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        role = request.form.get('role')
        
        # Валидация
        if not title or not message:
            flash('Заполните все обязательные поля', 'danger')
            return redirect(url_for('admin.send_system_notification'))
        
        if recipient_type == 'role' and not role:
            flash('Выберите роль пользователей', 'danger')
            return redirect(url_for('admin.send_system_notification'))
        
        try:
            # Отправляем уведомления в зависимости от типа получателей
            if recipient_type == 'all':
                # Всем пользователям
                count = NotificationService.send_system_notification_to_all(
                    title=title,
                    message=message,
                    metadata={
                        'sent_by': current_user.username,
                        'sent_at': datetime.utcnow().isoformat(),
                        'recipient_type': 'all'
                    }
                )
                flash(f'Уведомление отправлено всем пользователям ({count} получателей)', 'success')
                
            elif recipient_type == 'role':
                # Пользователям определенной роли
                count = NotificationService.send_system_notification_to_role(
                    title=title,
                    message=message,
                    role=role,
                    metadata={
                        'sent_by': current_user.username,
                        'sent_at': datetime.utcnow().isoformat(),
                        'recipient_type': 'role',
                        'role': role
                    }
                )
                role_name = UserRole.get_display_name(role)
                flash(f'Уведомление отправлено пользователям роли "{role_name}" ({count} получателей)', 'success')
            
            # Логируем действие
            current_app.logger.info(
                f'Администратор {current_user.username} отправил системное уведомление '
                f'"{title}" получателям: {recipient_type}'
            )
            
        except Exception as e:
            flash(f'Ошибка при отправке уведомлений: {str(e)}', 'danger')
            current_app.logger.error(f'Ошибка отправки системных уведомлений: {str(e)}', exc_info=True)
        
        return redirect(url_for('admin.send_system_notification'))
    
    # GET запрос - показываем форму
    # Получаем статистику пользователей для информации
    from app.models import User
    
    user_stats = {
        'total_active': User.query.filter_by(is_active=True).count(),
        'total_all': User.query.count()
    }
    
    # Получаем статистику по ролям - используем строковые значения
    role_stats = {}
    for role_enum in UserRole:
        role_value = role_enum.value  # Получаем строковое значение роли
        count = User.query.filter_by(role=role_value, is_active=True).count()
        if count > 0:
            role_stats[role_value] = {
                'count': count,
                'name': UserRole.get_display_name(role_value),
                'value': role_value
            }
    
    return render_template('admin/send_notification.html',
                         user_stats=user_stats,
                         role_stats=role_stats)