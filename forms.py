# production_system_v2/app/forms.py
"""
Формы для системы
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField, FloatField, DateField, IntegerField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError, NumberRange
from app.config import UserRole, OrderStatus
from app.models import User, Client
from flask_wtf.file import FileField, FileAllowed, MultipleFileField


class LoginForm(FlaskForm):
    """Форма входа в систему"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


# ========== НОВАЯ ФОРМА: КЛИЕНТ ==========
class ClientForm(FlaskForm):
    """Форма создания/редактирования клиента"""
    full_name = StringField('ФИО клиента', validators=[
        DataRequired(message='Введите ФИО клиента'),
        Length(min=3, max=200, message='ФИО должно быть от 3 до 200 символов')
    ])
    
    phone = StringField('Телефон', validators=[
        DataRequired(message='Введите телефон клиента'),
        Length(min=10, max=20, message='Телефон должен быть от 10 до 20 символов')
    ])
    
    email = StringField('Email', validators=[
        Optional(),
        Email(message='Введите корректный email адрес')
    ])
    
    address = StringField('Адрес', validators=[
        Optional(),
        Length(max=300, message='Адрес не должен превышать 300 символов')
    ])
    
    passport_data = StringField('Паспортные данные', validators=[
        Optional(),
        Length(max=200, message='Паспортные данные не должны превышать 200 символов')
    ])
    
    inn = StringField('ИНН', validators=[
        Optional(),
        Length(min=10, max=12, message='ИНН должен содержать 10 или 12 цифр')
    ])
    
    comment = TextAreaField('Комментарий', validators=[Optional()])
    
    submit = SubmitField('Сохранить')


# ========== НОВАЯ ФОРМА: ПОИСК КЛИЕНТА ==========
class ClientSearchForm(FlaskForm):
    """Форма поиска клиента"""
    search = StringField('Поиск', validators=[Optional()])
    submit = SubmitField('Найти')


class UserForm(FlaskForm):
    """Форма создания пользователя (админ)"""
    username = StringField('Имя пользователя', validators=[
        DataRequired(), 
        Length(min=3, max=64, message='Имя должно быть от 3 до 64 символов')
    ])
    
    email = StringField('Email', validators=[
        DataRequired(), 
        Email(message='Введите корректный email адрес')
    ])
    
    role = SelectField('Роль', 
                       choices=UserRole.get_choices_for_form(),
                       validators=[DataRequired()])
    
    is_active = BooleanField('Активен', default=True)
    submit = SubmitField('Создать пользователя')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Этот email уже зарегистрирован.')


class SellerForm(FlaskForm):
    """Форма создания/редактирования продавца"""
    name = StringField('Имя продавца', validators=[
        DataRequired(message='Введите имя продавца'),
        Length(min=2, max=100, message='Имя должно быть от 2 до 100 символов')
    ])
    phone = StringField('Телефон', validators=[
        Optional(),
        Length(max=20, message='Телефон не должен превышать 20 символов')
    ])
    email = StringField('Email', validators=[
        Optional(),
        Email(message='Введите корректный email адрес')
    ])
    is_active = BooleanField('Активен', default=True)
    submit = SubmitField('Сохранить')


