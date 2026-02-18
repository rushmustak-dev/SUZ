# production_system_v2/app/models.py
from datetime import datetime
from app import db
from app.config import OrderStatus, UserRole


class TimestampMixin:
    """Миксин для временных меток"""
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Client(db.Model, TimestampMixin):
    """Модель клиента"""
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    passport_data = db.Column(db.String(200), nullable=True)
    inn = db.Column(db.String(20), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    
    # Связь с заказами
    orders = db.relationship('Order', backref='client_ref', lazy='dynamic')
    
    def __repr__(self):
        return f'<Client {self.full_name} ({self.phone})>'


class User(db.Model, TimestampMixin):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default=UserRole.CLIENT, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    telegram_id = db.Column(db.String(50), nullable=True)
    
    orders_as_designer = db.relationship('Order', foreign_keys='Order.designer_id', backref='designer')
    orders_as_manager = db.relationship('Order', foreign_keys='Order.salon_manager_id', backref='salon_manager')
    notifications = db.relationship('Notification', 
                                   foreign_keys='Notification.user_id',
                                   backref='notification_user',
                                   lazy='dynamic',
                                   cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
    
    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False


class Seller(db.Model, TimestampMixin):
    """Модель продавца"""
    __tablename__ = 'sellers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    manager = db.relationship('User', foreign_keys=[manager_id], backref='sellers')
    orders = db.relationship('Order', backref='seller', lazy='dynamic')
    
    def __repr__(self):
        return f'<Seller {self.name}>'


class Order(db.Model, TimestampMixin):
    """Модель заказа"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    order_code = db.Column(db.String(12), nullable=True, default='')
    
    # НОВОЕ ПОЛЕ: связь с клиентом
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True, index=True)
    
    customer_name = db.Column(db.String(200), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(120))
    
    seller_id = db.Column(db.Integer, db.ForeignKey('sellers.id'))
    
    amount = db.Column(db.Float, nullable=False, default=0.0)
    furniture_amount = db.Column(db.Float, default=0.0)
    measurement_cost = db.Column(db.Float, default=0.0)
    other_costs = db.Column(db.Float, default=0.0)
    prepayment_amount = db.Column(db.Float, default=0.0)
    prepayment_method = db.Column(db.String(20))
    prepayment_date = db.Column(db.DateTime)
    
    deadline_date = db.Column(db.DateTime)
    installation_date = db.Column(db.DateTime)
    installation_address = db.Column(db.String(300), nullable=True)
    delivery_date = db.Column(db.DateTime)
    design_ready_date = db.Column(db.DateTime)
    archived_at = db.Column(db.DateTime)
    reclamation_date = db.Column(db.DateTime)
    
    status = db.Column(db.String(30), default=OrderStatus.NEW.value, nullable=False, index=True)
    
    salon_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    designer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    notes = db.Column(db.Text)
    reclamation_reason = db.Column(db.Text)
    
    product_name = db.Column(db.String(200), nullable=False, default='', server_default='', index=True)
    
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    deletion_reason = db.Column(db.Text)
    
    is_archived = db.Column(db.Boolean, default=False, index=True)
    is_reclamation = db.Column(db.Boolean, default=False, index=True)
    
    status_history = db.relationship('OrderStatusHistory', backref='status_order', lazy='dynamic')
    files = db.relationship('OrderFile', backref='file_order', lazy='dynamic')
    notifications = db.relationship('Notification', backref='notification_order', lazy='dynamic')
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])
    
    def __repr__(self):
        return f'<Order {self.order_number} ({self.status})>'


class OrderStatusHistory(db.Model, TimestampMixin):
    """История изменения статусов заказа"""
    __tablename__ = 'order_status_history'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    old_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notes = db.Column(db.Text)
    
    changed_by = db.relationship('User', foreign_keys=[changed_by_id])
    
    def __repr__(self):
        return f'<StatusHistory {self.order_id}: {self.old_status} -> {self.new_status}>'


class Notification(db.Model, TimestampMixin):
    """Уведомления"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    NOTIFICATION_TYPES = {
        'order_created': 'Создан заказ',
        'designer_assigned': 'Назначен конструктор',
        'design_created': 'Создан эскиз',
        'design_client_approved': 'Эскиз согласован',
        'design_completed': 'Разработка завершена',
        'purchase_completed': 'Закупка завершена',
        'return_to_design': 'Возврат на доработку',
        'quality_check': 'Проверка ОТК',
        'ready_for_delivery': 'Готов к отгрузке',
        'status_changed': 'Изменен статус',
        'file_uploaded': 'Загружен файл',
        'comment_added': 'Добавлен комментарий',
        'order_updated': 'Заказ изменен',
        'supplier_requests_generated': 'Сгенерированы заявки поставщикам',
        'system': 'Системное'
    }
    
    notification_type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime)
    details = db.Column(db.JSON)
    
    def __repr__(self):
        return f'<Notification {self.title} for {self.user_id}>'
    
    def get_type_display(self):
        return self.NOTIFICATION_TYPES.get(self.notification_type, self.notification_type)
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = datetime.utcnow()


class OrderFile(db.Model, TimestampMixin):
    """Файлы заказа"""
    __tablename__ = 'order_files'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    
    FILE_TYPES = {
        'source': 'Исходные файлы',
        'design': 'Файлы разработки',
        'review': 'Файлы согласования',
        'specification': 'Спецификации',
        'supplier_request': 'Заявки поставщикам',
        'other': 'Прочие файлы'
    }
    
    file_type = db.Column(db.String(20), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    description = db.Column(db.String(500))
    
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    uploaded_by = db.relationship('User', foreign_keys=[uploaded_by_id])
    
    def __repr__(self):
        return f'<OrderFile {self.filename} ({self.file_type})>'
    
    def get_file_type_display(self):
        return self.FILE_TYPES.get(self.file_type, self.file_type)
    
    def get_file_extension(self):
        if '.' in self.filename:
            return self.filename.split('.')[-1].lower()
        return ''
    
    def get_file_icon(self):
        extension = self.get_file_extension()
        
        if extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg']:
            return 'bi-file-image'
        elif extension == 'pdf':
            return 'bi-file-pdf'
        elif extension in ['doc', 'docx']:
            return 'bi-file-word'
        elif extension in ['xls', 'xlsx', 'csv']:
            return 'bi-file-excel'
        elif extension in ['dwg', 'dxf']:
            return 'bi-file-earmark-ruled'
        elif extension in ['zip', 'rar', '7z']:
            return 'bi-file-zip'
        else:
            return 'bi-file-earmark'
    
    def get_readable_size(self):
        if not self.file_size:
            return '0 Б'
        
        size = self.file_size
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"


class SystemSetting(db.Model):
    """Системные настройки"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False, index=True)
    data_type = db.Column(db.String(20), default='string')
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemSetting {self.key}>'


class PushSubscription(db.Model):
    """Подписки на push-уведомления"""
    __tablename__ = 'push_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    endpoint = db.Column(db.String(500), nullable=False, unique=True)
    auth_key = db.Column(db.String(100), nullable=False)
    p256dh_key = db.Column(db.String(200), nullable=False)
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='push_subscriptions')