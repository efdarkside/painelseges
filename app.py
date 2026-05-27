"""
Painel SEGES/DIGEC/PROGEP — Backend Flask
Sistema de acompanhamento de atividades da Secretaria de Formação
para Gestão do Conhecimento da UFMS.

Autor: Sistema gerado com base na Resolução n° 682-CD/2026
"""
import os
import sqlite3
from functools import wraps
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'troque-esta-chave-em-producao-12345')
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'seges.db')


# ============================================================
# BANCO DE DADOS
# ============================================================

def get_db():
    """Conecta ao banco SQLite (uma conexão por request)."""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Cria as tabelas e popula com dados iniciais."""
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    # ----- Usuários -----
    cur.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nome TEXT NOT NULL,
            email TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ----- Métricas (visão geral) -----
    cur.execute('''
        CREATE TABLE IF NOT EXISTS metricas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL,
            rotulo TEXT NOT NULL,
            valor TEXT NOT NULL,
            subtitulo TEXT,
            cor TEXT DEFAULT 'azul',
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ----- Competências da SEGES -----
    cur.execute('''
        CREATE TABLE IF NOT EXISTS competencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ordem INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            categoria TEXT,
            progresso INTEGER DEFAULT 0
        )
    ''')

    # ----- Ações do PDP -----
    cur.execute('''
        CREATE TABLE IF NOT EXISTS acoes_pdp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            modalidade TEXT,
            publico_alvo TEXT,
            status TEXT NOT NULL DEFAULT 'Programado',
            vagas INTEGER,
            ano INTEGER DEFAULT 2026,
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ----- Fases do PDP -----
    cur.execute('''
        CREATE TABLE IF NOT EXISTS fases_pdp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ordem INTEGER NOT NULL,
            descricao TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pendente',
            prazo TEXT
        )
    ''')

    # ----- Cursos / Capacitações -----
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            carga_horaria TEXT,
            modalidade TEXT,
            status TEXT NOT NULL DEFAULT 'Programado',
            inscritos INTEGER DEFAULT 0,
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ----- Banco de Talentos -----
    cur.execute('''
        CREATE TABLE IF NOT EXISTS talentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cargo TEXT,
            unidade TEXT,
            siape TEXT,
            formacao TEXT,
            competencias TEXT,
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ----- Solicitações de Atendimento -----
    cur.execute('''
        CREATE TABLE IF NOT EXISTS solicitacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servidor TEXT NOT NULL,
            siape TEXT,
            unidade TEXT,
            tipo TEXT NOT NULL,
            descricao TEXT,
            status TEXT NOT NULL DEFAULT 'Pendente',
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ----- Diagnóstico (eixos e indicadores) -----
    cur.execute('''
        CREATE TABLE IF NOT EXISTS diagnostico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            rotulo TEXT NOT NULL,
            valor TEXT NOT NULL,
            percentual INTEGER DEFAULT 0
        )
    ''')

    db.commit()

    # ----- Seed: usuário admin padrão -----
    # A senha vem da variável de ambiente ADMIN_PASSWORD; se não definida, usa um padrão
    admin_password = os.environ.get('ADMIN_PASSWORD', 'seges2026')
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')

    existe = cur.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]
    if existe == 0:
        cur.execute(
            'INSERT INTO usuarios (username, password_hash, nome, email) VALUES (?,?,?,?)',
            (
                admin_username,
                generate_password_hash(admin_password),
                'Administrador SEGES',
                'seges.progep@ufms.br'
            )
        )
    else:
        # Se já existir admin e a env ADMIN_PASSWORD estiver definida, atualiza a senha
        # (permite trocar a senha pelo painel do Render sem precisar de Shell)
        if os.environ.get('ADMIN_PASSWORD'):
            cur.execute(
                'UPDATE usuarios SET password_hash = ? WHERE username = ?',
                (generate_password_hash(admin_password), admin_username)
            )

    # ----- Seed: competências (REAIS, da Resolução n° 682-CD/2026) -----
    if cur.execute('SELECT COUNT(*) FROM competencias').fetchone()[0] == 0:
        competencias_iniciais = [
            (1, 'Diagnóstico de necessidades',
             'Realizar diagnóstico sistemático das necessidades de capacitação e desenvolvimento, a partir da análise dos processos de trabalho, fluxos operacionais, indicadores de desempenho e diretrizes do PDI/PPI da UFMS, em articulação com as unidades da UFMS, visando ao aprimoramento institucional e à qualificação da força de trabalho.',
             'Diagnóstico', 78),
            (2, 'Plano de Desenvolvimento de Pessoas',
             'Propor, executar e monitorar o Plano de Desenvolvimento de Pessoas – PDP, visando a capacitação anual dos servidores e colaboradores da UFMS.',
             'PDP', 65),
            (3, 'Relatório anual',
             'Elaborar o relatório anual de execução do PDP.',
             'Relatório', 30),
            (4, 'Gestão de recursos',
             'Gerir os recursos das Ações de Capacitação de Servidores.',
             'Gestão de Recursos', 52),
            (5, 'Banco de Talentos',
             'Sistematizar o banco de talentos com dados de formação e competências dos servidores da UFMS.',
             'Banco de Talentos', 88),
            (6, 'Atendimento individualizado',
             'Oferecer atendimento individualizado de orientação aos servidores.',
             'Atendimento', 91),
        ]
        cur.executemany(
            'INSERT INTO competencias (ordem, titulo, descricao, categoria, progresso) VALUES (?,?,?,?,?)',
            competencias_iniciais
        )

    # ----- Seed: métricas iniciais -----
    if cur.execute('SELECT COUNT(*) FROM metricas').fetchone()[0] == 0:
        metricas_iniciais = [
            ('servidores_pdp', 'Servidores no PDP 2026', '342', '↑ 18% em relação a 2025', 'azul'),
            ('cursos_ofertados', 'Cursos ofertados', '47', '28 concluídos · 19 em andamento', 'verde'),
            ('horas_capacitacao', 'Horas de capacitação', '1.840', 'Acumuladas no exercício 2026', 'amarelo'),
            ('banco_talentos', 'Banco de Talentos', '216', 'Servidores cadastrados', 'roxo'),
        ]
        cur.executemany(
            'INSERT INTO metricas (chave, rotulo, valor, subtitulo, cor) VALUES (?,?,?,?,?)',
            metricas_iniciais
        )

    # ----- Seed: fases do PDP -----
    if cur.execute('SELECT COUNT(*) FROM fases_pdp').fetchone()[0] == 0:
        fases_iniciais = [
            (1, 'Levantamento de necessidades (LNT) — todas as unidades', 'Concluído', ''),
            (2, 'Consolidação e priorização das demandas', 'Concluído', ''),
            (3, 'Aprovação do PDP pelo Comitê Gestor', 'Concluído', ''),
            (4, 'Execução das ações de capacitação', 'Em andamento', ''),
            (5, 'Monitoramento e avaliação de resultados', 'Pendente', 'Ago/2026'),
            (6, 'Elaboração do relatório anual de execução', 'Pendente', 'Dez/2026'),
        ]
        cur.executemany(
            'INSERT INTO fases_pdp (ordem, descricao, status, prazo) VALUES (?,?,?,?)',
            fases_iniciais
        )

    # ----- Seed: cursos (vindos das notícias reais do site da SEGES) -----
    if cur.execute('SELECT COUNT(*) FROM cursos').fetchone()[0] == 0:
        cursos_iniciais = [
            ('IsF — Inglês Comunicação Acadêmica', '120h', 'EaD', 'Em andamento', 58),
            ('IsF — Espanhol Serviços Turísticos (SED-MS)', '300h', 'Presencial', 'Em andamento', 32),
            ('Formação Multiplicadores ODS — PROCIDS', '40h', 'EaD', 'Em andamento', 75),
            ('Oficina Heteroidentificação', '8h', 'Presencial', 'Concluído', 28),
            ('TEA — Transtorno do Espectro Autista', '20h', 'EaD', 'Concluído', 43),
            ('Caminhos Inclusivos na Educ. Superior', '20h', 'Híbrido', 'Concluído', 47),
            ('LideraGOV 5.0 (ENAP)', '60h', 'EaD', 'Concluído', 22),
            ('Prevenção — Assédio Sexual e Moral', '4h', 'EaD', 'Concluído', 198),
            ('Assédio Moral: O que saber e fazer', '4h', 'EaD', 'Concluído', 201),
            ('Compensação Recesso — Cursos Online', '16h', 'EaD', 'Programado', 0),
            ('Licença Capacitação — Processos 2026/2', 'Variável', 'Externo', 'Programado', 0),
        ]
        cur.executemany(
            'INSERT INTO cursos (nome, carga_horaria, modalidade, status, inscritos) VALUES (?,?,?,?,?)',
            cursos_iniciais
        )

    # ----- Seed: ações do PDP -----
    if cur.execute('SELECT COUNT(*) FROM acoes_pdp').fetchone()[0] == 0:
        acoes_iniciais = [
            ('Curso IsF — Inglês Comunicação Acadêmica', 'EaD', 'Docentes/TAEs', 'Em andamento', 60),
            ('Oficina Heteroidentificação', 'Presencial', 'Comissões', 'Concluído', 30),
            ('Espectro Autista — TEA na Educação', 'EaD', 'TAEs', 'Concluído', 45),
            ('Caminhos Inclusivos na Educ. Superior', 'Híbrido', 'Docentes', 'Concluído', 50),
            ('LideraGOV 5.0 — Liderança no Setor Público', 'EaD/ENAP', 'Gestores', 'Concluído', 25),
            ('Prevenção e Enfrentamento — Assédio', 'EaD', 'Todos', 'Concluído', 200),
            ('Pós-graduação stricto sensu — Afastamento', 'Processo seletivo', 'Docentes/TAEs', 'Em seleção', 12),
            ('Capacita UFMS 2025 — Capacitação Técnica', 'Presencial/EaD', 'TAEs', 'Em seleção', 80),
            ('Compensação Recesso — Cursos Online', 'EaD', 'Todos', 'Programado', 150),
        ]
        cur.executemany(
            'INSERT INTO acoes_pdp (nome, modalidade, publico_alvo, status, vagas) VALUES (?,?,?,?,?)',
            acoes_iniciais
        )

    # ----- Seed: talentos (apenas os REAIS conhecidos) -----
    if cur.execute('SELECT COUNT(*) FROM talentos').fetchone()[0] == 0:
        talentos_iniciais = [
            ('Edemir Pereira Flores Junior', 'Secretário SEGES', 'SEGES/DIGEC/PROGEP', '',
             'Pós-graduação', 'Gestão do Conhecimento, PDP, Diagnóstico'),
            ('Elizeu Justino dos Santos Júnior', 'Secretário Substituto SEGES', 'SEGES/DIGEC/PROGEP', '',
             'Pós-graduação', 'Capacitação, PDP, Orientação'),
        ]
        cur.executemany(
            'INSERT INTO talentos (nome, cargo, unidade, siape, formacao, competencias) VALUES (?,?,?,?,?,?)',
            talentos_iniciais
        )

    # ----- Seed: diagnóstico inicial -----
    if cur.execute('SELECT COUNT(*) FROM diagnostico').fetchone()[0] == 0:
        diag_iniciais = [
            ('eixo', 'Gestão pública e processos', '32%', 68),
            ('eixo', 'Tecnologia e sistemas', '24%', 51),
            ('eixo', 'Inclusão e diversidade', '18%', 38),
            ('eixo', 'Línguas e internacionalização', '14%', 30),
            ('eixo', 'Saúde e bem-estar', '12%', 25),
            ('pdi', 'Eixo Excelência Acadêmica', '76%', 76),
            ('pdi', 'Eixo Gestão Inovadora', '82%', 82),
            ('pdi', 'Eixo Internacionalização', '58%', 58),
            ('pdi', 'Eixo Inclusão e Sustentabilidade', '91%', 91),
            ('indicador', 'Fluxos operacionais mapeados', '138', 0),
            ('indicador', 'Indicadores de desempenho analisados', '47', 0),
            ('indicador', 'Unidades com LNT realizado', '41 / 47', 0),
            ('indicador', 'Gaps identificados (alta prioridade)', '68', 0),
            ('indicador', 'Unidades sem retorno ao LNT', '6', 0),
        ]
        cur.executemany(
            'INSERT INTO diagnostico (categoria, rotulo, valor, percentual) VALUES (?,?,?,?)',
            diag_iniciais
        )

    db.commit()
    db.close()


# ============================================================
# AUTENTICAÇÃO
# ============================================================

def login_required(f):
    """Decorator que protege rotas administrativas."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar a área administrativa.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# ROTAS PÚBLICAS
