import importlib
from unittest.mock import patch

from test_regressions import ApplicationTestCase, FormFields


class ManagementTests(ApplicationTestCase):
    def principal(self):
        with self.app.app_context():
            usuario = self.db.session.get(self.Usuario, self.user_id)
            usuario.administrador_principal = True
            self.db.session.commit()
        self.login()

    def new_user(self, email="equipe@example.com", principal=False, ativo=True):
        with self.app.app_context():
            usuario = self.Usuario("Outra pessoa", email, self.password_hash, administrador_principal=principal)
            usuario.ativo = ativo
            self.db.session.add(usuario)
            self.db.session.commit()
            return usuario.id

    def new_type(self, nome="Assédio moral", ativo=True):
        with self.app.app_context():
            tipo = self.TipoSituacao(nome, "Descrição para o teste")
            tipo.ativo = ativo
            self.db.session.add(tipo)
            self.db.session.commit()
            return tipo.id

    def user_data(self, **changes):
        return {
            "nome": "Nova pessoa", "email": "nova@example.com", "perfil": "administrador",
            "senha": "password-for-tests", "confirmacao_senha": "password-for-tests", **changes,
        }

    def test_management_requires_principal_on_get_and_post(self):
        for path in ("/admin/administradores", "/admin/administradores/novo", "/admin/tipos-situacao", "/admin/tipos-situacao/novo"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)
        self.login()
        for path in (
            "/admin/administradores", "/admin/administradores/novo",
            f"/admin/administradores/{self.user_id}/editar", "/admin/tipos-situacao",
            "/admin/tipos-situacao/novo", f"/admin/tipos-situacao/{self.tipo_id}/editar",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        for path in (
            "/admin/administradores/novo", f"/admin/administradores/{self.user_id}/editar",
            f"/admin/administradores/{self.user_id}/status", "/admin/tipos-situacao/novo",
            f"/admin/tipos-situacao/{self.tipo_id}/editar", f"/admin/tipos-situacao/{self.tipo_id}/status",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, data={"ativo": "0"}).status_code, 403)

    def test_navigation_only_shows_management_to_principals(self):
        self.login()
        html = self.client.get("/admin/").get_data(as_text=True)
        self.assertNotIn('href="/admin/administradores"', html)
        self.assertNotIn('href="/admin/tipos-situacao"', html)
        self.principal()
        html = self.client.get("/admin/").get_data(as_text=True)
        self.assertIn('href="/admin/administradores"', html)
        self.assertIn('href="/admin/tipos-situacao"', html)

    def test_home_exposes_management_cards_only_to_principals(self):
        self.login()
        html = self.client.get("/admin/").get_data(as_text=True)
        self.assertEqual(html.count('class="admin-access-card"'), 2)
        self.assertIn("A gestão de administradores e tipos de situação é exclusiva", html)
        self.principal()
        html = self.client.get("/admin/").get_data(as_text=True)
        self.assertEqual(html.count('class="admin-access-card"'), 4)
        self.assertIn("Gerenciar administradores", html)
        self.assertIn("Gerenciar tipos", html)

    def test_list_pages_include_accessible_confirmation_and_section_navigation(self):
        self.principal()
        for route in ("/admin/administradores", "/admin/tipos-situacao"):
            with self.subTest(route=route):
                html = self.client.get(route).get_data(as_text=True)
                self.assertIn('aria-label="Seções de administração"', html)
                self.assertEqual(html.count('id="management-confirm"'), 1)
                self.assertIn('aria-labelledby="management-confirm-title"', html)
                self.assertIn('name="csrf_token"', html)
                self.assertIn('data-confirm-target=', html)
                self.assertIn('value="cancel" autofocus', html)

    def test_editor_pages_expose_frontend_validation_and_loading_feedback(self):
        self.principal()
        html = self.client.get("/admin/administradores/novo").get_data(as_text=True)
        self.assertIn("data-management-form", html)
        self.assertIn('aria-describedby="senha-feedback"', html)
        self.assertIn("data-password-feedback", html)
        self.assertIn("data-submit-feedback", html)
        html = self.client.get("/admin/tipos-situacao/novo").get_data(as_text=True)
        self.assertIn('data-counter-for="descricao"', html)
        self.assertIn("0/2000 caracteres", html)
        self.assertIn('js/admin.js', html)

    def test_principal_can_open_all_management_pages(self):
        self.principal()
        for path in (
            "/admin/administradores", "/admin/administradores/novo",
            f"/admin/administradores/{self.user_id}/editar", "/admin/tipos-situacao",
            "/admin/tipos-situacao/novo", f"/admin/tipos-situacao/{self.tipo_id}/editar",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assert_no_store(response)

    def test_create_admin_hashes_password_and_normalizes_email(self):
        self.principal()
        response = self.client.post("/admin/administradores/novo", data=self.user_data(email=" NOVA@example.com "))
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            usuario = self.Usuario.query.filter_by(email="nova@example.com").one()
            self.assertTrue(usuario.ativo)
            self.assertFalse(usuario.administrador_principal)
            self.assertNotEqual(usuario.senha, "password-for-tests")
            self.assertTrue(usuario.check_password("password-for-tests"))

    def test_password_starting_with_hash_prefix_is_still_hashed(self):
        self.principal()
        password = "scrypt:not-an-actual-hash"
        response = self.client.post("/admin/administradores/novo", data=self.user_data(senha=password, confirmacao_senha=password))
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            usuario = self.Usuario.query.filter_by(email="nova@example.com").one()
            self.assertNotEqual(usuario.senha, password)
            self.assertTrue(usuario.check_password(password))

    def test_create_admin_validates_fields_without_echoing_password(self):
        self.principal()
        for changes in (
            {"nome": ""}, {"nome": "x" * 151}, {"email": "invalido"},
            {"email": "ADMIN@example.com"}, {"perfil": "root"}, {"senha": "short"},
            {"confirmacao_senha": "different"}, {"senha": "x" * 129, "confirmacao_senha": "x" * 129},
        ):
            with self.subTest(field=next(iter(changes))):
                response = self.client.post("/admin/administradores/novo", data=self.user_data(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("password-for-tests", response.get_data(as_text=True))
                self.assertEqual(FormFields(response.get_data(as_text=True)).values["senha"], "")
        with self.app.app_context():
            self.assertEqual(self.Usuario.query.count(), 1)

    def test_principal_can_create_another_principal(self):
        self.principal()
        response = self.client.post("/admin/administradores/novo", data=self.user_data(perfil="principal"))
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            self.assertTrue(self.Usuario.query.filter_by(email="nova@example.com").one().administrador_principal)

    def test_edit_admin_without_password_preserves_existing_hash(self):
        target = self.new_user()
        self.principal()
        response = self.client.post(f"/admin/administradores/{target}/editar", data=self.user_data(
            nome="Nome atualizado", email="atualizado@example.com", senha="", confirmacao_senha="",
        ))
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            usuario = self.db.session.get(self.Usuario, target)
            self.assertEqual(usuario.nome, "Nome atualizado")
            self.assertEqual(usuario.email, "atualizado@example.com")
            self.assertEqual(usuario.senha, self.password_hash)

    def test_cannot_demote_or_deactivate_own_principal_account(self):
        self.principal()
        response = self.client.post(f"/admin/administradores/{self.user_id}/editar", data=self.user_data(
            email="admin@example.com", senha="", confirmacao_senha="", perfil="administrador",
        ))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post(f"/admin/administradores/{self.user_id}/status", data={"ativo": "0"}).status_code, 303)
        with self.app.app_context():
            usuario = self.db.session.get(self.Usuario, self.user_id)
            self.assertTrue(usuario.ativo)
            self.assertTrue(usuario.administrador_principal)

    def test_other_principal_can_be_demoted_without_affecting_current_principal(self):
        target = self.new_user(principal=True)
        self.principal()
        response = self.client.post(f"/admin/administradores/{target}/editar", data=self.user_data(
            email="equipe@example.com", senha="", confirmacao_senha="", perfil="administrador",
        ))
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            self.assertFalse(self.db.session.get(self.Usuario, target).administrador_principal)
            self.assertEqual(self.Usuario.query.filter_by(ativo=True, administrador_principal=True).count(), 1)

    def test_deactivation_revokes_sessions_even_after_reactivation(self):
        target = self.new_user()
        other = self.app.test_client()
        other.post("/admin/login", data={"email": "equipe@example.com", "password": self.password})
        self.assertEqual(other.get("/admin/").status_code, 200)
        self.principal()
        route = f"/admin/administradores/{target}/status"
        self.assertEqual(self.client.post(route, data={"ativo": "0"}).status_code, 303)
        self.assertEqual(other.get("/admin/").status_code, 302)
        self.assertEqual(other.post("/admin/login", data={"email": "equipe@example.com", "password": self.password}).status_code, 200)
        self.assertEqual(other.get("/admin/").status_code, 302)
        self.client.post(route, data={"ativo": "1"})
        self.assertEqual(other.get("/admin/").status_code, 302)
        other.post("/admin/login", data={"email": "equipe@example.com", "password": self.password})
        self.assertEqual(other.get("/admin/").status_code, 200)

    def test_status_action_is_idempotent_and_preserves_history(self):
        target = self.new_user()
        denuncia_id = self.create_denuncia()
        with self.app.app_context():
            self.db.session.add(self.Historico(denuncia_id, target, "Status", "pendente", "em_analise"))
            self.db.session.commit()
        self.principal()
        route = f"/admin/administradores/{target}/status"
        for _ in range(2):
            self.assertEqual(self.client.post(route, data={"ativo": "0"}).status_code, 303)
        with self.app.app_context():
            usuario = self.db.session.get(self.Usuario, target)
            self.assertEqual(usuario.versao_sessao, 2)
            self.assertFalse(usuario.ativo)
            historico = self.Historico.query.filter_by(usuario_id=target).one()
            self.assertEqual(historico.usuario.nome, "Outra pessoa")

    def test_password_reset_revokes_old_sessions(self):
        target = self.new_user()
        other = self.app.test_client()
        other.post("/admin/login", data={"email": "equipe@example.com", "password": self.password})
        self.principal()
        response = self.client.post(f"/admin/administradores/{target}/editar", data=self.user_data(email="equipe@example.com"))
        self.assertEqual(response.status_code, 303)
        self.assertEqual(other.get("/admin/").status_code, 302)
        other.post("/admin/login", data={"email": "equipe@example.com", "password": "password-for-tests"})
        self.assertEqual(other.get("/admin/").status_code, 200)

    def test_own_password_change_refreshes_only_current_session(self):
        self.principal()
        old_cookie = self.client.get_cookie(self.app.config["SESSION_COOKIE_NAME"]).value
        response = self.client.post(f"/admin/administradores/{self.user_id}/editar", data=self.user_data(
            email="admin@example.com", perfil="principal",
        ))
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.client.get("/admin/administradores").status_code, 200)
        other = self.app.test_client()
        other.set_cookie(self.app.config["SESSION_COOKIE_NAME"], old_cookie)
        self.assertEqual(other.get("/admin/").status_code, 302)

    def test_existing_and_new_accounts_are_not_automatically_principal(self):
        module = importlib.import_module("app")
        with self.app.app_context(), patch.dict("os.environ", {
            "ADMIN_EMAIL": "bootstrap@example.com", "ADMIN_PASSWORD": "bootstrap-password", "ADMIN_NAME": "Bootstrap",
        }):
            self.assertEqual(module.create_admin_from_env(), "created")
            self.assertFalse(self.Usuario.query.filter_by(email="bootstrap@example.com").one().administrador_principal)
            self.assertFalse(self.db.session.get(self.Usuario, self.user_id).administrador_principal)

    def test_cli_explicitly_sets_principal_and_is_idempotent(self):
        self.login()
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["set-principal", "--email", " ADMIN@example.com "])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        with self.app.app_context():
            usuario = self.db.session.get(self.Usuario, self.user_id)
            self.assertTrue(usuario.administrador_principal)
            version = usuario.versao_sessao
        self.assertEqual(runner.invoke(args=["set-principal", "--email", "admin@example.com"]).exit_code, 0)
        with self.app.app_context():
            self.assertEqual(self.db.session.get(self.Usuario, self.user_id).versao_sessao, version)

    def test_cli_rejects_missing_and_inactive_accounts(self):
        self.new_user(ativo=False)
        runner = self.app.test_cli_runner()
        for email in ("missing@example.com", "equipe@example.com"):
            self.assertNotEqual(runner.invoke(args=["set-principal", "--email", email]).exit_code, 0)

    def test_malformed_and_legacy_session_ids_are_rejected(self):
        for identity in (str(self.user_id), "invalid", "1:invalid", "1:1:1", "999999:1"):
            with self.subTest(identity=identity):
                with self.client.session_transaction() as session:
                    session["_user_id"] = identity
                self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_management_mutations_require_csrf(self):
        self.principal()
        self.app.config["WTF_CSRF_ENABLED"] = True
        for path, data in (
            ("/admin/administradores/novo", self.user_data()),
            (f"/admin/administradores/{self.user_id}/editar", self.user_data()),
            (f"/admin/administradores/{self.user_id}/status", {"ativo": "0"}),
            ("/admin/tipos-situacao/novo", {"nome": "Ameaça"}),
            (f"/admin/tipos-situacao/{self.tipo_id}/editar", {"nome": "Ameaça"}),
            (f"/admin/tipos-situacao/{self.tipo_id}/status", {"ativo": "0"}),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, data=data).status_code, 400)
        fields = FormFields(self.client.get("/admin/administradores/novo").get_data(as_text=True)).values
        response = self.client.post("/admin/administradores/novo", data=self.user_data(csrf_token=fields["csrf_token"]))
        self.assertEqual(response.status_code, 303)

    def test_admin_search_status_and_pagination(self):
        self.new_user(email="desativada@example.com", ativo=False)
        self.principal()
        html = self.client.get("/admin/administradores?status=ativos").get_data(as_text=True)
        self.assertNotIn("desativada@example.com", html)
        self.assertIn("admin@example.com", html)
        html = self.client.get("/admin/administradores?status=inativos&q=desativada").get_data(as_text=True)
        self.assertIn("desativada@example.com", html)
        self.assertNotIn("admin@example.com", html)
        for index in range(10):
            self.new_user(email=f"pessoa{index}@example.com")
        html = self.client.get("/admin/administradores?page=2").get_data(as_text=True)
        self.assertIn("Página 2 de 2", html)

    def test_new_type_is_immediately_available_for_submission(self):
        self.principal()
        response = self.client.post("/admin/tipos-situacao/novo", data={"nome": "  Assédio   moral  ", "descricao": "Humilhações recorrentes"})
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            tipo = self.TipoSituacao.query.filter_by(nome="Assédio moral").one()
            tipo_id = tipo.id
        public = self.app.test_client()
        self.assertIn("Assédio moral", public.get("/denuncias/formulario").get_data(as_text=True))
        response = public.post("/denuncias/formulario", data=self.payload(tipo_situacao=str(tipo_id)))
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            denuncia = self.Denuncia.query.one()
            self.assertEqual(denuncia.tipo_situacao_id, tipo_id)
            self.assertEqual(denuncia.categoria, "Assédio moral")

    def test_type_validation_and_normalized_duplicates(self):
        self.new_type()
        self.principal()
        for data in (
            {"nome": ""}, {"nome": "x" * 256}, {"nome": "Ameaça", "descricao": "x" * 2001},
            {"nome": " ASSÉDIO   MORAL "},
        ):
            with self.subTest(field=data["nome"][:20]):
                self.assertEqual(self.client.post("/admin/tipos-situacao/novo", data=data).status_code, 400)

    def test_inactive_type_cannot_be_submitted_or_recreated(self):
        tipo_id = self.new_type(ativo=False)
        html = self.client.get("/denuncias/formulario").get_data(as_text=True)
        self.assertNotIn("Assédio moral", html)
        for value in (str(tipo_id), "999999", "Outro", "-1", "1.5"):
            with self.subTest(value=value):
                response = self.client.post("/denuncias/formulario", data=self.payload(tipo_situacao=value))
                self.assertEqual(response.status_code, 400)
                self.assert_no_submissions()
        self.principal()
        response = self.client.post("/admin/tipos-situacao/novo", data={"nome": "Assédio moral"})
        self.assertEqual(response.status_code, 400)

    def test_type_rename_and_deactivation_preserve_complaint_snapshot(self):
        self.client.post("/denuncias/formulario", data=self.payload())
        self.principal()
        response = self.client.post(f"/admin/tipos-situacao/{self.tipo_id}/editar", data={"nome": "Situação geral", "descricao": "Texto atualizado"})
        self.assertEqual(response.status_code, 303)
        response = self.client.post(f"/admin/tipos-situacao/{self.tipo_id}/status", data={"ativo": "0"})
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            denuncia = self.Denuncia.query.one()
            self.assertEqual(denuncia.categoria, "Outro")
            self.assertEqual(denuncia.tipo_situacao_id, self.tipo_id)
            self.assertEqual(denuncia.tipo_situacao.nome, "Situação geral")
            self.assertFalse(denuncia.tipo_situacao.ativo)
        html = self.client.get("/admin/painel").get_data(as_text=True)
        self.assertIn("Outro", html)
        html = self.client.get("/denuncias/formulario").get_data(as_text=True)
        self.assertIn("Nenhum tipo de situação está disponível", html)
        self.assertIn('type="submit" disabled', html)
        self.assertNotIn(">Situação geral</option>", html)
        self.client.post(f"/admin/tipos-situacao/{self.tipo_id}/status", data={"ativo": "1"})
        response = self.client.post("/denuncias/formulario", data=self.payload())
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            self.assertEqual([d.categoria for d in self.Denuncia.query.order_by(self.Denuncia.id)], ["Outro", "Situação geral"])

    def test_type_search_and_status_filters(self):
        self.new_type(ativo=False)
        self.principal()
        html = self.client.get("/admin/tipos-situacao?status=ativos").get_data(as_text=True)
        self.assertNotIn("Assédio moral", html)
        html = self.client.get("/admin/tipos-situacao?status=inativos&q=moral").get_data(as_text=True)
        self.assertIn("Assédio moral", html)
        self.assertNotIn("Sem descrição adicional.", html)

    def test_type_form_escapes_user_content(self):
        self.principal()
        response = self.client.post("/admin/tipos-situacao/novo", data={"nome": "", "descricao": "</textarea><script>alert(1)</script>"})
        html = response.get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;/textarea&gt;", html)

    def test_mutation_error_rolls_back_and_never_echoes_password(self):
        from sqlalchemy.exc import IntegrityError

        self.principal()
        with patch.object(self.db.session, "commit", side_effect=IntegrityError("duplicate", {}, Exception("duplicate"))):
            response = self.client.post("/admin/administradores/novo", data=self.user_data())
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("password-for-tests", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(self.Usuario.query.count(), 1)

    def test_status_changes_only_accept_post_and_valid_action(self):
        self.principal()
        for path in (f"/admin/administradores/{self.user_id}/status", f"/admin/tipos-situacao/{self.tipo_id}/status"):
            self.assertEqual(self.client.get(path).status_code, 405)
            self.assertEqual(self.client.post(path, data={"ativo": "anything"}).status_code, 400)
