# Docentes e horários — Licenciatura em Informática

## Dados do docente

A sincronização com o SUAP usa a coleção `/api/rh/servidores/` filtrada pelo campus `ZN`. O portal aproveita, quando presentes e autorizados pelo token:

- nome;
- matrícula/SIAPE;
- e-mail;
- foto (`url_foto_75x100`, `url_foto`, `foto`, entre campos equivalentes);
- cargo/função para apoio à descrição;
- currículo Lattes, quando o campo `curriculo_lattes` ou `lattes_url` vier na resposta.

A **disciplina de ingresso** não é assumida como disponível na API. Por isso, existe o campo `ingresso_disciplina` na área restrita, permitindo o preenchimento manual. O mesmo vale para Lattes quando a API não retornar o link.

## Horários

O semestre 2026.2 da Licenciatura foi cadastrado a partir do arquivo `horário 2026.2 ZN - turmas v4.pdf`, versão 4 a partir de 17/08/2026. Foram consideradas as turmas `2.4411.1V`, `4.4411.1N`, `6.4411.1V` e `8.4411.1N`.

Os registros ficam em `teaching_assignments` e permitem:

- visualizar o horário atual por turma;
- abrir o perfil do docente a partir da tabela;
- mostrar, no perfil do docente, as disciplinas do semestre atual;
- manter histórico por semestre;
- cadastrar manualmente registros de semestres anteriores;
- reimportar explicitamente o horário 2026.2 pela área restrita.
