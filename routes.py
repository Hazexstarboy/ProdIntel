from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime, date
from scheduler import generate_schedule, generate_schedule_for_deadline, regenerate_all_schedules

from app import app

from models import db, User, Procedure, Job, Schedule

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
    email = request.form.get('email')
    password = request.form.get('password')
    if email == '' or password == '':
        flash('email or Password cannot be empty.')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User does not exist.')
        return redirect(url_for('login'))
    if not user.check_password(password):
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
    
@app.route('/admin')
@auth_required
def admin():
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('admin.html', user=user)

@app.route('/prodmanager')
@auth_required
def prodmanager():
    user = User.query.get(session['user_id'])
    if not user.is_prodmanager:
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('prodmanager.html', user=user)

@app.route('/storemanager')
@auth_required
def storemanager():
    user = User.query.get(session['user_id'])
    if not user.is_storemanager:
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('storemanager.html', user=user)

@app.route('/prodsupervisor')
@auth_required
def prodsupervisor():
    user = User.query.get(session['user_id'])
    if not user.is_prodsupervisor:
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('prodsupervisor.html', user=user)

@app.route('/storesupervisor')
@auth_required
def storesupervisor():
    user = User.query.get(session['user_id'])
    if not user.is_storesupervisor:
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('storesupervisor.html', user=user)

@app.route('/dispatch')
@auth_required
def dispatch():
    user = User.query.get(session['user_id'])
    if not user.is_dispatch:
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('dispatch.html', user=user)

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

@app.route('/grn')
@auth_required
def grn():
    return render_template('grn.html', user=User.query.get(session['user_id']))

@app.route('/schedule')
@auth_required
def schedule():
    schedules = db.session.query(Schedule, Job.job_name, Procedure.procedure_name).join(Job, Schedule.job_id == Job.id).join(Procedure, Schedule.procedure_id == Procedure.id).all()

    schedule_list = []
    for s, job_name, procedure_name in schedules:
        schedule_list.append({'job_name': job_name, 'procedure_name': procedure_name, 'start_datetime': s.start_datetime, 'end_datetime': s.end_datetime, 'planned_time': s.planned_time, 'planned_manpower': s.planned_manpower})

    return render_template('schedule.html', user=User.query.get(session['user_id']), schedules=schedule_list)

@app.route('/progress')
@auth_required
def progress():
    return render_template('progress.html', user=User.query.get(session['user_id']))

@app.route('/procedure')
@auth_required
def procedure():
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager or user.is_storemanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('procedure.html', user=user, procedures=Procedure.query.all())

@app.route('/job')
@auth_required
def job():
    return render_template('job.html', user=User.query.get(session['user_id']), jobs=Job.query.all())

@app.route('/profile')
@auth_required
def profile():
    return render_template('profile.html', user=User.query.get(session['user_id']))

@app.route('/profile', methods=['POST'])
@auth_required
def profile_post():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    cpassword = request.form.get('cpassword')

    if username == '':
        flash('Username cannot be empty.')
        return redirect(url_for('profile'))
    
    if email == '':
        flash('Email cannot be empty.')
        return redirect(url_for('profile'))
    
    if password == '' or cpassword == '':
        flash('Password cannot be empty.')
        return redirect(url_for('profile'))
    
    user = User.query.get(session['user_id'])

    if not check_password_hash(user.password_hash, cpassword):
        flash('Incorrect Password.')
        return redirect(url_for('profile'))
    
    if username != user.username:
        new_username = User.query.filter_by(username=username).first()
        if new_username:
            flash('Username already exists.')
            return redirect(url_for('profile'))
        
    new_password_hash = generate_password_hash(password)
    user.username = username
    user.email = email
    user.password_hash = new_password_hash
    db.session.commit()
    flash('Profile Updated Successfully.')
    return redirect(url_for('profile'))

@app.route('/logout')
@auth_required
def logout():
    session.pop('user_id')
    return redirect(url_for('login'))

@app.route('/procedure/add')
@auth_required
def add_procedure():
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager or user.is_storemanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('procedure/add.html', user=user)

