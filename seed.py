"""Initializes the portal database and loads authoritative course data from the PPCs.

The 2012 and 2018 matrices and their course-plan information are generated from the
PPC PDFs supplied with this release. The seed is idempotent for normal redeploys and
refreshes the discipline catalog for those two matrices so that an older demonstrative
record cannot remain in production.
"""
from pathlib import Path
import json
from datetime import datetime

from app import create_app
from app.extensions import db
from sqlalchemy import inspect, text
from app.models import (
    Discipline,
    DisciplinePrerequisite,
    Matrix,
    Project,
    SitePage,
    KnowledgeSource,
    Document,
)


def ensure_schema():
    """Apply small additive schema changes to an existing production DB.
    db.create_all() creates new tables but does not add columns to existing tables.
    This idempotent step keeps redeploys safe for the current MySQL database.
    """
    inspector = inspect(db.engine)
    additions = {
        "governance_members": {
            "siape": "VARCHAR(50) NULL", "substitute": "BOOLEAN NOT NULL DEFAULT 0",
            "semester": "VARCHAR(20) NULL", "governance_document_id": "INTEGER NULL",
        },
        "teachers": {"suap_id": "VARCHAR(80) NULL", "siape": "VARCHAR(50) NULL"},
        "projects": {
            "suap_id": "VARCHAR(80) NULL", "source_system": "VARCHAR(40) NOT NULL DEFAULT 'manual'",
            "campus": "VARCHAR(120) NULL", "academic_year": "INTEGER NULL",
            "has_licenciatura_students": "BOOLEAN NULL", "licenciatura_notes": "TEXT NULL",
        },
    }
    for table, columns in additions.items():
        if table not in inspector.get_table_names():
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for column, ddl in columns.items():
            if column not in existing:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    db.session.commit()


app = create_app()
BASE = Path(app.root_path).parent
CATALOG_FILE = BASE / "data" / "catalog" / "ppc_catalog.json"

OFFICIAL_OD_2025 = "https://portal.ifrn.edu.br/documents/24469/Oganiza%C3%A7%C3%A3o_Did%C3%A1tica_2025_-_Resolu%C3%A7%C3%A3o_110-2025.pdf"
OFFICIAL_DOCS = "https://portal.ifrn.edu.br/institucional/ensino/documentos-e-normativos/"


def html_list(items):
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def upsert_page(slug, title, category, content):
    page = SitePage.query.filter_by(slug=slug).first()
    if not page:
        page = SitePage(slug=slug, title=title, category=category)
        db.session.add(page)
    page.title = title
    page.category = category
    page.content = content
    page.published = True


def upsert_document(title, category, description, url):
    doc = Document.query.filter_by(title=title).first()
    if not doc:
        doc = Document(title=title, category=category, description=description, url=url)
        db.session.add(doc)
    else:
        doc.category = category
        doc.description = description
        doc.url = url
        doc.published = True


def load_catalog():
    catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    matrices = {
        2012: Matrix.query.filter_by(year=2012).first(),
        2018: Matrix.query.filter_by(year=2018).first(),
    }
    # Remove old prerequisite links before replacing the discipline rows.
    for year, matrix in matrices.items():
        if not matrix:
            continue
        ids = [d.id for d in Discipline.query.filter_by(matrix_id=matrix.id).all()]
        if ids:
            DisciplinePrerequisite.query.filter(
                DisciplinePrerequisite.discipline_id.in_(ids)
            ).delete(synchronize_session=False)
            DisciplinePrerequisite.query.filter(
                DisciplinePrerequisite.prerequisite_id.in_(ids)
            ).delete(synchronize_session=False)
            Discipline.query.filter(Discipline.id.in_(ids)).delete(synchronize_session=False)

    db.session.flush()
    by_name = {}
    for item in catalog:
        matrix = matrices[item["matrix_year"]]
        d = Discipline(
            matrix_id=matrix.id,
            code=None,
            name=item["name"],
            semester=item["semester"],
            area=item["area"],
            kind=item["kind"],
            credits=item["credits"],
            hours=item["hours"],
            lesson_hours=item["lesson_hours"],
            summary=item["summary"],
            objectives=item["objectives"],
            contents=item["contents"],
            methodology=item["methodology"],
            assessment=item["assessment"],
            bibliography_basic=item["bibliography_basic"],
            bibliography_complementary=item["bibliography_complementary"],
        )
        db.session.add(d)
        by_name[(item["matrix_year"], item["name"])] = d
    db.session.flush()

    for item in catalog:
        d = by_name[(item["matrix_year"], item["name"])]
        for prereq_name in item.get("prerequisites", []):
            p = by_name.get((item["matrix_year"], prereq_name))
            if p:
                db.session.add(DisciplinePrerequisite(discipline_id=d.id, prerequisite_id=p.id))


