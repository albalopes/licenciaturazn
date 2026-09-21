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

## Atualização — Área do aluno, ENADE e Memoria

### Visualização administrativa da Área do Aluno
- `/admin/visao-aluno` abre a Área do Aluno com dados fictícios.
- O modo demonstração pode navegar por visão geral, trajetória, boletim, horário, turmas e ENADE sem gravar respostas do administrador.
- Os dados fictícios não criam usuários ou matrículas no banco.

### Resultados do simulado ENADE
- `/admin/enade/resultados` mostra participantes, questões respondidas, acertos, aproveitamento, pontos e última resposta.
- Há exportação CSV identificada e CSV anônimo para compartilhamento pedagógico.
- Os resultados reais são associados às contas SUAP que responderem ao simulado.

### Memoria
- `/admin/memoria` sincroniza a coleção pública de Licenciatura em Informática: https://memoria.ifrn.edu.br/handle/1044/1045
- A sincronização atualiza os registros locais e pode ser repetida para incorporar novos trabalhos.
- A página pública de TCC apresenta os trabalhos sincronizados e links institucionais de biblioteca, normalização, depósito, termo de autorização, Periódicos CAPES/CAFe e diploma.
