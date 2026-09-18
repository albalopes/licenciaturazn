# Arquitetura

```text
app/
├── blueprints/
│   ├── public/       # rotas públicas
│   ├── admin/        # CRUD e área restrita
│   ├── auth/         # OAuth2 SUAP + sessão
│   └── api/          # endpoints JSON públicos
├── controllers/      # reservado para controllers de domínio mais complexos
├── models/           # SQLAlchemy ORM
├── services/         # SUAP, autenticação e regras de integração
├── templates/        # Views Jinja2
└── static/
    ├── css/
    ├── js/
    └── img/
```

A aplicação usa Application Factory e Blueprints. A camada de apresentação é Jinja2; a persistência é SQLAlchemy; integrações externas ficam em services.

## Regra essencial das matrizes

Uma disciplina pertence a uma matriz específica. Não reutilize automaticamente uma disciplina de 2018 em 2026. Se a nova matriz alterar carga horária, ementa ou pré-requisitos, crie o registro correspondente à nova matriz.

### Projetos

A entidade `Project` separa projetos de pesquisa, ensino e extensão dos demais conteúdos acadêmicos. O campo `is_pibid` permite uma área específica do PIBID sem criar uma estrutura paralela. Isso facilita futuras ampliações para subprojetos, bolsistas, escolas parceiras e resultados.