def seed_pages():
    upsert_page(
        "sobre-o-curso", "Sobre o curso", "O curso",
        """
        <p>O Curso Superior de Licenciatura em Informática, presencial, do IFRN – Campus Natal-Zona Norte, forma docentes para atuação na educação básica na área de Informática.</p>
        <h2>Documentos curriculares</h2>
        <p>O portal apresenta separadamente as matrizes de 2012 e 2018. O PPC de 2012 foi aprovado pela Resolução nº 10/2012-CONSUP/IFRN. O documento de 2018 registra a adequação pela Deliberação nº 21/2018-CONSEPEX, de 10/09/2018.</p>
        <p><a class="btn btn-outline" href="/static/docs/ppc_licenciatura_informatica_2012.pdf">Consultar PPC 2012</a> <a class="btn btn-outline" href="/static/docs/ppc_licenciatura_informatica_2018.pdf">Consultar PPC 2018</a></p>
        <h2>Tempo de integralização</h2>
        <p>As duas matrizes têm duração prevista de 8 semestres. Pela Organização Didática do IFRN, o tempo máximo de integralização para cursos de graduação é de duas vezes a duração prevista na matriz, portanto a referência institucional é de até 16 semestres.</p>
        <p>O portal também mantém uma área para o novo PPC de 2026, que permanece não publicado até que haja documento oficial disponível.</p>
        """,
    )

    upsert_page(
        "vida-academica", "Vida acadêmica", "Vida acadêmica",
        """
        <p>Esta seção reúne orientações para integralização curricular, prática profissional, TCC, ATPA, aproveitamento de estudos, certificação de conhecimentos, estágio extracurricular, assistência estudantil e calendário acadêmico.</p>
        <div class="card-grid three">
          <a class="feature-card" href="/pagina/tcc"><h3>TCC</h3><p>Regras específicas das matrizes e normas institucionais atuais.</p></a>
          <a class="feature-card" href="/pagina/estagio-docente"><h3>Estágio docente</h3><p>Etapas, carga horária e atividades previstas nos PPCs.</p></a>
          <a class="feature-card" href="/pagina/atpa"><h3>ATPA</h3><p>Atividades de aprofundamento e documentação.</p></a>
          <a class="feature-card" href="/pagina/aproveitamento-de-estudos"><h3>Aproveitamento</h3><p>Critérios e documentos conforme a Organização Didática 2025.</p></a>
          <a class="feature-card" href="/pagina/certificacao-de-conhecimentos"><h3>Certificação de conhecimentos</h3><p>Avaliação, limites e procedimentos.</p></a>
          <a class="feature-card" href="/pagina/estagio-extracurricular"><h3>Estágio extracurricular</h3><p>Como a atividade aparece nos PPCs e na integralização.</p></a>
        </div>
        """,
    )

    upsert_page(
        "tcc", "Trabalho de Conclusão de Curso", "Vida acadêmica",
        """
        <h2>PPC 2012</h2>
        <p>O TCC é componente curricular obrigatório para a obtenção do título de Licenciado e é materializado por meio de uma monografia. O desenvolvimento ocorre no último período, a partir da verticalização dos conhecimentos construídos nos projetos realizados ao longo do curso ou do aprofundamento em pesquisas acadêmico-científicas.</p>
        <p>O trabalho é acompanhado por professor orientador, com plano de atividades, reuniões periódicas, elaboração da monografia e avaliação/defesa pública perante banca. A banca é composta pelo orientador e mais dois componentes, podendo incluir profissional externo. A aprovação exige no mínimo 60 pontos.</p>
        <h2>PPC 2018</h2>
        <p>O Desenvolvimento de Pesquisa Acadêmico-Científica equivale ao TCC e é obrigatório. O PPC admite monografia, artigo científico publicado em revista ou periódico com ISSN e capítulo de livro publicado com ISBN.</p>
        <p>O TCC é desenvolvido nos 7º e 8º períodos, com dois Seminários de Orientação ao TCC. Há plano de atividades, reuniões com o orientador, elaboração do produto e defesa pública. A avaliação considera estrutura, organização dos conteúdos, atualidade e adequação das informações, aspectos linguístico-textuais e apresentação. A aprovação exige no mínimo 60 pontos.</p>
        <h2>Organização Didática vigente</h2>
        <p>A Organização Didática 2025 estabelece que o TCC, quando previsto no PPC, é componente obrigatório; prevê orientação, plano de atividades, reuniões, produção acadêmica e avaliação/defesa. Entre os produtos possíveis estão monografia, artigo, livro/capítulo, registro de programa de computador, patente, relatório técnico e produção técnica, conforme previsão do PPC e aprovação do Colegiado.</p>
        <p>Após a defesa, a versão final deve ser entregue em até 30 dias. O limite geral para conclusão do TCC é de dois semestres após a conclusão das disciplinas previstas na matriz ou até o fim do prazo máximo de conclusão do curso, o que ocorrer primeiro.</p>
        <p><a href="https://portal.ifrn.edu.br/documents/24469/Oganiza%C3%A7%C3%A3o_Did%C3%A1tica_2025_-_Resolu%C3%A7%C3%A3o_110-2025.pdf">Fonte: Organização Didática do IFRN 2025</a></p>
        """,
    )

    upsert_page(
        "estagio-docente", "Estágio docente", "Vida acadêmica",
        """
        <h2>PPC 2012</h2>
        <p>O Estágio Curricular Supervisionado (Estágio Docente) é prática profissional obrigatória, inicia-se a partir do 5º período e totaliza 400 horas, distribuídas em quatro etapas de 100 horas.</p>
        <ol><li><strong>Estágio I:</strong> caracterização e observação da escola, revisão/aprofundamento de referenciais teóricos e portfólio.</li><li><strong>Estágio II:</strong> caracterização e observação da escola e sala de aula, planejamento da regência e portfólio.</li><li><strong>Estágio III:</strong> observação, regência prioritariamente no ensino fundamental e portfólio.</li><li><strong>Estágio IV:</strong> observação, regência no ensino médio/profissional/EJA, projeto de intervenção, portfólio e relatório final.</li></ol>
        <p>O estudante que já exerce atividade docente regular na educação básica, na mesma disciplina da formação, pode requerer redução de até 200 horas, conforme o PPC.</p>
        <h2>PPC 2018</h2>
        <p>O Estágio Docente também totaliza 400 horas, em quatro etapas de 100 horas, iniciadas no 5º período e distribuídas nos quatro últimos semestres. O PPC prevê, preferencialmente, 40 horas de efetiva regência, distribuídas equitativamente entre os Estágios III e IV.</p>
        <p>Os Estágios I e II contam com orientação por turma de até 20 estudantes; III e IV, por turma de até 10 estudantes. O Estágio IV deve estar no último período e os estágios anteriores constituem pré-requisitos nos semestres imediatamente anteriores, salvo exceções aprovadas pelo Colegiado.</p>
        <p>Em ambos os PPCs, a escolha das escolas deve priorizar escolas públicas, inclusive cursos técnicos integrados e EJA do próprio IFRN, e cada etapa exige relatório.</p>
        """,
    )

    upsert_page(
        "atpa", "Atividades Teórico-Práticas de Aprofundamento (ATPA)", "Vida acadêmica",
        """
        <h2>PPC 2018</h2>
        <p>As ATPA são atividades de aprofundamento em áreas específicas de interesse dos estudantes. O estudante deve cumprir no mínimo 200 horas, reconhecidas pelo Colegiado do Curso.</p>
        <p>Podem compor as ATPA: participação em eventos, cursos, exposição/publicação de trabalhos, publicações em periódicos, coautoria de capítulos, projetos de extensão, pesquisa e ensino, tutoria/monitoria, organização de eventos, estágio extracurricular ou voluntário, programas de iniciação à docência, atividades específicas do curso e representação estudantil.</p>
        <p>Exemplos de limites previstos no PPC 2018 incluem 50h por projeto semestral ou 100h por projeto anual de pesquisa, ensino ou extensão; 25h por processo seletivo de tutoria/monitoria; 50h por estágio extracurricular semestral ou 100h anual, observada a carga horária mínima de 50h; e 40h por semestre em programas de iniciação à docência.</p>
        <p>A validação é solicitada à Coordenação do Curso pelo SUAP, com os documentos comprobatórios.</p>
        <h2>PPC 2012</h2>
        <p>O PPC 2012 não usa a denominação ATPA: prevê 200 horas de <em>Outras Atividades Acadêmico-Científico-Culturais</em>, reconhecidas pelo Colegiado. A pontuação das atividades é convertida em horas, segundo o quadro do PPC. Entre as atividades estão eventos, cursos, publicações, extensão, iniciação científica, iniciação à docência, monitoria, organização de eventos, estágio extracurricular/voluntário, visitas técnicas, representação estudantil e participação em núcleos/grupos de estudo.</p>
        <p>Para o registro, o estudante apresenta requerimento e documentação comprobatória; a validação é feita por banca composta pelo coordenador e pelo menos dois docentes do curso. Somente atividades realizadas durante o vínculo com o curso são contabilizadas.</p>
        """,
    )

    upsert_page(
        "estagio-extracurricular", "Estágio extracurricular", "Vida acadêmica",
        """
        <p>O estágio extracurricular não substitui automaticamente o Estágio Docente obrigatório. Nos PPCs, ele aparece como atividade que pode contribuir para a integralização das atividades complementares/ATPA.</p>
        <h2>PPC 2012</h2><p>O quadro de outras atividades acadêmico-científico-culturais considera estágio extracurricular ou voluntário na área do curso ou afim, com carga horária total mínima de 50 horas.</p>
        <h2>PPC 2018</h2><p>O quadro de ATPA considera estágio extracurricular ou voluntário na área do curso ou afim, com carga horária total mínima de 50 horas, atribuindo como referência 50h por estágio semestral ou 100h por estágio anual.</p>
        <h2>Procedimento institucional</h2><p>A formalização da prática profissional deve observar a Organização Didática e os fluxos institucionais aplicáveis. O estudante deve verificar o calendário e as orientações da Coordenação/Setor responsável antes de iniciar a atividade.</p>
        """,
    )

    upsert_page(
        "aproveitamento-de-estudos", "Aproveitamento de estudos", "Vida acadêmica",
        f"""
        <p>As orientações abaixo têm como referência a Organização Didática do IFRN atualizada pela Resolução nº 110/2025-CONSUP/IFRN.</p>
        <h2>Quanto pode ser aproveitado?</h2><p>Para cursos de graduação, o estudante pode obter dispensa, por aproveitamento de estudos e certificação de conhecimentos em conjunto, de até 50% da carga horária de disciplinas do curso, salvo disposições legais em contrário.</p>
        <h2>Requisitos</h2>{html_list([
          'conteúdos e cargas horárias com, no mínimo, 70% de correspondência com os programas das disciplinas do IFRN;',
          'disciplina cursada com aprovação em outro curso do mesmo nível ou nível posterior, ou em curso técnico de nível médio para aproveitamento em graduação correlata;',
          'disciplina cursada antes do ingresso no IFRN;',
          'disciplina cursada dentro do prazo previsto pela Organização Didática, considerado o tempo máximo de integralização do curso acrescido de dois anos;',
          'pré-requisitos da disciplina do IFRN, quando existentes, já integralizados.'
        ])}
        <h2>Documentos</h2>{html_list(['histórico acadêmico;','programas/ementas das disciplinas cursadas;','documento que comprove a autorização ou reconhecimento do curso de origem.'])}
        <p>A equivalência é analisada pela Coordenação de Curso e, em seguida, por docente especialista. A correspondência deve considerar os conteúdos dos programas, e não apenas os nomes das disciplinas.</p>
        <p>As solicitações obedecem aos períodos do calendário acadêmico e devem ser feitas mediante requerimento à Direção Acadêmica no período de matrícula ou renovação.</p>
        <p><a href="{OFFICIAL_OD_2025}">Consultar a Organização Didática 2025</a></p>
        """,
    )

    upsert_page(
        "certificacao-de-conhecimentos", "Certificação de conhecimentos", "Vida acadêmica",
        f"""
        <p>A Certificação de Conhecimentos permite solicitar dispensa de disciplina por meio de avaliação de conhecimentos e experiências previamente adquiridos, inclusive fora do ambiente escolar.</p>
        <h2>Regras da Organização Didática 2025</h2>{html_list([
          'a avaliação é teórica ou teórico-prática, conforme as características da disciplina;',
          'a banca é designada pela Diretoria Acadêmica, ouvida a Coordenação de Curso, e tem pelo menos dois docentes especialistas e um membro da equipe técnico-pedagógica;',
          'o estudante é dispensado da disciplina se obtiver aproveitamento igual ou superior a 60 pontos;',
          'podem ser requeridas no máximo quatro avaliações por estudante em cada período letivo;',
          'para cada disciplina, a certificação pode ser requerida uma única vez;',
          'é vedada a certificação em disciplina na qual o estudante tenha sido reprovado no IFRN;',
          'a ausência à avaliação cancela automaticamente o processo, sem recurso.'
        ])}
        <p>O requerimento deve enumerar as disciplinas pretendidas e respeitar os períodos do calendário acadêmico.</p>
        <p><a href="{OFFICIAL_OD_2025}">Consultar a Organização Didática 2025</a></p>
        """,
    )

    upsert_page(
        "assistencia-estudantil", "Assistência estudantil", "Vida acadêmica",
        """
        <p>A assistência estudantil deve ser consultada nos canais oficiais do IFRN e do Campus Natal-Zona Norte, especialmente quanto a editais, programas, auxílios, prazos e critérios de seleção.</p>
        <p><a href="https://portal.ifrn.edu.br/" target="_blank" rel="noopener">Portal do IFRN</a></p>
        <p><a href="https://suap.ifrn.edu.br/" target="_blank" rel="noopener">SUAP</a></p>
        <p>Os programas e critérios podem mudar de acordo com o edital e o período letivo; por isso, o portal do curso não reproduz regras que dependam de edital vigente.</p>
        """,
    )

    upsert_page(
        "calendario-academico", "Calendário acadêmico", "Vida acadêmica",
        """
        <p>Os prazos de matrícula, renovação, cancelamento, aproveitamento de estudos, certificação de conhecimentos, TCC e demais procedimentos dependem do calendário acadêmico vigente do campus.</p>
        <p>A Organização Didática 2025 determina que o calendário acadêmico contemple, entre outros itens, os períodos para requerimento de aproveitamento de estudos e certificação de conhecimentos.</p>
        <p><a href="https://portal.ifrn.edu.br/" target="_blank" rel="noopener">Acesse o portal do IFRN para consultar o calendário vigente.</a></p>
        """,
    )


