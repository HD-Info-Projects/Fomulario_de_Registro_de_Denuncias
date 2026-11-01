# Sistema de Registro de Denúncias

Aplicação Flask para registro, análise e exportação de denúncias.

## Aparência

O frontend usa o tema claro no primeiro acesso. O botão no cabeçalho alterna entre os temas claro e escuro, incluindo o login e a área administrativa. A escolha é salva no navegador e mantida ao navegar ou recarregar a página.

O botão de tema exibe apenas o ícone de sol/lua e mantém um nome acessível e uma dica de ação.

## Testes

- Frontend (Node.js, sem dependências adicionais): `node --test tests/*.test.cjs`.
- Backend (com as dependências do projeto instaladas): `python -m unittest discover -s tests -p 'test_*.py'`.

Os testes do backend usam SQLite na memória e arquivos temporários, sem carregar o `.env` nem acessar o banco real.

## Análise das denúncias

- Alterações parciais preservam os campos não enviados. Um texto vazio ou `null` limpa explicitamente um campo opcional.
- A severidade pode ser definida como baixa, média, alta, crítica ou não definida, com registro no histórico.
- Os filtros de datas do painel, dashboard e exportações usam a **data de cadastro**. A data da ocorrência continua visível nos detalhes da denúncia.
- Depois do cadastro, o navegador é redirecionado à confirmação. Erros preservam os textos preenchidos; os anexos precisam ser selecionados novamente.

## Administradores e tipos de situação

As seções **Administradores** (`/admin/administradores`) e **Tipos de situação** (`/admin/tipos-situacao`) ficam disponíveis somente para administradores principais. Os demais administradores continuam acessando as denúncias, o dashboard e as exportações.

- Administradores principais podem cadastrar contas, editar nome/e-mail/perfil, redefinir senhas e desativar/reativar o acesso.
- A própria conta não pode ser desativada nem perder o próprio perfil principal. É possível criar outros principais para compartilhar a gestão com responsabilidade.
- Contas não são apagadas: a desativação preserva a autoria dos históricos. Desativação, troca de senha e mudança de perfil revogam sessões anteriores; reativar a conta não restaura essas sessões.
- Tipos de situação têm nome, descrição opcional e situação ativo/inativo. Apenas os ativos aparecem no formulário público.
- Cada denúncia mantém o nome da classificação no momento do registro. Renomear ou desativar um tipo não reescreve as denúncias antigas.
- Se todos os tipos forem desativados, o formulário informa a indisponibilidade e impede o envio até que um tipo seja reativado.

### Usar o CRUD pela interface

1. Entre como administrador principal e abra **Administradores** pelo cartão da página inicial ou pela navbar.
2. Use **Novo administrador** para cadastrar e **Editar** para alterar os dados. Na edição, deixe as senhas vazias para manter a senha atual.
3. Para desativar/reativar, use a ação na tabela e confira o nome na janela de confirmação antes de prosseguir. Cancelar ou pressionar Escape não envia a alteração.
4. A seção **Tipos de situação** funciona da mesma forma e pode ser acessada pelas abas internas. Novos tipos ativos aparecem no formulário público.

As telas conferem a confirmação de senha, mostram o limite da descrição e bloqueiam cliques repetidos durante o envio. As mensagens de sucesso/erro vêm do backend: não há cadastro fictício ou armazenamento de contas no navegador. A configuração inicial do banco e do primeiro principal continua sendo necessária; os cadastros do dia a dia são feitos pelas telas.

### Atualizar uma instalação existente

Faça backup do banco e aplique a migração antes de reiniciar a aplicação com o código novo:

```bash
alembic upgrade head
python -m flask --app app set-principal --email "seu-email-cadastrado@exemplo.com"
```

A migração preserva usuários e denúncias, importa os cinco tipos originais e as classificações legadas. **Nenhuma conta é promovida automaticamente.** O comando `set-principal` exige uma conta ativa já cadastrada. Se ainda não houver conta, configure `ADMIN_EMAIL`/`ADMIN_PASSWORD` e execute `python -m flask --app app create-admin` antes de promovê-la.

Entre novamente no sistema após a atualização/promoção. Sessões de versões anteriores são encerradas por segurança. Os links das novas seções aparecerão para a conta principal; o botão de tema permanece à direita da navbar.

No Docker, depois de atualizar os arquivos:

```bash
docker compose build
docker compose run --rm migrate
docker compose up -d
docker compose exec web python -m flask --app app set-principal --email "seu-email-cadastrado@exemplo.com"
```

## Execução local

1. Crie um `.env` a partir de `.env.example`.
2. Ajuste `SECRET_KEY` e `DATABASE_URI`.
3. Instale dependências com `pip install -r requirements.txt`.
4. Rode migrations com `alembic upgrade head`.
5. Inicie com `python app.py`.

## Docker

1. Crie um `.env` a partir de `.env.example`.
2. Defina senhas fortes para `SECRET_KEY`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` e `ADMIN_PASSWORD`.
3. Suba os serviços com `docker compose up --build -d`.
4. O serviço `migrate` executa `alembic upgrade head` antes do `web` iniciar.
5. A aplicação ficará em `http://127.0.0.1:5000` por padrão.

Os uploads são persistidos no volume `uploads`. O banco MySQL é persistido no volume `mysql_data`.

Para produção, coloque um proxy reverso com HTTPS na frente do serviço `web`. Se usar Nginx/Traefik no mesmo host, mantenha `APP_BIND=127.0.0.1`, use `SESSION_COOKIE_SECURE=1` e ajuste `TRUSTED_PROXY_HOPS=1` apenas quando o proxy for confiável.

O usuário admin inicial é criado de forma idempotente quando `ADMIN_EMAIL` e `ADMIN_PASSWORD` estiverem definidos. Se o e-mail já existir, o usuário não é recriado nem tem a senha alterada automaticamente.

## Observações

- Não coloque `.env` dentro da imagem Docker.
- O arquivo local `token.txt` também é excluído do build. Se uma imagem antiga já tiver incluído uma credencial real, reconstrua a imagem e revogue/substitua a credencial exposta.
- Em produção, use `SESSION_COOKIE_SECURE=1` atrás de HTTPS.
- No Docker Compose, o rate limit usa Redis. Em execução local, `RATELIMIT_STORAGE_URI=memory://` é suficiente para desenvolvimento.
- Se a aplicação ficar atrás de proxy reverso confiável, ajuste `TRUSTED_PROXY_HOPS` para preservar IP/protocolo corretos.
