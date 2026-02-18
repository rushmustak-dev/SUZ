# production_system_v2/app/auth.py
"""
Аутентификация пользователей (только вход, регистрация через админку)
"""

from flask import render_template, redirect, url_for, flash, request, Blueprint
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import db
from app.models import User
from app.forms import LoginForm
from app.permissions import admin_required

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему"""
    # Если пользователь уже авторизован, перенаправляем на главную
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        # Ищем пользователя по email
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            # Проверяем пароль
            if check_password_hash(user.password_hash, form.password.data):
                # Проверяем активен ли пользователь
                if user.is_active:
                    login_user(user, remember=form.remember.data)
                    
                    # Перенаправление на запрошенную страницу
                    next_page = request.args.get('next')
                    if not next_page or not next_page.startswith('/'):
                        next_page = url_for('main.index')
                    
                    flash(f'Добро пожаловать, {user.username}!', 'success')
                    return redirect(next_page)
                else:
                    flash('Ваш аккаунт отключен. Обратитесь к администратору.', 'warning')
            else:
                flash('Неверный email или пароль.', 'danger')
        else:
            flash('Неверный email или пароль.', 'danger')
    
    return render_template('auth/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('auth.login'))


@auth.route('/admin/create_user', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    """Создание пользователя администратором"""
    from app.forms import UserForm
    
    form = UserForm()
    
    if form.validate_on_submit():
        # Проверяем, не существует ли уже пользователь с таким email
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Пользователь с таким email уже существует.', 'danger')
            return redirect(url_for('auth.create_user'))
        
        try:
            # Создаём нового пользователя
            user = User(
                username=form.username.data,
                email=form.email.data,
                role=form.role.data,
                is_active=form.is_active.data
            )
            
            # Генерируем пароль
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            password = ''.join(secrets.choice(alphabet) for i in range(10))
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # TODO: Отправить пароль на email пользователя
            
            flash(f'Пользователь {user.username} создан. Пароль: {password}', 'success')
            return redirect(url_for('main.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании пользователя: {str(e)}', 'danger')
    
    return render_template('auth/create_user.html', form=form)