# ============================================================

@app.route('/')
def index():
    """Painel público — exibe todos os dados."""
    return render_template('painel.html')


@app.route('/api/dados')
def api_dados():
    """API que devolve todos os dados em JSON para o frontend consumir."""
    db = get_db()

    def rows(query):
        return [dict(r) for r in db.execute(query).fetchall()]

    return jsonify({
        'metricas': rows('SELECT * FROM metricas ORDER BY id'),
        'competencias': rows('SELECT * FROM competencias ORDER BY ordem'),
        'fases_pdp': rows('SELECT * FROM fases_pdp ORDER BY ordem'),
        'acoes_pdp': rows('SELECT * FROM acoes_pdp ORDER BY id'),
        'cursos': rows('SELECT * FROM cursos ORDER BY id'),
        'talentos': rows('SELECT * FROM talentos ORDER BY nome'),
        'solicitacoes': rows('SELECT * FROM solicitacoes ORDER BY criado_em DESC LIMIT 20'),
        'diagnostico': rows('SELECT * FROM diagnostico ORDER BY categoria, id'),
    })


@app.route('/api/solicitacao', methods=['POST'])
def api_nova_solicitacao():
    """Endpoint público: servidor registra uma solicitação."""
    data = request.get_json() or request.form
    servidor = data.get('servidor', '').strip()
    tipo = data.get('tipo', '').strip()
    if not servidor or not tipo:
        return jsonify({'erro': 'Nome do servidor e tipo são obrigatórios.'}), 400

    db = get_db()
    db.execute(
        '''INSERT INTO solicitacoes (servidor, siape, unidade, tipo, descricao, status)
           VALUES (?,?,?,?,?,?)''',
        (servidor, data.get('siape', ''), data.get('unidade', ''),
         tipo, data.get('descricao', ''), 'Pendente')
    )
    db.commit()
    return jsonify({'ok': True, 'mensagem': 'Solicitação registrada com sucesso!'})


