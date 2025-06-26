from app import app
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_prodmanager = db.Column(db.Boolean, nullable=False, default=False)
    is_storemanager = db.Column(db.Boolean, nullable=False, default=False)
    is_prodsupervisor = db.Column(db.Boolean, nullable=False, default=False)
    is_storesupervisor = db.Column(db.Boolean, nullable=False, default=False)
    is_dispatch = db.Column(db.Boolean, nullable=False, default=False)

    @property
    def password(self):
        raise AttributeError('Password is not readable')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Manager(db.Model):
    __tablename__ = 'manager'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    managers = db.relationship('User', backref='manager')

class Supervisor(db.Model):
    __tablename__ = 'supervisor'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    supervisors = db.relationship('User', backref='supervisor')

class Job(db.Model):
    __tablename__ = 'job'
    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(80), nullable=False)
    job_description = db.Column(db.String(200), nullable=False)
    deadline_date = db.Column(db.Date, nullable=False, default=lambda: datetime.today().date())
    deadline_time = db.Column(db.Time, nullable=False, default=lambda: datetime.utcnow().time())

class Material(db.Model):
    __tablename__ = 'material'
    id = db.Column(db.Integer, primary_key=True)
    material_name = db.Column(db.String(120), nullable=False)
    material_description = db.Column(db.String(200), nullable=False)
    material_supplier = db.Column(db.String(120), nullable=False)
    material_quantity = db.Column(db.Integer, nullable=False, default=0)

class Procedure(db.Model):
    __tablename__ = 'procedure'
    id = db.Column(db.Integer, primary_key=True)
    sequence = db.Column(db.Integer, nullable=False, default=0)
    procedure_name = db.Column(db.String(120), nullable=False)
    procedure_description = db.Column(db.String(520), nullable=False)
    procedure_plantime = db.Column(db.Integer, nullable=False, default=0)
    procedure_planmanpower = db.Column(db.Integer, nullable=False, default=0)
    procedure_is_prod = db.Column(db.Boolean, nullable=False, default=False)
    procedure_is_store = db.Column(db.Boolean, nullable=False, default=False)

class Schedule(db.Model):
    __tablename__ = 'schedule'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    procedure_id = db.Column(db.Integer, db.ForeignKey('procedure.id'), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    planned_time = db.Column(db.Integer, nullable=False, default=0)
    planned_manpower = db.Column(db.Integer, nullable=False, default=0)

    job = db.relationship('Job', backref='schedules')
    procedure = db.relationship('Procedure', backref='schedules')

class Progress(db.Model):
    __tablename__ = 'progress'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    procedure_id = db.Column(db.Integer, db.ForeignKey('procedure.id'), nullable=False)
    actual_time = db.Column(db.Integer, nullable=False, default=0)
    actual_manpower = db.Column(db.Integer, nullable=False, default=0)

with app.app_context():
    db.create_all()

    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username = 'admin', email = 'admin@gmail.com', password = 'admin', is_admin = True)
        db.session.add(admin)
        db.session.commit()
    prodmanager = User.query.filter_by(username='prodmanager').first()
    if not prodmanager:
        prodmanager = User(username = 'prodmanager', email = 'prodmanager@gmail.com', password = 'prodmanager', is_prodmanager = True)
        db.session.add(prodmanager)
        db.session.commit()
    storemanager = User.query.filter_by(username='storemanager').first()
    if not storemanager:
        storemanager = User(username = 'storemanager', email = 'storemanager@gmail.com', password = 'storemanager', is_storemanager = True)
        db.session.add(storemanager)
        db.session.commit()
    prodsupervisor = User.query.filter_by(username='prodsupervisor').first()
    if not prodsupervisor:
        prodsupervisor = User(username = 'prodsupervisor', email = 'prodsupervisor@gmail.com', password = 'prodsupervisor', is_prodsupervisor = True)
        db.session.add(prodsupervisor)
        db.session.commit()
    storesupervisor = User.query.filter_by(username='storesupervisor').first()
    if not storesupervisor:
        storesupervisor = User(username = 'storesupervisor', email = 'storesupervisor@gmail.com', password = 'storesupervisor', is_storesupervisor = True)
        db.session.add(storesupervisor)
        db.session.commit()