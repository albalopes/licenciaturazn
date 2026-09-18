# Deploy no GitHub e Portainer CE

Este projeto está preparado para ser mantido em um repositório GitHub e implantado no Portainer Community Edition.

## 1. GitHub

Envie o conteúdo desta pasta para a raiz do repositório. Não envie `.env` nem credenciais.

```bash
git init
git add .
git commit -m "Versão inicial do portal"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

O `.gitignore` já impede o versionamento de `.env`, caches Python e outros arquivos locais.

## 2. Portainer CE

Use **Stacks > Add stack > Git repository** e informe a URL do repositório e a branch `main`.

Como o compose da raiz (`docker-compose.yml`) já está preparado para o seu cenário, ele pode ser usado diretamente como arquivo Compose. O arquivo `docker-compose.portainer.yml` é mantido como uma cópia explícita para ambientes em que você prefira selecioná-lo no campo de caminho do Compose.

### Importante: este projeto NÃO cria MySQL

O `docker-compose.yml` contém somente o serviço `web`. O banco deve existir previamente no servidor.

O container Flask precisa estar na mesma rede Docker do MySQL:

- `database_network` — comunicação Flask ↔ MySQL
- `proxy_network` — acesso do Nginx Proxy Manager/reverse proxy ↔ Flask

As duas redes são declaradas como `external: true`, portanto precisam existir antes do deploy.

Confira no servidor:

```bash
docker network ls
```

Se ainda não existirem:

```bash
docker network create proxy_network
docker network create database_network
```

Se o MySQL já estiver em execução, conecte-o à `database_network` caso ainda não esteja:

```bash
docker network connect database_network NOME_DO_CONTAINER_MYSQL
```

## 3. Variáveis da Stack

Não use `env_file: .env` no Portainer. O compose foi configurado para receber as variáveis diretamente da seção **Environment variables** da Stack.

As duas variáveis obrigatórias são:

```text
SECRET_KEY
DATABASE_URL
```

Para o MySQL existente, por exemplo:

```text
DATABASE_URL=mysql+pymysql://usuario:senha@mysql:3306/licenciaturazn
```

Substitua `mysql` pelo nome/hostname real do seu container na `database_network`.

Para o SUAP, configure pelo menos:

```text
SUAP_CLIENT_ID
SUAP_CLIENT_SECRET
SUAP_REDIRECT_URI
```

Para o chatbot com IA:

```text
OPENAI_API_KEY
```

A chave da OpenAI é opcional. Sem ela, o assistente pode trabalhar com a recuperação documental disponível no projeto.

## 4. Nginx Proxy Manager

O Flask escuta internamente na porta `5003` e usa `expose`, não `ports`. O Nginx Proxy Manager deve estar conectado à `proxy_network`.

No Proxy Host, encaminhe para o serviço/container do portal na porta `5003`.

Exemplo conceitual:

```text
https://licenciatura.seu-dominio
        ↓
Nginx Proxy Manager
        ↓ proxy_network
licenciaturazn_web :5003
```

## 5. OAuth do SUAP

O `SUAP_REDIRECT_URI` precisa corresponder exatamente à URL cadastrada na aplicação OAuth do SUAP.

Em produção, não use `http://localhost:5003/...`. Use o domínio público do portal, por exemplo:

```text
https://licenciatura.seu-dominio/auth/suap/callback
```

## 6. Atualizações pelo GitHub

Depois de alterar o código:

```bash
git add .
git commit -m "Atualiza portal"
git push
```

No Portainer, faça o redeploy/pull da Stack para buscar a nova versão.

## 7. Segurança

- Nunca publique `.env` ou tokens no GitHub.
- Use Fine-grained Personal Access Token do GitHub apenas para leitura do repositório.
- Mantenha `Contents: Read-only` para o repositório utilizado pelo Portainer.
- Não coloque `OPENAI_API_KEY`, `SUAP_CLIENT_SECRET` ou senha do MySQL no código.
- Para produção, use HTTPS.

### Inicialização automática do banco

Na inicialização do container, `docker-entrypoint.sh` aguarda o MySQL existente ficar disponível e executa `python seed.py` antes de iniciar o Gunicorn. O seed usa `db.create_all()` para criar as tabelas ausentes e foi escrito para não duplicar os registros demonstrativos já existentes. O MySQL continua sendo um container externo conectado pela `database_network`.

## IMPORTANTE — contexto do build

Esta versão já inclui as matrizes 2012 e 2018 com ementas, objetivos, conteúdos, bibliografias e pré-requisitos extraídos dos PPCs fornecidos, além das páginas de TCC, Estágio Docente, ATPA, Estágio extracurricular, Aproveitamento de Estudos e Certificação de Conhecimentos baseadas na Organização Didática 2025.

O `Dockerfile` desta versão está na raiz do repositório. O Portainer deve construir com `context: .` apontando para essa raiz. Se o código estiver dentro de uma subpasta no GitHub, ajuste o contexto para essa subpasta ou mova os arquivos para a raiz.

Durante o build será exibida uma listagem de `/app` e será validada a existência de `app/models/__init__.py`, `project.py` e `knowledge.py`.


# Administradores do portal: username, matrícula, id ou e-mail do SUAP, separados por vírgulas.
ADMIN_SUAP_USERS=

## Atualização desta versão

O `seed.py` continua sendo executado automaticamente no `docker-entrypoint.sh`. Além de `db.create_all()`, esta versão possui uma etapa idempotente de atualização de esquema para as novas colunas de projetos e governança. Portanto, o banco MySQL existente pode permanecer no mesmo container/stack.

A área restrita agora possui:

- paginação e busca nos cadastros;
- edição e exclusão dos principais recursos;
- sincronização de projetos ativos do SUAP para Pesquisa, Ensino e Extensão, filtrados para Natal-Zona Norte;
- marcação manual de participação de estudantes da Licenciatura em Informática;
- importação de portarias do Colegiado e NDE em PDF;
- extração automática de composição, matrícula, função e suplência;
- histórico de portarias e docentes por semestre;
- sincronização de fotos de docentes com o SUAP quando a API fornecer a foto.

Para a sincronização SUAP, mantenha o escopo OAuth com `read identificacao email` ou outro conjunto de escopos que o cliente cadastrado no SUAP esteja autorizado a solicitar.


### API do SUAP
A integração de projetos e fotos de servidores utiliza a API atual documentada em `https://suap.ifrn.edu.br/api/docs/` e não utiliza mais `/api/v2/`.
