# Echo

Prática de fala em inglês com repetição espaçada (SM-2) e **nível adaptativo estilo ELO**.
A aprendiz lê uma pergunta realista, responde em voz alta, o áudio é transcrito (Whisper) e
avaliado por Claude em três eixos (estrutura/conteúdo, gramática, fluência). As notas alimentam o
agendador do card e o rating de nível, que define a dificuldade das próximas perguntas.

Plano completo: [docs/PLAN.md](docs/PLAN.md). Prompts de IA (texto exato, v1): `backend/apps/ai/prompts/`.

## Stack
Django 5.2 + DRF · PostgreSQL 16 · Celery + Redis · React 19 + Vite + Tailwind + Recharts ·
Anthropic (`claude-opus-5` avalia, `claude-sonnet-5` gera) · OpenAI `whisper-1` · Oracle Cloud + Coolify.

## Rodando localmente

### Opção A — Docker Compose (tudo)
```bash
cp backend/.env.example backend/.env      # opcional: chaves de API
docker compose -f infra/docker-compose.yml up --build
# API: http://localhost:8000  ·  SPA (Vite): http://localhost:5173  ·  Admin: http://localhost:8000/admin/
docker compose -f infra/docker-compose.yml exec backend python manage.py createsuperuser
```
Sem chaves de API, `ECHO_AI_PROVIDER=fake` (default no Compose) usa geradores/avaliadores
determinísticos para testar a UI sem custo.

### Opção B — local (uv + npm)
```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
cd backend && uv sync && cp .env.example .env
uv run python manage.py migrate && uv run python manage.py createsuperuser
uv run python manage.py runserver                 # terminal 1
uv run celery -A config worker -l info            # terminal 2 (precisa de ffmpeg no PATH)
cd ../frontend && npm install && npm run dev      # terminal 3 → http://localhost:5173
```

## Testes e lint
```bash
cd backend && uv run pytest            # SQLite por padrão
ECHO_TEST_USE_POSTGRES=1 DATABASE_URL=postgres://echo:echo@localhost:5432/echo uv run pytest
uv run ruff check . && uv run ruff format --check .
cd ../frontend && npx vitest run && npm run build && npx oxlint src
```

## Parâmetros do produto
Tudo que é ajustável (pesos do composite, K do ELO, bandas CEFR, proporção de sondas, intervalo
máximo, modelos de IA) está em `backend/config/settings/base.py` sob `ECHO_*`.

## Deploy
Ver [infra/coolify/README.md](infra/coolify/README.md).