class OrderForm(FlaskForm):
    """Форма создания заказа"""

    # НОВОЕ ПОЛЕ: выбор существующего клиента
    client_id = SelectField('Клиент', coerce=int, validators=[Optional()])
    
    # НОВОЕ ПОЛЕ: создание нового клиента (флаг)
    create_new_client = BooleanField('Создать нового клиента', default=False)
    
    customer_name = StringField('Имя заказчика', validators=[
        DataRequired(message='Введите имя заказчика'),
        Length(max=200, message='Имя не должно превышать 200 символов')
    ])
    
    customer_phone = StringField('Телефон', validators=[
        DataRequired(message='Введите телефон заказчика')
    ])
    
    customer_email = StringField('Email заказчика', validators=[
        Optional(),
        Email(message='Введите корректный email адрес')
    ])
    
    order_code = StringField('Дополнительный код (12 символов)', validators=[
        Optional(),
        Length(max=12, message='Код не должен превышать 12 символов')
    ])
    
    seller_id = SelectField('Продавец', coerce=int, validators=[Optional()])
    
    manager_id = SelectField('Менеджер', coerce=int, validators=[Optional()])
    
    amount = FloatField('Сумма заказа (руб.)', validators=[
        DataRequired(message='Введите сумму заказа'),
        NumberRange(min=0, message='Сумма должна быть положительной')
    ])
    
    furniture_amount = FloatField('Стоимость мебели (руб.)', validators=[
        DataRequired(message='Введите стоимость мебели'),
        NumberRange(min=0, message='Сумма должна быть положительной')
    ])
    
    measurement_cost = FloatField('Стоимость замера (руб.)', validators=[
        Optional(),
        NumberRange(min=0, message='Стоимость замера должна быть положительной')
    ])
    
    prepayment_amount = FloatField('Сумма предоплаты (руб.)', validators=[
        Optional(),
        NumberRange(min=0, message='Сумма должна быть положительной')
    ])
    
    other_costs = FloatField('Прочие расходы (руб.)', validators=[
        Optional(),
        NumberRange(min=0, message='Сумма должна быть положительной')
    ])
    
    prepayment_method = SelectField('Способ оплаты', choices=[
        ('', 'Не выбрано'),
        ('cash', 'Наличный расчет'),
        ('cashless', 'Безналичный расчет'),
        ('card', 'Банковская карта'),
        ('sbp', 'СБП (Система быстрых платежей)'),
        ('other', 'Другой способ')
    ], validators=[Optional()])
    
    prepayment_date = DateField('Дата предоплаты', format='%Y-%m-%d', validators=[Optional()])
    deadline_date = DateField('Срок выполнения', format='%Y-%m-%d', validators=[Optional()])
    installation_date = DateField('Дата монтажа', format='%Y-%m-%d', validators=[
        DataRequired(message='Укажите дату монтажа')
    ])
    installation_address = StringField('Адрес монтажа', validators=[
        Optional(),
        Length(max=300, message='Адрес не должен превышать 300 символов')
    ])
    
    source_files = MultipleFileField('Исходные файлы', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'dwg', 'dxf', 'zip', 'rar', 
                    'txt', 'rtf', 'ppt', 'pptx', 'psd', 'ai', 'cdr', 'skp', 'max', 'fbx', 'stl'],
                   'Разрешены изображения, документы, чертежи и архивы')
    ])
    
    # ИСПРАВЛЕННЫЕ МЕТОДЫ ВАЛИДАЦИИ - ВСЕ С ЗАЩИТОЙ ОТ NONE
    def validate_furniture_amount(self, field):
        # Проверяем, что оба значения не None перед сравнением
        if field.data is not None and self.amount.data is not None:
            if field.data > self.amount.data:
                raise ValidationError('Стоимость мебели не может превышать общую стоимость')

    def validate_amount(self, field):
        if field.data is not None:
            # Защита от None через or 0
            furniture = float(self.furniture_amount.data or 0)
            measurement = float(self.measurement_cost.data or 0)
            other = float(self.other_costs.data or 0)
            
            expected_total = furniture + measurement + other
            
            if abs(field.data - expected_total) > 0.01:
                raise ValidationError(
                    f'Общая стоимость ({field.data:.2f} ₽) должна равняться сумме: '
                    f'Мебель ({furniture:.2f} ₽) + Замер ({measurement:.2f} ₽) + Прочие ({other:.2f} ₽) = '
                    f'{expected_total:.2f} ₽'
                )

    def validate_measurement_cost(self, field):
        # Проверяем, что оба значения не None перед сравнением
        if field.data is not None and self.amount.data is not None:
            if field.data > self.amount.data:
                raise ValidationError('Стоимость замера не может превышать общую стоимость заказа')

    def validate_other_costs(self, field):
        # Проверяем, что оба значения не None перед сравнением
        if field.data is not None and self.amount.data is not None:
            if field.data > self.amount.data:
                raise ValidationError('Прочие расходы не могут превышать общую стоимость заказа')

    def validate_prepayment_amount(self, field):
        # Проверяем, что оба значения не None перед сравнением
        if field.data is not None and self.amount.data is not None:
            if field.data > self.amount.data:
                raise ValidationError('Сумма предоплаты не может превышать сумму заказа')
       
    product_name = StringField('Наименование изделия', 
                              validators=[DataRequired()],
                              render_kw={'placeholder': 'Кухня, шкаф-купе, гардеробная...'})
                              
    notes = TextAreaField('Примечания', validators=[Optional()])

    submit = SubmitField('Создать заказ')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from flask_login import current_user
        from app.models import User, Seller, Client
        
        # Заполняем список клиентов
        client_choices = [(0, '-- Не выбран --')]
        clients = Client.query.filter().order_by(Client.full_name).limit(100).all()
        client_choices += [(c.id, f"{c.full_name} ({c.phone})") for c in clients]
        self.client_id.choices = client_choices
        
        # Заполняем список продавцов
        seller_choices = [(0, 'Не выбран')]
        
        if current_user and current_user.is_authenticated:
            if current_user.role in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
                sellers = Seller.query.filter_by(is_active=True).order_by(Seller.name).all()
                seller_choices += [(s.id, s.name) for s in sellers]
            elif current_user.role == UserRole.SALON_MANAGER.value:
                sellers = Seller.query.filter_by(
                    manager_id=current_user.id, 
                    is_active=True
                ).order_by(Seller.name).all()
                seller_choices += [(s.id, s.name) for s in sellers]
        
        self.seller_id.choices = seller_choices
        
        # Заполняем менеджеров
        manager_choices = []
        if current_user and current_user.is_authenticated:
            if current_user.role in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
                managers = User.query.filter_by(role=UserRole.SALON_MANAGER.value, is_active=True).order_by(User.username).all()
                manager_choices = [(0, 'Выберите магазин')] + [(m.id, m.username) for m in managers]
            else:
                manager_choices = [(current_user.id, current_user.username)] if current_user.role == UserRole.SALON_MANAGER.value else []
        
        self.manager_id.choices = manager_choices