# ============================================================
# ROTAS DE LOGIN/LOGOUT
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute(
            'SELECT * FROM usuarios WHERE username = ?', (username,)
        ).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_nome'] = user['nome']
            flash(f'Bem-vindo(a), {user["nome"]}!', 'success')
            return redirect(request.args.get('next') or url_for('admin'))
        flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('index'))


# ============================================================
# ROTAS ADMINISTRATIVAS — CRUD
# ============================================================

@app.route('/admin')
@login_required
def admin():
    db = get_db()
    stats = {
        'metricas': db.execute('SELECT COUNT(*) FROM metricas').fetchone()[0],
        'cursos': db.execute('SELECT COUNT(*) FROM cursos').fetchone()[0],
        'acoes_pdp': db.execute('SELECT COUNT(*) FROM acoes_pdp').fetchone()[0],
        'talentos': db.execute('SELECT COUNT(*) FROM talentos').fetchone()[0],
        'solicitacoes_pendentes': db.execute(
            "SELECT COUNT(*) FROM solicitacoes WHERE status='Pendente'"
        ).fetchone()[0],
    }
    return render_template('admin.html', stats=stats)


# --- CRUD genérico para cada tabela ---
TABELAS = {
    'metricas': {
        'titulo': 'Métricas (Visão Geral)',
        'campos': ['chave', 'rotulo', 'valor', 'subtitulo', 'cor'],
        'rotulos': ['Chave', 'Rótulo', 'Valor', 'Subtítulo', 'Cor (azul, verde, amarelo, roxo)'],
    },
    'competencias': {
        'titulo': 'Competências Institucionais',
        'campos': ['ordem', 'titulo', 'descricao', 'categoria', 'progresso'],
        'rotulos': ['Ordem', 'Título', 'Descrição', 'Categoria', 'Progresso (%)'],
    },
    'fases_pdp': {
        'titulo': 'Fases do PDP',
        'campos': ['ordem', 'descricao', 'status', 'prazo'],
        'rotulos': ['Ordem', 'Descrição', 'Status', 'Prazo'],
    },
    'acoes_pdp': {
        'titulo': 'Ações do PDP',
        'campos': ['nome', 'modalidade', 'publico_alvo', 'status', 'vagas'],
        'rotulos': ['Nome', 'Modalidade', 'Público-alvo', 'Status', 'Vagas'],
    },
    'cursos': {
        'titulo': 'Cursos e Capacitações',
        'campos': ['nome', 'carga_horaria', 'modalidade', 'status', 'inscritos'],
        'rotulos': ['Nome', 'Carga horária', 'Modalidade', 'Status', 'Inscritos'],
    },
    'talentos': {
        'titulo': 'Banco de Talentos',
        'campos': ['nome', 'cargo', 'unidade', 'siape', 'formacao', 'competencias'],
        'rotulos': ['Nome', 'Cargo', 'Unidade', 'SIAPE', 'Formação', 'Competências'],
    },
    'solicitacoes': {
        'titulo': 'Solicitações de Atendimento',
        'campos': ['servidor', 'siape', 'unidade', 'tipo', 'descricao', 'status'],
        'rotulos': ['Servidor', 'SIAPE', 'Unidade', 'Tipo', 'Descrição', 'Status'],
    },
    'diagnostico': {
        'titulo': 'Diagnóstico de Necessidades',
        'campos': ['categoria', 'rotulo', 'valor', 'percentual'],
        'rotulos': ['Categoria (eixo, pdi, indicador)', 'Rótulo', 'Valor', 'Percentual'],
    },
}