@app.route('/procedure/add', methods=['POST'])
@auth_required
def add_procedure_post():
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager or user.is_storemanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    
    procedure_name = request.form.get('procedure_name')
    procedure_description = request.form.get('procedure_description')
    procedure_plantime = request.form.get('procedure_plantime')
    procedure_planmanpower = request.form.get('procedure_planmanpower')
    sequence = request.form.get('sequence')

    if procedure_name == '':
        flash('Procedure Name cannot be empty.')
        return redirect(url_for('add_procedure'))
    
    if procedure_description == '':
        flash('Procedure Description cannot be empty.')
        return redirect(url_for('add_procedure'))

    if procedure_plantime == '' or not procedure_plantime.isdigit():
        flash('Procedure Plan Time must be a valid number.')
        return redirect(url_for('add_procedure'))
    
    if procedure_planmanpower == '' or not procedure_planmanpower.isdigit():
        flash('Procedure Plan Manpower must be a valid number.')
        return redirect(url_for('add_procedure'))
    
    if sequence == '' or not sequence.isdigit():
        flash('Sequence must be a valid number.')
        return redirect(url_for('add_procedure'))
    
    if user.is_prodmanager:
        procedure = Procedure(procedure_name=procedure_name, procedure_description=procedure_description, procedure_plantime=int(procedure_plantime), procedure_planmanpower=int(procedure_planmanpower), sequence=int(sequence), procedure_is_prod=True, procedure_is_store=False)
    elif user.is_storemanager:
        procedure = Procedure(procedure_name=procedure_name, procedure_description=procedure_description, procedure_plantime=int(procedure_plantime), procedure_planmanpower=int(procedure_planmanpower), sequence=int(sequence), procedure_is_prod=False, procedure_is_store=True)
    db.session.add(procedure)
    db.session.commit()
    
    # Regenerate all schedules since procedures have changed
    regenerate_all_schedules()
    
    flash('Procedure added successfully.')
    return redirect(url_for('procedure'))

@app.route('/procedure/<int:id>/edit')
@auth_required
def edit_procedure(id):
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager or user.is_storemanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('procedure/edit.html', user=user, procedure=Procedure.query.get(id))

@app.route('/procedure/<int:id>/edit', methods=['POST'])
@auth_required
def edit_procedure_post(id):
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager or user.is_storemanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    
    procedure = Procedure.query.get(id)

    procedure_name = request.form.get('procedure_name')
    procedure_description = request.form.get('procedure_description')
    procedure_plantime = request.form.get('procedure_plantime')
    procedure_planmanpower = request.form.get('procedure_planmanpower')
    sequence = request.form.get('sequence')

    if procedure_name == '':
        flash('Procedure Name cannot be empty.')
        return redirect(url_for('edit_procedure', id=id))
    
    if procedure_description == '':
        flash('Procedure Description cannot be empty.')
        return redirect(url_for('edit_procedure', id=id))
    
    if procedure_plantime == '' or not procedure_plantime.isdigit():
        flash('Procedure Plan Time must be a valid number.')
        return redirect(url_for('edit_procedure', id=id))
    
    if procedure_planmanpower == '' or not procedure_planmanpower.isdigit():
        flash('Procedure Plan Manpower must be a valid number.')
        return redirect(url_for('edit_procedure', id=id))
    
    if sequence == '' or not sequence.isdigit():
        flash('Sequence must be a valid number.')
        return redirect(url_for('edit_procedure', id=id))
    
    procedure.procedure_name = procedure_name
    procedure.procedure_description = procedure_description
    procedure.procedure_plantime = int(procedure_plantime)
    procedure.procedure_planmanpower = int(procedure_planmanpower)
    procedure.sequence = int(sequence)
    db.session.commit()
    
    # Regenerate all schedules since procedures have changed
    regenerate_all_schedules()
    
    flash('Procedure updated successfully.')
    return redirect(url_for('procedure'))

@app.route('/procedure/<int:id>/delete')
@auth_required
def delete_procedure(id):
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager or user.is_storemanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('procedure/delete.html', user=user, procedure=Procedure.query.get(id))