class OrderEditForm(FlaskForm):
    """Форма редактирования заказа (для админа и директора)"""
    product_name = StringField('Наименование изделия', 
                              validators=[DataRequired()],
                              render_kw={'placeholder': 'Кухня, шкаф-купе, гардеробная...'})
    
    # НОВОЕ ПОЛЕ: клиент
    client_id = SelectField('Клиент', coerce=int, validators=[Optional()])
    
    customer_name = StringField('Имя заказчика', validators=[
        DataRequired(message='Введите имя заказчика'),
        Length(max=200, message='Имя не должно превышать 200 символов')
    ])
    
    customer_phone = StringField('Телефон', validators=[
        DataRequired(message='Введите телефон заказчика')
    ])
    
    customer_email = StringField('Email заказчика', validators=[
        Optional(),
        Email(message='Введите корректный email адрес')
    ])
    
    order_code = StringField('Дополнительный код (12 символов)', validators=[
        Optional(),
        Length(max=12, message='Код не должен превышать 12 символов')
    ])
    
    seller_id = SelectField('Продавец', coerce=int, validators=[Optional()])
    
    manager_id = SelectField('Менеджер', coerce=int, validators=[Optional()])
    
    designer_id = SelectField('Конструктор', coerce=int, validators=[Optional()])
    
    amount = FloatField('Сумма заказа (руб.)', validators=[
        DataRequired(message='Введите сумму заказа'),
        NumberRange(min=0, message='Сумма должна быть положительной')
    ])
    
    furniture_amount = FloatField('Стоимость мебели (руб.)', validators=[
        DataRequired(message='Введите стоимость мебели'),
        NumberRange(min=0, message='Сумма должна быть положительной')
    ])
    
    measurement_cost = FloatField('Стоимость замера (руб.)', validators=[
        Optional(),
        NumberRange(min=0, message='Стоимость замера должна быть положительной')
    ])
    
    prepayment_amount = FloatField('Сумма предоплаты (руб.)', validators=[
        Optional(),
        NumberRange(min=0, message='Сумма должна быть положительной')
    ])
    
    other_costs = FloatField('Прочие расходы (руб.)', validators=[
        Optional(),
        NumberRange(min=0, message='Сумма должна быть положительной')
    ])
    
    prepayment_method = SelectField('Способ оплаты', choices=[
        ('', 'Не выбрано'),
        ('cash', 'Наличный расчет'),
        ('cashless', 'Безналичный расчет'),
        ('card', 'Банковская карта'),
        ('sbp', 'СБП (Система быстрых платежей)'),
        ('other', 'Другой способ')
    ], validators=[Optional()])
    
    prepayment_date = DateField('Дата предоплаты', format='%Y-%m-%d', validators=[Optional()])
    
    deadline_date = DateField('Срок выполнения', format='%Y-%m-%d', validators=[Optional()])
    
    installation_date = DateField('Дата монтажа', format='%Y-%m-%d', validators=[
        DataRequired(message='Укажите дату монтажа')
    ])
    installation_address = StringField('Адрес монтажа', validators=[
        Optional(),
        Length(max=300, message='Адрес не должен превышать 300 символов')
    ])
    
    design_ready_date = DateField('Дата готовности чертежей', format='%Y-%m-%d', validators=[Optional()])
    
    notes = TextAreaField('Примечания', validators=[Optional()])
    
    status = SelectField('Статус заказа', validators=[Optional()])
    
    submit = SubmitField('Сохранить изменения')
    
    # ИСПРАВЛЕННЫЕ МЕТОДЫ ВАЛИДАЦИИ - ВСЕ С ЗАЩИТОЙ ОТ NONE
    def validate_furniture_amount(self, field):
        # Проверяем, что оба значения не None перед сравнением
        if field.data is not None and self.amount.data is not None:
            if field.data > self.amount.data:
                raise ValidationError('Стоимость мебели не может превышать общую стоимость')

    def validate_amount(self, field):
        if field.data is not None:
            # Защита от None через or 0
            furniture = float(self.furniture_amount.data or 0)
            measurement = float(self.measurement_cost.data or 0)
            other = float(self.other_costs.data or 0)
            
            expected_total = furniture + measurement + other
            
            if abs(field.data - expected_total) > 0.01:
                raise ValidationError(
                    f'Общая стоимость ({field.data:.2f} ₽) должна равняться сумме: '
                    f'Мебель ({furniture:.2f} ₽) + Замер ({measurement:.2f} ₽) + Прочие ({other:.2f} ₽) = '
                    f'{expected_total:.2f} ₽'
                )

    def validate_prepayment_amount(self, field):
        # Проверяем, что оба значения не None перед сравнением
        if field.data is not None and self.amount.data is not None:
            if field.data > self.amount.data:
                raise ValidationError('Сумма предоплаты не может превышать сумму заказа')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from flask_login import current_user
        from app.models import User, Seller, Client
        
        # Заполняем список клиентов
        client_choices = [(0, '-- Не выбран --')]
        clients = Client.query.order_by(Client.full_name).limit(100).all()
        client_choices += [(c.id, f"{c.full_name} ({c.phone})") for c in clients]
        self.client_id.choices = client_choices
        
        # Заполняем список продавцов
        seller_choices = [(0, 'Не выбран')]
        
        if current_user and current_user.is_authenticated:
            if current_user.role in [UserRole.ADMIN.value, UserRole.DIRECTOR.value, UserRole.SALON_HEAD.value]:
                sellers = Seller.query.filter_by(is_active=True).order_by(Seller.name).all()
                seller_choices += [(s.id, s.name) for s in sellers]
        
        self.seller_id.choices = seller_choices
        
        # Заполняем список менеджеров
        manager_choices = [(0, 'Не выбран')]
        managers = User.query.filter_by(role=UserRole.SALON_MANAGER.value, is_active=True).order_by(User.username).all()
        manager_choices += [(m.id, m.username) for m in managers]
        self.manager_id.choices = manager_choices
        
        # Заполняем список конструкторов
        designer_choices = [(0, 'Не назначен')]
        designers = User.query.filter(
            User.role.in_([UserRole.DESIGNER.value, UserRole.HEAD_DESIGNER.value]),
            User.is_active == True
        ).order_by(User.username).all()
        designer_choices += [(d.id, d.username) for d in designers]
        self.designer_id.choices = designer_choices
        
        # Заполняем список статусов
        status_choices = [('', '--- Не изменять ---')]
        all_statuses = OrderStatus.get_all_statuses()
        status_choices += [(status[0], status[1]) for status in all_statuses]
        self.status.choices = status_choices


