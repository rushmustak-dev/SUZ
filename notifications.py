# production_system_v2/app/notifications.py
"""
Маршруты для работы с уведомлениями
"""

from flask import render_template, jsonify, request, Blueprint
from flask_login import login_required, current_user
from app import db
from app.models import Notification
from app.services.notification_service import NotificationService
from app.config import UserRole
from datetime import datetime, timedelta  # ДОБАВЬТЕ ЭТОТ ИМПОРТ
import json

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/')
@login_required
def notifications_list():
    """Страница со всеми уведомлениями"""
    page = request.args.get('page', 1, type=int)
    show_all = request.args.get('show_all', 'false').lower() == 'true'
    
    # Получаем уведомления
    if show_all:
        query = Notification.query.filter_by(user_id=current_user.id)
    else:
        query = Notification.query.filter_by(user_id=current_user.id, is_read=False)
    
    notifications = query.order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    # Статистика
    stats = NotificationService.get_notification_stats(current_user.id)
    
    return render_template('notifications/list.html',
                         notifications=notifications,
                         show_all=show_all,
                         stats=stats)


@notifications_bp.route('/api/unread')
@login_required
def api_unread_notifications():
    """API для получения непрочитанных уведомлений (для dropdown)"""
    limit = request.args.get('limit', 5, type=int)
    notifications = NotificationService.get_unread_notifications(current_user.id, limit)
    
    notifications_data = []
    for notification in notifications:
        # Парсим details из JSON если они есть
        metadata = {}
        if notification.details:
            try:
                metadata = json.loads(notification.details)
            except:
                metadata = {'raw': str(notification.details)}
        
        # Форматируем дату для отображения
        created_at = notification.created_at
        now = datetime.now()
        
        # Если сегодня - показываем только время
        if created_at.date() == now.date():
            time_str = created_at.strftime('%H:%M')
        # Если вчера - показываем "вчера"
        elif created_at.date() == (now.date() - timedelta(days=1)):
            time_str = 'вчера'
        # Если в этом году - показываем дату без года
        elif created_at.year == now.year:
            time_str = created_at.strftime('%d.%m')
        # Иначе - полная дата
        else:
            time_str = created_at.strftime('%d.%m.%Y')
        
        notifications_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'icon': NotificationService.NOTIFICATION_ICONS.get(
                notification.notification_type, 'bi-bell'
            ),
            'color': NotificationService.NOTIFICATION_COLORS.get(
                notification.notification_type, 'secondary'
            ),
            'created_at': time_str,  # Форматированная дата для отображения
            'created_at_full': created_at.strftime('%Y-%m-%d %H:%M:%S'),  # Полная дата для сортировки
            'created_at_iso': created_at.isoformat(),  # ISO формат для JS
            'is_read': notification.is_read,
            'order_id': notification.order_id,
            'metadata': metadata
        })
    
    # Получаем общее количество непрочитанных
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({
        'success': True,
        'count': len(notifications_data),
        'unread_count': unread_count,
        'notifications': notifications_data
    })


@notifications_bp.route('/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_as_read(notification_id):
    """Пометить уведомление как прочитанное"""
    if NotificationService.mark_as_read(notification_id, current_user.id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Уведомление не найдено'}), 404


@notifications_bp.route('/read-all', methods=['POST'])
@login_required
def mark_all_as_read():
    """Пометить все уведомления как прочитанные"""
    count = NotificationService.mark_all_as_read(current_user.id)
    return jsonify({'success': True, 'count': count})


@notifications_bp.route('/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """Удалить уведомление"""
    if NotificationService.delete_notification(notification_id, current_user.id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Уведомление не найдено'}), 404


@notifications_bp.route('/delete-read', methods=['POST'])
@login_required
def delete_all_read():
    """Удалить все прочитанные уведомления"""
    count = NotificationService.delete_all_read(current_user.id)
    return jsonify({'success': True, 'count': count})


@notifications_bp.route('/api/stats')
@login_required
def api_notification_stats():
    """API для получения статистики"""
    stats = NotificationService.get_notification_stats(current_user.id)
    return jsonify(stats)