@app.route('/admin/trocar-senha', methods=['GET', 'POST'])
@login_required
def admin_trocar_senha():
    """Permite ao administrador trocar a própria senha pelo navegador."""
    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual', '')
        nova_senha = request.form.get('nova_senha', '')
        confirmar = request.form.get('confirmar', '')

        db = get_db()
        user = db.execute(
            'SELECT * FROM usuarios WHERE id = ?', (session['user_id'],)
        ).fetchone()

        if not check_password_hash(user['password_hash'], senha_atual):
            flash('Senha atual incorreta.', 'danger')
        elif len(nova_senha) < 8:
            flash('A nova senha deve ter pelo menos 8 caracteres.', 'danger')
        elif nova_senha != confirmar:
            flash('A confirmação não confere com a nova senha.', 'danger')
        else:
            db.execute(
                'UPDATE usuarios SET password_hash = ? WHERE id = ?',
                (generate_password_hash(nova_senha), session['user_id'])
            )
            db.commit()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('admin'))

    return render_template('trocar_senha.html')


@app.route('/admin/<tabela>')
@login_required
def admin_listar(tabela):
    if tabela not in TABELAS:
        flash('Tabela inválida.', 'danger')
        return redirect(url_for('admin'))
    db = get_db()
    registros = db.execute(f'SELECT * FROM {tabela} ORDER BY id').fetchall()
    return render_template(
        'crud_lista.html',
        tabela=tabela,
        config=TABELAS[tabela],
        registros=registros
    )


