# Deploy no Portainer — licenciaturazn

## Estrutura obrigatória do repositório

O repositório usado pela Stack deve ter o `Dockerfile` na raiz. A estrutura mínima é:

```text
Dockerfile
docker-compose.portainer.yml
docker-entrypoint.sh
requirements.txt
run.py
seed.py
app/
  __init__.py
  models/
    __init__.py
    project.py
    knowledge.py
```

Não coloque todo o projeto dentro de uma subpasta, a menos que o `build.context` do Compose seja alterado para essa subpasta.

## Portainer

Use a Stack `licenciaturazn` e faça o build a partir do repositório/branch que contém o `Dockerfile` na raiz.

O build agora executa uma validação explícita. Se o contexto estiver errado, o log do build mostrará o conteúdo recebido em `/app` e indicará qual arquivo não foi encontrado.

O container usa o nome `licenciaturazn_web` e a porta interna `5003`.
