from flask_sqlalchemy import SQLAlchemy

# Single shared SQLAlchemy instance, initialised in the app factory.
db = SQLAlchemy()
