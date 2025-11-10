import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

def create_app():
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///budget.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    from .models import User, Category, Transaction, Budget, Report  # noqa

    with app.app_context():
        db.create_all()
        ensure_seed_data()

    from .blueprints.auth import bp as auth_bp
    from .blueprints.core import bp as core_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(core_bp)
    return app

def ensure_seed_data():
    from .models import User, Category, db
    if not User.query.filter_by(email="admin@gmail.com").first():
        u = User(email="admin@gmail.com")
        u.set_password("admin123")
        u.is_admin = True
        db.session.add(u)
        db.session.commit()
    if Category.query.count()==0:
        for name, ctype in [
            ("Income","income"),("Salary","income"),("Bonus","income"),
            ("Groceries","expense"),("Rent","expense"),("Utilities","expense"),
            ("Transport","expense"),("Dining","expense"),("Health","expense"),
            ("Entertainment","expense"),("Misc","expense")
        ]:
            db.session.add(Category(name=name, type=ctype))
        db.session.commit()
