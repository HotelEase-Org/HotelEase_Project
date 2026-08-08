def register_blueprints(app):
    from .auth import auth_bp
    from .guest import guest_bp
    from .reception import reception_bp
    from .housekeeping import housekeeping_bp
    from .manager import manager_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(guest_bp)
    app.register_blueprint(reception_bp)
    app.register_blueprint(housekeeping_bp)
    app.register_blueprint(manager_bp)