def seed_documents():
    upsert_document(
        "PPC — Licenciatura em Informática — 2012",
        "PPC",
        "Projeto Pedagógico do Curso aprovado pela Resolução nº 10/2012-CONSUP/IFRN. Documento usado para a matriz histórica de 2012.",
        "/static/docs/ppc_licenciatura_informatica_2012.pdf",
    )
    upsert_document(
        "PPC — Licenciatura em Informática — adequação 2018",
        "PPC",
        "PPC aprovado pela Resolução nº 10/2012-CONSUP/IFRN, com adequação pela Deliberação nº 21/2018-CONSEPEX, de 10/09/2018.",
        "/static/docs/ppc_licenciatura_informatica_2018.pdf",
    )
    upsert_document(
        "Organização Didática do IFRN — 2025",
        "Normativo",
        "Organização Didática atualizada pela Resolução nº 110/2025-CONSUP/IFRN. Referência para aproveitamento, certificação, prática profissional, TCC e integralização.",
        OFFICIAL_OD_2025,
    )
    upsert_document(
        "Documentos e normativos do IFRN",
        "Normativo",
        "Página institucional para consulta de PPCs, Organização Didática e demais documentos acadêmicos.",
        OFFICIAL_DOCS,
    )


def seed_matrices():
    matrices = [
        (2012, "PPC 2012 — matriz histórica", "historica", "Projeto Pedagógico aprovado pela Resolução nº 10/2012-CONSUP/IFRN. Matriz de 8 semestres e 3.404 horas totais.", "/static/docs/ppc_licenciatura_informatica_2012.pdf"),
        (2018, "PPC 2018 — adequação curricular", "atual", "Projeto aprovado pela Resolução nº 10/2012-CONSUP/IFRN, com adequação pela Deliberação nº 21/2018-CONSEPEX, de 10/09/2018. Matriz de 8 semestres e 3.404 horas totais.", "/static/docs/ppc_licenciatura_informatica_2018.pdf"),
        (2026, "Novo PPC 2026", "implantacao", "Estrutura reservada para o novo PPC. O conteúdo permanece não publicado até a disponibilização oficial do documento.", None),
    ]
    for year,title,status,desc,url in matrices:
        m=Matrix.query.filter_by(year=year).first()
        if not m:
            m=Matrix(year=year)
            db.session.add(m)
        m.title=title; m.status=status; m.description=desc; m.document_url=url; m.duration_semesters=8; m.total_hours=3404 if year in (2012,2018) else None; m.is_published=(year in (2012,2018))


