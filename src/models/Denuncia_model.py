from datetime import date
from enum import Enum
from src.settings.extensions import db

class StatusEnum(Enum):
    PENDENTE = 'pendente'
    EM_ANALISE = 'em_analise'
    SUSPENSO = 'suspenso'
    FINALIZADO = 'finalizado'

class Denuncia(db.Model):
    
    __tablename__ = "denuncias"
    
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(255), nullable=False)
    frequencia = db.Column(db.String(255), nullable=False)
    data = db.Column(db.Date, nullable=False, index=True)
    testemunha = db.Column(db.String(10), nullable=False)
    nomes_testemunhas = db.Column(db.Text(), nullable=True)
    descricao_do_fato = db.Column(db.Text, nullable=False)
    
    vitima_id = db.Column(db.Integer, db.ForeignKey("vitimas.id"), nullable=False, index=True)
    ofesor_id = db.Column(db.Integer, db.ForeignKey("ofesors.id"), nullable=False, index=True)
    
    vitima = db.relationship("Vitima", back_populates="denuncias")
    ofesor = db.relationship("Ofesor", back_populates="denuncias")
    
    data_public = db.Column(db.Date, nullable=True, index=True)
    # data_inicio = db.Column(db.Date, nullable=True)
    # data_fim = db.Column(db.Date, nullable=True)
    
    status = db.Column(
        db.String(25),
        default=StatusEnum.PENDENTE.value,
        server_default=StatusEnum.PENDENTE.value,
        nullable=False,
        index=True
    )
    severidade = db.Column(db.String(25), nullable=True)
    evidencias = db.Column(db.String(50), nullable=True)
    responsavel = db.Column(db.String(150), nullable=True)
    
    # Depoimentos
    depoimento_vitima = db.Column(db.Text, nullable=True)
    depoimento_acusado = db.Column(db.Text, nullable=True)
    depoimento_testemunha = db.Column(db.Text, nullable=True)
    depoimento_admin = db.Column(db.Text, nullable=True)
    
    # Fotos e Videos da denuncias:
    anexos = db.relationship(
        "DenunciaAnexos",
        back_populates='denuncia',
        cascade="all, delete-orphan"
    )
    historicos = db.relationship(
        "DenunciaHistorico",
        back_populates="denuncia",
        cascade="all, delete-orphan",
        order_by="DenunciaHistorico.criado_em.desc()"
    )
    
    
    def __init__(self, categoria,
                 frequencia,
                 data,
                 testemunha,
                 nomes_testemunhas,
                 descricao_do_fato,
                 vitima_id,
                 ofesor_id,
                 data_public):
        self.categoria = categoria
        self.frequencia = frequencia
        self.data = data
        self.testemunha = testemunha
        self.nomes_testemunhas = nomes_testemunhas
        self.descricao_do_fato = descricao_do_fato
        self.vitima_id = vitima_id
        self.ofesor_id = ofesor_id
        self.data_public = data_public
        
    def insert_depoimento(self, depoimento_vitima, depoimento_acusado, depoimento_testemunha, depoimento_admin):
        self.depoimento_vitima = depoimento_vitima
        self.depoimento_acusado = depoimento_acusado
        self.depoimento_testemunha = depoimento_testemunha
        self.depoimento_admin = depoimento_admin
        
    def __repr__(self):
        return f"Denuncia: {self.id}"
    
    def to_dict(self):
        dias_pendente = None

        if self.status == StatusEnum.PENDENTE.value and self.data_public:
            dias_pendente = (date.today() - self.data_public).days

        return {
            "id": self.id,
            "categoria": self.categoria,
            "frequencia": self.frequencia,
            "data": self.data.strftime("%d/%m/%Y") if self.data else None,
            "data_public": self.data_public.strftime("%d/%m/%Y") if self.data_public else None,
            "testemunha": self.testemunha,
            "nomes_testemunhas": self.nomes_testemunhas,
            "descricao_do_fato": self.descricao_do_fato,
            "status": self.status,
            "severidade": self.severidade,
            "evidencias": self.evidencias,
            "responsavel": self.responsavel,
            "dias_pendente": dias_pendente,
            "pendente_antiga": dias_pendente is not None and dias_pendente >= 7,
            "depoimento_vit": self.depoimento_vitima,
            "depoimento_acu": self.depoimento_acusado,
            "depoimento_vitima": self.depoimento_vitima,
            "depoimento_acusado": self.depoimento_acusado,
            "depoimento_testemunha": self.depoimento_testemunha,
            "depoimento_admin": self.depoimento_admin,

            # --- Dados da vítima ---
            "vitima": {
                "id": self.vitima.id,
                "nome": self.vitima.nome,
                "idade": self.vitima.idade,
                "telefone": self.vitima.telefone,
                "email": self.vitima.email,
                "setor_cargo": self.vitima.setor_cargo
            } if self.vitima else None,

            # --- Dados do ofensor ---
            "ofensor": {
                "id": self.ofesor.id,
                "nome": self.ofesor.nome,
                "setor_cargo": self.ofesor.setor_cargo,
                "descricao": self.ofesor.descricao
            } if self.ofesor else None,
            
            "anexos": [ 
                {
                    "id": anexo.id,
                    "file_path": anexo.file_path,
                    "file_type": anexo.file_type,
                    "original_name": anexo.original_name
                } for anexo in self.anexos
            ],
            "historico": [
                {
                    "campo": historico.campo,
                    "valor_anterior": historico.valor_anterior,
                    "valor_novo": historico.valor_novo,
                    "usuario": historico.usuario.nome if historico.usuario else "Sistema",
                    "criado_em": historico.criado_em.strftime("%d/%m/%Y %H:%M") if historico.criado_em else None
                } for historico in self.historicos[:8]
            ]
        }
