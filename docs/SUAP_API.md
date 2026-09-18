# Integração com a API atual do SUAP

A integração deste projeto usa a API disponível em `https://suap.ifrn.edu.br/api/docs/` e a base `https://suap.ifrn.edu.br/api/`.

> **Importante:** esta versão do projeto não utiliza mais rotas `/api/v2/`.

## Projetos

A sincronização administrativa consulta as coleções atuais configuradas para:

- Pesquisa: `pesquisa/projetos/`
- Extensão: `pesquisa/extensao/` (com `extensao/projetos/` como fallback configurável)
- Ensino: `ensino/projetos/` (com `ensino/projetos-ensino/` como fallback configurável)

A aplicação pagina as respostas usando `limit` e `offset` até percorrer a coleção disponível. Depois filtra pelo Campus Natal-Zona Norte.

Os campos retornados pelo SUAP são normalizados para o modelo local de projetos. Como os nomes dos campos podem variar entre módulos, a implementação aceita aliases para título, campus, situação, período, coordenador, equipe, URL etc.

A sincronização **não sobrescreve** as marcações editoriais feitas na área restrita, especialmente:

- `is_pibid`;
- `has_licenciatura_students`;
- `licenciatura_notes`;
- `featured`;
- `published`.

Assim, a Coordenação pode sincronizar os dados oficiais do SUAP e manter manualmente a informação de participação de estudantes da Licenciatura em Informática.

## Servidores e fotos

O endpoint configurado para servidores é `rh/servidores/`. A rotina percorre as páginas disponíveis e procura a fotografia pelos campos conhecidos da resposta (`foto`, `foto_url`, `url_foto`, `imagem`, entre outros).

As fotos são atualizadas:

1. quando uma nova portaria do Colegiado/NDE é importada pela área restrita;
2. quando o administrador usa **Sincronizar fotos com SUAP** na área de docentes.

A identificação preferencial é a matrícula/SIAPE extraída da portaria.

## OAuth

O consumo dos endpoints protegidos ocorre com o token OAuth2 do usuário autenticado no SUAP. A aplicação já mantém o fluxo de autorização, renovação do token e os endpoints configuráveis em `app/config.py` e nas variáveis da Stack.

Se a documentação atual do `/api/docs/` alterar o caminho de uma coleção, basta ajustar a respectiva variável `SUAP_ENDPOINT_*` no Portainer; não é necessário alterar a lógica de sincronização.