with app.app_context():
    db.create_all()
    ensure_schema()
    seed_matrices()
    db.session.flush()
    load_catalog()
    seed_pages()
    seed_documents()

    # Keep the existing demonstrative PIBID/project records, but avoid creating duplicates.
    if not Project.query.filter_by(is_pibid=True).first():
        db.session.add(Project(
            title="PIBID — Informática", acronym="PIBID Informática", project_type="ensino",
            description="Registro inicial para a área específica do PIBID. Atualize com os dados oficiais do subprojeto vigente.",
            objectives="Cadastrar objetivos, escolas parceiras, ações formativas e resultados do subprojeto.",
            coordinator="Cadastrar coordenação do subprojeto", period="Cadastrar período", status="A atualizar",
            is_pibid=True, featured=True, published=True,
        ))
    # Portarias fornecidas para iniciar o histórico do Colegiado e NDE.
    from app.models import GovernanceDocument
    from app.services.governance import import_governance
    governance_seed = [
        ("colegiado", "Colegiado 2026.1", BASE / "app/static/docs/governance/colegiado_2026_1.pdf"),
        ("colegiado", "Colegiado 2026.2", BASE / "app/static/docs/governance/colegiado_2026_2.pdf"),
        ("nde", "NDE 2025", BASE / "app/static/docs/governance/nde_2025.pdf"),
        ("nde", "NDE 2026.2", BASE / "app/static/docs/governance/nde_2026_2.pdf"),
    ]
    for body, title, path in governance_seed:
        if path.exists() and not GovernanceDocument.query.filter_by(title=title).first():
            try:
                # Initial import does not require SUAP; photos are filled later on admin import/sync.
                import_governance(path, body, title=title, document_url=f"/static/docs/governance/{path.name}")
            except Exception as exc:
                db.session.rollback()
                print(f"Aviso: não foi possível importar {title}: {exc}")

    # Reprocessa somente o histórico de atuação das portarias que já existem.
    # Isso é necessário porque a portaria do Colegiado 2026.1 registra atuação
    # em 2025.2 e 2026.1 na mesma tabela.
    from app.services.governance import parse_governance_pdf
    from app.models import TeacherHistory, Teacher, GovernanceMember
    for body, title, path in governance_seed:
        doc = GovernanceDocument.query.filter_by(title=title).first()
        if not doc or not path.exists():
            continue
        try:
            parsed = parse_governance_pdf(path, body)
            for item in parsed['members']:
                if item['role'].lower() not in ('docente', 'coordenadora', 'coordenador'):
                    continue
                teacher = Teacher.query.filter_by(name=item['name']).first()
                if not teacher:
                    continue
                terms = item.get('atuacao') or [parsed.get('semester')]
                for term in terms:
                    if term and not TeacherHistory.query.filter_by(teacher_id=teacher.id, semester=term, body=body).first():
                        db.session.add(TeacherHistory(teacher_id=teacher.id, semester=term, body=body, role=item['role'], governance_document_id=doc.id))
        except Exception as exc:
            print(f"Aviso: não foi possível atualizar histórico de {title}: {exc}")
    # A página de docentes representa a composição vigente do curso; os nomes que
    # aparecem somente em portarias históricas permanecem no histórico, mas deixam
    # de ser exibidos como docentes atuais.
    current_names = set()
    for current_doc in GovernanceDocument.query.filter_by(active=True).all():
        for member in GovernanceMember.query.filter_by(governance_document_id=current_doc.id, active=True).all():
            if member.role and member.role.lower() in ('docente', 'coordenadora', 'coordenador'):
                current_names.add(member.name)
    for teacher in Teacher.query.all():
        if TeacherHistory.query.filter_by(teacher_id=teacher.id).first():
            teacher.active = teacher.name in current_names

    db.session.commit()
    print("Seed concluído: matrizes 2012/2018, ementas, pré-requisitos, governança e páginas acadêmicas carregados.")


def seed_knowledge():
    from app.services.knowledge import index_source, knowledge_dir
    knowledge_files = [
        (BASE / "app" / "static" / "docs" / "ppc_licenciatura_informatica_2012.pdf", 2012, "PPC Licenciatura em Informática — 2012"),
        (BASE / "app" / "static" / "docs" / "ppc_licenciatura_informatica_2018.pdf", 2018, "PPC Licenciatura em Informática — 2018"),
    ]
    for project_file, year, title in knowledge_files:
        filename = project_file.name
        if KnowledgeSource.query.filter_by(matrix_year=year).first():
            continue
        stored_file = knowledge_dir() / filename
        stored_file.write_bytes(project_file.read_bytes())
        source = KnowledgeSource(
            title=title, document_type="PPC", matrix_year=year,
            description=f"PPC usado como fonte primária da matriz {year}.", filename=filename, active=True,
            indexed_at=datetime.utcnow(),
        )
        db.session.add(source)
        db.session.commit()
        try:
            index_source(source)
            print(f"{title} indexado na base de conhecimento.")
        except Exception as exc:
            db.session.rollback()
            print(f"Aviso: não foi possível indexar {title}: {exc}")

with app.app_context():
    seed_knowledge()
