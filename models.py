from mimetypes import inited
from app import app
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

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
        prodsupervisor = User(username = 'prodsupervisor', email = 'prodsupervisor', password = 'prodsupervisor', is_prodsupervisor = True)
        db.session.add(prodsupervisor)
        db.session.commit()
    dispatch = User.query.filter_by(username='dispatch').first()
    if not dispatch:
        dispatch = User(username = 'dispatch', email = 'dispatch@gmail.com', password = 'dispatch', is_dispatch = True)
        db.session.add(dispatch)
        db.session.commit()