@app.route('/admin/<tabela>/novo', methods=['GET', 'POST'])
@login_required
def admin_novo(tabela):
    if tabela not in TABELAS:
        return redirect(url_for('admin'))
    config = TABELAS[tabela]
    if request.method == 'POST':
        valores = [request.form.get(c, '').strip() for c in config['campos']]
        placeholders = ','.join('?' * len(config['campos']))
        colunas = ','.join(config['campos'])
        db = get_db()
        db.execute(f'INSERT INTO {tabela} ({colunas}) VALUES ({placeholders})', valores)
        db.commit()
        flash('Registro criado com sucesso!', 'success')
        return redirect(url_for('admin_listar', tabela=tabela))
    return render_template('crud_form.html', tabela=tabela, config=config, registro=None)


@app.route('/admin/<tabela>/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_editar(tabela, id):
    if tabela not in TABELAS:
        return redirect(url_for('admin'))
    config = TABELAS[tabela]
    db = get_db()
    if request.method == 'POST':
        valores = [request.form.get(c, '').strip() for c in config['campos']]
        set_clause = ','.join(f'{c}=?' for c in config['campos'])
        db.execute(f'UPDATE {tabela} SET {set_clause} WHERE id=?', valores + [id])
        db.commit()
        flash('Registro atualizado!', 'success')
        return redirect(url_for('admin_listar', tabela=tabela))
    registro = db.execute(f'SELECT * FROM {tabela} WHERE id=?', (id,)).fetchone()
    if not registro:
        flash('Registro não encontrado.', 'danger')
        return redirect(url_for('admin_listar', tabela=tabela))
    return render_template('crud_form.html', tabela=tabela, config=config, registro=registro)


@app.route('/admin/<tabela>/excluir/<int:id>', methods=['POST'])
@login_required
def admin_excluir(tabela, id):
    if tabela not in TABELAS:
        return redirect(url_for('admin'))
    db = get_db()
    db.execute(f'DELETE FROM {tabela} WHERE id=?', (id,))
    db.commit()
    flash('Registro excluído.', 'info')
    return redirect(url_for('admin_listar', tabela=tabela))


# ============================================================
# INICIALIZAÇÃO
# ============================================================

@app.cli.command('init-db')
def init_db_command():
    """Comando: flask init-db — recria o banco."""
    init_db()
    print('Banco de dados inicializado com dados iniciais.')


# Inicializa o banco na primeira execução
with app.app_context():
    if not os.path.exists(app.config['DATABASE']):
        init_db()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
