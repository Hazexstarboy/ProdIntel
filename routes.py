from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date

from app import app

from models import db, User

def auth_required(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if 'user_id' not in session:
            flash('You need to Login first.')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return inner

def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

@app.route('/login')
def login():
    return render_template('login.html', user=None)

@app.route('/login', methods=['POST'])
def login_post():
    email = request.form.get('username')
    password = request.form.get('password')
    if email == '' or password == '':
        flash('Username or Password cannot be empty.')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User does not exist.')
        return redirect(url_for('login'))
    if not check_password_hash(password):
        flash('Incorrect Password.')
        return redirect(url_for('login'))
    
    session['user_id'] = user.id

    if user.is_admin:
        return redirect(url_for('admin'))
    elif user.is_prodmanager:
        return redirect(url_for('prodmanager'))
    elif user.is_storemanager:
        return redirect(url_for('storemanager'))
    elif user.is_prodsupervisor:
        return redirect(url_for('prodsupervisor'))
    elif user.is_storesupervisor:
        return redirect(url_for('storesupervisor'))
    elif user.is_dispatch:
        return redirect(url_for('dispatch'))
    else:
        return redirect(url_for('index'))
    
@app.route('/')
@auth_required
def index():
    user = get_current_user()
    if user is None:
        flash('User not found.')
        return redirect(url_for('login'))
    if user.is_admin:
        return redirect(url_for('admin'))
    elif user.is_prodmanager:
        return redirect(url_for('prodmanager'))
    elif user.is_storemanager:
        return redirect(url_for('storemanager'))
    elif user.is_prodsupervisor:
        return redirect(url_for('prodsupervisor'))
    elif user.is_storesupervisor:
        return redirect(url_for('storesupervisor'))
    elif user.is_dispatch:
        return redirect(url_for('dispatch'))
    else:
        return render_template('index.html', user=user)
    
@app.route('/admin')
@auth_required
def admin():
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('admin.html', user=user)