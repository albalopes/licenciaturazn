# Portal da Licenciatura em Informática — IFRN Natal-Zona Norte

Projeto base em Flask para o portal acadêmico da Licenciatura em Informática do IFRN Campus Natal-Zona Norte.

## Características

- Flask com Application Factory.
- Blueprints separados para público, autenticação, administração e API.
- Organização MVC: controllers/blueprints, models, services e templates.
- MySQL + SQLAlchemy ORM.
- Flask-Migrate para evolução do banco.
- Área administrativa protegida pelo Flask-Login.
- Login preparado para OAuth2 Authorization Code do SUAP.
- Separação de dados por matriz: 2012, 2018 e 2026.
- Matriz com visualização em cards ou quadro/tabela.
- Página individual de disciplina com plano de curso.
- CSS e JavaScript separados em `app/static`.
- Docker Compose para o container Flask conectado a um MySQL existente; o projeto não cria um container de banco.

## Identidade visual

A interface usa uma paleta verde inspirada na identidade do IFRN/SUAP, com navegação institucional, cartões, tabelas, badges e componentes responsivos. O projeto não embute uma cópia proprietária do design system; os estilos em `static/css/ifrn.css` são uma implementação própria inspirada na linguagem visual observada no SUAP.

## SUAP OAuth2

O IFRN mantém clientes oficiais de referência para acesso OAuth2 à API do SUAP. Este projeto utiliza o fluxo de Authorization Code, adequado para uma aplicação Flask com segredo no servidor.

1. Crie uma aplicação OAuth2 no SUAP.
2. Use `Client Type: Confidential`.
3. Use `Authorization Grant Type: Authorization Code`.
4. Cadastre a URI de callback, por exemplo:
   `http://localhost:5003/auth/suap/callback`
5. Copie `.env.example` para `.env`.
6. Preencha `SUAP_CLIENT_ID`, `SUAP_CLIENT_SECRET` e `SUAP_REDIRECT_URI`.
7. Configure `ADMIN_SUAP_USERS` com os usuários autorizados a administrar o portal.

O projeto não guarda a senha do SUAP. O token OAuth fica somente na sessão do usuário e o refresh token é usado para renovar o acesso quando necessário.

### Endpoints usados

- Autorização: `/o/authorize/`
- Token: `/o/token/`
- Dados do usuário: `/api/rh/eu/`
- Meus vínculos: `/api/rh/meus-vinculos/`
- Meus dados de RH: `/api/rh/meus-dados/`
- Dados acadêmicos do aluno: `/api/ensino/meus-dados-aluno/`
- Períodos: `/api/ensino/periodos/`

Confirme os endpoints e escopos disponíveis na documentação atual da API do SUAP antes da publicação em produção.

## Execução local sem Docker

    python -m venv .venv
    # Linux/macOS
    source .venv/bin/activate
    # Windows
    # .venv\\Scripts\\activate
    pip install -r requirements.txt
    cp .env.example .env

Configure `DATABASE_URL` para um MySQL local e execute:

    python seed.py
    flask --app run run --debug

## Execução com Docker

    cp .env.example .env
    docker compose up --build

Em outro terminal, inicialize os dados:

    docker compose exec web python seed.py

Acesse `http://localhost:5003`.

## Administração

Acesse `/auth/login`. O usuário será redirecionado ao SUAP. Depois do callback, o sistema consulta `/api/rh/eu/`, cria/atualiza o usuário local e aplica a lista de administradores configurada em `ADMIN_SUAP_USERS`.

A área `/admin` possui telas iniciais para:

- matrizes;
- disciplinas e planos de curso;
- docentes;
- páginas institucionais;
- documentos;
- eventos/calendário.

## Próximas evoluções recomendadas

1. Importador oficial do PPC 2018 para a matriz e planos de curso.
2. Cadastro completo da matriz 2012.
3. Importador do novo PPC 2026 assim que publicado.
4. CRUD completo para pré-requisitos e correquisitos.
5. CRUD para Colegiado e NDE com portarias e atas.
6. CRUD para cronograma de entradas.
7. Biblioteca de documentos com upload seguro.
8. Controle de permissões por função, além de `is_admin`.
9. Auditoria das alterações administrativas.
10. Testes automatizados e pipeline de CI.
11. Cache de consultas públicas e proteção de rate limiting.
12. Integração opcional com dados acadêmicos do SUAP sem armazenar informações acadêmicas desnecessárias.

## Observação sobre conteúdo

O `seed.py` cria somente estrutura e textos demonstrativos. Não use os dados de exemplo como dados acadêmicos oficiais. Os dados das matrizes devem ser importados a partir dos PPCs e normas oficiais correspondentes a cada vínculo.

## Assistente documental (RAG)

O portal agora inclui `/assistente`, um chatbot preparado para responder perguntas a partir dos documentos oficiais cadastrados na base de conhecimento.

### Fluxo

1. O administrador entra em `/admin/conhecimento`.
2. Envia um PDF oficial (PPC, Organização Didática ou regulamento) e informa, quando aplicável, a matriz relacionada.
3. O sistema extrai o texto, divide o PDF em trechos e registra a página de origem.
4. Com `OPENAI_API_KEY`, cada trecho recebe embedding e a pergunta também é vetorizada para recuperação semântica.
5. Os trechos recuperados são enviados ao modelo configurado em `OPENAI_MODEL` pela Responses API.
6. A resposta apresenta as fontes consultadas.

Sem `OPENAI_API_KEY`, o sistema continua funcional em modo de recuperação textual: ele localiza e apresenta os trechos relevantes, mas não gera uma resposta conversacional por IA.

### Configuração da IA

No `.env`:

    OPENAI_API_KEY=
    OPENAI_BASE_URL=https://api.openai.com/v1
    OPENAI_MODEL=gpt-5.6-luna
    OPENAI_EMBEDDING_MODEL=text-embedding-3-small

A chave da API deve ficar somente no servidor. Nunca coloque a chave no JavaScript do navegador ou no repositório Git.

### Documentos iniciais

O projeto acompanha uma cópia do PPC 2012 utilizado no desenvolvimento anterior, em `data/knowledge/`. O `seed.py` tenta indexá-lo automaticamente. A Organização Didática e o PPC 2018 devem ser cadastrados pelo painel administrativo a partir das versões oficiais correspondentes.

### Observação institucional

O assistente é uma ferramenta de consulta e não substitui a Coordenação de Curso ou os setores responsáveis por decisões acadêmicas. O prompt do sistema orienta o modelo a não inventar regras e a indicar quando as fontes não são suficientes.

## Projetos e PIBID

O portal também possui uma área para divulgação de projetos de **pesquisa, ensino e extensão**, com filtros por categoria e página individual para cada projeto. Há ainda uma entrada específica para **PIBID** (`/pibid`), permitindo destacar projetos vinculados ao programa sem misturá-los à navegação geral.

Na administração, o menu **Projetos** permite cadastrar título, sigla, categoria, descrição, objetivos, coordenação, equipe, período, situação, apoio/financiamento, parceiros e links. Um projeto pode ser marcado como **PIBID**, **destaque** e/ou **publicado**.


### API do SUAP
A integração de projetos e fotos de servidores utiliza a API atual documentada em `https://suap.ifrn.edu.br/api/docs/` e não utiliza mais `/api/v2/`.