@app.route('/procedure/<int:id>/delete', methods=['POST'])
@auth_required
def delete_procedure_post(id):
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager or user.is_storemanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    
    procedure = Procedure.query.get(id)
    if not procedure:
        flash('Procedure not found.')
        return redirect(url_for('procedure'))
    db.session.delete(procedure)
    db.session.commit()
    
    # Regenerate all schedules since procedures have changed
    regenerate_all_schedules()
    
    flash('Procedure deleted successfully.')
    return redirect(url_for('procedure'))

@app.route('/job/add')
@auth_required
def add_job():
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('job/add.html', user=user)

@app.route('/job/add', methods=['POST'])
@auth_required
def add_job_post():
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    
    job_name = request.form.get('job_name')
    job_description = request.form.get('job_description')
    deadline_date = request.form.get('deadline_date')
    deadline_time = request.form.get('deadline_time')
    
    if job_name == '':
        flash('Job Name cannot be empty.')
        return redirect(url_for('add_job'))
    
    if job_description == '':
        flash('Job Description cannot be empty.')
        return redirect(url_for('add_job'))

    if deadline_date == '' or not deadline_date:
        flash('Completion Date must be a valid date.')
        return redirect(url_for('add_job'))
    
    if deadline_time == '' or not deadline_time:
        flash('Completion Time must be a valid time.')
        return redirect(url_for('add_job'))

    deadline_date_obj = date.fromisoformat(deadline_date)
    deadline_time_obj = datetime.strptime(deadline_time, '%H:%M').time()

    job = Job(job_name=job_name, job_description=job_description, deadline_date=deadline_date_obj, deadline_time=deadline_time_obj)
    db.session.add(job)
    db.session.commit()
    
    # Regenerate all schedules since a new job has been added
    regenerate_all_schedules()

    flash('Job added successfully.')
    return redirect(url_for('job'))

@app.route('/job/<int:id>/edit')
@auth_required
def edit_job(id):
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('job/edit.html', user=user, job=Job.query.get(id))

@app.route('/job/<int:id>/edit', methods=['POST'])
@auth_required
def edit_job_post(id):
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    
    job = Job.query.get(id)

    job_name = request.form.get('job_name')
    job_description = request.form.get('job_description')
    deadline_date = request.form.get('deadline_date')
    deadline_time = request.form.get('deadline_time')

    if job_name == '':
        flash('Job Name cannot be empty.')
        return redirect(url_for('edit_job', id=id))
    
    if job_description == '':
        flash('Job Description cannot be empty.')
        return redirect(url_for('edit_job', id=id))
    
    if deadline_date == '' or not deadline_date:
        flash('Completion Date must be a valid date.')
        return redirect(url_for('edit_job', id=id))
    
    if deadline_time == '' or not deadline_time:
        flash('Completion Time must be a valid time.')
        return redirect(url_for('edit_job', id=id))
    
    job.job_name = job_name
    job.job_description = job_description
    job.deadline_date = date.fromisoformat(deadline_date)
    job.deadline_time = datetime.strptime(deadline_time, '%H:%M').time()
    db.session.commit()
    
    # Regenerate all schedules since job has been updated
    regenerate_all_schedules()
    
    flash('Job updated successfully.')
    return redirect(url_for('job'))

@app.route('/job/<int:id>/delete')
@auth_required
def delete_job(id):
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    return render_template('job/delete.html', user=user, job=Job.query.get(id))

@app.route('/job/<int:id>/delete', methods=['POST'])
@auth_required
def delete_job_post(id):
    user = User.query.get(session['user_id'])
    if not (user.is_admin or user.is_prodmanager):
        flash('You are not authorized to access this page.')
        return redirect(url_for('index'))
    
    job = Job.query.get(id)
    if not job:
        flash('Job not found.')
        return redirect(url_for('job'))
    db.session.delete(job)
    db.session.commit()
    
    # Regenerate all schedules since job has been deleted
    regenerate_all_schedules()
    
    flash('Job deleted successfully.')
    return redirect(url_for('job'))