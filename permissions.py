# production_system_v2/app/permissions.py
"""
Система проверки прав для статусов
"""

from functools import wraps
from flask import flash, redirect, url_for, request, abort
from flask_login import current_user
from app.config import Config, OrderStatus, UserRole


# production_system_v2/app/permissions.py
def check_status_permission(old_status, new_status, user):
    """Проверка разрешения на изменение статуса"""
    # Преобразуем статусы к строковым значениям
    old_str = old_status.value if hasattr(old_status, 'value') else str(old_status)
    new_str = new_status.value if hasattr(new_status, 'value') else str(new_status)
    
    # Администратор может всё
    if user.role == UserRole.ADMIN:
        return True
    
    # Директор может менять любые статусы начиная с purchase_completed, пропуская этапы
    if user.role == UserRole.DIRECTOR:
        # Все статусы, доступные директору
        director_statuses = {
            'purchase_completed',
            'manufacturing',
            'installation',
            'quality_check',
            'return_to_design',
            'ready_for_delivery',
            'delivered',
            'completed',
            'archived',
            'reclamation'
        }
        
        # Директор может:
        # 1. Из любого director_statuses в любой другой director_statuses (кроме себя)
        # 2. Пропускать сколько угодно этапов
        
        if old_str in director_statuses and new_str in director_statuses:
            return True
        
        return False
    
    # Конструктор может работать только со своими заказами
    if user.role == UserRole.DESIGNER:
        allowed_for_designer = [
            ('design_client_approved', 'in_design'),
            ('in_design', 'design_completed'),
            ('return_to_design', 'in_design'),
            ('new', 'design'),
            ('design', 'design_review'),
            ('return_to_design', 'design_review'),
        ]
        return (old_str, new_str) in allowed_for_designer  # ИСПРАВЛЕНО: используем строки!
    
    # Руководитель конструкторов тоже может переводить DESIGN -> DESIGN_REVIEW
    if (old_str == 'design' and 
        new_str == 'design_review' and 
        user.role == UserRole.HEAD_DESIGNER):
        return True
    
    # ДЛЯ ВСЕХ ОСТАЛЬНЫХ РОЛЕЙ ИСПОЛЬЗУЕМ КОНФИГУРАЦИЮ ИЗ Config.STATUS_PERMISSIONS
    from app.config import Config
    
    # Проверяем, есть ли такой переход в разрешенных
    if (old_str, new_str) not in Config.STATUS_PERMISSIONS:
        return False
    
    # Получаем роли, которым разрешен этот переход
    allowed_roles = Config.STATUS_PERMISSIONS.get((old_str, new_str), [])
    
    return user.role in allowed_roles


def status_change_required(f):
    """Декоратор для проверки прав изменения статуса"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Пожалуйста, войдите в систему.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        # Получаем заказ из параметров
        from app.models import Order
        order_id = kwargs.get('order_id')
        order = Order.query.get_or_404(order_id)
        
        # Проверяем права
        new_status = request.form.get('status')
        if not check_status_permission(order.status, new_status, current_user):
            flash('У вас нет прав для изменения этого статуса.', 'danger')
            return redirect(url_for('main.order_detail', order_id=order_id))
        
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """Декоратор для проверки ролей"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Пожалуйста, войдите в систему.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.role not in roles and current_user.role != UserRole.ADMIN:
                flash('У вас нет прав для доступа к этой странице.', 'danger')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Добавить функцию проверки прав удаления:

def can_delete_order(user, order):
    """Проверка прав на удаление заказа"""
    # Администратор может удалять любые заказы
    if user.role == UserRole.ADMIN:
        return True
    
    # Начальник цеха может удалять только заказы в статусах производства
    if user.role == UserRole.HEAD_PRODUCTION:
        return order.status in [
            OrderStatus.MANUFACTURING.value,
            OrderStatus.INSTALLATION.value,
            OrderStatus.QUALITY_CHECK.value,
            OrderStatus.READY_FOR_DELIVERY.value
        ]
    
    return False


def delete_order_required(f):
    """Декоратор для проверки прав удаления заказа"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Пожалуйста, войдите в систему.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        # Получаем заказ из параметров
        from app.models import Order
        order_id = kwargs.get('order_id')
        order = Order.query.get_or_404(order_id)
        
        # Проверяем права
        if not can_delete_order(current_user, order):
            flash('У вас нет прав для удаления этого заказа.', 'danger')
            return redirect(url_for('main.order_detail', order_id=order_id))
        
        return f(*args, **kwargs)
    return decorated_function

# Специальные декораторы для ролей
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def admin_or_director_required(f):
    """Декоратор для проверки прав администратора или директора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in [UserRole.ADMIN.value, UserRole.DIRECTOR.value]:
            flash('У вас нет прав для выполнения этого действия.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def head_designer_required(f):
    return role_required(UserRole.HEAD_DESIGNER, UserRole.ADMIN)(f)

def salon_manager_required(f):
    """Разрешить не только менеджеров, но и админов, директоров, руководителей"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))
        if current_user.role not in [UserRole.SALON_MANAGER, UserRole.ADMIN, 
                                     UserRole.DIRECTOR, UserRole.SALON_HEAD]:
            flash('У вас нет прав для этой операции.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def designer_required(f):
    return role_required(UserRole.DESIGNER, UserRole.HEAD_DESIGNER, UserRole.ADMIN)(f)

def head_supply_required(f):
    return role_required(UserRole.HEAD_SUPPLY, UserRole.ADMIN)(f)

def head_production_required(f):
    return role_required(UserRole.HEAD_PRODUCTION, UserRole.ADMIN)(f)

def quality_control_required(f):
    return role_required(UserRole.QUALITY_CONTROL, UserRole.ADMIN)(f)
    
def director_required(f):
    """Декоратор для проверки роли директора или администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Пожалуйста, войдите в систему.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if current_user.role not in [UserRole.DIRECTOR, UserRole.ADMIN, UserRole.HEAD_DESIGN]:
            flash('У вас нет прав для доступа к этой странице.', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function

def salon_head_required(f):
    """Декоратор для проверки роли руководителя салона и выше"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Пожалуйста, войдите в систему.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        allowed_roles = [UserRole.SALON_HEAD, UserRole.DIRECTOR, UserRole.ADMIN]
        if current_user.role not in allowed_roles:
            flash('У вас нет прав для доступа к этой странице.', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function