class OrderStatusForm(FlaskForm):
    """Форма изменения статуса заказа"""
    status = SelectField('Новый статус', validators=[DataRequired()])
    notes = TextAreaField('Комментарий', validators=[Optional()])
    submit = SubmitField('Изменить статус')
    
    def __init__(self, *args, available_statuses=None, **kwargs):
        super().__init__(*args, **kwargs)
        if available_statuses:
            normalized_choices = []
            for status_item in available_statuses:
                if hasattr(status_item, 'value'):
                    status_value = status_item.value
                else:
                    status_value = str(status_item)
                
                display_name = OrderStatus.get_display_name(status_value)
                normalized_choices.append((status_value, display_name))
            
            self.status.choices = normalized_choices
            
    manager_id = SelectField('Менеджер', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from flask_login import current_user
        from app.models import User
        
        if current_user and current_user.is_authenticated:
            if current_user.role not in ['salon_manager']:
                managers = User.query.filter_by(role='salon_manager', is_active=True).order_by(User.username).all()
                self.manager_id.choices = [(0, 'Выберите менеджера')] + [(m.id, m.username) for m in managers]
            else:
                self.manager_id.choices = [(current_user.id, current_user.username)]


class AssignDesignerForm(FlaskForm):
    """Форма назначения конструктора"""
    designer_id = SelectField('Конструктор', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Назначить')
    
    def __init__(self, *args, designers=None, **kwargs):
        super().__init__(*args, **kwargs)
        if designers:
            self.designer_id.choices = designers


class UploadFileForm(FlaskForm):
    """Форма загрузки файлов"""
    file_type = SelectField('Тип файлов', choices=[
        ('source', 'Исходные файлы'),
        ('design', 'Файлы разработки'),
        ('review', 'Файлы согласования'),
        ('specification', 'Спецификации'),
        ('other', 'Прочие файлы')
    ], validators=[DataRequired()])
    
    files = MultipleFileField('Файлы', validators=[
        DataRequired(message='Выберите файлы для загрузки'),
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'dwg', 'dxf', 'zip', 'rar'], 
                   'Разрешены изображения, документы и архивы')
    ])
    
    submit = SubmitField('Загрузить файлы')


class CommentForm(FlaskForm):
    """Форма добавления комментария"""
    comment = TextAreaField('Комментарий', validators=[
        DataRequired(message='Введите текст комментария'),
        Length(min=1, max=1000, message='Комментарий должен быть от 1 до 1000 символов')
    ])
    submit = SubmitField('Добавить комментарий')


class ChangePasswordForm(FlaskForm):
    """Форма изменения пароля"""
    current_password = PasswordField('Текущий пароль', validators=[
        DataRequired(message='Введите текущий пароль')
    ])
    new_password = PasswordField('Новый пароль', validators=[
        DataRequired(message='Введите новый пароль'),
        Length(min=6, message='Пароль должен быть не менее 6 символов')
    ])
    confirm_password = PasswordField('Подтвердите новый пароль', validators=[
        DataRequired(message='Подтвердите новый пароль')
    ])
    submit = SubmitField('Изменить пароль')