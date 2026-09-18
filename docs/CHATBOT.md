# Assistente documental do curso

## Componentes

- `app/blueprints/chatbot/`: página e endpoint JSON.
- `app/services/document_processor.py`: extração e fragmentação de PDFs.
- `app/services/knowledge.py`: armazenamento e indexação da base documental.
- `app/services/chatbot.py`: recuperação lexical/semântica e geração da resposta.
- `app/models/knowledge.py`: `KnowledgeSource` e `KnowledgeChunk`.
- `app/templates/chatbot/index.html`: interface pública.

## Modelo de dados

`KnowledgeSource` representa um documento oficial. `KnowledgeChunk` representa um trecho do documento, com página e embedding opcional.

## Segurança

A chave de IA fica no servidor. O endpoint do chatbot recebe apenas a pergunta e o filtro de matriz. O portal utiliza CSRF no formulário web.

Para produção, recomenda-se acrescentar rate limiting, limites de tamanho de arquivo, antivírus/varredura de uploads, auditoria e autenticação para consultas sensíveis.

## Fontes e respostas

O sistema recupera primeiro os trechos da base documental. O modelo recebe apenas os trechos recuperados e é instruído a não completar lacunas com conhecimento externo. A resposta retorna também os documentos/páginas recuperados para transparência.
