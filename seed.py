from app import create_app
from app.extensions import db
from app.models import Discipline, Matrix, Project, SitePage, KnowledgeSource

app = create_app()

with app.app_context():
    db.create_all()

    if not Matrix.query.filter_by(year=2012).first():
        db.session.add(Matrix(year=2012, title="PPC original", status="historica", description="Matriz histórica baseada no PPC original aprovado em 2012.", duration_semesters=8, total_hours=3404, is_published=True))
    if not Matrix.query.filter_by(year=2018).first():
        db.session.add(Matrix(year=2018, title="PPC com adequação de 2018", status="atual", description="Estrutura para a matriz vigente/adequada em 2018. Cadastre as disciplinas e planos oficiais pelo painel administrativo.", duration_semesters=8, total_hours=3404, is_published=True))
    if not Matrix.query.filter_by(year=2026).first():
        db.session.add(Matrix(year=2026, title="Novo PPC 2026", status="implantacao", description="Estrutura reservada para o novo PPC de 2026, após publicação oficial.", duration_semesters=8, is_published=False))
    db.session.commit()

    if not SitePage.query.filter_by(slug="sobre-o-curso").first():
        db.session.add(SitePage(slug="sobre-o-curso", title="Sobre o curso", category="O curso", content="Página inicial de conteúdo. Substitua este texto pelo conteúdo oficial do PPC e das páginas institucionais."))
    pages = {
        "vida-academica": ("Vida acadêmica", "Vida acadêmica", "Reúna nesta página as orientações gerais e os links para TCC, estágio, ATPA, aproveitamento, certificação, assistência e calendário."),
        "tcc": ("Trabalho de Conclusão de Curso", "Vida acadêmica", "Cadastrar aqui as regras do TCC conforme a matriz/PPC do estudante e a regulamentação institucional vigente."),
        "estagio-docente": ("Estágio docente", "Vida acadêmica", "Cadastrar aqui as etapas, pré-requisitos, documentos e orientações do estágio docente."),
        "estagio-extracurricular": ("Estágio extracurricular", "Vida acadêmica", "Cadastrar aqui as regras e procedimentos do estágio extracurricular."),
        "atpa": ("Atividades Teórico-Práticas de Aprofundamento", "Vida acadêmica", "Cadastrar aqui as categorias, limites, documentos e fluxo de registro das ATPA."),
        "aproveitamento-de-estudos": ("Aproveitamento de estudos", "Vida acadêmica", "Cadastrar aqui o fluxo e os requisitos conforme a Organização Didática vigente."),
        "certificacao-de-conhecimentos": ("Certificação de conhecimentos", "Vida acadêmica", "Cadastrar aqui as regras, prazos e etapas da certificação."),
        "assistencia-estudantil": ("Assistência estudantil", "Vida acadêmica", "Cadastrar aqui programas, editais e links oficiais da assistência estudantil."),
        "calendario-academico": ("Calendário acadêmico", "Vida acadêmica", "Cadastrar aqui eventos e links para o calendário acadêmico oficial."),
    }
    for slug,(title,category,content) in pages.items():
        if not SitePage.query.filter_by(slug=slug).first():
            db.session.add(SitePage(slug=slug,title=title,category=category,content=content))
    db.session.commit()

    matrix = Matrix.query.filter_by(year=2018).first()
    if matrix and not matrix.disciplines:
        sample = Discipline(matrix_id=matrix.id, code="EXEMPLO", name="Disciplina de exemplo", semester=1, area="Exemplo", kind="obrigatoria", credits=4, hours=60, lesson_hours=80, summary="Registro demonstrativo. Substitua pelo plano de curso oficial da matriz 2018.", objectives="Exemplo de objetivo.", contents="Exemplo de conteúdo.", methodology="Exemplo de metodologia.", assessment="Exemplo de avaliação.", bibliography_basic="Cadastrar bibliografia oficial.", bibliography_complementary="Cadastrar bibliografia oficial.")
        db.session.add(sample)
        db.session.commit()


    if not Project.query.filter_by(is_pibid=True).first():
        db.session.add(Project(
            title="PIBID — Informática",
            acronym="PIBID Informática",
            project_type="ensino",
            description="Registro demonstrativo para a área específica do PIBID. Substitua pelos dados oficiais do subprojeto vigente.",
            objectives="Cadastrar objetivos, escolas parceiras, ações formativas e resultados do subprojeto.",
            coordinator="Cadastrar coordenação do subprojeto",
            period="Cadastrar período",
            status="Demonstrativo",
            is_pibid=True,
            featured=True,
            published=True,
        ))
        db.session.commit()

    print("Seed concluído. Os registros demonstrativos devem ser substituídos pelos dados oficiais.")


# Indexa o PPC 2012 que acompanha este protótipo, quando pypdf estiver instalado.
def seed_knowledge():
    from pathlib import Path
    from app.services.knowledge import index_source
    project_file = Path(app.root_path).parent / "data" / "knowledge" / "PPC_Licenciatura_em_Informatica_2012.pdf"
    if not project_file.exists() or KnowledgeSource.query.filter_by(filename=project_file.name).first():
        return
    from app.services.knowledge import knowledge_dir
    stored_file = knowledge_dir() / project_file.name
    stored_file.write_bytes(project_file.read_bytes())
    source = KnowledgeSource(
        title="PPC Licenciatura em Informática — 2012",
        document_type="PPC",
        matrix_year=2012,
        description="PPC 2012 utilizado como documento histórico da matriz.",
        filename=stored_file.name,
        active=True,
    )
    db.session.add(source)
    db.session.commit()
    try:
        index_source(source)
        print("PPC 2012 indexado na base de conhecimento.")
    except Exception as exc:
        db.session.rollback()
        print(f"Aviso: não foi possível indexar o PPC 2012: {exc}")


with app.app_context():
    seed_knowledge()
