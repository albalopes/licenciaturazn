# Integração com a API atual do SUAP

A integração deste projeto utiliza exclusivamente a API atual em `/api/` documentada em `https://suap.ifrn.edu.br/api/docs/` e no `/api/openapi.json`.

## Endpoints confirmados na documentação fornecida em 18/09/2026

### Gestão de Pessoas

- `GET /api/rh/servidores/?campus=ZN&page=1` — coleção de servidores do Campus Natal-Zona Norte.
  - Parâmetros disponíveis confirmados na documentação: `nome`, `campus`, `matricula`, `setor`, `cargo_emprego` e `page`.
  - O retorno inclui, entre outros, `matricula`, `nome`, `campus`, `cargo`, `funcao`, `curriculo_lattes` e `url_foto_75x100`.
- `GET /api/rh/servidores_funcao_ativa/` — servidores com função ativa.
- `GET /api/rh/servidores/detalhado/` — dados detalhados de servidores.
- `GET /api/rh/servidores/integra/` — dados de servidores com escopo do Integra.
- `GET /api/rh/servidor-resumido/?matricula={matricula}` — dados resumidos de um servidor.

O schema documentado para `servidor-resumido` contém `matricula`, `nome`, `campus`, `email` e `foto`. O documento de referência também registra que esse endpoint pode responder `403 Permission denied`, portanto a disponibilidade da foto depende das permissões do usuário/token.

### Pesquisa

- `GET /api/pesquisa/projetos/` — projetos de pesquisa.

### Extensão

- `GET /api/extensao/projetos/` — projetos de extensão.

### Ensino

A documentação fornecida não apresenta um endpoint de projetos de ensino. Ela apresenta os recursos de ensino acadêmico, como diários, disciplinas, materiais, trabalhos, alunos e portal de professores, mas não um recurso `projetos`.

Por isso o sistema **não inventa** um endpoint de projetos de ensino. Projetos de ensino continuam podendo ser cadastrados/gerenciados manualmente no portal até que o SUAP disponibilize esse recurso na API documentada.

## Sincronização de projetos

A rotina:

1. consulta os endpoints atuais de Pesquisa e Extensão;
2. percorre a paginação retornada pela API (`results`, `count` e `next`);
3. mantém somente projetos do Campus Natal-Zona Norte;
4. mantém somente projetos ativos/em andamento;
5. atualiza os dados do SUAP sem sobrescrever `has_licenciatura_students` e `licenciatura_notes`, que são informações mantidas pela Coordenação.

Nenhuma rota `/api/v2/` é utilizada.

## Fotos dos docentes

Ao importar uma portaria, o sistema usa a matrícula/SIAPE extraída do PDF e consulta:

`GET /api/rh/servidores/?campus=ZN&matricula={matricula}&page=1`

Quando o SUAP devolver `url_foto_75x100`, ele é associado ao cadastro do docente. O botão **Sincronizar dados e fotos com SUAP** faz uma consulta paginada de `/rh/servidores/?campus=ZN` e cruza os servidores com os docentes do curso pela matrícula/SIAPE. O endpoint `servidor-resumido` permanece apenas como fallback.

Se o token não tiver permissão para `/rh/servidores/`, a sincronização informa o erro na área restrita em vez de preencher dados fictícios.
