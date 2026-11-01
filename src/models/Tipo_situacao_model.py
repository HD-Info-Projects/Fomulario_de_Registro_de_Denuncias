from hashlib import sha256
import unicodedata

from src.settings.extensions import db


def tipo_nome_chave(nome):
    normalizado = unicodedata.normalize("NFKC", " ".join(nome.split())).casefold()
    return sha256(normalizado.encode("utf-8")).hexdigest()


class TipoSituacao(db.Model):
    __tablename__ = "tipos_situacao"
    __table_args__ = (db.UniqueConstraint("chave_nome", name="uq_tipos_situacao_chave_nome"),)

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    chave_nome = db.Column(db.String(64), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())

    denuncias = db.relationship("Denuncia", back_populates="tipo_situacao")

    def __init__(self, nome, descricao=None):
        self.set_nome(nome)
        self.descricao = descricao
        self.ativo = True

    def set_nome(self, nome):
        self.nome = " ".join(nome.split())
        self.chave_nome = tipo_nome_chave(self.nome)
