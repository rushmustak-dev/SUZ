# production_system_v2/commands.py
"""
CLI команды для управления задачами и архивацией
"""

import click
from flask.cli import with_appcontext
from datetime import datetime, timedelta
from app import db
from app.models import Order, User, OrderStatusHistory, Notification
from app.config import OrderStatus
from app.tasks import (
    auto_archive_completed_orders,
    cleanup_old_notifications,
    check_overdue_orders,
    check_design_ready_dates,
    send_daily_statistics
)


@click.group()
def tasks():
    """Команды для управления фоновыми задачами"""
    pass


@tasks.command('run-all')
@with_appcontext
def run_all_tasks():
    """Запуск всех фоновых задач"""
    click.echo("🚀 Запуск всех фоновых задач...")
    
    results = {}
    
    click.echo("1. Автоматическая архивация заказов...")
    results['archive'] = auto_archive_completed_orders()
    
    click.echo("2. Очистка старых уведомлений...")
    results['cleanup'] = cleanup_old_notifications()
    
    click.echo("3. Проверка просроченных заказов...")
    results['overdue'] = check_overdue_orders()
    
    click.echo("4. Проверка сроков чертежей...")
    results['design_dates'] = check_design_ready_dates()
    
    click.echo("5. Отправка ежедневной статистики...")
    results['statistics'] = send_daily_statistics()
    
    click.echo("\n📊 Результаты выполнения задач:")
    click.echo(f"• Архивировано заказов: {results['archive']}")
    click.echo(f"• Удалено уведомлений: {results['cleanup']}")
    click.echo(f"• Создано уведомлений о просрочке: {results['overdue']}")
    click.echo(f"• Создано уведомлений о чертежах: {results['design_dates']}")
    click.echo(f"• Отправлено отчетов статистики: {results['statistics']}")


@tasks.command('archive')
@click.option('--force', is_flag=True, help='Архивировать все завершенные заказы независимо от даты')
@with_appcontext
def archive_command(force):
    """Ручной запуск архивации заказов"""
    if force:
        click.echo("⚠️  Режим FORCE: архивация всех завершенных заказов")
        
        orders_to_archive = Order.query.filter(
            Order.status == OrderStatus.COMPLETED,
            Order.is_archived == False,
            Order.is_deleted == False
        ).all()
        
        archived_count = 0
        
        for order in orders_to_archive:
            try:
                order.is_archived = True
                order.archived_at = datetime.utcnow()
                order.status = OrderStatus.ARCHIVED
                
                # Запись в историю
                history = OrderStatusHistory(
                    order_id=order.id,
                    old_status=OrderStatus.COMPLETED,
                    new_status=OrderStatus.ARCHIVED,
                    changed_by_id=1,  # Системный пользователь
                    notes="Ручная архивация (force mode)"
                )
                db.session.add(history)
                
                archived_count += 1
                click.echo(f"✓ Заказ {order.order_number} архивирован")
                
            except Exception as e:
                click.echo(f"✗ Ошибка при архивации заказа {order.order_number}: {str(e)}")
                db.session.rollback()
        
        if archived_count > 0:
            db.session.commit()
            click.echo(f"\n✅ Успешно архивировано {archived_count} заказов")
        else:
            click.echo("\nℹ️  Нет заказов для архивации")
    
    else:
        click.echo("🔄 Запуск автоматической архивации...")
        result = auto_archive_completed_orders()
        click.echo(f"✅ Автоматически архивировано {result} заказов")


@tasks.command('check-overdue')
@with_appcontext
def check_overdue_command():
    """Проверка просроченных заказов"""
    click.echo("🔍 Проверка просроченных заказов...")
    result = check_overdue_orders()
    click.echo(f"✅ Создано {result} уведомлений о просрочке")


@tasks.command('cleanup-notifications')
@click.option('--days', default=30, help='Удалять уведомления старше N дней')
@with_appcontext
def cleanup_notifications_command(days):
    """Очистка старых уведомлений"""
    click.echo(f"🗑️  Очистка уведомлений старше {days} дней...")
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    deleted_count = Notification.query.filter(
        Notification.is_read == True,
        Notification.created_at < cutoff_date
    ).delete()
    
    db.session.commit()
    
    click.echo(f"✅ Удалено {deleted_count} старых уведомлений")


@tasks.command('stats')
@with_appcontext
def stats_command():
    """Отправка статистики"""
    click.echo("📊 Отправка ежедневной статистики...")
    result = send_daily_statistics()
    click.echo(f"✅ Отправлено {result} отчетов с статистикой")


@tasks.command('list-jobs')
def list_jobs_command():
    """Список запланированных задач"""
    from app import scheduler
    
    if not scheduler.running:
        click.echo("Планировщик задач не запущен")
        return
    
    jobs = scheduler.get_jobs()
    
    if not jobs:
        click.echo("Нет запланированных задач")
        return
    
    click.echo(f"📅 Запланировано {len(jobs)} задач:\n")
    
    for i, job in enumerate(jobs, 1):
        click.echo(f"{i}. {job.name}")
        click.echo(f"   ID: {job.id}")
        click.echo(f"   Триггер: {job.trigger}")
        click.echo(f"   Следующее выполнение: {job.next_run_time}")
        click.echo()


# Регистрация команд
def init_app(app):
    app.cli.add_command(tasks)


# Команды для архивации (сохраняем из предыдущего ответа)
@click.command('archive-orders')
@click.option('--days', default=7, help='Через сколько дней архивировать заказы')
@with_appcontext
def archive_orders_command(days):
    """Ручная архивация завершенных заказов"""
    # ... (оставляем предыдущую реализацию)


@click.command('restore-from-archive')
@click.argument('order_number')
@click.option('--reason', required=True, help='Причина восстановления (рекламация)')
@with_appcontext
def restore_from_archive_command(order_number, reason):
    """Восстановление заказа из архива"""
    # ... (оставляем предыдущую реализацию)


def init_app(app):
    app.cli.add_command(tasks)
    app.cli.add_command(archive_orders_command)
    app.cli.add_command(restore_from_archive_command)