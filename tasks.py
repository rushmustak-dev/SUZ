# production_system_v2/app/tasks.py
"""
Фоновые задачи для архивации и автоматических операций
"""

from datetime import datetime, timedelta
from app import db
from app.models import Order, User, OrderStatusHistory, Notification
from app.config import OrderStatus
import logging

logger = logging.getLogger(__name__)

def auto_archive_completed_orders():
    """
    Автоматическая архивация завершенных заказов через 7 дней
    Возвращает количество архивированных заказов
    """
    try:
        logger.info("Запуск задачи автоматической архивации...")
        
        # Находим системного пользователя (администратора)
        system_user = User.query.filter_by(role='admin').first()
        if not system_user:
            logger.warning("Не найден системный пользователь для архивации")
            return 0
        
        # Находим заказы, завершенные более 7 дней назад и не архивные
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        orders_to_archive = Order.query.filter(
            Order.status == OrderStatus.COMPLETED,
            Order.is_archived == False,
            Order.is_deleted == False,
            Order.updated_at < cutoff_date,
            Order.updated_at.isnot(None)  # Убеждаемся, что есть дата обновления
        ).all()
        
        archived_count = 0
        errors = []
        
        logger.info(f"Найдено {len(orders_to_archive)} заказов для архивации")
        
        for order in orders_to_archive:
            try:
                # Архивируем заказ
                order.is_archived = True
                order.archived_at = datetime.utcnow()
                order.status = OrderStatus.ARCHIVED
                
                # Запись в историю
                history = OrderStatusHistory(
                    order_id=order.id,
                    old_status=OrderStatus.COMPLETED,
                    new_status=OrderStatus.ARCHIVED,
                    changed_by_id=system_user.id,
                    notes="Автоматическая архивация через 7 дней после завершения"
                )
                db.session.add(history)
                
                # Создаем уведомление для менеджера
                notification = Notification(
                    order_id=order.id,
                    user_id=order.salon_manager_id,
                    notification_type='order_archived',
                    title=f'Заказ архивирован: {order.order_number}',
                    message=f'Заказ {order.order_number} автоматически перемещен в архив спустя 7 дней после завершения.',
                    details={'order_id': order.id}
                )
                db.session.add(notification)
                
                archived_count += 1
                
                logger.info(f"Заказ {order.order_number} автоматически архивирован")
                
            except Exception as e:
                errors.append(f"Заказ {order.order_number}: {str(e)}")
                logger.error(f"Ошибка при архивации заказа {order.order_number}: {str(e)}")
                db.session.rollback()
        
        # Сохраняем изменения
        if archived_count > 0:
            db.session.commit()
            logger.info(f"Автоматически архивировано {archived_count} заказов")
        
        if errors:
            logger.error(f"Ошибки при архивации: {', '.join(errors)}")
            
        return archived_count
            
    except Exception as e:
        logger.error(f"Ошибка в задаче автоматической архивации: {str(e)}")
        db.session.rollback()
        return 0

def cleanup_old_notifications():
    """
    Очистка старых прочитанных уведомлений (старше 30 дней)
    Возвращает количество удаленных уведомлений
    """
    try:
        logger.info("Запуск задачи очистки старых уведомлений...")
        
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        # Удаляем прочитанные уведомления старше 30 дней
        deleted_count = Notification.query.filter(
            Notification.is_read == True,
            Notification.created_at < cutoff_date
        ).delete()
        
        db.session.commit()
        
        if deleted_count > 0:
            logger.info(f"Удалено {deleted_count} старых уведомлений")
        else:
            logger.info("Нет старых уведомлений для удаления")
            
        return deleted_count
            
    except Exception as e:
        logger.error(f"Ошибка при очистке уведомлений: {str(e)}")
        db.session.rollback()
        return 0

def check_overdue_orders():
    """
    Проверка и уведомление о просроченных заказах
    Возвращает количество созданных уведомлений
    """
    try:
        logger.info("Запуск задачи проверки просроченных заказов...")
        
        today = datetime.utcnow().date()
        notification_count = 0
        
        # Находим заказы с просроченными сроками
        overdue_orders = Order.query.filter(
            Order.deadline_date.isnot(None),
            db.func.date(Order.deadline_date) < today,
            Order.status.notin_([
                OrderStatus.COMPLETED, 
                OrderStatus.ARCHIVED, 
                OrderStatus.DELIVERED,
                OrderStatus.RECLAMATION
            ]),
            Order.is_deleted == False,
            Order.is_archived == False
        ).all()
        
        logger.info(f"Найдено {len(overdue_orders)} просроченных заказов")
        
        for order in overdue_orders:
            try:
                # Проверяем, есть ли уже уведомление о просрочке за последние 3 дня
                three_days_ago = datetime.utcnow() - timedelta(days=3)
                existing_notification = Notification.query.filter(
                    Notification.order_id == order.id,
                    Notification.notification_type == 'order_overdue',
                    Notification.created_at > three_days_ago
                ).first()
                
                if not existing_notification:
                    # Создаем уведомление для менеджера
                    notification = Notification(
                        order_id=order.id,
                        user_id=order.salon_manager_id,
                        notification_type='order_overdue',
                        title=f'ПРОСРОЧЕН СРОК: {order.order_number}',
                        message=f'Срок выполнения заказа {order.order_number} был {order.deadline_date.strftime("%d.%m.%Y")}. Заказ просрочен на {(today - order.deadline_date.date()).days} дней.',
                        details={
                            'order_id': order.id,
                            'order_number': order.order_number,
                            'deadline_date': order.deadline_date.isoformat() if order.deadline_date else None,
                            'days_overdue': (today - order.deadline_date.date()).days
                        }
                    )
                    db.session.add(notification)
                    notification_count += 1
                    
                    logger.info(f"Создано уведомление о просрочке для заказа {order.order_number}")
            
            except Exception as e:
                logger.error(f"Ошибка при создании уведомления для заказа {order.id}: {str(e)}")
        
        db.session.commit()
        
        logger.info(f"Создано {notification_count} уведомлений о просрочке")
        return notification_count
        
    except Exception as e:
        logger.error(f"Ошибка при проверке просроченных заказов: {str(e)}")
        db.session.rollback()
        return 0

