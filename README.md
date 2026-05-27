# Painel SEGES/DIGEC/PROGEP — UFMS

Sistema web de acompanhamento de atividades da Secretaria de Formação para Gestão do Conhecimento (SEGES), conforme Resolução n° 682-CD/2026.

## Funcionalidades

- **Painel público** com 6 abas (Visão Geral, PDP, Cursos, Diagnóstico, Banco de Talentos, Atendimento)
- **Área administrativa** protegida por login para edição de todos os dados
- **API JSON** que alimenta o frontend dinamicamente
- **Formulário público** para servidores registrarem solicitações de atendimento
- **CRUD completo** (criar, editar, excluir) para todas as 8 tabelas do sistema

## Estrutura do projeto

```
seges-backend/
├── app.py                 # Servidor Flask + rotas + lógica do banco
├── requirements.txt       # Dependências Python
├── Procfile               # Comando de inicialização (Render)
├── render.yaml            # Configuração de deploy no Render
├── seges.db               # Banco SQLite (criado automaticamente)
├── static/
│   └── styles.css         # Estilos da aplicação
└── templates/
    ├── base.html          # Layout base
    ├── painel.html        # Painel público
    ├── login.html         # Tela de login
    ├── admin.html         # Dashboard administrativo
    ├── crud_lista.html    # Listagem genérica de registros
    └── crud_form.html     # Formulário genérico de edição
```

## Como rodar localmente

```bash
# 1. Crie um ambiente virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute
python app.py
```

Acesse `http://localhost:5000` no navegador.

## Credenciais iniciais

- **Usuário:** `admin`
- **Senha:** `seges2026`

**Importante:** altere a senha após o primeiro acesso editando o registro do usuário diretamente no banco (ou crie um script de troca de senha).

## Deploy no Render (gratuito)

### Opção 1 — Via Git (recomendado)

1. Crie um repositório no GitHub com este código
2. Acesse [render.com](https://render.com) e faça login
3. Clique em **New → Web Service**
4. Conecte o repositório do GitHub
5. O Render detectará automaticamente o `render.yaml` e fará todo o setup
6. Em poucos minutos seu site estará no ar em `https://seges-painel.onrender.com`

### Opção 2 — Configuração manual no Render

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app`
- **Environment Variables:**
  - `SECRET_KEY`: gere uma string aleatória longa
  - `PYTHON_VERSION`: `3.11.6`

### Importante sobre o SQLite no Render

O plano gratuito do Render usa armazenamento efêmero — **o banco SQLite é resetado a cada novo deploy**. Para produção real, você tem três opções:

1. **Disco persistente** (R$ ~5/mês no Render): plano pago com disco fixo
2. **Migrar para PostgreSQL** (gratuito no Render): troque SQLite por Postgres no `app.py`
3. **Banco externo** (Supabase, Neon — gratuitos): conecte via variável de ambiente

Para começar, o SQLite é perfeito. Quando crescer, migre.

## Como o frontend recebe os dados

O painel público faz uma chamada `GET /api/dados` que retorna JSON com todas as informações. Quando um administrador edita algo no admin, ao recarregar o painel os novos dados aparecem.

## Como adicionar novos campos

1. Edite a tabela no `init_db()` em `app.py`
2. Adicione o campo no dicionário `TABELAS` (campos + rótulos)
3. Atualize o template `painel.html` para exibir o novo campo
4. Apague `seges.db` e rode novamente para recriar o banco

## Como trocar a senha do admin

Por enquanto, via terminal Python:

```python
from app import app, get_db
from werkzeug.security import generate_password_hash

with app.app_context():
    db = get_db()
    db.execute(
        'UPDATE usuarios SET password_hash = ? WHERE username = ?',
        (generate_password_hash('nova_senha_aqui'), 'admin')
    )
    db.commit()
```

## Origem dos dados iniciais

- **Competências (6 itens):** texto literal da Resolução n° 682-CD/2026
- **Contato e equipe:** site oficial da SEGES (`progep.ufms.br/diretorias/digec/seges-2/`)
- **Cursos listados:** notícias reais publicadas no site da SEGES (IsF/Andifes, Capacita UFMS, LideraGOV, etc.)
- **Números (métricas, percentuais, vagas, valores):** ILUSTRATIVOS — devem ser substituídos pelos reais via área administrativa

## Suporte e contato

Sistema desenvolvido com base nas competências e atividades da SEGES/DIGEC/PROGEP/UFMS.
Contato institucional: seges.progep@ufms.br · (67) 3345-7076
