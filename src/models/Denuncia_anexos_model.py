from src.settings.extensions import db

class DenunciaAnexos(db.Model):
    
    __tablename__ = "denuncias_anexos"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relação com tabela de denuncias:
    id_denuncia = db.Column(db.Integer, db.ForeignKey('denuncias.id'), nullable=False, index=True)
    denuncia = db.relationship("Denuncia", back_populates='anexos')
    
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    
    def __init__(self, id_denuncia, file_path, file_type, original_name):
        self.id_denuncia = id_denuncia
        self.file_path = file_path
        self.file_type = file_type
        self.original_name = original_name
        
    def __repr__(self):
        return f"Anexo: {self.id} - {self.file_type}"
