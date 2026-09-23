from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from src.settings.extensions import db

PASSWORD_HASH_PREFIXES = ("scrypt:", "pbkdf2:", "argon2:")

class Usuario(db.Model, UserMixin):
    
    __tablename__ = "usuarios"
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    senha = db.Column(db.String(255), nullable=False)
    
    def __init__(self, nome, email, senha):
        self.nome = nome
        self.email = email.strip().lower()
        if self.is_password_hash(senha):
            self.senha = senha
        else:
            self.set_password(senha)

    @staticmethod
    def is_password_hash(senha):
        return isinstance(senha, str) and senha.startswith(PASSWORD_HASH_PREFIXES)

    def set_password(self, senha):
        self.senha = generate_password_hash(senha)

    def check_password(self, senha):
        try:
            return check_password_hash(self.senha, senha)
        except (TypeError, ValueError):
            return False

    def is_legacy_password(self, senha):
        return not self.is_password_hash(self.senha) and self.senha == senha
    
    def __repr__(self):
        return f"User: {self.nome} - {self.email}"