def check_design_ready_dates():
    """
    Проверка приближающихся сроков готовности чертежей
    Уведомляет конструкторов за 2 дня до дедлайна
    """
    try:
        logger.info("Запуск задачи проверки сроков готовности чертежей...")
        
        today = datetime.utcnow().date()
        two_days_later = today + timedelta(days=2)
        notification_count = 0
        
        # Находим заказы, у которых срок готовности чертежей через 2 дня
        orders = Order.query.filter(
            Order.design_ready_date.isnot(None),
            db.func.date(Order.design_ready_date) == two_days_later,
            Order.status.in_([OrderStatus.IN_DESIGN, OrderStatus.DESIGN]),
            Order.is_deleted == False,
            Order.is_archived == False,
            Order.designer_id.isnot(None)
        ).all()
        
        logger.info(f"Найдено {len(orders)} заказов с приближающимся сроком чертежей")
        
        for order in orders:
            try:
                # Создаем уведомление для конструктора
                notification = Notification(
                    order_id=order.id,
                    user_id=order.designer_id,
                    notification_type='design_deadline_approaching',
                    title=f'СРОК ЧЕРТЕЖЕЙ: {order.order_number}',
                    message=f'Срок готовности чертежей по заказу {order.order_number} - {order.design_ready_date.strftime("%d.%m.%Y")} (осталось 2 дня).',
                    details={
                        'order_id': order.id,
                        'order_number': order.order_number,
                        'design_ready_date': order.design_ready_date.isoformat() if order.design_ready_date else None,
                        'days_left': 2
                    }
                )
                db.session.add(notification)
                notification_count += 1
                
                logger.info(f"Создано уведомление о сроке чертежей для заказа {order.order_number}")
            
            except Exception as e:
                logger.error(f"Ошибка при создании уведомления для конструктора заказа {order.id}: {str(e)}")
        
        db.session.commit()
        
        logger.info(f"Создано {notification_count} уведомлений о сроках чертежей")
        return notification_count
        
    except Exception as e:
        logger.error(f"Ошибка при проверке сроков готовности чертежей: {str(e)}")
        db.session.rollback()
        return 0

def send_daily_statistics():
    """
    Отправка ежедневной статистики администраторам
    """
    try:
        logger.info("Запуск задачи отправки ежедневной статистики...")
        
        from app.services.mail_service import MailService
        
        # Находим всех администраторов
        admins = User.query.filter_by(role='admin', is_active=True).all()
        
        if not admins:
            logger.warning("Не найдены активные администраторы для отправки статистики")
            return 0
        
        # Собираем статистику за вчерашний день
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        today = datetime.utcnow().date()
        
        # Статистика по заказам
        new_orders = Order.query.filter(
            db.func.date(Order.created_at) == yesterday,
            Order.is_deleted == False
        ).count()
        
        completed_orders = Order.query.filter(
            db.func.date(Order.updated_at) == yesterday,
            Order.status == OrderStatus.COMPLETED,
            Order.is_deleted == False
        ).count()
        
        # Статистика по статусам
        status_stats = {}
        for status in [OrderStatus.NEW, OrderStatus.DESIGN, OrderStatus.MANUFACTURING, OrderStatus.DELIVERED]:
            status_stats[status] = Order.query.filter(
                Order.status == status,
                Order.is_deleted == False,
                Order.is_archived == False
            ).count()
        
        # Формируем отчет
        report = f"""
Ежедневная статистика за {yesterday.strftime('%d.%m.%Y')}

📊 Общая статистика:
• Новых заказов: {new_orders}
• Завершенных заказов: {completed_orders}

📈 Текущие заказы по статусам:
• НОВЫЙ: {status_stats.get(OrderStatus.NEW, 0)}
• В разработке: {status_stats.get(OrderStatus.DESIGN, 0) + status_stats.get(OrderStatus.IN_DESIGN, 0)}
• В производстве: {status_stats.get(OrderStatus.MANUFACTURING, 0)}
• Отгружено: {status_stats.get(OrderStatus.DELIVERED, 0)}

💼 Всего активных заказов: {sum(status_stats.values())}
"""
        
        # Отправляем каждому администратору
        sent_count = 0
        for admin in admins:
            if admin.email:
                try:
                    MailService.send_email(
                        recipient=admin.email,
                        subject=f'Ежедневная статистика за {yesterday.strftime("%d.%m.%Y")}',
                        body=report,
                        html_body=f"<pre>{report}</pre>"
                    )
                    sent_count += 1
                    logger.info(f"Статистика отправлена администратору {admin.email}")
                except Exception as e:
                    logger.error(f"Ошибка отправки статистики администратору {admin.email}: {str(e)}")
        
        logger.info(f"Отправлено {sent_count} отчетов с ежедневной статистикой")
        return sent_count
        
    except Exception as e:
        logger.error(f"Ошибка при отправке ежедневной статистики: {str(e)}")
        return 0