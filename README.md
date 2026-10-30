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
