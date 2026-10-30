import csv
import importlib
import io
import os
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from werkzeug.security import generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FormFields(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.textarea = None
        self.select = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        name = attrs.get("name")

        if tag == "input" and name:
            self.values[name] = attrs.get("value", "")
        elif tag == "textarea" and name:
            self.textarea = name
            self.values[name] = ""
        elif tag == "select":
            self.select = name
        elif tag == "option" and self.select and "selected" in attrs:
            self.values[self.select] = attrs.get("value", "")

    def handle_data(self, data):
        if self.textarea:
            self.values[self.textarea] += data

    def handle_endtag(self, tag):
        if tag == "textarea":
            self.textarea = None
        elif tag == "select":
            self.select = None


class ApplicationRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.TemporaryDirectory(prefix="denuncias-tests-")
        cls.addClassCleanup(cls.root.cleanup)
        environment = {
            "SECRET_KEY": "isolated-tests-not-a-production-key",
            "DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_FOLDER": str(Path(cls.root.name) / "initial-uploads"),
            "RATELIMIT_STORAGE_URI": "memory://",
            "SESSION_COOKIE_SECURE": "0",
            "TRUSTED_PROXY_HOPS": "0",
            "ADMIN_EMAIL": "",
            "ADMIN_PASSWORD": "",
        }

        # Importa o aplicativo real, mas nunca carrega credenciais ou banco locais.
        with patch.dict(os.environ, environment), patch("dotenv.load_dotenv", return_value=False):
            module = importlib.import_module("app")

        if module.app.config["SQLALCHEMY_DATABASE_URI"] != "sqlite:///:memory:":
            raise RuntimeError("Os testes exigem um banco SQLite isolado na memória.")

        cls.app = module.app
        cls.db = module.db
        module.limiter.enabled = False

        from src.models.Denuncia_model import Denuncia
        from src.models.Denuncia_anexos_model import DenunciaAnexos
        from src.models.Denuncia_historico_model import DenunciaHistorico
        from src.models.Ofensor_model import Ofesor
        from src.models.Usuario_model import Usuario
        from src.models.Vitima_model import Vitima

        cls.Denuncia = Denuncia
        cls.Anexo = DenunciaAnexos
        cls.Historico = DenunciaHistorico
        cls.Ofesor = Ofesor
        cls.Usuario = Usuario
        cls.Vitima = Vitima
        cls.password = "test-password-only"
        cls.password_hash = generate_password_hash(cls.password)
        image = io.BytesIO()
        Image.new("RGB", (2, 2), "blue").save(image, format="PNG")
        cls.png = image.getvalue()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.db.session.remove()
            cls.db.engine.dispose()

    def setUp(self):
        uploads = tempfile.TemporaryDirectory(dir=self.root.name)
        self.addCleanup(uploads.cleanup)
        self.upload_folder = Path(uploads.name)
        self.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            UPLOAD_FOLDER=str(self.upload_folder),
            ALLOWED_EXTENSIONS={"png", "jpg", "jpeg", "webp", "mp4", "mov", "avi", "mkv"},
            MAX_CONTENT_LENGTH=100 * 1024 * 1024,
            MAX_UPLOAD_FILE_SIZE=25 * 1024 * 1024,
            MAX_FILES_PER_DENUNCIA=5,
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            self.db.create_all()
            user = self.Usuario("Administrador fictício", "admin@example.com", self.password_hash)
            self.db.session.add(user)
            self.db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()

    def login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def create_denuncia(self, *, cadastro=date(2026, 10, 30), ocorrencia=date(2025, 1, 15), **changes):
        with self.app.app_context():
            vitima = self.Vitima("Vítima fictícia", 30, "(11) 99999-9999", "", "Teste")
            ofensor = self.Ofesor("Ofensor fictício", "Teste", "Descrição fictícia")
            self.db.session.add_all([vitima, ofensor])
            self.db.session.flush()
            denuncia = self.Denuncia(
                "Outro", "Única", ocorrencia, "Não", "", "Fatos fictícios",
                vitima.id, ofensor.id, cadastro,
            )
            denuncia.severidade = "media"
            denuncia.responsavel = "Equipe atual"
            denuncia.depoimento_vitima = "Relato da vítima"
            denuncia.depoimento_acusado = "Relato do acusado"
            denuncia.depoimento_testemunha = "Relato da testemunha"
            denuncia.depoimento_admin = "Observação interna"

            for key, value in changes.items():
                setattr(denuncia, key, value)

            self.db.session.add(denuncia)
            self.db.session.commit()
            return denuncia.id

    def state(self, denuncia_id):
        with self.app.app_context():
            denuncia = self.db.session.get(self.Denuncia, denuncia_id)
            return {
                key: getattr(denuncia, key)
                for key in (
                    "status", "severidade", "responsavel", "depoimento_vitima",
                    "depoimento_acusado", "depoimento_testemunha", "depoimento_admin",
                )
            }

    def history(self, denuncia_id):
        with self.app.app_context():
            return [
                (item.campo, item.valor_anterior, item.valor_novo, item.usuario_id)
                for item in self.Historico.query.filter_by(denuncia_id=denuncia_id).order_by(self.Historico.id)
            ]

    def payload(self, **changes):
        data = {
            "nome": "Vítima fictícia do formulário", "idade": "30", "telefone": "11999999999",
            "email": "vitima@example.com", "setor": "Setor fictício", "nomeOfensor": "Ofensor fictício",
            "setorOfensor": "Outro setor", "descricaoOfensor": "Descrição fictícia do ofensor",
            "tipo_situacao": "Outro", "frequencia": "Uma vez", "data_ocorrencia": "2025-01-15",
            "descricaoFatos": "Relato fictício para o teste", "testemunhas": "Sim",
            "nome_testemunhas": "Testemunha fictícia",
        }
        return {**data, **changes}

    def assert_no_store(self, response):
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        self.assertIn("private", response.headers.get("Cache-Control", ""))

    def assert_no_submissions(self):
        with self.app.app_context():
            for model in (self.Denuncia, self.Vitima, self.Ofesor, self.Anexo):
                self.assertEqual(model.query.count(), 0)
        self.assertEqual(list(self.upload_folder.iterdir()), [])

    def test_admin_routes_require_login(self):
        for route in (
            "/admin/", "/admin/painel", "/admin/dashboard", "/admin/anexos/1",
            "/admin/exportar/csv", "/admin/exportar/excel", "/admin/exportar/pdf",
            "/admin/denuncia/1/exportar/csv", "/export/exportar/csv",
        ):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/login", response.headers["Location"])
        response = self.client.post("/admin/denuncia/1/atualizar", json={"status": "em_analise"})
        self.assertEqual(response.status_code, 302)

    def test_login_accepts_normalized_email_and_valid_password(self):
        response = self.client.post("/admin/login", data={"email": " ADMIN@example.com ", "password": self.password})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_login_rejects_invalid_password(self):
        response = self.client.post("/admin/login", data={"email": "admin@example.com", "password": "incorrect"})
        self.assertIn("Usuário ou senha inválidos", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_logout_requires_post_and_revokes_access(self):
        self.login()
        self.assertEqual(self.client.get("/admin/logout").status_code, 405)
        self.assertEqual(self.client.post("/admin/logout").status_code, 302)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_partial_update_preserves_omitted_fields(self):
        denuncia_id = self.create_denuncia()
        before = self.state(denuncia_id)
        self.login()
        response = self.client.post(f"/admin/denuncia/{denuncia_id}/atualizar", json={"status": "em_analise"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.state(denuncia_id), {**before, "status": "em_analise"})
        self.assertEqual(self.history(denuncia_id), [("Status", "pendente", "em_analise", self.user_id)])

    def test_explicit_empty_values_clear_only_requested_fields(self):
        denuncia_id = self.create_denuncia()
        before = self.state(denuncia_id)
        self.login()
        response = self.client.post(
            f"/admin/denuncia/{denuncia_id}/atualizar",
            json={"responsavel": "", "depoimento_admin": None, "severidade": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.state(denuncia_id), {**before, "responsavel": None, "depoimento_admin": None, "severidade": None})

    def test_invalid_json_is_rejected_without_changes(self):
        denuncia_id = self.create_denuncia()
        before = self.state(denuncia_id)
        self.login()
        for payload in ([], [{"status": "em_analise"}], None, "texto", 1, True, {}, {"desconhecido": "valor"}):
            with self.subTest(payload=payload):
                response = self.client.post(f"/admin/denuncia/{denuncia_id}/atualizar", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.get_json()["sucesso"])
                self.assertEqual(self.state(denuncia_id), before)
        response = self.client.post(f"/admin/denuncia/{denuncia_id}/atualizar", data="{broken", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.history(denuncia_id), [])

    def test_invalid_fields_are_rejected_atomically(self):
        denuncia_id = self.create_denuncia()
        before = self.state(denuncia_id)
        self.login()
        for invalid in (
            {"status": None}, {"status": ""}, {"status": "invalido"}, {"status": []},
            {"severidade": "urgente"}, {"severidade": {}}, {"responsavel": []},
            {"responsavel": "x" * 151}, {"depoimento_vitima": "x" * 10001},
        ):
            with self.subTest(field=next(iter(invalid))):
                response = self.client.post(
                    f"/admin/denuncia/{denuncia_id}/atualizar", json={"status": "em_analise", **invalid},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.state(denuncia_id), before)
                self.assertEqual(self.history(denuncia_id), [])

    def test_severity_is_saved_and_audited(self):
        denuncia_id = self.create_denuncia()
        before = self.state(denuncia_id)
        self.login()
        response = self.client.post(f"/admin/denuncia/{denuncia_id}/atualizar", json={"severidade": "critica"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.state(denuncia_id), {**before, "severidade": "critica"})
        self.assertEqual(self.history(denuncia_id), [("Severidade", "media", "critica", self.user_id)])
        graph = self.client.get("/admin/filter/severidade").get_json()
        self.assertEqual(graph["values"][graph["labels"].index("Crítica")], 1)
        html = self.client.get("/admin/painel").get_data(as_text=True)
        self.assertEqual(FormFields(html).values["severidade"], "critica")

    def test_unchanged_update_does_not_create_audit_entries(self):
        denuncia_id = self.create_denuncia()
        self.login()
        response = self.client.post(f"/admin/denuncia/{denuncia_id}/atualizar", json={"severidade": "media"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.history(denuncia_id), [])

    def test_all_severity_levels_and_explicit_clear_are_supported(self):
        denuncia_id = self.create_denuncia()
        self.login()
        for severity in ("baixa", "media", "alta", "critica", None):
            with self.subTest(severity=severity):
                response = self.client.post(f"/admin/denuncia/{denuncia_id}/atualizar", json={"severidade": severity})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.state(denuncia_id)["severidade"], severity)
                self.assertEqual(self.state(denuncia_id)["responsavel"], "Equipe atual")

    def test_update_rolls_back_data_and_audit_on_failure(self):
        denuncia_id = self.create_denuncia()
        before = self.state(denuncia_id)
        self.login()
        with self.assertLogs(self.app.logger, level="ERROR"), patch.object(self.db.session, "commit", side_effect=RuntimeError("simulated failure")):
            response = self.client.post(f"/admin/denuncia/{denuncia_id}/atualizar", json={"status": "em_analise"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.state(denuncia_id), before)
        self.assertEqual(self.history(denuncia_id), [])

    def test_csrf_is_required_for_form_and_admin_update(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        response = self.client.post("/denuncias/formulario", data=self.payload())
        self.assertEqual(response.status_code, 400)
        denuncia_id = self.create_denuncia()
        self.login()
        response = self.client.post(f"/admin/denuncia/{denuncia_id}/atualizar", json={"status": "em_analise"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.state(denuncia_id)["status"], "pendente")

    def test_form_accepts_valid_csrf_token(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        fields = FormFields(self.client.get("/denuncias/formulario").get_data(as_text=True)).values
        response = self.client.post("/denuncias/formulario", data=self.payload(csrf_token=fields["csrf_token"]))
        self.assertEqual(response.status_code, 303)

    def test_admin_update_accepts_valid_csrf_header(self):
        denuncia_id = self.create_denuncia()
        self.login()
        self.app.config["WTF_CSRF_ENABLED"] = True
        fields = FormFields(self.client.get("/denuncias/formulario").get_data(as_text=True)).values
        response = self.client.post(
            f"/admin/denuncia/{denuncia_id}/atualizar", json={"status": "em_analise"},
            headers={"X-CSRFToken": fields["csrf_token"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.state(denuncia_id)["status"], "em_analise")

    def test_success_redirect_prevents_resubmission_on_refresh(self):
        response = self.client.post("/denuncias/formulario", data=self.payload())
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], "/denuncias/success")
        self.assert_no_store(response)
        for _ in range(2):
            confirmation = self.client.get(response.headers["Location"])
            self.assertEqual(confirmation.status_code, 200)
        with self.app.app_context():
            self.assertEqual(self.Denuncia.query.count(), 1)

    def test_validation_errors_preserve_form_fields(self):
        payload = self.payload(idade="999")
        response = self.client.post("/denuncias/formulario", data=payload)
        self.assertEqual(response.status_code, 400)
        values = FormFields(response.get_data(as_text=True)).values
        for name, value in payload.items():
            with self.subTest(field=name):
                self.assertEqual(values[name], value)
        self.assert_no_store(response)
        self.assert_no_submissions()

    def test_preserved_fields_are_html_escaped(self):
        payload = self.payload(idade="999", nome='" autofocus onfocus="alert(1)', descricaoFatos='</textarea><script>alert("test")</script>')
        response = self.client.post("/denuncias/formulario", data=payload)
        html = response.get_data(as_text=True)
        values = FormFields(html).values
        self.assertEqual(values["nome"], payload["nome"])
        self.assertEqual(values["descricaoFatos"], payload["descricaoFatos"])
        self.assertNotIn('<script>alert("test")</script>', html)
        self.assertIn("&lt;/textarea&gt;", html)

    def test_invalid_uploads_are_rejected_before_saving(self):
        for filename, content in (("arquivo.exe", self.png), ("arquivo.png", b"not an image"), ("vazio.png", b"")):
            with self.subTest(filename=filename):
                response = self.client.post("/denuncias/formulario", data={**self.payload(), "arquivos": (io.BytesIO(content), filename)})
                self.assertEqual(response.status_code, 400)
                self.assert_no_submissions()

    def test_upload_count_and_size_limits(self):
        self.app.config["MAX_FILES_PER_DENUNCIA"] = 1
        response = self.client.post("/denuncias/formulario", data={
            **self.payload(), "arquivos": [(io.BytesIO(self.png), "um.png"), (io.BytesIO(self.png), "dois.png")],
        })
        self.assertEqual(response.status_code, 400)
        self.app.config["MAX_UPLOAD_FILE_SIZE"] = len(self.png) - 1
        response = self.client.post("/denuncias/formulario", data={**self.payload(), "arquivos": (io.BytesIO(self.png), "grande.png")})
        self.assertEqual(response.status_code, 400)
        self.assert_no_submissions()

    def test_uploaded_evidence_requires_login_and_is_not_cached(self):
        response = self.client.post("/denuncias/formulario", data={**self.payload(), "arquivos": (io.BytesIO(self.png), "evidencia.png")})
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            attachment = self.Anexo.query.one()
            attachment_id, filename = attachment.id, attachment.file_path
        self.assertEqual((self.upload_folder / filename).read_bytes(), self.png)
        route = f"/admin/anexos/{attachment_id}"
        self.assertEqual(self.client.get(route).status_code, 302)
        self.login()
        with self.client.get(route) as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_data(), self.png)
            self.assert_no_store(response)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            etag = response.headers["ETag"]
        with self.client.get(route, headers={"If-None-Match": etag}) as response:
            self.assert_no_store(response)
        self.client.post("/admin/logout")
        self.assertEqual(self.client.get(route).status_code, 302)

    def test_failed_submission_preserves_text_and_cleans_files(self):
        payload = self.payload()
        with self.assertLogs(self.app.logger, level="ERROR"), patch.object(self.db.session, "commit", side_effect=RuntimeError("simulated failure")):
            response = self.client.post("/denuncias/formulario", data={**payload, "arquivos": (io.BytesIO(self.png), "evidencia.png")})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(FormFields(response.get_data(as_text=True)).values["descricaoFatos"], payload["descricaoFatos"])
        self.assert_no_submissions()

    def test_partial_file_is_removed_when_save_fails(self):
        def fail_save(upload, destination):
            Path(destination).write_bytes(b"partial file")
            raise OSError("simulated disk error")

        with self.assertLogs(self.app.logger, level="ERROR"), patch("werkzeug.datastructures.FileStorage.save", new=fail_save):
            response = self.client.post("/denuncias/formulario", data={**self.payload(), "arquivos": (io.BytesIO(self.png), "evidencia.png")})
        self.assertEqual(response.status_code, 500)
        self.assert_no_submissions()

    def test_panel_dashboard_and_exports_filter_by_registration_date(self):
        self.create_denuncia(descricao_do_fato="Cadastro dentro do período")
        self.create_denuncia(cadastro=date(2026, 9, 1), ocorrencia=date(2026, 10, 30), descricao_do_fato="Cadastro fora do período")
        self.login()
        query = "?data_inicio=2026-10-30&data_fim=2026-10-30"
        panel = self.client.get(f"/admin/painel{query}").get_data(as_text=True)
        self.assertIn("Cadastro dentro do período", panel)
        self.assertNotIn("Cadastro fora do período", panel)
        self.assertIn("Data de cadastro:", panel)
        self.assertIn("15/01/2025", panel)
        dashboard = self.client.get(f"/admin/dashboard{query}").get_data(as_text=True)
        self.assertIn('<p id="totalDenuncias">1</p>', dashboard)
        self.assertEqual(self.client.get(f"/admin/meses-denuncias{query}").get_json()["Out"], 1)
        response = self.client.get(f"/admin/exportar/csv{query}")
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Descrição"], "Cadastro dentro do período")
        self.assert_no_store(response)
        response.close()

    def test_exports_return_complete_csv_excel_and_pdf(self):
        from openpyxl import load_workbook

        self.create_denuncia(descricao_do_fato="=SUM(A1:A2)")
        self.login()
        response = self.client.get("/admin/exportar/csv")
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(rows[0]["Descrição"], "'=SUM(A1:A2)")
        response.close()
        response = self.client.get("/admin/exportar/excel")
        workbook = load_workbook(io.BytesIO(response.get_data()))
        self.assertEqual(list(workbook.active.values)[1][-1], "'=SUM(A1:A2)")
        workbook.close()
        self.assert_no_store(response)
        response = self.client.get("/admin/exportar/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_data().startswith(b"%PDF-"))
        self.assert_no_store(response)

    def test_csv_export_includes_more_than_two_batches(self):
        first_id = self.create_denuncia()
        with self.app.app_context():
            first = self.db.session.get(self.Denuncia, first_id)
            self.db.session.add_all([
                self.Denuncia("Outro", "Única", first.data, "Não", "", f"Relato fictício {index}", first.vitima_id, first.ofesor_id, first.data_public)
                for index in range(204)
            ])
            self.db.session.commit()
        self.login()
        response = self.client.get("/admin/exportar/csv")
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        response.close()
        self.assertEqual(len(rows), 205)
        self.assertEqual(len({row["ID"] for row in rows}), 205)


class BuildConfigurationTests(unittest.TestCase):
    def test_token_file_is_excluded_from_docker_build(self):
        rules = {
            line.strip()
            for line in (PROJECT_ROOT / ".dockerignore").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertIn("token.txt", rules)
        self.assertNotIn("!token.txt", rules)


if __name__ == "__main__":
    unittest.main()
