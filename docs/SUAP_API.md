# Integração com a API atual do SUAP

A integração utiliza a documentação oficial disponibilizada pelo SUAP em:

https://suap.ifrn.edu.br/api/docs/

A base da API utilizada pelo projeto é:

```text
https://suap.ifrn.edu.br/api/
```

## OAuth2

O projeto usa o fluxo OAuth2 `Authorization Code` no backend Flask. O cliente oficial do IFRN para Django documenta uma aplicação `Confidential` com `Authorization Code`, enquanto o repositório oficial de clientes do IFRN orienta a obtenção de autorização/token pela documentação do SUAP.

Configuração:

```env
SUAP_BASE_URL=https://suap.ifrn.edu.br
SUAP_AUTH_URL=https://suap.ifrn.edu.br/o/authorize/
SUAP_TOKEN_URL=https://suap.ifrn.edu.br/o/token/
SUAP_API_BASE_URL=https://suap.ifrn.edu.br/api/
SUAP_CLIENT_ID=
SUAP_CLIENT_SECRET=
SUAP_REDIRECT_URI=https://SEU_DOMINIO/auth/suap/callback
SUAP_SCOPE=read
```

## Endpoints atuais usados pelo projeto

Os endpoints abaixo substituem a configuração antiga baseada em `/api/v2/minhas-informacoes/...`:

| Função | Endpoint |
|---|---|
| Identidade do usuário | `/api/rh/eu/` |
| Meus vínculos | `/api/rh/meus-vinculos/` |
| Meus dados de RH | `/api/rh/meus-dados/` |
| Dados do aluno | `/api/ensino/meus-dados-aluno/` |
| Períodos | `/api/ensino/periodos/` |

O endpoint `/api/rh/eu/` é especialmente importante: há registro de 2026 no cliente oficial de JavaScript do IFRN informando que o antigo `/api/eu` passou a retornar 404 e que o equivalente atual é `/api/rh/eu/`.

## Diário acadêmico

Os endpoints de diário (`meu-diario/...`) continuam configuráveis por variável de ambiente. Isso evita acoplar o portal a uma rota que possa mudar na documentação atual do SUAP sem precisar alterar o código.

```env
SUAP_ENDPOINT_VIRTUAL_CLASSES=meu-diario/turmas-virtuais/
SUAP_ENDPOINT_REPORT=meu-diario/boletim/{year}/{period}/
SUAP_ENDPOINT_SCHEDULE=meu-diario/horario/{year}/{period}/
```

Antes de habilitar essas funções em produção, confira as respectivas rotas na documentação atual em `/api/docs/`.

## Rotas internas do portal

Depois do login pelo SUAP:

- `/suap/meus-dados`
- `/suap/api/eu`
- `/suap/api/vinculos`
- `/suap/api/dados-pessoais`
- `/suap/api/dados-aluno`
- `/suap/api/periodos`
- `/suap/api/turmas-virtuais`
- `/suap/api/boletim/<ano>/<periodo>`
- `/suap/api/horario/<ano>/<periodo>`

Todas são protegidas por login e o token OAuth2 permanece no backend/sessão do Flask; ele não é enviado ao JavaScript do navegador.

## Segurança

- `SUAP_CLIENT_SECRET` deve ficar somente nas variáveis de ambiente do Portainer.
- Não coloque `.env` no GitHub.
- O token OAuth2 é armazenado na sessão do Flask.
- O backend tenta renovar o access token usando refresh token quando necessário.
- Respostas 401, 403 e 404 da API são tratadas explicitamente.

## Fontes

- Documentação oficial da API do SUAP: https://suap.ifrn.edu.br/api/docs/
- Clientes oficiais do IFRN para API do SUAP: https://github.com/IFRN/suapi
- Cliente OAuth2 SUAP Django oficial do IFRN: https://github.com/ifrn-oficial/cliente_suap_django
- Cliente OAuth2 SUAP JavaScript oficial do IFRN: https://github.com/ifrn-oficial/cliente_suap_javascript
