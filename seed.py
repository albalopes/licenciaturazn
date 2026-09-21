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
from app.services.enade import seed_exams
from app.models import (
    Discipline,
    DisciplinePrerequisite,
    Matrix,
    Project,
    SitePage,
    KnowledgeSource,
    Document,
    Teacher,
    TeachingAssignment,
    CourseCoordinator,
    AcademicPublication,
    FAQ,
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
        "teachers": {"suap_id": "VARCHAR(80) NULL", "siape": "VARCHAR(50) NULL", "ingresso_disciplina": "VARCHAR(180) NULL"},
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
        2009: Matrix.query.filter_by(year=2009).first(),
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


def seed_faqs():
    items = [
        ("Como funciona o revezamento das entradas do curso?", """A Licenciatura em Informática recebe uma nova turma por ano e alterna o turno de ingresso: um ano no período vespertino e, no ano seguinte, no período noturno. Para 2027, a entrada prevista é noturna. Confirme sempre a oferta no edital vigente. <a href="/ingressos">Veja o cronograma de entradas</a> e <a href="https://portal.ifrn.edu.br/cursos/buscar/?campus=natalzonanorte" target="_blank" rel="noopener">consulte os cursos do Campus Natal-Zona Norte</a>.""", "Ingresso", 1),
        ("O que faço se abandonei o curso e quero voltar?", """Se você evadiu e ainda houver tempo hábil para concluir o curso dentro do prazo de integralização, pode solicitar <strong>reintegração de matrícula</strong>. O pedido é analisado pelo Colegiado do curso, considerando a situação acadêmica e as condições para conclusão. <a href="/pagina/vida-academica">Veja as orientações de vida acadêmica</a> e consulte a Secretaria Acadêmica para o procedimento e o período de solicitação.""", "Matrícula", 2),
        ("Qual é o prazo máximo para concluir a Licenciatura?", """As matrizes têm duração prevista de 8 semestres. A Organização Didática do IFRN estabelece, para cursos de graduação, tempo máximo de integralização correspondente a duas vezes a duração prevista na matriz. <a href="/pagina/sobre-o-curso">Veja as informações do curso</a> e consulte a <a href="https://portal.ifrn.edu.br/documents/24469/Oganiza%C3%A7%C3%A3o_Did%C3%A1tica_2025_-_Resolu%C3%A7%C3%A3o_110-2025.pdf" target="_blank" rel="noopener">Organização Didática 2025</a>.""", "Matrícula", 3),
        ("Onde encontro o calendário acadêmico?", """Você pode consultar o calendário vigente diretamente no portal do Campus Natal-Zona Norte. <a href="https://portal.ifrn.edu.br/campus/natalzonanorte/ensino/calendario-academico/" target="_blank" rel="noopener">Abrir o Calendário Acadêmico do Campus</a>.""", "Calendário", 4),
        ("Onde vejo os horários da Licenciatura?", """Na página de horários você encontra as turmas do semestre atual em uma grade semanal, com os dias da semana nas colunas. <a href="/horarios">Consultar horários</a>.""", "Horários", 5),
        ("Como encontro o contato de um professor?", """Acesse a página de docentes e escolha o professor. Você encontrará, quando disponíveis, foto, e-mail, disciplina de ingresso, Lattes e as disciplinas que ele está lecionando no semestre. <a href="/docentes">Ver docentes</a>.""", "Docentes", 6),
        ("Onde encontro ajuda para TCC e depósito no Memoria?", """Na página de TCC você encontra as orientações para as diferentes matrizes, normas de normalização, depósito no Memoria, Nada Consta da Biblioteca e informações para solicitar o diploma. <a href="/pagina/tcc">Acessar as orientações de TCC</a>.""", "TCC", 7),
        ("Onde encontro os editais de auxílio e assistência estudantil?", """Os editais de alimentação, transporte e outros programas de assistência são publicados pelo Campus. <a href="https://portal.ifrn.edu.br/campus/natalzonanorte/processo-seletivos-bolsas-para-estudantes/programas-de-alimentacao-estudantil-apoio-a-formacao-estudantil-e-auxilio-transporte/" target="_blank" rel="noopener">Consultar os programas de assistência estudantil</a>.""", "Assistência", 8),
        ("Onde encontro os documentos para estágio extracurricular?", """A página de Estágio do IFRN reúne o Termo de Compromisso, Plano de Atividades, relatórios do estagiário e supervisor, relatório de visita do orientador, termo aditivo, termo de realização e manuais do SUAP. <a href="/pagina/estagio-extracurricular">Ver orientações de estágio extracurricular</a>.""", "Estágio", 9),
    ]
    for question, answer, category, position in items:
        item = FAQ.query.filter_by(question=question).first()
        if not item:
            item = FAQ(question=question)
            db.session.add(item)
        item.answer = answer
        item.category = category
        item.position = position
        item.published = True


def seed_coordinators():
    # Histórico consolidado a partir dos Boletins de Serviço/Diário Oficial do IFRN.
    # As datas abaixo registram a vigência conhecida; quando o registro encontrado não informa
    # as datas exatas, a observação identifica explicitamente a aproximação.
    records = [
        {
            "name": "Bruno Sielly Jales Costa",
            "start_year": 2010,
            "end_year": 2013,
            "role": "Coordenador do curso",
            "profile_url": "https://docente.ifrn.edu.br/brunocosta/curriculum",
            "notes": (
                "Currículo institucional do professor registra atuação como Coordenador de Curso da "
                "Licenciatura em Informática no IFRN/ZN de dezembro de 2010 a março de 2013. "
                "A Portaria nº 090/2011-DG/ZN também registra Bruno Sielly Jales Costa na coordenação "
                "do NDE da Licenciatura em Informática, com efeitos a partir de 10/12/2010."
            ),
        },
        {
            "name": "João Maria Nascimento",
            "start_year": 2013,
            "end_year": 2014,
            "role": "Coordenador do curso",
            "profile_url": "https://portal.ifrn.edu.br/campus/reitoria/noticias/campus-zona-norte-promove-1a-semana-de-licenciatura-em-informatica/",
            "notes": (
                "Notícia institucional publicada em 04/09/2013 identifica João Maria Nascimento como "
                "coordenador do curso. O período exato de início e término da função não foi localizado "
                "nos registros consultados; o intervalo exibido é uma referência histórica aproximada, "
                "entre o período documentado de Bruno Sielly Jales Costa e a designação de Diego Silveira Costa Nascimento em 2014."
            ),
        },
        {
            "name": "Diego Silveira Costa Nascimento",
            "start_year": 2014,
            "end_year": 2016,
            "role": "Coordenador do curso",
            "profile_url": "https://portal.ifrn.edu.br/servidores/",
            "notes": (
                "Designado para a Coordenação do Curso de Licenciatura em Informática pela "
                "Portaria nº 273/2014-DG/ZN, de 30/10/2014. Dispensado da função com efeitos "
                "a partir de 01/10/2016, conforme Portaria nº 270/2016-DG/ZN/IFRN."
            ),
        },
        {
            "name": "Otávio Bruno Leite Barbosa",
            "start_year": 2016,
            "end_year": 2017,
            "role": "Coordenador do curso",
            "profile_url": "https://portal.ifrn.edu.br/servidores/",
            "notes": (
                "Designado para exercer a Função Comissionada de Coordenação de Curso (FUC-001), "
                "com efeitos a partir de 01/10/2016, conforme Portaria nº 271/2016-DG/ZN/IFRN. "
                "O registro seguinte de designação da função identifica Francisco das Chagas da Silva Júnior "
                "a partir de 17/10/2017."
            ),
        },
        {
            "name": "Francisco das Chagas da Silva Junior",
            "start_year": 2017,
            "end_year": 2025,
            "role": "Coordenador do curso",
            "profile_url": "https://portal.ifrn.edu.br/servidores/?page=18",
            "notes": (
                "Designado para a Coordenação do Curso de Licenciatura em Informática pela "
                "Portaria nº 252/2017-DG/ZN/RE/IFRN, de 17/10/2017. "
                "Dispensado do cargo com efeitos a partir de 08/09/2025 pela Portaria nº 282, "
                "de 22/08/2025, publicada no DOU de 10/10/2025."
            ),
        },
    ]

    for data in records:
        item = CourseCoordinator.query.filter_by(name=data["name"]).first()
        if not item:
            item = CourseCoordinator(name=data["name"])
            db.session.add(item)
        item.start_year = data["start_year"]
        item.end_year = data["end_year"]
        item.role = data["role"]
        item.profile_url = data["profile_url"]
        item.notes = data["notes"]
        item.active = True

    current = CourseCoordinator.query.filter_by(name="Alba Sandyra Bezerra Lopes Campos").first()
    if not current:
        current = CourseCoordinator(name="Alba Sandyra Bezerra Lopes Campos", start_year=2025, end_year=None)
        db.session.add(current)
    current.start_year = 2025
    current.end_year = None
    current.role = "Coordenadora do curso"
    current.profile_url = "mailto:alba.lopes@ifrn.edu.br"
    current.notes = "Coordenadora atual do curso. A página institucional do Campus Natal-Zona Norte informa Alba Sandyra Bezerra Lopes Campos como coordenadora da Licenciatura em Informática."
    current.active = True


def seed_pages():
    upsert_page(
        "sobre-o-curso", "Sobre o curso", "O curso",
        """
        <p>O Curso Superior de Licenciatura em Informática, presencial, do IFRN – Campus Natal-Zona Norte, forma docentes para atuação na educação básica na área de Informática.</p>
        <h2>Documentos curriculares</h2>
        <p>O portal mantém as versões históricas e a estrutura curricular do curso: PPC 2009, PPC 2012, adequação de 2018 e o espaço reservado ao novo PPC de 2026.</p>
        <p>O PPC 2009 foi aprovado pela Resolução nº 071/2009-CONSUP/IFRN e apresenta matriz de 8 semestres e 3.070 horas. O PPC 2012 foi aprovado pela Resolução nº 10/2012-CONSUP/IFRN. O documento de 2018 registra a adequação pela Deliberação nº 21/2018-CONSEPEX, de 10/09/2018.</p>
        <p><a class="btn btn-outline" href="/static/docs/ppc_licenciatura_informatica_2009.pdf">Consultar PPC 2009</a> <a class="btn btn-outline" href="/static/docs/ppc_licenciatura_informatica_2012.pdf">Consultar PPC 2012</a> <a class="btn btn-outline" href="/static/docs/ppc_licenciatura_informatica_2018.pdf">Consultar PPC 2018</a></p>
        <h2>Tempo de integralização</h2>
        <p>As matrizes históricas de 2009, 2012 e 2018 têm duração prevista de 8 semestres. Pela Organização Didática do IFRN, o tempo máximo de integralização para cursos de graduação é de duas vezes a duração prevista na matriz, portanto a referência institucional é de até 16 semestres.</p>
        <p>Se você ingressar a partir de 2027, encontrará aqui uma área específica para o novo PPC de 2026. Os detalhes serão preenchidos assim que o documento oficial estiver disponível.</p>
        """,
    )

    upsert_page(
        "vida-academica", "Vida acadêmica", "Vida acadêmica",
        """
        <p>Se você está organizando sua vida acadêmica, aqui estão reunidas as orientações que mais costumam fazer diferença: integralização curricular, prática profissional, TCC, ATPA, aproveitamento de estudos, certificação de conhecimentos, estágio extracurricular, assistência estudantil e calendário acadêmico.</p>
        <div class="card-grid three">
          <a class="feature-card" href="/pagina/tcc"><h3>TCC</h3><p>Regras específicas das matrizes e normas institucionais atuais.</p></a>
          <a class="feature-card" href="/pagina/estagio-docente"><h3>Estágio docente</h3><p>Etapas, carga horária e atividades previstas nos PPCs.</p></a>
          <a class="feature-card" href="/pagina/atpa"><h3>ATPA</h3><p>Atividades de aprofundamento e documentação.</p></a>
          <a class="feature-card" href="/pagina/aproveitamento-de-estudos"><h3>Aproveitamento</h3><p>Critérios e documentos conforme a Organização Didática 2025.</p></a>
          <a class="feature-card" href="/pagina/certificacao-de-conhecimentos"><h3>Certificação de conhecimentos</h3><p>Avaliação, limites e procedimentos.</p></a>
          <a class="feature-card" href="/pagina/estagio-extracurricular"><h3>Estágio extracurricular</h3><p>Como a atividade aparece nos PPCs e na integralização.</p></a>
          <a class="feature-card" href="/horarios"><h3>Horários</h3><p>Veja a grade semanal das turmas da Licenciatura.</p></a>
          <a class="feature-card" href="/faq"><h3>Dúvidas frequentes</h3><p>Respostas rápidas sobre matrícula, ingresso, TCC e vida acadêmica.</p></a>
          <a class="feature-card" href="https://portal.ifrn.edu.br/campus/natalzonanorte/ensino/calendario-academico/" target="_blank" rel="noopener"><h3>Calendário acadêmico</h3><p>Consulte o calendário vigente diretamente no Campus Natal-Zona Norte.</p></a>
        </div>
        """,
    )

    upsert_page(
        "tcc", "Trabalho de Conclusão de Curso", "Vida acadêmica",
        """
        <h2>PPC 2009</h2>
        <p>O PPC 2009 prevê a prática como componente curricular em 400 horas, incluindo Projetos Integradores do 3º ao 6º período e Monografia nos 7º e 8º períodos. A monografia é apresentada a banca examinadora composta pelo orientador e mais dois componentes, podendo incluir profissional externo.</p>
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
        <h2>PPC 2009</h2>
        <p>O PPC 2009 prevê 200 horas de <em>Atividades Acadêmico-Científico-Culturais</em>. Entre as atividades reconhecidas estão conferências e palestras, cursos e minicursos, encontros estudantis, iniciação científica, monitoria, voluntariado, publicações, visitas técnicas, extensão, congressos, exposições de trabalhos, grupos de estudo e representação estudantil. A validação é solicitada à Coordenação com documentos comprobatórios e analisada conforme as regras do PPC.</p>
        <h2>PPC 2012</h2>
        <p>O PPC 2012 não usa a denominação ATPA: prevê 200 horas de <em>Outras Atividades Acadêmico-Científico-Culturais</em>, reconhecidas pelo Colegiado. A pontuação das atividades é convertida em horas, segundo o quadro do PPC. Entre as atividades estão eventos, cursos, publicações, extensão, iniciação científica, iniciação à docência, monitoria, organização de eventos, estágio extracurricular/voluntário, visitas técnicas, representação estudantil e participação em núcleos/grupos de estudo.</p>
        <p>Para o registro, o estudante apresenta requerimento e documentação comprobatória; a validação é feita por banca composta pelo coordenador e pelo menos dois docentes do curso. Somente atividades realizadas durante o vínculo com o curso são contabilizadas.</p>
        """,
    )

    upsert_page(
        "estagio-extracurricular", "Estágio extracurricular", "Vida acadêmica",
        """
        <p>O estágio extracurricular é uma experiência de formação realizada em ambiente de trabalho e, para este curso, <strong>não substitui automaticamente o Estágio Docente obrigatório</strong>. Nos PPCs, ele aparece como atividade que pode contribuir para a integralização das atividades complementares/ATPA.</p>

        <div class="notice-card"><strong>Antes de iniciar o estágio</strong><p>Não comece a atividade sem verificar a formalização com o setor responsável por estágios do Campus. O IFRN mantém orientações, formulários e manuais atualizados na página institucional de estágios.</p><a class="btn btn-primary" href="https://portal.ifrn.edu.br/institucional/extensao/mundo-do-trabalho/estagio/" target="_blank" rel="noopener">Abrir página oficial de Estágios do IFRN</a></div>

        <h2>O estágio pode contar para a formação no curso?</h2>
        <p><strong>PPC 2012:</strong> o quadro de outras atividades acadêmico-científico-culturais considera estágio extracurricular ou voluntário na área do curso ou afim, com carga horária total mínima de 50 horas.</p>
        <p><strong>PPC 2018:</strong> o quadro de ATPA considera estágio extracurricular ou voluntário na área do curso ou afim, com carga horária total mínima de 50 horas, atribuindo como referência 50h por estágio semestral ou 100h por estágio anual.</p>
        <p>A validação das horas para a integralização deve ser solicitada conforme o procedimento acadêmico aplicável ao PPC do estudante, com a documentação comprobatória.</p>

        <h2>Documentação para formalização e acompanhamento</h2>
        <p>Na página institucional atual do IFRN estão disponíveis modelos para as principais etapas do estágio, incluindo:</p>
        <ul>
          <li><strong>Termo de Compromisso de Estágio</strong> e Plano de Atividades;</li>
          <li><strong>Termo Aditivo de Estágio</strong>, quando houver alteração das condições do estágio;</li>
          <li><strong>Relatório de Estágio — Estagiário e Supervisor</strong>;</li>
          <li><strong>Relatório de Visita à Organização Concedente — Professor Orientador</strong>;</li>
          <li><strong>Termo de Realização do Estágio</strong>, para o encerramento.</li>
        </ul>
        <p>O IFRN também disponibiliza manuais específicos do SUAP para <strong>estagiário, orientador e supervisor</strong>. A página institucional foi atualizada em julho de 2026.</p>

        <div class="link-grid">
          <a class="notice-card" href="https://portal.ifrn.edu.br/documents/29175/2_-_TERMO_DE_COMPROMISSO_E_PLANO_DE_ATIVIDADES_DE_ESTAGIO_D01bYCa_i1Cdz7l.doc" target="_blank" rel="noopener"><strong>Termo de Compromisso + Plano de Atividades</strong><span>Modelo oficial do IFRN</span></a>
          <a class="notice-card" href="https://portal.ifrn.edu.br/documents/29173/Relatorio_estagio.doc" target="_blank" rel="noopener"><strong>Relatório de Estágio — Estagiário e Supervisor</strong><span>Modelo oficial do IFRN</span></a>
          <a class="notice-card" href="https://portal.ifrn.edu.br/documents/29178/5_-_RELATORIO_DE_VISITA_A_ORGANIZACAO_CONCEDENTE_DIUZcw1_EZxuRgX.doc" target="_blank" rel="noopener"><strong>Relatório de Visita — Professor Orientador</strong><span>Modelo oficial do IFRN</span></a>
          <a class="notice-card" href="https://portal.ifrn.edu.br/documents/29172/TERMO_ADITIVO_3.doc" target="_blank" rel="noopener"><strong>Termo Aditivo de Estágio</strong><span>Modelo oficial do IFRN</span></a>
          <a class="notice-card" href="https://portal.ifrn.edu.br/documents/29177/TERMO_DE_REALIZACAO_DO_ESTAGIO_3.doc" target="_blank" rel="noopener"><strong>Termo de Realização do Estágio</strong><span>Modelo oficial do IFRN</span></a>
          <a class="notice-card" href="https://portal.ifrn.edu.br/documents/27988/CARTILHA_DO_EST%C3%81GIO.pdf" target="_blank" rel="noopener"><strong>Cartilha do Estágio</strong><span>Orientações institucionais</span></a>
        </div>

        <h2>Manuais do SUAP</h2>
        <div class="link-grid">
          <a class="notice-card" href="https://portal.ifrn.edu.br/documents/2836/Manual_estagio_estagi%C3%A1rio.pdf" target="_blank" rel="noopener"><strong>Manual do Estagiário</strong><span>Cadastro, relatórios, documentos e acompanhamento no SUAP</span></a>
          <a class="notice-card" href="https://portal.ifrn.edu.br/documents/2834/Manual_estagio_orientador.pdf" target="_blank" rel="noopener"><strong>Manual do Orientador</strong><span>Visitas, orientações e relatórios</span></a>
          <a class="notice-card" href="https://portal.ifrn.edu.br/documents/2835/Manual_estagio_supervisor.pdf" target="_blank" rel="noopener"><strong>Manual do Supervisor</strong><span>Relatório do supervisor e acompanhamento</span></a>
        </div>

        <h2>Como funciona o acompanhamento?</h2>
        <ol>
          <li>Cadastro do estágio, com Plano de Atividades e Termo de Compromisso.</li>
          <li>Acompanhamento pelo professor orientador e pelo supervisor da concedente.</li>
          <li>Relatórios de atividades do estagiário e do supervisor em periodicidade não superior a seis meses.</li>
          <li>Registro de aditivo quando houver alteração nas condições do estágio.</li>
          <li>Encerramento com o Termo de Realização do Estágio.</li>
        </ol>
        <p>O Manual do Estagiário do SUAP descreve essas etapas e orienta sobre o envio dos relatórios e documentos. Para as regras e fluxos mais recentes, prevalecem as orientações disponíveis no portal institucional e no setor de estágios do Campus.</p>

        <div class="notice-card"><strong>Campus Natal-Zona Norte</strong><p>A página de Relações com o Mundo do Trabalho do Campus apresenta o setor responsável por convênios, estágios e contratos de aprendizagem e orienta sobre a formalização e a entrega dos relatórios.</p><a class="btn btn-outline" href="https://portal.ifrn.edu.br/campus/natalzonanorte/extensao/relacoes-com-o-mundo-do-trabalho/" target="_blank" rel="noopener">Ver orientações do Campus Natal-Zona Norte</a></div>

        <p class="table-note"><strong>Fonte institucional:</strong> página “Estágio Técnico Supervisionado” do IFRN, atualizada em 07/07/2026, e página “Relações com o Mundo do Trabalho” do Campus Natal-Zona Norte. Consulte sempre os documentos oficiais antes de formalizar um novo estágio.</p>
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
        <p>Se você precisar de apoio para permanecer no curso, encontrar atendimento ou entender os programas de assistência, comece pela Coordenação de Atividades Estudantis (COAES/ZN). Reunimos aqui os contatos e os caminhos mais úteis para você.</p>
        <h2>Assistência estudantil</h2>
        <p>Você pode consultar os programas de <strong>Auxílio-Transporte</strong>, <strong>Auxílio-Alimentação</strong>, <strong>PAFE</strong> e outros auxílios diretamente nas páginas oficiais do Campus e do IFRN. Os prazos e critérios mudam conforme cada edital.</p>
        <div class="feature-grid">
          <a class="feature-card" href="https://portal.ifrn.edu.br/campus/natalzonanorte/processo-seletivos-bolsas-para-estudantes/programas-de-alimentacao-estudantil-apoio-a-formacao-estudantil-e-auxilio-transporte/" target="_blank" rel="noopener"><h3>Auxílios 2026</h3><p>Consulte o edital, cronograma, documentos e resultados do Campus Natal-Zona Norte.</p><span>Ver página oficial →</span></a>
          <a class="feature-card" href="https://portal.ifrn.edu.br/campus/natalzonanorte/estudantes/" target="_blank" rel="noopener"><h3>Estudantes · COAES</h3><p>Veja a equipe, contatos e programas de assistência estudantil.</p><span>Ir para a página →</span></a>
          <a class="feature-card" href="https://suap.ifrn.edu.br/" target="_blank" rel="noopener"><h3>SUAP</h3><p>Use o módulo de Assistência Estudantil quando o edital indicar inscrição pelo sistema.</p><span>Acessar SUAP →</span></a>
        </div>
        <h2>Saúde e acolhimento</h2>
        <p>O Campus conta com uma equipe multiprofissional vinculada à assistência estudantil. Se você precisar de orientação, acolhimento psicológico, atendimento médico, odontológico ou encaminhamento social, procure a COAES.</p>
        <div class="admin-table"><table><thead><tr><th>Atendimento</th><th>Profissional</th><th>Contato</th></tr></thead><tbody>
        <tr><td>Psicologia</td><td>Margareth Rose Barreto Lima Pinheiro</td><td><a href="mailto:psicologia.zn@ifrn.edu.br">psicologia.zn@ifrn.edu.br</a></td></tr>
        <tr><td>Medicina</td><td>Evanilson Francisco de Moura</td><td><a href="mailto:evanilson.moura@ifrn.edu.br">evanilson.moura@ifrn.edu.br</a></td></tr>
        <tr><td>Odontologia</td><td>Gerliene Maria Silva Araujo</td><td><a href="mailto:gerliene.araujo@ifrn.edu.br">gerliene.araujo@ifrn.edu.br</a></td></tr>
        <tr><td>Serviço Social</td><td>COAES / Serviço Social</td><td><a href="mailto:servicosocial.zn@ifrn.edu.br">servicosocial.zn@ifrn.edu.br</a></td></tr>
        <tr><td>COAES</td><td>Coordenação de Atividades Estudantis</td><td><a href="mailto:coaes.zn@ifrn.edu.br">coaes.zn@ifrn.edu.br</a></td></tr>
        </tbody></table></div>
        <p><a href="https://portal.ifrn.edu.br/campus/natalzonanorte/estudantes/" target="_blank" rel="noopener">Confira os contatos atualizados da equipe de estudantes no site oficial do Campus.</a></p>
        <div class="notice-card"><p><strong>Como marcar atendimento?</strong></p><p>As páginas atuais do Campus Natal-Zona Norte apresentam os profissionais e contatos, mas não publicam um fluxo específico e atualizado de agendamento médico ou odontológico. Por isso, antes de se deslocar, entre em contato com a COAES ou diretamente com o profissional pelo e-mail acima para confirmar o procedimento vigente.</p><p>Quando houver urgência, procure o setor de saúde e siga as orientações da equipe.</p></div>
        <h2>Uma dica importante</h2>
        <p>Mantenha seus dados de contato atualizados no SUAP e acompanhe seu e-mail institucional. Editais e convocações podem ter prazos próprios.</p>
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
        "PPC — Licenciatura em Informática — 2009",
        "PPC",
        "Projeto Pedagógico do Curso Superior de Licenciatura Plena em Informática, aprovado pela Resolução nº 071/2009-CONSUP/IFRN. Matriz de 8 semestres e 3.070 horas totais.",
        "/static/docs/ppc_licenciatura_informatica_2009.pdf",
    )
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
    upsert_document(
        "Calendário Acadêmico 2026 — Campus Natal-Zona Norte",
        "Calendário",
        "Calendário acadêmico vigente do Campus Natal-Zona Norte. Consulte a página oficial para acompanhar eventuais atualizações e retificações.",
        "https://portal.ifrn.edu.br/campus/natalzonanorte/ensino/calendario-academico/",
    )


def seed_matrices():
    matrices = [
        (2009, "PPC 2009 — matriz de implantação", "historica", "Projeto Pedagógico aprovado pela Resolução nº 071/2009-CONSUP/IFRN. Matriz de 8 semestres e 3.070 horas totais.", "/static/docs/ppc_licenciatura_informatica_2009.pdf"),
        (2012, "PPC 2012 — matriz histórica", "historica", "Projeto Pedagógico aprovado pela Resolução nº 10/2012-CONSUP/IFRN. Matriz de 8 semestres e 3.404 horas totais.", "/static/docs/ppc_licenciatura_informatica_2012.pdf"),
        (2018, "PPC 2018 — adequação curricular", "atual", "Projeto aprovado pela Resolução nº 10/2012-CONSUP/IFRN, com adequação pela Deliberação nº 21/2018-CONSEPEX, de 10/09/2018. Matriz de 8 semestres e 3.404 horas totais.", "/static/docs/ppc_licenciatura_informatica_2018.pdf"),
        (2026, "Novo PPC 2026", "implantacao", "Estrutura reservada para o novo PPC. O conteúdo permanece não publicado até a disponibilização oficial do documento.", None),
    ]
    for year,title,status,desc,url in matrices:
        m=Matrix.query.filter_by(year=year).first()
        if not m:
            m=Matrix(year=year)
            db.session.add(m)
        m.title=title; m.status=status; m.description=desc; m.document_url=url; m.duration_semesters=8; m.total_hours=3070 if year == 2009 else (3404 if year in (2012,2018) else None); m.is_published=(year in (2009,2012,2018))



def seed_entrances():
    entries = [
        (2027, "Noturno", 2026, "Entrada prevista para 2027 no período noturno, conforme o planejamento do curso. Confirme a oferta no edital vigente."),
        (2028, "Vespertino", 2026, "Revezamento previsto: entrada no período vespertino no ano seguinte à entrada noturna."),
        (2029, "Noturno", 2026, "Revezamento previsto: entrada no período noturno."),
    ]
    for year, shift, matrix_year, notes in entries:
        item = EntranceSchedule.query.filter_by(year=year).first()
        if not item:
            item = EntranceSchedule(year=year)
            db.session.add(item)
        item.shift=shift; item.matrix_year=matrix_year; item.notes=notes; item.published=True


def seed_teaching_schedule():
    path = BASE / "data" / "licenciatura_horarios_2026_2.json"
    if not path.exists():
        return
    items = json.loads(path.read_text(encoding="utf-8"))
    # O seed inicial não sobrescreve registros já cadastrados. A área restrita
    # oferece uma ação explícita para reimportar o arquivo do semestre.
    if TeachingAssignment.query.filter_by(semester="2026.2").first():
        return
    teacher_cache = {}
    for item in items:
        names = [n.strip() for n in item["teacher"].split("/")]
        for name in names:
            teacher = teacher_cache.get(name)
            if teacher is None:
                teacher = Teacher.query.filter(Teacher.name.ilike(name)).first()
                if not teacher:
                    teacher = Teacher(name=name, active=True)
                    db.session.add(teacher)
                    db.session.flush()
                teacher_cache[name] = teacher
            db.session.add(TeachingAssignment(
                teacher_id=teacher.id,
                teacher_name=teacher.name,
                semester="2026.2",
                course=item["course"],
                class_code=item["class_code"],
                weekday=item["weekday"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                room=item.get("room"),
                source="horário 2026.2 ZN - turmas v4.pdf",
            ))

with app.app_context():
    db.create_all()
    ensure_schema()
    seed_matrices()
    db.session.flush()
    load_catalog()
    seed_teaching_schedule()
    seed_coordinators()
    seed_pages()
    seed_faqs()
    seed_entrances()
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
    print("Seed concluído: matrizes 2009/2012/2018, ementas, pré-requisitos, governança e páginas acadêmicas carregados.")


def seed_publications():
    """Catálogo inicial de publicações verificadas em fontes institucionais e anais."""
    records = [
        dict(year=2015, title="Formação Inicial Docente em Questão: o PIBID na Licenciatura em Informática", authors="Anna Raquel da S. Marinho; Francisco das Chagas da Silva Júnior; Givanaldo Rocha de Souza; Pauleany Simões de Morais", event="XXI Workshop de Informática na Escola (WIE 2015)", publication_type="Artigo em evento", themes="PIBID;formação docente;licenciatura em informática", student_authors="Anna Raquel da S. Marinho", teacher_authors="Francisco das Chagas da Silva Júnior; Givanaldo Rocha de Souza; Pauleany Simões de Morais", doi="https://doi.org/10.5753/cbie.wie.2015.370", url="https://doi.org/10.5753/cbie.wie.2015.370", source="SBC / Anais do WIE 2015", description="Relato e reflexão sobre a atuação de bolsistas do PIBID da Licenciatura em Informática em escolas públicas da Zona Norte de Natal."),
        dict(year=2015, title="Um Estudo sobre a Evasão no Curso de Licenciatura em Informática do IFRN – Campus Natal – Zona Norte", authors="Odair Soares de Souza; Pauleany Simões de Morais; Francisco das Chagas da Silva Júnior", event="XXIII Workshop sobre Educação em Computação (WEI 2015)", publication_type="Artigo em evento", themes="evasão;licenciatura em informática;permanência estudantil", student_authors="Odair Soares de Souza", teacher_authors="Pauleany Simões de Morais; Francisco das Chagas da Silva Júnior", doi="https://doi.org/10.5753/wei.2015.10238", url="https://sol.sbc.org.br/index.php/wei/article/view/10238", source="SBC / Anais do WEI 2015"),
        dict(year=2015, title="Formação inicial de professores, significado do PIBID e a atuação do licenciado em informática na escola pública", authors="Francisco das Chagas da Silva Junior; Pauleany Simões de Morais; Givanaldo Rocha de Souza", event="III Colóquio Nacional — A produção do conhecimento em Educação Profissional", publication_type="Artigo em evento", themes="PIBID;formação docente;educação profissional", student_authors="", teacher_authors="Francisco das Chagas da Silva Junior; Pauleany Simões de Morais; Givanaldo Rocha de Souza", url="https://memoria.ifrn.edu.br/handle/1044/1265", source="Memoria IFRN / Anais 2015"),
        dict(year=2015, title="Inclusão digital para idosos: experiência de formação docente em projeto de extensão no Campus Natal Zona-Norte", authors="Francisco das Chagas da Silva Junior; Pauleany Simões de Morais", event="Revista Diálogos da Extensão", publication_type="Artigo em periódico", themes="inclusão digital;extensão;formação docente;idosos", student_authors="", teacher_authors="Francisco das Chagas da Silva Junior; Pauleany Simões de Morais", doi="https://doi.org/10.15628/dialogos.2015.3888", url="https://www2.ifrn.edu.br/ojs/index.php/DIALOGOS/article/view/3888", source="Revista Diálogos da Extensão"),
        dict(year=2016, title="Saberes e Fazeres da Docência na Licenciatura em Informática: Relato de Experiência das Ações do PIBID", authors="Givanaldo Rocha de Souza; Pauleany Simões de Morais; Jeanne da Silva Barbosa Bulcão; Anna Raquel da Silva Marinho; Danylla de Medeiros Souza", event="XXII Workshop de Informática na Escola (WIE 2016)", publication_type="Artigo em evento", themes="PIBID;formação docente;computação na educação", student_authors="Jeanne da Silva Barbosa Bulcão; Anna Raquel da Silva Marinho; Danylla de Medeiros Souza", teacher_authors="Givanaldo Rocha de Souza; Pauleany Simões de Morais", doi="https://doi.org/10.5753/cbie.wie.2016.241", url="https://doi.org/10.5753/cbie.wie.2016.241", source="SBC / Anais do WIE 2016"),
        dict(year=2016, title="Ensinar e Aprender Informática: análises a partir da mediação com a Placa Raspberry Pi", authors="Aysla Mylene Ferreira da Rocha; Diego Silveira Costa Nascimento; Gisele Rogéria Penatieri", event="III Congresso Nacional de Educação (CONEDU 2016)", publication_type="Artigo em evento", themes="robótica;Raspberry Pi;ensino de informática;tecnologia educacional", student_authors="Aysla Mylene Ferreira da Rocha", teacher_authors="Diego Silveira Costa Nascimento", url="https://www.editorarealize.com.br/index.php/artigo/visualizar/20904", source="Realize Editora / Anais do CONEDU 2016"),
        dict(year=2017, title="O uso do Scratch na Educação Básica: Um relato de experiência vivenciada no PIBID", authors="Anna Raquel da Silva Marinho; Givanaldo Rocha de Souza; Jean Clemisson Santos Rosa; Pauleany Simões de Morais", event="XXIII Workshop de Informática na Escola (WIE 2017)", publication_type="Artigo em evento", themes="Scratch;programação em blocos;PIBID;pensamento computacional", student_authors="Anna Raquel da Silva Marinho", teacher_authors="Givanaldo Rocha de Souza; Pauleany Simões de Morais", doi="https://doi.org/10.5753/cbie.wie.2017.402", url="https://doi.org/10.5753/cbie.wie.2017.402", source="SBC / Anais do WIE 2017"),
        dict(year=2017, title="Estudo de caso sobre uso de TDICs pelos discentes do Ensino Médio: propostas de intervenção do PIBID de Informática", authors="Jeanne da Silva Barbosa Bulcão; Paulo Augusto Lima Júnior; Darcleiton M. da Silva; Lucas Barbosa de Araújo; Diego Silveira Costa Nascimento", event="VI Congresso Brasileiro de Informática na Educação (CBIE 2017)", publication_type="Artigo em evento", themes="TDIC;PIBID;letramento digital;pensamento computacional", student_authors="Jeanne da Silva Barbosa Bulcão; Paulo Augusto Lima Júnior; Darcleiton M. da Silva; Lucas Barbosa de Araújo", teacher_authors="Diego Silveira Costa Nascimento", doi="https://doi.org/10.5753/cbie.wcbie.2017.883", url="https://doi.org/10.5753/cbie.wcbie.2017.883", source="SBC / Anais do WCBIE 2017"),
        dict(year=2017, title="Um Relato de Experiência da Implantação de um Modelo de Fábrica de Software Escola (FaSEs)", authors="Edmilson Barbalho Campos Neto; Alba Sandyra Bezerra Lopes; Diego Silveira Costa Nascimento", event="25º Workshop sobre Educação em Computação (WEI 2017)", publication_type="Artigo em evento", themes="fábrica de software escola;engenharia de software;aprendizagem baseada em projetos", student_authors="", teacher_authors="Edmilson Barbalho Campos Neto; Alba Sandyra Bezerra Lopes; Diego Silveira Costa Nascimento", doi="https://doi.org/10.5753/wei.2017.3540", url="https://doi.org/10.5753/wei.2017.3540", source="SBC / Anais do WEI 2017"),
        dict(year=2018, title="Estimulando o pensamento computacional e o raciocínio lógico no ensino fundamental por meio da OBI e computação desplugada", authors="Jéssica Silva de Souza; Alba Sandyra Bezerra Lopes", event="XXIX Simpósio Brasileiro de Informática na Educação (SBIE 2018)", publication_type="Artigo em evento", themes="pensamento computacional;computação desplugada;OBI;ensino fundamental", student_authors="Jéssica Silva de Souza", teacher_authors="Alba Sandyra Bezerra Lopes", doi="https://doi.org/10.5753/cbie.sbie.2018.1893", url="https://doi.org/10.5753/cbie.sbie.2018.1893", source="SBC / Anais do SBIE 2018"),
        dict(year=2018, title="Uma Análise Curricular das Disciplinas de Algoritmos e Lógica Computacional em Cursos de Licenciatura em Informática e Computação", authors="Jeanne da Silva Barbosa Bulcão; Edmilson Barbalho Campos Neto; Keila Cruz Moreira", event="XXIV Workshop de Informática na Escola (WIE 2018)", publication_type="Artigo em evento", themes="currículo;algoritmos;lógica computacional;licenciatura em informática", student_authors="Jeanne da Silva Barbosa Bulcão", teacher_authors="Edmilson Barbalho Campos Neto; Keila Cruz Moreira", doi="https://doi.org/10.5753/cbie.wie.2018.548", url="https://doi.org/10.5753/cbie.wie.2018.548", source="SBC / Anais do WIE 2018"),
        dict(year=2018, title="A utilização do Google Sala de Aula na Educação Básica: uma plataforma pedagógica de apoio à Educação Contextualizada", authors="Jairo Rodrigo Soares Carneiro; Alba Sandyra Bezerra Lopes; Edmilson Barbalho Campos Neto", event="XXIV Workshop de Informática na Escola (WIE 2018)", publication_type="Artigo em evento", themes="Google Sala de Aula;educação básica;tecnologias educacionais;educação contextualizada", student_authors="Jairo Rodrigo Soares Carneiro", teacher_authors="Alba Sandyra Bezerra Lopes; Edmilson Barbalho Campos Neto", doi="https://doi.org/10.5753/cbie.wie.2018.401", url="https://doi.org/10.5753/cbie.wie.2018.401", source="SBC / Anais do WIE 2018"),
        dict(year=2018, title="O Início de uma Prática de Letramento Digital Voltada para Pessoas com Deficiência Visual", authors="Keila Cruz Moreira; Leonardo Brunno Silva de Lima; Lindemberg Cordeiro dos Santos", event="III Congresso sobre Tecnologias na Educação (Ctrl+E 2018)", publication_type="Artigo em evento", themes="acessibilidade;deficiência visual;letramento digital;inclusão", student_authors="Leonardo Brunno Silva de Lima; Lindemberg Cordeiro dos Santos", teacher_authors="Keila Cruz Moreira", url="https://ceur-ws.org/Vol-2185/CtrlE_2018_paper_123.pdf", source="CEUR-WS / Anais do Ctrl+E 2018", description="Trabalho desenvolvido por estudantes da Licenciatura em Informática do Campus Natal-Zona Norte, sob orientação de Keila Moreira; o portal do IFRN registra a participação e o reconhecimento no evento."),
        dict(year=2024, title="Tecnologias Digitais na Educação para a inclusão de pessoas com Transtorno do Espectro Autista: uma revisão bibliográfica", authors="Pedro Henrique Silva Assunção; Pedro Lucas Fernandes Pereira; Alba Sandyra Bezerra Lopes; Sandra Cristinne Xavier da Câmara", event="XI Encontro Nacional de Computação dos Institutos Federais (ENCompIF 2024)", publication_type="Artigo em evento", themes="tecnologias digitais;educação inclusiva;autismo;tecnologia assistiva", student_authors="Pedro Henrique Silva Assunção; Pedro Lucas Fernandes Pereira", teacher_authors="Alba Sandyra Bezerra Lopes; Sandra Cristinne Xavier da Câmara", doi="https://doi.org/10.5753/encompif.2024.2511", url="https://doi.org/10.5753/encompif.2024.2511", source="SBC / Anais do ENCompIF 2024"),
        dict(year=2024, title="Experiência intercultural no ensino de pensamento computacional por meio do desenvolvimento de jogos digitais", authors="Pedro H. Silva Assunção; Edmilson B. Campos Neto; Alba S. B. Lopes Campos", event="XXXII Workshop sobre Educação em Computação (WEI 2024)", publication_type="Artigo em evento", themes="pensamento computacional;desenvolvimento de jogos;internacionalização;interculturalidade", student_authors="Pedro H. Silva Assunção", teacher_authors="Edmilson B. Campos Neto; Alba S. B. Lopes Campos", doi="https://doi.org/10.5753/wei.2024.2365", url="https://doi.org/10.5753/wei.2024.2365", source="SBC / Anais do WEI 2024"),
        dict(year=2024, title="Desenvolvendo competências nas áreas STEM por meio de rodas de conversas e oficinas", authors="Clara Freire M. Teixeira; Maria Isabel M. Oliveira; Maria Laura B. da Silva; Alba Sandyra B. L. Campos; Karolayne S. de Azevedo", event="18º Women in Information Technology (WIT 2024)", publication_type="Artigo em evento", themes="STEM;meninas na computação;gênero;Projeto Ada;extensão", student_authors="Clara Freire M. Teixeira; Maria Isabel M. Oliveira; Maria Laura B. da Silva", teacher_authors="Alba Sandyra B. L. Campos", doi="https://doi.org/10.5753/wit.2024.2660", url="https://doi.org/10.5753/wit.2024.2660", source="SBC / Anais do WIT 2024"),
        dict(year=2024, title="Aprendendo e explorando a natureza: um jogo interativo para a educação infantil", authors="Lairton Santos de Araújo; Alba Sandyra Bezerra Lopes", event="V Simpósio de Educação do IFRN", publication_type="Artigo em evento", themes="jogos educativos;educação infantil;tecnologia educacional", student_authors="Lairton Santos de Araújo", teacher_authors="Alba Sandyra Bezerra Lopes", url="https://simposioeducacao.ifrn.edu.br/wp-content/uploads/2024/05/RESUMOS-APRESENTACAO.pdf", source="IFRN / V Simpósio de Educação 2024", description="Trabalho listado entre os resumos expandidos aprovados para apresentação oral no V Simpósio de Educação do IFRN."),
        dict(year=2024, title="Integração de tecnologias digitais na educação de pessoas com transtorno do espectro autista", authors="Pedro Henrique Silva Assunção; Pedro Lucas Fernandes Pereira; Alba Sandyra Bezerra Lopes", event="V Simpósio de Educação do IFRN", publication_type="Artigo em evento", themes="tecnologias digitais;educação inclusiva;autismo;tecnologia assistiva", student_authors="Pedro Henrique Silva Assunção; Pedro Lucas Fernandes Pereira", teacher_authors="Alba Sandyra Bezerra Lopes", url="https://simposioeducacao.ifrn.edu.br/wp-content/uploads/2024/05/TRABALHOS-APROVADOS.pdf", source="IFRN / V Simpósio de Educação 2024", description="Trabalho listado entre os trabalhos aprovados do eixo Inclusão e diversidade do V Simpósio de Educação do IFRN."),
        dict(year=2024, title="A construção e comunicação de conceitos pelo estudante com transtorno do espectro autista", authors="Keila Cruz Moreira; Helber Wagner da Silva; Rebecca Cruz Pinheiro", event="V Congresso Internacional de Educação Inclusiva (CINTEDI 2024)", publication_type="Artigo em evento", themes="autismo;comunicação;inclusão;intervenção pedagógica", student_authors="", teacher_authors="Keila Cruz Moreira", url="https://editorarealize.com.br/artigo/visualizar/108083", source="Realize Editora / Anais do V CINTEDI 2024"),
        dict(year=2024, title="O impacto positivo das tecnologias digitais no desenvolvimento de habilidades sociais e educacionais em estudantes com transtorno do espectro autista", authors="Pedro Henrique Silva Assunção; Pedro Lucas Fernandes Pereira; Keila Cruz Moreira", event="V Congresso Internacional de Educação Inclusiva (CINTEDI 2024)", publication_type="Artigo em evento", themes="autismo;tecnologias digitais;inclusão;tecnologia assistiva", student_authors="Pedro Henrique Silva Assunção; Pedro Lucas Fernandes Pereira", teacher_authors="Keila Cruz Moreira", url="https://editorarealize.com.br/artigo/visualizar/108256", source="Realize Editora / Anais do V CINTEDI 2024"),
        dict(year=2024, title="Tecnologias Digitais na Formação de Praças da Polícia Militar do Rio Grande do Norte (2020/2021)", authors="Keila Cruz Moreira; Diego Farias Pimenta; Francisco das Chagas da Silva Junior", event="Vigilantis Semper — Revista Científica de Segurança Pública", publication_type="Artigo em periódico", themes="tecnologias digitais;formação profissional;educação;polícia militar", student_authors="", teacher_authors="Keila Cruz Moreira; Francisco das Chagas da Silva Junior", url="https://www.escavador.com/sobre/3009978/keila-cruz-moreira", source="Registro bibliográfico consultado / Escavador", description="Registro bibliográfico de produção de 2024 localizada no currículo público de Keila Cruz Moreira. O catálogo mantém a página do currículo como rota de verificação enquanto a página do periódico não foi localizada na busca."),
        dict(year=2025, title="O curso de aperfeiçoamento Escola da Terra e a formação continuada docente: uma construção de saberes sobre a escola do campo", authors="Giovana Gomes Albino; Keila Cruz Moreira; Clarissa Souza de Andrade Honda", event="Seminário Internacional de Educação do Campo e Educação em Territórios Rurais / EPPECPB", publication_type="Artigo em evento", themes="formação docente;educação do campo;formação continuada;Escola da Terra", student_authors="Giovana Gomes Albino", teacher_authors="Keila Cruz Moreira", url="https://www.even3.com.br/anais/isiec2024/969998-o-curso-de-aperfeicoamento-escola-da-terra-e-a-formacao-continuada-docente--uma-construcao-de-saberes-sobre-a-esc/", source="Even3 / Anais do evento", description="Artigo completo publicado em 07/04/2025 nos anais do evento; a página informa ISBN 978-65-272-1272-0."),
        dict(year=2023, title="Inteligência artificial e gamificação no ensino de metáforas", authors="Rebecca Cruz Pinheiro; Keila Cruz Moreira", event="IX Congresso Nacional de Educação (CONEDU 2023)", publication_type="Artigo em evento", themes="inteligência artificial;gamificação;educação;ensino", student_authors="Rebecca Cruz Pinheiro", teacher_authors="Keila Cruz Moreira", url="https://editorarealize.com.br/artigo/visualizar/98442", source="Realize Editora / Anais do IX CONEDU 2023"),
        dict(year=2021, title="Uma trajetória extensionista rumo ao letramento digital na microrregião do litoral sul potiguar", authors="Simeone Gregorio dos Santos; Keila Cruz Moreira; Helber Wagner da Silva", event="Revista Brasileira de Extensão Universitária", publication_type="Artigo em periódico", themes="letramento digital;extensão;inclusão digital;educação", student_authors="Simeone Gregorio dos Santos", teacher_authors="Keila Cruz Moreira", doi="https://doi.org/10.36661/2358-0399.2021v12i2.11610", url="https://doi.org/10.36661/2358-0399.2021v12i2.11610", source="Revista Brasileira de Extensão Universitária"),
        dict(year=2019, title="Diagnóstico e estratégia de prevenção ao uso abusivo de smartphones na escola", authors="Helber Wagner da Silva; Nivia de Araújo Lopes; Aline da Silva Bispo; Keila Cruz Moreira", event="Revista de Estudos e Pesquisas sobre Ensino Tecnológico (EDUCITEC)", publication_type="Artigo em periódico", themes="smartphones;educação profissional;dependência de internet;tecnologia educacional", student_authors="", teacher_authors="Keila Cruz Moreira", doi="https://doi.org/10.31417/educitec.v5i12.858", url="https://sistemascmc.ifam.edu.br/educitec/index.php/educitec/article/view/858", source="EDUCITEC"),
        dict(year=2018, title="O ensino médio integrado na perspectiva da pedagogia histórico-crítica", authors="Fábio Alexandre Araújo dos Santos; Joseane Duarte Santos; Andrezza Maria Batista do Nascimento Tavares; Keila Cruz Moreira", event="Revista Portuguesa de Investigação Educacional", publication_type="Artigo em periódico", themes="ensino médio integrado;pedagogia histórico-crítica;educação profissional", student_authors="", teacher_authors="Keila Cruz Moreira", url="https://revistas.ucp.pt/index.php/investigacaoeducacional/article/view/3455", source="Revista Portuguesa de Investigação Educacional"),
    ]
    for data in records:
        if not AcademicPublication.query.filter_by(title=data['title'], year=data['year']).first():
            db.session.add(AcademicPublication(**data, published=True))
    db.session.commit()


def seed_knowledge():
    from app.services.knowledge import index_source, knowledge_dir
    knowledge_files = [
        (BASE / "app" / "static" / "docs" / "ppc_licenciatura_informatica_2009.pdf", 2009, "PPC Licenciatura em Informática — 2009"),
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


def seed_teaching_schedule():
    path = BASE / "data" / "licenciatura_horarios_2026_2.json"
    if not path.exists():
        return
    items = json.loads(path.read_text(encoding="utf-8"))
    # O seed inicial não sobrescreve registros já cadastrados. A área restrita
    # oferece uma ação explícita para reimportar o arquivo do semestre.
    if TeachingAssignment.query.filter_by(semester="2026.2").first():
        return
    teacher_cache = {}
    for item in items:
        names = [n.strip() for n in item["teacher"].split("/")]
        for name in names:
            teacher = teacher_cache.get(name)
            if teacher is None:
                teacher = Teacher.query.filter(Teacher.name.ilike(name)).first()
                if not teacher:
                    teacher = Teacher(name=name, active=True)
                    db.session.add(teacher)
                    db.session.flush()
                teacher_cache[name] = teacher
            db.session.add(TeachingAssignment(
                teacher_id=teacher.id,
                teacher_name=teacher.name,
                semester="2026.2",
                course=item["course"],
                class_code=item["class_code"],
                weekday=item["weekday"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                room=item.get("room"),
                source="horário 2026.2 ZN - turmas v4.pdf",
            ))

with app.app_context():
    seed_publications()
    seed_knowledge()


with app.app_context():
    seed_exams()
