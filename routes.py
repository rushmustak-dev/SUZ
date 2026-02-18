# production_system_v2/app/routes.py
"""
Основные маршруты системы
"""

from flask import (
    render_template, redirect, url_for, flash, request, Blueprint, 
    jsonify, send_from_directory, send_file, session, current_app, abort
)
from flask_login import login_required, current_user
from app import db
from app.models import User, Order, OrderStatusHistory, OrderFile, Notification, Client
from app.config import OrderStatus, UserRole
from app.permissions import (
    admin_required, head_designer_required, salon_manager_required,
    designer_required, head_supply_required, head_production_required,
    quality_control_required, status_change_required, delete_order_required
)
from app.services.order_service import OrderService
from app.services.notification_service import NotificationService
from app.services.file_service import FileService
from app.forms import OrderForm, ChangePasswordForm, UploadFileForm, CommentForm, OrderEditForm, SellerForm, ClientForm, ClientSearchForm
import os
from datetime import datetime, timedelta
from werkzeug.security import safe_join
from app.services.archive_service import ArchiveService
from app.models import Seller
from app.services.schedule_service import ScheduleService

main = Blueprint('main', __name__)


# ========== НОВЫЕ МАРШРУТЫ: КЛИЕНТЫ ==========

@main.route('/clients')
@login_required
def client_list():
    """Список клиентов"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    per_page = 20
    
    query = Client.query.order_by(Client.full_name)
    
    if search:
        query = query.filter(
            (Client.full_name.contains(search)) |
            (Client.phone.contains(search)) |
            (Client.email.contains(search))
        )
    
    clients = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('clients/list.html',
                         clients=clients,
                         search=search)


@main.route('/clients/create', methods=['GET', 'POST'])
@login_required
def client_create():
    """Создание нового клиента"""
    form = ClientForm()
    
    if form.validate_on_submit():
        try:
            client = Client(
                full_name=form.full_name.data,
                phone=form.phone.data,
                email=form.email.data,
                address=form.address.data,
                passport_data=form.passport_data.data,
                inn=form.inn.data,
                comment=form.comment.data
            )
            
            db.session.add(client)
            db.session.commit()
            
            flash(f'Клиент {client.full_name} успешно создан', 'success')
            return redirect(url_for('main.client_view', client_id=client.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании клиента: {str(e)}', 'danger')
    
    return render_template('clients/create.html', form=form)


@main.route('/clients/<int:client_id>')
@login_required
def client_view(client_id):
    """Просмотр клиента"""
    client = Client.query.get_or_404(client_id)
    
    # Получаем заказы клиента
    orders = Order.query.filter_by(client_id=client.id, is_deleted=False).order_by(Order.created_at.desc()).all()
    
    return render_template('clients/view.html',
                         client=client,
                         orders=orders,
                         OrderStatus=OrderStatus)


@main.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
@login_required
def client_edit(client_id):
    """Редактирование клиента"""
    client = Client.query.get_or_404(client_id)
    form = ClientForm(obj=client)
    
    if form.validate_on_submit():
        try:
            client.full_name = form.full_name.data
            client.phone = form.phone.data
            client.email = form.email.data
            client.address = form.address.data
            client.passport_data = form.passport_data.data
            client.inn = form.inn.data
            client.comment = form.comment.data
            
            db.session.commit()
            
            flash('Клиент успешно обновлен', 'success')
            return redirect(url_for('main.client_view', client_id=client.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении клиента: {str(e)}', 'danger')
    
    return render_template('clients/edit.html', form=form, client=client)

@main.route('/api/clients/<int:client_id>')
@login_required
def client_get_api(client_id):
    """API для получения данных клиента по ID"""
    client = Client.query.get_or_404(client_id)
    
    # Подсчет заказов клиента (не удаленных)
    orders_count = Order.query.filter_by(
        client_id=client.id, 
        is_deleted=False
    ).count()
    
    return jsonify({
        'success': True,
        'client': {
            'id': client.id,
            'full_name': client.full_name,
            'phone': client.phone,
            'email': client.email or '',
            'address': client.address or '',
            'passport_data': client.passport_data or '',
            'inn': client.inn or '',
            'comment': client.comment or '',
            'orders_count': orders_count
        }
    })

@main.route('/clients/<int:client_id>/delete', methods=['POST'])
@login_required
@admin_required
def client_delete(client_id):
    """Удаление клиента (только админ)"""
    client = Client.query.get_or_404(client_id)
    
    # Проверяем, есть ли заказы у клиента
    orders_count = Order.query.filter_by(client_id=client.id, is_deleted=False).count()
    if orders_count > 0:
        flash(f'Невозможно удалить клиента. У него есть {orders_count} заказ(ов).', 'danger')
        return redirect(url_for('main.client_list'))
    
    try:
        # Сохраняем имя для сообщения
        client_name = client.full_name
        
        # Удаляем клиента
        db.session.delete(client)
        db.session.commit()
        
        flash(f'Клиент {client_name} успешно удален', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка при удалении клиента {client_id}: {str(e)}")
        flash(f'Ошибка при удалении клиента: {str(e)}', 'danger')
    
    return redirect(url_for('main.client_list'))


@main.route('/api/clients/search')
@login_required
def client_search_api():
    """API для поиска клиентов (AJAX)"""
    search = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    
    if len(search) < 2:
        return jsonify({'success': True, 'clients': []})
    
    clients = Client.query.filter(
        (Client.full_name.contains(search)) |
        (Client.phone.contains(search)) |
        (Client.email.contains(search))
    ).limit(limit).all()
    
    result = []
    for c in clients:
        result.append({
            'id': c.id,
            'full_name': c.full_name,
            'phone': c.phone,
            'email': c.email,
            'address': c.address,
            'orders_count': c.orders.count()
        })
    
    return jsonify({'success': True, 'clients': result})


@main.route('/orders/trash')
@login_required
@admin_required
def order_trash():
    """Корзина с удаленными заказами (только для администратора)"""
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    query = Order.query.filter(Order.is_deleted == True)
    
    if search:
        query = query.filter(
            (Order.order_number.contains(search)) |
            (Order.customer_name.contains(search)) |
            (Order.customer_phone.contains(search))
        )
    
    query = query.order_by(Order.deleted_at.desc())
    
    deleted_orders = query.paginate(page=page, per_page=20, error_out=False)
    
    return render_template('orders/trash.html',
                         deleted_orders=deleted_orders,
                         search=search,
                         OrderStatus=OrderStatus)


@main.route('/orders/<int:order_id>/delete', methods=['GET', 'POST'])
@login_required
@delete_order_required
def delete_order(order_id):
    """Удаление заказа"""
    order = Order.query.get_or_404(order_id)
    
    if request.method == 'GET':
        return render_template('orders/delete_confirm.html',
                             order=order,
                             OrderStatus=OrderStatus)
    
    deletion_reason = request.form.get('deletion_reason', '').strip()
    
    if not deletion_reason:
        flash('Укажите причину удаления заказа', 'danger')
        return redirect(url_for('main.delete_order', order_id=order_id))
    
    try:
        old_order_number = order.order_number
        
        order.is_deleted = True
        order.deleted_at = datetime.utcnow()
        order.deleted_by_id = current_user.id
        order.deletion_reason = deletion_reason
        
        order.order_number = f"DELETED_{order.order_number}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        history = OrderStatusHistory(
            order_id=order.id,
            old_status=order.status,
            new_status="DELETED",
            changed_by_id=current_user.id,
            notes=f"Заказ удален. Причина: {deletion_reason}"
        )
        db.session.add(history)
        
        db.session.commit()
        
        if current_user.role == UserRole.HEAD_PRODUCTION:
            admins = User.query.filter_by(role=UserRole.ADMIN).all()
            for admin in admins:
                NotificationService.create_notification(
                    admin.id,
                    'system',
                    f'Заказ удален начальником цеха: {old_order_number}',
                    f'Начальник цеха {current_user.username} удалил заказ {old_order_number}. Причина: {deletion_reason}',
                    order.id,
                    metadata={'deleted_by': current_user.username, 'deletion_reason': deletion_reason}
                )
        
        flash(f'Заказ {old_order_number} удален', 'success')
        
        if current_user.role == UserRole.ADMIN:
            return redirect(url_for('main.order_trash'))
        else:
            return redirect(url_for('main.order_list'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении заказа: {str(e)}', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))


@main.route('/orders/<int:order_id>/restore', methods=['POST'])
@login_required
@admin_required
def restore_order(order_id):
    """Восстановление заказа (только для администратора)"""
    order = Order.query.get_or_404(order_id)
    
    if not order.is_deleted:
        flash('Заказ не удален', 'warning')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    try:
        if order.order_number.startswith('DELETED_'):
            parts = order.order_number.split('_')
            if len(parts) >= 3:
                original_number = parts[1]
                order.order_number = original_number
        
        order.is_deleted = False
        order.deleted_at = None
        order.deleted_by_id = None
        order.deletion_reason = None
        
        last_history = OrderStatusHistory.query.filter_by(
            order_id=order.id
        ).order_by(OrderStatusHistory.created_at.desc()).first()
        
        if last_history and last_history.new_status != "DELETED":
            order.status = last_history.new_status
        
        db.session.commit()
        
        flash(f'Заказ {order.order_number} восстановлен', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при восстановлении заказа: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order_id))


@main.route('/orders/<int:order_id>/permanent_delete', methods=['POST'])
@login_required
@admin_required
def permanent_delete_order(order_id):
    """Полное удаление заказа из системы (только для администратора)"""
    order = Order.query.get_or_404(order_id)
    
    if not order.is_deleted:
        flash('Сначала удалите заказ в корзину', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    if request.method == 'GET':
        return render_template('orders/permanent_delete_confirm.html',
                             order=order)
    
    try:
        current_app.logger.warning(
            f"Полное удаление заказа ID: {order.id}, "
            f"Номер: {order.order_number}, "
            f"Клиент: {order.customer_name}, "
            f"Удалил: {current_user.username}"
        )
        
        from app.services.file_service import FileService
        files = order.files.all()
        for file in files:
            try:
                FileService.delete_file(file)
            except Exception as e:
                current_app.logger.error(f"Ошибка удаления файла {file.filename}: {e}")
        
        OrderStatusHistory.query.filter_by(order_id=order.id).delete()
        Notification.query.filter_by(order_id=order.id).delete()
        
        db.session.delete(order)
        db.session.commit()
        
        flash('Заказ полностью удален из системы', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка полного удаления заказа {order_id}: {e}")
        flash(f'Ошибка при полном удалении заказа: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_trash'))


@main.route('/')
@login_required
def index():
    """Главная страница"""
    stats = OrderService.get_statistics(current_user)
    
    if current_user.role in [UserRole.ADMIN, UserRole.DIRECTOR, UserRole.HEAD_DESIGNER, UserRole.SALON_HEAD]:
        recent_orders = Order.query.filter_by(is_deleted=False)\
            .order_by(Order.created_at.desc()).limit(10).all()
    elif current_user.role == UserRole.SALON_MANAGER:
        recent_orders = Order.query.filter_by(
            salon_manager_id=current_user.id,
            is_deleted=False
        ).order_by(Order.created_at.desc()).limit(10).all()
    elif current_user.role == UserRole.DESIGNER:
        recent_orders = Order.query.filter_by(
            designer_id=current_user.id,
            is_deleted=False
        ).order_by(Order.created_at.desc()).limit(10).all()
    elif current_user.role == UserRole.HEAD_SUPPLY:
        recent_orders = Order.query.filter(
            Order.status.in_([OrderStatus.DESIGN_COMPLETED, OrderStatus.PURCHASE, OrderStatus.PURCHASE_COMPLETED]),
            Order.is_deleted == False
        ).order_by(Order.created_at.desc()).limit(10).all()
    elif current_user.role == UserRole.HEAD_PRODUCTION:
        recent_orders = Order.query.filter(
            Order.status.in_([OrderStatus.MANUFACTURING, OrderStatus.INSTALLATION, 
                            OrderStatus.QUALITY_CHECK, OrderStatus.READY_FOR_DELIVERY]),
            Order.is_deleted == False
        ).order_by(Order.created_at.desc()).limit(10).all()
    elif current_user.role == UserRole.QUALITY_CONTROL:
        recent_orders = Order.query.filter_by(
            status=OrderStatus.QUALITY_CHECK,
            is_deleted=False
        ).order_by(Order.created_at.desc()).limit(10).all()
    else:
        recent_orders = []
    
    return render_template('index.html',
                         stats=stats,
                         recent_orders=recent_orders,
                         OrderStatus=OrderStatus,
                         UserRole=UserRole)


@main.route('/orders')
@login_required
def order_list():
    """Список заказов"""
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    query = OrderService.get_orders_for_user(current_user, status_filter, search)
    
    orders = query.paginate(page=page, per_page=20, error_out=False)
    
    return render_template('orders/list.html',
                         orders=orders,
                         status_filter=status_filter,
                         search=search,
                         OrderStatus=OrderStatus)


@main.route('/orders/create', methods=['GET', 'POST'])
@login_required
@salon_manager_required
def create_order():
    """Создание нового заказа"""
    form = OrderForm()
    
    draft_data = session.pop('draft_data', None)
    if draft_data and request.method == 'GET':
        form.customer_name.data = draft_data.get('customer_name', '')
        form.customer_phone.data = draft_data.get('customer_phone', '')
        form.customer_email.data = draft_data.get('customer_email', '')
        form.product_name.data = draft_data.get('product_name', '')
        form.installation_address.data = draft_data.get('object_address', '')
        form.notes.data = draft_data.get('special_terms', '')
        form.order_code.data = draft_data.get('contract_number', '')
        
        flash('Данные загружены из черновика. Проверьте и дополните информацию.', 'info')
    
    tomorrow = datetime.utcnow().date() + timedelta(days=1)
    
    if form.validate_on_submit():
        try:
            salon_manager_id = current_user.id
            
            if (current_user.role in [UserRole.ADMIN, UserRole.DIRECTOR, UserRole.SALON_HEAD] and 
                form.manager_id.data and form.manager_id.data > 0):
                salon_manager_id = form.manager_id.data
            
            # Обработка клиента
            client_id = None
            if form.client_id.data and form.client_id.data > 0:
                client_id = form.client_id.data
            elif form.create_new_client.data:
                # Создаем нового клиента
                try:
                    new_client = Client(
                        full_name=form.customer_name.data,
                        phone=form.customer_phone.data,
                        email=form.customer_email.data,
                        address=form.installation_address.data
                    )
                    db.session.add(new_client)
                    db.session.flush()
                    client_id = new_client.id
                    flash(f'Создан новый клиент: {new_client.full_name}', 'info')
                except Exception as e:
                    current_app.logger.error(f'Ошибка создания клиента: {e}')
            
            order_data = {
                'customer_name': form.customer_name.data,
                'customer_phone': form.customer_phone.data,
                'customer_email': form.customer_email.data,
                'product_name': form.product_name.data.strip(),
                'amount': form.amount.data,
                'furniture_amount': form.furniture_amount.data,
                'other_costs': form.other_costs.data,
                'measurement_cost': form.measurement_cost.data if form.measurement_cost.data else None,
                'deadline_date': form.deadline_date.data.isoformat() if form.deadline_date.data else None,
                'installation_date': form.installation_date.data.isoformat() if form.installation_date.data else None,
                'installation_address': form.installation_address.data,
                'notes': form.notes.data,
                'salon_manager_id': salon_manager_id,
                'prepayment_amount': form.prepayment_amount.data if form.prepayment_amount.data else 0.0,
                'prepayment_method': form.prepayment_method.data if form.prepayment_method.data else None,
                'prepayment_date': form.prepayment_date.data.isoformat() if form.prepayment_date.data else None,
                'client_id': client_id
            }
            order_data['order_code'] = form.order_code.data
            
            order = OrderService.create_order(order_data, current_user)
            
            if form.seller_id.data and form.seller_id.data > 0:
                order.seller_id = form.seller_id.data
            
            db.session.commit()
            
            if 'source_files' in request.files:
                files = request.files.getlist('source_files')
                uploaded_files = []
                
                for i, file in enumerate(files):
                    if file and file.filename:
                        try:
                            saved_file = FileService.save_file(
                                order, 
                                file, 
                                'source',
                                current_user,
                                description='Загружено при создании заказа'
                            )
                            if saved_file:
                                uploaded_files.append(saved_file)
                        except Exception as file_error:
                            current_app.logger.error(f'Ошибка загрузки файла {file.filename}: {str(file_error)}')
                            continue
                
                if uploaded_files:
                    flash(f'Загружено {len(uploaded_files)} исходных файлов.', 'success')
            
            flash(f'Заказ {order.order_number} успешно создан!', 'success')
            return redirect(url_for('main.order_detail', order_id=order.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании заказа: {str(e)}', 'danger')
    
    return render_template('orders/create.html', 
                         form=form, 
                         tomorrow=tomorrow,
                         current_user=current_user)


@main.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    """Детальная информация о заказе"""
    order = Order.query.get_or_404(order_id)
    
    if not OrderService.can_view_order(order, current_user):
        flash('У вас нет прав для просмотра этого заказа.', 'danger')
        return redirect(url_for('main.index'))
    
    status_history = OrderStatusHistory.query.filter_by(order_id=order_id)\
        .order_by(OrderStatusHistory.created_at.desc()).all()
    
    available_statuses = OrderService.get_available_statuses(order, current_user)
    
    show_status_form = len(available_statuses) > 0 or current_user.role == UserRole.ADMIN
    
    designers = []
    current_date = datetime.utcnow().date()
    
    if current_user.role in ['admin', 'head_designer', 'director']:
        designers = User.query.filter(
            User.role.in_(['designer', 'head_designer']),
            User.is_active == True
        ).order_by(User.username).all()
    
    summary = ScheduleService.get_schedule_summary(order)
    
    # Получаем клиента
    client = None
    if order.client_id:
        client = Client.query.get(order.client_id)
    
    return render_template('orders/detail.html',
                         order=order,
                         client=client,
                         status_history=status_history,
                         available_statuses=available_statuses,
                         designers=designers,
                         current_date=current_date,
                         show_status_form=show_status_form,
                         OrderStatus=OrderStatus)


@main.route('/order/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
    print(f"\n{'='*60}")
    print(f"!!! РОУТ EDIT_ORDER ВЫЗВАН для order_id={order_id}")
    print(f"!!! Метод: {request.method}")
    print(f"!!! User: {current_user.id} ({current_user.username})")
    
    if request.method == 'POST':
        print(f"!!! POST данные: {dict(request.form)}")
        print(f"!!! POST files: {request.files}")
    
    order = Order.query.get_or_404(order_id)
    print(f"!!! Заказ найден: {order.order_number}")
    
    # Проверка прав
    if current_user.role not in ['admin', 'director']:
        print(f"!!! Пользователь {current_user.id} не имеет прав на редактирование")
        flash('У вас нет прав для редактирования заказа', 'danger')
        return redirect(url_for('main.order_detail', order_id=order.id))
    
    form = OrderEditForm(obj=order)
    print(f"!!! Форма создана")
    
    if request.method == 'POST':
        print(f"!!! Валидация формы...")
        if form.validate_on_submit():
            print(f"!!! ФОРМА ВАЛИДНА!")
            try:
                # Подготовка данных
                order_data = {
                    'product_name': form.product_name.data,
                    'customer_name': form.customer_name.data,
                    'customer_phone': form.customer_phone.data,
                    'customer_email': form.customer_email.data,
                    'order_code': form.order_code.data,
                    'installation_address': form.installation_address.data,
                    'client_id': form.client_id.data,
                    'amount': form.amount.data,
                    'furniture_amount': form.furniture_amount.data,
                    'measurement_cost': form.measurement_cost.data,
                    'other_costs': form.other_costs.data,
                    'prepayment_amount': form.prepayment_amount.data,
                    'prepayment_method': form.prepayment_method.data,
                    'prepayment_date': form.prepayment_date.data,
                    'deadline_date': form.deadline_date.data,
                    'installation_date': form.installation_date.data,
                    'design_ready_date': form.design_ready_date.data,
                    'designer_id': form.designer_id.data,
                    'salon_manager_id': form.manager_id.data,
                    'seller_id': form.seller_id.data,
                    'notes': form.notes.data,
                    'status': form.status.data
                }
                print(f"!!! Подготовлены данные для обновления: {order_data}")
                
                # ВАЖНО: сохраняем результат update_order
                updated_order, changes = OrderService.update_order(order, order_data, current_user)
                print(f"!!! OrderService.update_order выполнен успешно")
                print(f"!!! Изменения: {changes}")
                
                print(f"!!! Попытка коммита в БД...")
                db.session.commit()
                print(f"!!! КОММИТ УСПЕШНО ВЫПОЛНЕН")
                
                print(f"!!! Создание flash сообщения...")
                flash(f'Заказ успешно обновлен. Изменения: {", ".join(changes)}', 'success')
                print(f"!!! Flash сообщение создано")
                
                # ИСПРАВЛЕНИЕ: используем updated_order.id вместо order.id
                print(f"!!! Редирект на order_detail, order_id={updated_order.id}")
                return redirect(url_for('main.order_detail', order_id=updated_order.id))
                
            except Exception as e:
                db.session.rollback()
                print(f"!!! ОШИБКА в блоке try: {str(e)}")
                import traceback
                traceback.print_exc()
                flash(f'Ошибка при обновлении заказа: {str(e)}', 'danger')
        else:
            print(f"!!! ФОРМА НЕ ВАЛИДНА!")
            print(f"!!! Ошибки формы: {form.errors}")
            for field, errors in form.errors.items():
                print(f"!!!   {field}: {errors}")
    
    # Получаем историю статусов
    status_history = OrderStatusHistory.query.filter_by(order_id=order.id)\
        .order_by(OrderStatusHistory.created_at.desc()).limit(5).all()
    
    print(f"!!! Рендеринг шаблона edit.html")
    return render_template('orders/edit.html', 
                          form=form, 
                          order=order, 
                          status_history=status_history,
                          OrderStatus=OrderStatus,
                          request=request)

    """Редактирование заказа (только для администратора и директора)"""
    order = Order.query.get_or_404(order_id)
    
    if current_user.role not in [UserRole.ADMIN.value]:
        flash('У вас нет прав для редактирования заказов.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    if order.is_deleted:
        flash('Нельзя редактировать удаленный заказ.', 'danger')
        return redirect(url_for('main.order_trash'))
    
    form = OrderEditForm()
    
    if request.method == 'GET':
        form.product_name.data = order.product_name
        form.customer_name.data = order.customer_name
        form.customer_phone.data = order.customer_phone
        form.customer_email.data = order.customer_email
        form.order_code.data = order.order_code
        form.amount.data = order.amount
        form.furniture_amount.data = order.furniture_amount
        form.measurement_cost.data = order.measurement_cost
        form.other_costs.data = order.other_costs
        form.prepayment_amount.data = order.prepayment_amount
        form.prepayment_method.data = order.prepayment_method
        form.prepayment_date.data = order.prepayment_date.date() if order.prepayment_date else None
        form.deadline_date.data = order.deadline_date.date() if order.deadline_date else None
        form.installation_date.data = order.installation_date.date() if order.installation_date else None
        form.design_ready_date.data = order.design_ready_date.date() if order.design_ready_date else None
        form.notes.data = order.notes
        form.seller_id.data = order.seller_id or 0
        form.manager_id.data = order.salon_manager_id or 0
        form.designer_id.data = order.designer_id or 0
        form.client_id.data = order.client_id or 0
    
    if form.validate_on_submit():
        try:
            order_data = {
                'product_name': form.product_name.data,
                'customer_name': form.customer_name.data,
                'customer_phone': form.customer_phone.data,
                'customer_email': form.customer_email.data,
                'order_code': form.order_code.data,
                'amount': form.amount.data,
                'furniture_amount': form.furniture_amount.data,
                'measurement_cost': form.measurement_cost.data,
                'other_costs': form.other_costs.data,
                'prepayment_amount': form.prepayment_amount.data,
                'prepayment_method': form.prepayment_method.data,
                'prepayment_date': form.prepayment_date.data.isoformat() if form.prepayment_date.data else None,
                'deadline_date': form.deadline_date.data.isoformat() if form.deadline_date.data else None,
                'installation_date': form.installation_date.data.isoformat() if form.installation_date.data else None,
                'installation_address': form.installation_address.data,
                'design_ready_date': form.design_ready_date.data.isoformat() if form.design_ready_date.data else None,
                'notes': form.notes.data,
                'seller_id': form.seller_id.data,
                'salon_manager_id': form.manager_id.data,
                'designer_id': form.designer_id.data,
                'client_id': form.client_id.data if form.client_id.data > 0 else None,
                'status': form.status.data if form.status.data else None
            }
            
            updated_order, changes = OrderService.update_order(order, order_data, current_user)
            
            db.session.commit()
            
            if changes:
                flash(f'Заказ {updated_order.order_number} успешно обновлен. Изменения: {", ".join(changes)}', 'success')
            else:
                flash('Изменения не были внесены.', 'info')
            
            return redirect(url_for('main.order_detail', order_id=order.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении заказа: {str(e)}', 'danger')
    
    status_history = OrderStatusHistory.query.filter_by(order_id=order_id)\
        .order_by(OrderStatusHistory.created_at.desc()).limit(10).all()
    
    return render_template('orders/edit.html',
                         form=form,
                         order=order,
                         status_history=status_history,
                         OrderStatus=OrderStatus,
                         UserRole=UserRole)
     
@main.route('/orders/<int:order_id>/update_status', methods=['POST'])
@login_required
@status_change_required
def update_order_status(order_id):
    """Обновление статуса заказа"""
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    notes = request.form.get('notes', '')
    
    try:
        OrderService.change_order_status(order, new_status, current_user, notes)
        flash('Статус заказа обновлен.', 'success')
    except Exception as e:
        flash(f'Ошибка при обновлении статуса: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order_id))


@main.route('/orders/<int:order_id>/assign_designer', methods=['POST'])
@login_required
@designer_required
def assign_designer(order_id):
    """Назначение конструктора на заказ"""
    order = Order.query.get_or_404(order_id)
    
    if current_user.role not in ['admin', 'head_designer', 'director']:
        flash('У вас нет прав для назначения конструктора.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    designer_id = request.form.get('designer_id')
    design_ready_date_str = request.form.get('design_ready_date')
    
    try:
        if not design_ready_date_str:
            flash('Укажите дату готовности чертежей', 'danger')
            return redirect(url_for('main.order_detail', order_id=order_id))
        
        design_ready_date = datetime.strptime(design_ready_date_str, '%Y-%m-%d')
        
        designer = User.query.get_or_404(designer_id)
        
        if designer.role not in ['designer', 'head_designer']:
            flash('Выбранный пользователь не является конструктором.', 'danger')
            return redirect(url_for('main.order_detail', order_id=order_id))
        
        order.designer_id = designer.id
        order.status = OrderStatus.DESIGN
        order.design_ready_date = design_ready_date
        
        history = OrderStatusHistory(
            order_id=order.id,
            old_status=OrderStatus.NEW,
            new_status=OrderStatus.DESIGN,
            changed_by_id=current_user.id,
            notes=f'Назначен конструктор: {designer.username}. Дата готовности чертежей: {design_ready_date.strftime("%d.%m.%Y")}'
        )
        db.session.add(history)
        
        NotificationService.notify_designer_assigned(order, designer, current_user)
        
        db.session.commit()
        
        flash(f'Конструктор {designer.username} назначен на заказ. Дата готовности чертежей: {design_ready_date.strftime("%d.%m.%Y")}', 'success')
    except ValueError as e:
        flash(f'Ошибка формата даты: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при назначении конструктора: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order_id))


@main.route('/orders/<int:order_id>/upload', methods=['POST'])
@login_required
def upload_file(order_id):
    """Загрузка файла для заказа"""
    order = Order.query.get_or_404(order_id)
    file_type = request.form.get('file_type')
    
    if not FileService.can_upload_to_folder(current_user, order, file_type):
        flash('У вас нет прав для загрузки файлов в эту папку.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    if 'files' not in request.files:
        flash('Не выбраны файлы для загрузки.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    files = request.files.getlist('files')
    descriptions = request.form.getlist('descriptions[]')
    
    if not files or not files[0].filename:
        flash('Не выбраны файлы для загрузки.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    try:
        saved_files = FileService.save_files(order, files, file_type, current_user, descriptions)
        
        if saved_files:
            flash(f'Успешно загружено {len(saved_files)} файлов.', 'success')
        else:
            flash('Не удалось загрузить файлы.', 'warning')
            
    except ValueError as e:
        flash(str(e), 'danger')
    except Exception as e:
        flash(f'Ошибка при загрузке файлов: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order_id))


@main.route('/files/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    """Удаление файла"""
    from app.models import OrderFile
    from app.services.file_service import FileService
    from app.config import UserRole
    
    order_file = OrderFile.query.get_or_404(file_id)
    order = order_file.file_order
    
    if not (current_user.role == UserRole.ADMIN or 
            current_user.id == order_file.uploaded_by_id or
            current_user.id == order.salon_manager_id or
            (current_user.role == UserRole.HEAD_DESIGNER and order_file.file_type in ['design', 'review'])):
        
        flash('У вас нет прав для удаления этого файла.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order.id))
    
    try:
        if FileService.delete_file(order_file):
            flash('Файл успешно удален.', 'success')
        else:
            flash('Ошибка при удалении файла.', 'danger')
    except Exception as e:
        flash(f'Ошибка при удалении файла: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order.id))


@main.route('/download/<int:file_id>')
@login_required
def download_by_id(file_id):
    """Простое скачивание файла по ID"""
    order_file = OrderFile.query.get_or_404(file_id)
    
    if hasattr(order_file, 'order'):
        order = order_file.order
    elif hasattr(order_file, 'file_order'):
        order = order_file.file_order
    else:
        from app.models import Order
        order = Order.query.get(order_file.order_id)
    
    from app.services.file_service import FileService
    if not FileService.can_download_from_folder(current_user, order, order_file.file_type):
        flash('У вас нет прав для доступа к этому файлу.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order.id))
    
    if not os.path.exists(order_file.file_path):
        current_app.logger.error(f"Файл не найден: {order_file.file_path}")
        flash('Файл не найден на сервере.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order.id))
    
    try:
        return send_file(
            order_file.file_path, 
            as_attachment=True, 
            download_name=order_file.original_filename,
            mimetype=None
        )
    except Exception as e:
        current_app.logger.error(f"Ошибка при скачивании файла {file_id}: {e}")
        flash(f'Ошибка при скачивании файла: {str(e)}', 'danger')
        return redirect(url_for('main.order_detail', order_id=order.id))


@main.route('/orders/<int:order_id>/add_comment', methods=['POST'])
@login_required
def add_comment(order_id):
    """Добавление комментария к заказу"""
    order = Order.query.get_or_404(order_id)
    
    # Убираем проверку ролей - все авторизованные могут комментировать
    # Просто проверяем, что комментарий не пустой
    
    comment_text = request.form.get('comment', '').strip()
    
    if not comment_text:
        flash('Комментарий не может быть пустым.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    try:
        if order.notes:
            order.notes += f"\n\n[{datetime.utcnow().strftime('%d.%m.%Y %H:%M')}] {current_user.username}: {comment_text}"
        else:
            order.notes = f"[{datetime.utcnow().strftime('%d.%m.%Y %H:%M')}] {current_user.username}: {comment_text}"
        
        users_to_notify = []
        
        if order.salon_manager and order.salon_manager.id != current_user.id:
            users_to_notify.append(order.salon_manager)
        
        if order.designer and order.designer.id != current_user.id:
            users_to_notify.append(order.designer)
        
        if users_to_notify:
            NotificationService.create_notifications_for_users(
                users_to_notify,
                'comment_added',
                f'Новый комментарий: {order.order_number}',
                f'{current_user.username} добавил комментарий к заказу: {comment_text[:100]}...',
                order.id,
                metadata={'comment_by': current_user.username, 'url': f'/orders/{order.id}'}
            )
        
        db.session.commit()
        flash('Комментарий добавлен.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при добавлении комментария: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order_id))

@main.route('/orders/<int:order_id>/admin_update_status', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_update_order_status(order_id):
    """Изменение статуса заказа администратором (на любой статус)"""
    order = Order.query.get_or_404(order_id)
    
    if request.method == 'POST':
        new_status = request.form.get('status')
        notes = request.form.get('notes', '')
        
        try:
            if new_status not in [status.value for status in OrderStatus]:
                flash('Некорректный статус.', 'danger')
                return redirect(url_for('main.admin_update_order_status', order_id=order_id))
            
            old_status = order.status
            
            order.status = new_status
            
            history = OrderStatusHistory(
                order_id=order.id,
                old_status=old_status,
                new_status=new_status,
                changed_by_id=current_user.id,
                notes=f'Администратор изменил статус. {notes}'
            )
            db.session.add(history)
            
            NotificationService.create_status_change_notification(
                order, 
                old_status, 
                new_status, 
                current_user,
                notes
            )
            
            db.session.commit()
            flash('Статус заказа изменен администратором.', 'success')
            return redirect(url_for('main.order_detail', order_id=order_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при изменении статуса: {str(e)}', 'danger')
    
    all_statuses = [(status.value, OrderStatus.get_display_name(status)) 
                    for status in OrderStatus]
    
    return render_template('orders/admin_update_status.html',
                         order=order,
                         all_statuses=all_statuses,
                         OrderStatus=OrderStatus)


@main.route('/calendar')
@login_required
def calendar():
    """Календарь заказов"""
    return render_template('calendar.html')


@main.route('/api/calendar/events')
@login_required
def calendar_events():
    """API для получения событий календаря"""
    
    query = OrderService.get_orders_for_user(current_user, 'all', '')
    query = query.filter_by(is_archived=False)
    orders = query.all()
    events = []
    
    for order in orders:
        if order.installation_date:
            events.append({
                'id': f'installation_{order.id}',
                'title': f'📅 {order.order_number} - Монтаж',
                'start': order.installation_date.isoformat(),
                'color': '#0d6efd',
                'textColor': 'white',
                'extendedProps': {
                    'order_id': order.id,
                    'type': 'installation',
                    'customer': order.customer_name,
                    'status': order.status
                }
            })
        
        if order.deadline_date:
            events.append({
                'id': f'deadline_{order.id}',
                'title': f'⏰ {order.order_number} - Срок',
                'start': order.deadline_date.isoformat(),
                'color': '#dc3545' if order.deadline_date.date() < datetime.utcnow().date() else '#ffc107',
                'textColor': 'white',
                'extendedProps': {
                    'order_id': order.id,
                    'type': 'deadline',
                    'customer': order.customer_name,
                    'status': order.status
                }
            })
        
        if order.updated_at:
            events.append({
                'id': f'status_{order.id}',
                'title': f'🔄 {order.order_number} - {OrderStatus.get_display_name(order.status)}',
                'start': order.updated_at.isoformat(),
                'color': {
                    OrderStatus.NEW: '#6c757d',
                    OrderStatus.DESIGN: '#ffc107',
                    OrderStatus.CLIENT_APPROVED: '#28a745',
                    OrderStatus.IN_DESIGN: '#0d6efd',
                    OrderStatus.DESIGN_COMPLETED: '#28a745',
                    OrderStatus.PURCHASE: '#17a2b8',
                    OrderStatus.PURCHASE_COMPLETED: '#28a745',
                    OrderStatus.MANUFACTURING: '#fd7e14',
                    OrderStatus.INSTALLATION: '#0d6efd',
                    OrderStatus.QUALITY_CHECK: '#ffc107',
                    OrderStatus.RETURN_TO_DESIGN: '#dc3545',
                    OrderStatus.READY_FOR_DELIVERY: '#17a2b8',
                    OrderStatus.DELIVERED: '#28a745',
                    OrderStatus.COMPLETED: '#20c997'
                }.get(order.status, '#6c757d'),
                'textColor': 'white',
                'extendedProps': {
                    'order_id': order.id,
                    'type': 'status_change',
                    'customer': order.customer_name,
                    'status': order.status
                }
            })
    
    return jsonify(events)


@main.route('/reports')
@login_required
def reports():
    """Страница отчетов"""
    if current_user.role == UserRole.ADMIN:
        total_orders = Order.query.filter_by(is_deleted=False).count()
        completed_orders = Order.query.filter_by(
            status=OrderStatus.COMPLETED,
            is_deleted=False
        ).count()
        total_amount = db.session.query(
            db.func.sum(Order.amount)
        ).filter_by(is_deleted=False).scalar() or 0
        
        monthly_stats = []
        for i in range(6):
            month = (datetime.utcnow().replace(day=1) - timedelta(days=30*i))
            year_month = month.strftime('%Y-%m')
            
            monthly_orders = Order.query.filter(
                Order.order_number.like(f'{year_month}-%'),
                Order.is_deleted == False
            ).all()
            
            monthly_amount = sum(o.amount for o in monthly_orders if o.amount)
            
            monthly_stats.append({
                'month': month.strftime('%B %Y'),
                'orders_count': len(monthly_orders),
                'total_amount': monthly_amount
            })
        
        stats = {
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0,
            'total_amount': total_amount,
            'monthly_stats': monthly_stats
        }
    else:
        stats = OrderService.get_statistics(current_user)
    
    return render_template('reports/index.html', stats=stats)


@main.route('/export/orders')
@login_required
def export_orders():
    """Экспорт заказов в Excel"""
    try:
        import pandas as pd
        from io import BytesIO
        
        query = OrderService.get_orders_for_user(current_user, 'all', '')
        orders = query.all()
        
        data = []
        for order in orders:
            client_info = ''
            if order.client_id:
                client = Client.query.get(order.client_id)
                if client:
                    client_info = f"{client.full_name} ({client.phone})"
            
            data.append({
                'Номер заказа': order.order_number,
                'Код': order.order_code or '',
                'Клиент': client_info,
                'Заказчик': order.customer_name,
                'Телефон': order.customer_phone,
                'Email': order.customer_email or '',
                'Статус': OrderStatus.get_display_name(order.status),
                'Сумма': order.amount,
                'Менеджер': order.salon_manager.username if order.salon_manager else '',
                'Конструктор': order.designer.username if order.designer else '',
                'Дата создания': order.created_at.strftime('%d.%m.%Y'),
                'Срок выполнения': order.deadline_date.strftime('%d.%m.%Y') if order.deadline_date else '',
                'Дата монтажа': order.installation_date.strftime('%d.%m.%Y') if order.installation_date else ''
            })
        
        df = pd.DataFrame(data)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Заказы', index=False)
            
            worksheet = writer.sheets['Заказы']
            for i, col in enumerate(df.columns):
                column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + i)].width = column_width
        
        output.seek(0)
        
        filename = f'orders_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f'Ошибка при экспорте: {str(e)}', 'danger')
        return redirect(url_for('main.reports'))


@main.route('/admin')
@login_required
def admin_dashboard():
    """Перенаправление на админ-панель"""
    if current_user.role != UserRole.ADMIN:
        flash('У вас нет прав для доступа к админ-панели.', 'danger')
        return redirect(url_for('main.index'))
    
    return redirect(url_for('admin.index'))


@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Профиль пользователя"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        try:
            if not current_user.check_password(form.current_password.data):
                flash('Текущий пароль указан неверно', 'danger')
                return redirect(url_for('main.profile'))
            
            if form.new_password.data != form.confirm_password.data:
                flash('Новые пароли не совпадают', 'danger')
                return redirect(url_for('main.profile'))
            
            current_user.set_password(form.new_password.data)
            db.session.commit()
            
            flash('Пароль успешно изменен', 'success')
            return redirect(url_for('main.profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при изменении пароля: {str(e)}', 'danger')
    
    return render_template('profile/index.html', form=form)


@main.route('/toggle_theme', methods=['POST'])
@login_required
def toggle_theme():
    """Переключение светлой/тёмной темы"""
    theme = request.form.get('theme', 'light')
    
    session['theme'] = theme
    
    return jsonify({'success': True, 'theme': theme})
    

@main.route('/archive')
@login_required
@salon_manager_required
def archive_list():
    """Список архивных заказов"""
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    archived_orders = ArchiveService.get_archived_orders(
        current_user, search, page, 20
    )
    
    return render_template('archive/list.html',
                         orders=archived_orders,
                         search=search,
                         OrderStatus=OrderStatus)


@main.route('/reclamations')
@login_required
def reclamations_list():
    """Список рекламаций"""
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    reclamations = ArchiveService.get_reclamation_orders(
        current_user, search, page, 20
    )
    
    return render_template('reclamations/list.html',
                         reclamations=reclamations,
                         search=search,
                         OrderStatus=OrderStatus)


@main.route('/orders/<int:order_id>/archive', methods=['POST'])
@login_required
@admin_required
def archive_order(order_id):
    """Ручная архивация заказа"""
    order = Order.query.get_or_404(order_id)
    
    if order.status != OrderStatus.COMPLETED:
        flash('Можно архивировать только завершенные заказы', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    try:
        ArchiveService.archive_order(order, current_user)
        flash(f'Заказ {order.order_number} перемещен в архив', 'success')
    except Exception as e:
        flash(f'Ошибка при архивации: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order_id))


@main.route('/archive/<int:order_id>/restore', methods=['GET', 'POST'])
@login_required
def restore_from_archive(order_id):
    """Восстановление заказа из архива для рекламации"""
    order = Order.query.get_or_404(order_id)
    
    if not ArchiveService.can_restore_from_archive(current_user, order):
        flash('У вас нет прав на восстановление этого заказа', 'danger')
        return redirect(url_for('main.archive_list'))
    
    if not order.is_archived:
        flash('Заказ не находится в архиве', 'danger')
        return redirect(url_for('main.archive_list'))
    
    if request.method == 'POST':
        reclamation_reason = request.form.get('reclamation_reason', '').strip()
        
        if not reclamation_reason:
            flash('Укажите причину рекламации', 'danger')
            return redirect(url_for('main.restore_from_archive', order_id=order_id))
        
        try:
            ArchiveService.restore_from_archive(order, current_user, reclamation_reason)
            flash(f'Заказ {order.order_number} восстановлен для рекламации', 'success')
            return redirect(url_for('main.order_detail', order_id=order_id))
        except Exception as e:
            flash(f'Ошибка при восстановлении: {str(e)}', 'danger')
    
    return render_template('archive/restore.html',
                         order=order,
                         OrderStatus=OrderStatus)


@main.route('/reclamations/<int:order_id>/process', methods=['POST'])
@login_required
@head_designer_required
def process_reclamation(order_id):
    """Обработка рекламации - назначение конструктора"""
    order = Order.query.get_or_404(order_id)
    
    if order.status != OrderStatus.RECLAMATION:
        flash('Это не рекламация', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    designer_id = request.form.get('designer_id')
    
    if not designer_id:
        flash('Выберите конструктора', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    try:
        designer = User.query.get_or_404(designer_id)
        
        order.designer_id = designer.id
        order.status = OrderStatus.DESIGN
        
        history = OrderStatusHistory(
            order_id=order.id,
            old_status=OrderStatus.RECLAMATION,
            new_status=OrderStatus.DESIGN,
            changed_by_id=current_user.id,
            notes=f"Рекламация в обработке. Назначен конструктор: {designer.username}"
        )
        db.session.add(history)
        
        db.session.commit()
        
        flash(f'Конструктор {designer.username} назначен на рекламацию', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order_id))  


# ==================== МАРШРУТЫ ДЛЯ ПРОДАВЦОВ ====================

@main.route('/sellers')
@login_required
def seller_list():
    """Список продавцов"""
    if current_user.role not in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, 
                                 UserRole.SALON_HEAD.value, UserRole.SALON_MANAGER.value]:
        flash('У вас нет прав для просмотра продавцов.', 'danger')
        return redirect(url_for('main.index'))
    
    search = request.args.get('search', '')
    show_inactive = request.args.get('show_inactive', '0') == '1'
    
    query = Seller.query
    
    if current_user.role == UserRole.SALON_MANAGER.value:
        query = query.filter_by(manager_id=current_user.id)
    elif current_user.role in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
        pass
    else:
        flash('У вас нет прав для просмотра продавцов.', 'danger')
        return redirect(url_for('main.index'))
    
    if not show_inactive:
        query = query.filter_by(is_active=True)
    
    if search:
        query = query.filter(
            (Seller.name.contains(search)) |
            (Seller.phone.contains(search)) |
            (Seller.email.contains(search))
        )
    
    sellers = query.order_by(Seller.is_active.desc(), Seller.name).all()
    
    return render_template('sellers/list.html',
                         sellers=sellers,
                         search=search,
                         show_inactive=show_inactive,
                         UserRole=UserRole)


@main.route('/sellers/create', methods=['GET', 'POST'])
@login_required
def create_seller():
    """Создание нового продавца"""
    if current_user.role not in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
        flash('У вас нет прав для создания продавцов.', 'danger')
        return redirect(url_for('main.seller_list'))
    
    form = SellerForm()
    
    managers = User.query.filter_by(role=UserRole.SALON_MANAGER.value).order_by(User.username).all()
    
    if form.validate_on_submit():
        try:
            seller = Seller(
                name=form.name.data,
                phone=form.phone.data,
                email=form.email.data,
                is_active=form.is_active.data,
                manager_id=request.form.get('manager_id', current_user.id)
            )
            
            db.session.add(seller)
            db.session.commit()
            
            flash(f'Продавец {seller.name} успешно создан.', 'success')
            return redirect(url_for('main.seller_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании продавца: {str(e)}', 'danger')
    
    return render_template('sellers/create.html',
                         form=form,
                         managers=managers,
                         current_user=current_user)


@main.route('/sellers/<int:seller_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_seller(seller_id):
    """Редактирование продавца"""
    seller = Seller.query.get_or_404(seller_id)
    
    if current_user.role not in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
        if current_user.role == UserRole.SALON_MANAGER.value:
            if seller.manager_id != current_user.id:
                flash('Вы можете редактировать только своих продавцов.', 'danger')
                return redirect(url_for('main.seller_list'))
        else:
            flash('У вас нет прав для редактирования продавцов.', 'danger')
            return redirect(url_for('main.seller_list'))
    
    form = SellerForm(obj=seller)
    
    if form.validate_on_submit():
        try:
            seller.name = form.name.data
            seller.phone = form.phone.data
            seller.email = form.email.data
            seller.is_active = form.is_active.data
            
            if current_user.role in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
                new_manager_id = request.form.get('manager_id')
                if new_manager_id:
                    seller.manager_id = int(new_manager_id)
            
            db.session.commit()
            
            flash(f'Продавец {seller.name} успешно обновлен.', 'success')
            return redirect(url_for('main.seller_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении продавца: {str(e)}', 'danger')
    
    managers = []
    if current_user.role in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
        managers = User.query.filter_by(role=UserRole.SALON_MANAGER.value).order_by(User.username).all()
    
    return render_template('sellers/edit.html',
                         form=form,
                         seller=seller,
                         managers=managers,
                         current_user=current_user)


@main.route('/sellers/<int:seller_id>/delete', methods=['POST'])
@login_required
def delete_seller(seller_id):
    """Удаление продавца"""
    seller = Seller.query.get_or_404(seller_id)
    
    if current_user.role not in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
        flash('У вас нет прав для удаления продавцов.', 'danger')
        return redirect(url_for('main.seller_list'))
    
    order_count = seller.orders.count()
    if order_count > 0:
        flash(f'Невозможно удалить продавца. У него есть {order_count} заказ(ов).', 'danger')
        return redirect(url_for('main.seller_list'))
    
    try:
        db.session.delete(seller)
        db.session.commit()
        flash(f'Продавец {seller.name} удален.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении продавца: {str(e)}', 'danger')
    
    return redirect(url_for('main.seller_list'))


@main.route('/sellers/<int:seller_id>/toggle_active', methods=['POST'])
@login_required
def toggle_seller_active(seller_id):
    """Активация/деактивация продавца"""
    seller = Seller.query.get_or_404(seller_id)
    
    if current_user.role not in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
        if current_user.role == UserRole.SALON_MANAGER.value:
            if seller.manager_id != current_user.id:
                flash('Вы можете управлять только своими продавцами.', 'danger')
                return redirect(url_for('main.seller_list'))
        else:
            flash('У вас нет прав для управления статусом продавцов.', 'danger')
            return redirect(url_for('main.seller_list'))
    
    try:
        seller.is_active = not seller.is_active
        db.session.commit()
        
        status = "активирован" if seller.is_active else "деактивирован"
        flash(f'Продавец {seller.name} {status}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при изменении статуса: {str(e)}', 'danger')
    
    return redirect(url_for('main.seller_list'))


@main.route('/design_dashboard')
@login_required
@head_designer_required
def design_dashboard():
    """Дашборд для руководителя конструкторов"""
    designers = User.query.filter(
        User.role == UserRole.DESIGNER,
        User.is_active == True
    ).order_by(User.username).all()
    
    designer_stats = {}
    today = datetime.utcnow().date()
    
    for designer in designers:
        designer_orders = Order.query.filter(
            Order.designer_id == designer.id,
            Order.is_deleted == False,
            Order.is_archived == False
        ).all()
        
        status_counts = {}
        for status in [OrderStatus.DESIGN, OrderStatus.DESIGN_REVIEW, 
                       OrderStatus.CLIENT_APPROVED, OrderStatus.IN_DESIGN,
                       OrderStatus.RETURN_TO_DESIGN]:
            status_counts[status.value] = sum(1 for o in designer_orders if o.status == status.value)
        
        overdue_designs = []
        for order in designer_orders:
            if order.design_ready_date and order.design_ready_date.date() < today:
                if order.status in [OrderStatus.DESIGN.value, OrderStatus.CLIENT_APPROVED.value, 
                                   OrderStatus.IN_DESIGN.value, OrderStatus.RETURN_TO_DESIGN.value]:
                    overdue_designs.append(order)
        
        due_soon = []
        for order in designer_orders:
            if order.design_ready_date:
                days_left = (order.design_ready_date.date() - today).days
                if 0 <= days_left <= 3:
                    if order.status in [OrderStatus.DESIGN.value, OrderStatus.CLIENT_APPROVED.value, 
                                       OrderStatus.IN_DESIGN.value, OrderStatus.RETURN_TO_DESIGN.value]:
                        due_soon.append(order)
        
        designer_stats[designer.id] = {
            'designer': designer,
            'total_orders': len(designer_orders),
            'status_counts': status_counts,
            'overdue_count': len(overdue_designs),
            'due_soon_count': len(due_soon),
            'overdue_designs': overdue_designs[:5],
            'due_soon_designs': due_soon[:5],
            'recent_orders': designer_orders[:10]
        }
    
    all_design_orders = Order.query.filter(
        Order.designer_id.isnot(None),
        Order.is_deleted == False,
        Order.is_archived == False
    ).all()
    
    total_stats = {
        'total_orders': len(all_design_orders),
        'total_designers': len(designers),
        'total_overdue': sum(stats['overdue_count'] for stats in designer_stats.values()),
        'total_due_soon': sum(stats['due_soon_count'] for stats in designer_stats.values()),
        'by_status': {}
    }
    
    for status in [OrderStatus.DESIGN, OrderStatus.DESIGN_REVIEW, OrderStatus.CLIENT_APPROVED, 
                   OrderStatus.IN_DESIGN, OrderStatus.DESIGN_COMPLETED, OrderStatus.RETURN_TO_DESIGN]:
        count = sum(1 for o in all_design_orders if o.status == status.value)
        total_stats['by_status'][status.value] = {
            'count': count,
            'name': OrderStatus.get_display_name(status)
        }
    
    return render_template('design_dashboard/index.html',
                         designer_stats=designer_stats,
                         total_stats=total_stats,
                         designers=designers,
                         OrderStatus=OrderStatus,
                         UserRole=UserRole,
                         today=today)   
                         
@main.route('/orders/<int:order_id>/schedule_check', methods=['GET'])
@login_required
def check_schedule(order_id):
    """Проверка расписания заказа"""
    order = Order.query.get_or_404(order_id)
    
    if not OrderService.can_view_order(order, current_user):
        flash('У вас нет прав для просмотра этого заказа.', 'danger')
        return redirect(url_for('main.index'))
    
    conflicts = ScheduleService.check_schedule_conflicts(order)
    optimization = ScheduleService.get_schedule_optimization(order)
    summary = ScheduleService.get_schedule_summary(order)
    
    return jsonify({
        'success': True,
        'order_number': order.order_number,
        'conflicts': conflicts,
        'optimization': optimization,
        'summary': summary,
        'has_critical_conflicts': any(c['severity'] == 'danger' for c in conflicts)
    })


@main.route('/orders/<int:order_id>/reschedule_installation', methods=['POST'])
@login_required
def reschedule_installation(order_id):
    """Перенос даты монтажа"""
    order = Order.query.get_or_404(order_id)
    
    if current_user.role not in [
        UserRole.SALON_MANAGER.value, 
        UserRole.SALON_HEAD.value,
        UserRole.ADMIN.value,
        UserRole.DIRECTOR.value
    ]:
        if current_user.id != order.salon_manager_id:
            flash('У вас нет прав для изменения даты монтажа.', 'danger')
            return redirect(url_for('main.order_detail', order_id=order_id))
    
    new_date_str = request.form.get('new_date')
    reason = request.form.get('reason', '').strip()
    
    if not new_date_str:
        flash('Укажите новую дату монтажа', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    if not reason:
        flash('Укажите причину переноса', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    try:
        success, message = ScheduleService.reschedule_installation(
            order, new_date_str, current_user, reason
        )
        
        if success:
            flash(f'Дата монтажа изменена: {message}', 'success')
        else:
            flash(f'Ошибка: {message}', 'danger')
            
    except Exception as e:
        flash(f'Ошибка при переносе даты: {str(e)}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order_id))


@main.route('/orders/<int:order_id>/optimize_schedule', methods=['POST'])
@login_required
def optimize_schedule(order_id):
    """Оптимизация расписания заказа"""
    order = Order.query.get_or_404(order_id)
    
    if current_user.role not in [
        UserRole.SALON_MANAGER.value,
        UserRole.SALON_HEAD.value,
        UserRole.ADMIN.value,
        UserRole.DIRECTOR.value,
        UserRole.HEAD_DESIGNER.value
    ]:
        flash('У вас нет прав для оптимизации расписания.', 'danger')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    optimization = ScheduleService.get_schedule_optimization(order)
    
    if not optimization['can_optimize']:
        flash('Нет возможностей для оптимизации расписания', 'info')
        return redirect(url_for('main.order_detail', order_id=order_id))
    
    apply_changes = request.form.get('apply_changes', 'false') == 'true'
    
    result = ScheduleService.optimize_schedule(
        order, current_user, apply_changes=apply_changes
    )
    
    if result['success']:
        flash(result['message'], 'success')
        
        if result['changes']:
            changes_html = "<br>".join([f"• {change['message']}" for change in result['changes'][:3]])
            flash(f'Изменения: {changes_html}', 'info')
    else:
        flash(result['message'], 'warning')
    
    if result['conflicts']:
        critical_conflicts = [c for c in result['conflicts'] if c['severity'] in ['danger', 'warning']]
        if critical_conflicts:
            conflicts_html = "<br>".join([f"⚠️ {c['message']}" for c in critical_conflicts[:2]])
            flash(f'Конфликты: {conflicts_html}', 'danger')
    
    return redirect(url_for('main.order_detail', order_id=order_id))


@main.route('/orders/<int:order_id>/schedule_summary', methods=['GET'])
@login_required
def schedule_summary(order_id):
    """Полная сводка по расписанию заказа"""
    order = Order.query.get_or_404(order_id)
    
    if not OrderService.can_view_order(order, current_user):
        flash('У вас нет прав для просмотра этого заказа.', 'danger')
        return redirect(url_for('main.index'))
    
    summary = ScheduleService.get_schedule_summary(order)
    
    return render_template('orders/schedule_summary.html',
                         order=order,
                         summary=summary,
                         OrderStatus=OrderStatus)   


@main.route('/push/subscribe', methods=['POST', 'OPTIONS'])
@login_required
def push_subscribe():
    """Подписка на push-уведомления"""
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        subscription = data.get('subscription')
        if not subscription:
            return jsonify({'success': False, 'error': 'Нет subscription данных'}), 400
        
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        from app.services.web_push_service import WebPushService
        success, message = WebPushService.subscribe(
            current_user.id,
            subscription,
            user_agent
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        current_app.logger.error(f"Ошибка подписки на push: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@main.route('/push/unsubscribe', methods=['POST', 'OPTIONS'])
@login_required
def push_unsubscribe():
    """Отписка от push-уведомлений"""
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    try:
        data = request.get_json()
        endpoint = data.get('endpoint') if data else None
        
        from app.services.web_push_service import WebPushService
        success, message = WebPushService.unsubscribe(current_user.id, endpoint)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        current_app.logger.error(f"Ошибка отписки от push: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@main.route('/notifications')
@login_required
def notifications_center():
    """Центр уведомлений"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('notifications/center.html',
                         notifications=notifications,
                         NotificationService=NotificationService)


@main.route('/api/notifications/unread')
@login_required
def get_unread_notifications_api():
    """API для получения непрочитанных уведомлений"""
    notifications = NotificationService.get_unread_notifications(current_user.id, limit=10)
    
    result = []
    for n in notifications:
        result.append({
            'id': n.id,
            'title': n.title,
            'message': n.message[:100] + ('...' if len(n.message) > 100 else ''),
            'created_at': n.created_at.isoformat(),
            'order_id': n.order_id,
            'icon': NotificationService.NOTIFICATION_ICONS.get(n.notification_type, 'bi-bell'),
            'color': NotificationService.NOTIFICATION_COLORS.get(n.notification_type, 'secondary')
        })
    
    return jsonify({
        'count': len(result),
        'notifications': result
    })    


@main.route('/push/vapid-public-key', methods=['GET'])
@login_required
def get_vapid_public_key():
    """Получение публичного ключа VAPID для клиента"""
    from app.config import Config
    response = jsonify({
        'success': True,
        'public_key': Config.VAPID_PUBLIC_KEY
    })
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response