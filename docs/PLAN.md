# Echo — plano do MVP: prática de fala em inglês com repetição espaçada e nível adaptativo

> Versão 2 (2026-09-16), após as 24 decisões tomadas no chat. As decisões estão consolidadas na seção 12; os parâmetros ajustáveis estão na seção 12.2 (e em `backend/config/settings/base.py`, prefixo `ECHO_*`).
>
> **Status da implementação (2026-09-16):** fases 0–6 implementadas neste repositório (backend Django com 161 testes em SQLite e PostgreSQL, frontend React com dashboard validado pelo skill `dataviz`, imagem Docker multi-arch, CI). Da fase 7 falta apenas o deploy real no Oracle Cloud + Coolify (guia em `infra/coolify/README.md`). Paleta dos gráficos em `docs/dataviz-palette.md`. Fase 8 (RLS, grupos, exportar/apagar dados) segue no backlog.

## 1. Contexto

**Problema.** A usuária (inglês A2–B1, mudando-se para o Canadá) precisa treinar *recordação ativa* falada: ler uma pergunta realista (entrevista, compras, cotidiano, viagem), responder em voz alta sem preparo e receber feedback consistente que mostre progresso real ao longo de meses. Pronúncia fica fora (outra ferramenta cobre).

**Solução.** Um app web onde cada pergunta gerada por IA vira um *card* fixo com agendamento SM-2 (estilo Anki) individual e um nível CEFR atribuído. A cada dia ela escolhe categorias e quantos cards novos quer; responde por áudio no navegador; o áudio é transcrito (Whisper) e avaliado por Claude em três eixos (estrutura/conteúdo, gramática, fluência aparente). As notas alimentam (a) o agendador do card e (b) um **rating de nível do aluno, estilo ELO**, que por sua vez define a dificuldade das próximas perguntas. Um dashboard mostra o que o Anki não mostra: evolução das notas por eixo e do nível ao longo do tempo.

**Restrições e decisões de base.**
- Isolamento por usuário desde o dia 1 (cada usuário é um tenant); organizações ficaram fora; "grupos de estudo" N:N ficam no backlog para competição futura.
- Stack: Django 5.2 LTS + DRF, React 19 + Vite + Tailwind (shadcn/ui, Recharts), PostgreSQL 16, Celery + Redis, API Anthropic (Opus 5 avalia, Sonnet 5 gera), OpenAI `whisper-1` transcreve.
- Deploy: Oracle Cloud Free Tier (VM ARM Ampere) gerenciado por Coolify; áudios no Oracle Object Storage via API S3.
- Sem gamificação, sem pronúncia, rubric fixo em prompt, usuários criados pelo admin.

---

## 2. Isolamento multi-tenant (tenant = usuário)

### 2.1 Comparação feita (mantida para registro)

| Critério | **Linha (`user_id` em toda tabela)** | **Linha + PostgreSQL RLS** | **Schema por tenant (`django-tenants`)** | **Banco por tenant** |
|---|---|---|---|---|
| Força do isolamento | Média: depende de todo query filtrar | Alta: o banco recusa linhas alheias mesmo se o código esquecer | Alta (lógica) | Muito alta |
| Custo de migração | 1 `migrate` | 1 `migrate` + policies | N× por deploy | N bancos |
| Operação | Baixa | Média (roles, `SET LOCAL`, pooling) | Média-alta (Celery, pgbouncer, testes) | Alta |
| Stats globais / admin | Triviais | Triviais com role admin | Difíceis | Muito difíceis |
| Ecossistema | Nativo; `django-multitenant` está parado desde 2023 → fazer à mão | `django-rls-tenants` 1.3 e `django-rls` 2.0, jovens mas mantidas | `django-tenants` 3.14, maduro e invasivo | Raro |
| Decisão | **Agora** | **Fase 2** | Não | Não |

### 2.2 Regras de implementação (todas viram testes)

1. **`OwnedModel`** abstrato em `core/models.py`: `user = ForeignKey(User, on_delete=CASCADE, editable=False)`. Todo modelo de dados de negócio herda dele. Exceção deliberada: `Category` (pode ser global) — ver 3.2.
2. **Escopo explícito na API**: `OwnedQuerySetMixin` em `accounts/scoping.py` filtra `user=request.user` em todo `get_queryset()`; `perform_create()` injeta `user`; serializers nunca aceitam `user` do cliente.
3. **Manager fail-closed**: `OwnedModel.objects` exige o usuário corrente numa contextvar (preenchida pelo middleware a partir da sessão, ou explicitamente por tasks/comandos via `owner_context(user_id)`) e **levanta exceção** se não houver. Acesso global deliberado (admin, manutenção, stats agregadas futuras) usa `OwnedModel.all_users`. Isso inverte o padrão fail-open que vaza dados quando alguém esquece um filtro.
4. **Lookups por UUID dentro do queryset escopado** → acesso cruzado devolve 404, não 403.
5. **Toda `UniqueConstraint` inclui `user`** (ou é condicional a `owner IS NULL` para categorias globais).
6. **Integridade entre tabelas**: sem FK composta no Django, a camada de serviço valida que FKs entre modelos do usuário apontam para o mesmo `user` (ex.: `Card.category` é global ou pertence ao mesmo usuário), com teste.
7. **Áudios em prefixo por usuário** (`users/<user_id>/attempts/<attempt_id>.<ext>`) servidos por URL assinada de curta duração; nunca públicos.
8. **Workers recebem `user_id` explícito** e abrem `owner_context`.
9. **Testes de isolamento**: dois usuários; para cada endpoint, A não lê/altera/lista nada de B; teste que varre `apps.get_models()` e falha se algum modelo de negócio não herdar `OwnedModel` (lista de exceções explícita: `Category`, `StudyGroup*`); teste que varre as views DRF e falha se alguma não usar o mixin.

**Fase 2 — RLS (aditiva):** policies `USING (user_id = current_setting('app.current_user')::uuid)` com `ENABLE` + `FORCE ROW LEVEL SECURITY`; middleware faz `SET LOCAL` dentro de `ATOMIC_REQUESTS=True`; role de runtime não-superusuário, não-dono, sem `BYPASSRLS`; `django-rls-tenants` como opção para não fazer à mão.

**Backlog — grupos de estudo (competição):** `StudyGroup(id, name, slug, created_by)` e `StudyGroupMembership(user, group, role, joined_at)` N:N (nome evita colisão com `auth.Group`). O que se compartilha num grupo é *agregado e opt-in* (rating, cards respondidos, sequência) — nunca áudio, transcrição ou feedback. Nada disso entra no MVP; o modelo atual não precisa mudar para receber isso.

---

## 3. Modelo de dados

Convenções: UUID como PK; `created_at`/`updated_at` via `TimeStampedModel`; datas de agendamento em `DateField` na timezone da usuária; `JSONField` só para dados sem filtro relacional.

### 3.1 App `accounts`

**User** (custom, login por e-mail)
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| email | EmailField unique | `USERNAME_FIELD` |
| full_name | CharField | |
| timezone | CharField | `America/Sao_Paulo` hoje, `America/Toronto` depois; define o "dia" da sessão |
| feedback_language | Enum(pt-BR, en) default pt-BR | idioma do feedback da IA |
| default_new_cards_per_day | SmallInt default 3 | pré-preenche a tela do dia |
| level_rating | Int default 1150 | rating ELO atual (seção 4.7); admin define o inicial |
| level_rating_initial | Int | para o gráfico e para reset |
| counted_attempts | Int default 0 | nº de tentativas que moveram o rating (define o fator K) |
| is_active, is_staff | Boolean | `is_staff` = admin global (Django admin) |

Parâmetros globais do sistema (pesos do composite, `max_interval_days`, fatores K, bandas CEFR, modelos de IA) ficam em `settings.py` (`ECHO_*`), não em tabela, no MVP.

### 3.2 App `cards`

**Category** (não herda `OwnedModel`)
| Campo | Tipo | Notas |
|---|---|---|
| owner | FK User null | **NULL = global** (mantida por você no admin); preenchido = pessoal do usuário |
| slug, name, description, generation_hint | | como antes; `description` e `generation_hint` vão para o prompt de geração |
| is_active, sort_order | | |

Constraints: `UniqueConstraint(slug) WHERE owner IS NULL` e `UniqueConstraint(owner, slug)`. Queryset visível ao usuário: `owner IS NULL OR owner = user`. Categorias-semente globais: `everyday-situations`, `shopping`, `job-interview`, `travel` (textos em 9.4). Criar categoria pessoal = `POST /categories/`; global = admin.

**Card** (herda `OwnedModel`)
| Campo | Tipo | Notas |
|---|---|---|
| category | FK Category PROTECT | |
| question_text | TextField | exatamente como gerada; **imutável** |
| scenario | TextField null | 1 frase de contexto opcional |
| key_points | JSONField list[str] | 2–4 pontos que uma resposta completa cobre; usados pelo avaliador; exibidos só após a resposta |
| cefr_level | Enum(A1, A2, B1, B2, C1, C2) | nível pedido ao gerador |
| difficulty_rating | Int | rating numérico da pergunta (banda + modificador; 4.7) |
| probe | Enum(none, above, below) | pergunta-sonda acima/abaixo do nível do aluno na geração |
| status | Enum(active, suspended, archived) | |
| source | Enum(generated, manual) | |
| created_in_session | FK DailySession SET_NULL | |
| generation_model, prompt_version | CharField | |

Índices: `(user, status)`, `(user, category)`, `(user, cefr_level)`.

### 3.3 App `scheduling`

**SchedulerState** (OneToOne Card; herda `OwnedModel`)
| Campo | Notas |
|---|---|
| maturity Enum(new, learning, mature) | derivado do intervalo, persistido para filtro |
| ease_factor Decimal(4,2) default 2.50 | mín. 1.30 |
| interval_days, repetitions, lapses, total_reviews | |
| due_date Date null | null enquanto `new` |
| last_reviewed_on Date null; last_quality SmallInt null | |

Índices: `(user, due_date)`, `(user, maturity)`.

**ReviewLog** (herda `OwnedModel`; uma linha por aplicação do agendador)
| Campo | Notas |
|---|---|
| card FK; attempt OneToOne | |
| reviewed_on Date | data da sessão |
| quality 0–5; composite_score Decimal(3,2) | |
| ease/interval/due/maturity `_before` e `_after` | |
| scheduler_version | `sm2-v1` |

### 3.4 App `leveling` (novo)

**LevelLog** (herda `OwnedModel`; uma linha por tentativa que moveu o rating)
| Campo | Notas |
|---|---|
| attempt OneToOne; card FK | |
| logged_on Date | |
| rating_before, rating_after, delta | Int |
| question_rating | Int (cópia de `Card.difficulty_rating`) |
| expected, actual | Decimal(4,3) | E e A da fórmula (4.7) |
| k_factor | SmallInt |
| level_version | `elo-v1` |

`leveling/elo.py`: funções puras (`expected_score`, `actual_from_composite`, `k_for`, `apply_result`, `band_for_rating`, `rating_for_level`), testadas por tabela.

### 3.5 App `practice`

**DailySession** (herda `OwnedModel`): `session_date` (`UNIQUE(user, session_date)`), `new_cards_target`, `categories` M2M, `status Enum(generating, ready, in_progress, completed, failed)`, `generation_error`, `rating_at_start` (snapshot do rating usado na geração), `completed_at`.

**SessionNewCard**: `session`, `card`, `position`, `origin Enum(generated, carried_over)`; `UNIQUE(session, card)`. A fila de vencidos não é materializada (calculada ao vivo).

**Attempt** (herda `OwnedModel`)
| Campo | Notas |
|---|---|
| card FK; session FK SET_NULL | |
| attempt_number | `UNIQUE(card, attempt_number)` |
| counts_for_scheduling Boolean | 1ª tentativa concluída do card no dia; também governa o rating |
| audio_file, audio_mime, audio_size_bytes | prefixo por usuário |
| audio_duration_seconds Decimal(6,2) | **medida por ffprobe no worker** (blobs de MediaRecorder não trazem duração confiável); fallback: `verbose_json.duration` / timer do cliente |
| status Enum(uploaded, probing, transcribing, evaluating, scheduling, completed, failed) | |
| failure_stage, error_message | retry idempotente |
| transcript_text, transcript_segments JSON, word_count, words_per_minute, transcription_model | |
| completed_at | |

**Evaluation** (OneToOne Attempt; herda `OwnedModel`)
| Campo | Notas |
|---|---|
| structure_score, grammar_score, fluency_score SmallInt 1–5 | |
| structure_feedback, grammar_feedback, fluency_feedback | 1–3 frases, idioma da usuária |
| grammar_issues JSON list[{quote, correction, type, explanation}] | `type` enum fechado (9.2) |
| fluency_markers JSON {fillers, false_starts, repetitions} | |
| composite_score Decimal(3,2); sm2_quality SmallInt | |
| improved_answer TextField null | **gerado sob demanda** (botão); null até ser pedido |
| improved_answer_model, improved_answer_generated_at | |
| model, prompt_version, raw_response JSON, input_tokens, output_tokens, latency_ms | |

### 3.6 App `ai`

**AIRequestLog** (herda `OwnedModel`): `kind Enum(generate_questions, transcribe, evaluate, improve_answer)`, `provider`, `model`, `input_tokens`, `output_tokens`, `audio_seconds`, `estimated_cost_usd`, `latency_ms`, `status`, `error`, `related_object_type/id`.

### 3.7 Relações

```
User 1──* Category(owner)        Category(owner=NULL) = global
User 1──* Card *──1 Category
Card 1──1 SchedulerState
Card 1──* Attempt 1──1 Evaluation
Attempt 1──1 ReviewLog   (só quando counts_for_scheduling)
Attempt 1──1 LevelLog    (idem)
User 1──* DailySession *──* Category
DailySession 1──* SessionNewCard *──1 Card
DailySession 1──* Attempt
```

---

## 4. Regras de negócio

### 4.1 Criar a sessão do dia
1. `session_date = localdate(now, user.timezone)`; se já existe → 409 com a sessão (UI oferece "continuar").
2. *Carried-over*: cards `maturity=new`, `status=active`, sem tentativa concluída → `SessionNewCard(origin=carried_over)` nas primeiras posições, **contam para N**.
3. `to_generate = max(0, N − carried_over)`; se > 0, enfileira `generate_session_cards(session_id, user_id)`; status `generating`; UI faz polling até `ready` (5–15 s).
4. Geração: **uma chamada** (Sonnet 5) com os *slots* já definidos pelo backend — categoria e nível CEFR por slot (4.7.3) — e até 80 perguntas recentes do usuário nas mesmas categorias para evitar repetição. Cada pergunta vira `Card` (+ `cefr_level`, `difficulty_rating`, `probe`) + `SchedulerState(new)` + `SessionNewCard(generated)`.
5. Falha → `failed` + `generation_error`; endpoint de retry.

### 4.2 Fila da sessão
1. **Novos**: `SessionNewCard` por `position`, sem tentativa concluída hoje.
2. **Vencidos**: `due_date <= session_date`, `maturity != new`, card ativo, sem tentativa concluída hoje; ordem `due_date` asc → `ease_factor` asc → `created_at`. Não filtrados por categoria nem por nível.
Sessão vira `completed` quando a fila esvazia.

### 4.3 Novos não respondidos → voltam no dia seguinte como `carried_over`, contam para N, mantêm nível e categoria originais.

### 4.4 Tentativas repetidas no mesmo dia → permitidas; todas no histórico e nas estatísticas de notas; só a **primeira concluída** tem `counts_for_scheduling=true` e gera `ReviewLog` + `LevelLog`.

### 4.5 Sem fala (< 5 palavras) → notas 1, aviso "não detectamos fala suficiente", `counts_for_scheduling=false` (não move agendador nem rating), card continua na fila, UI convida a regravar.

### 4.6 Pipeline de uma tentativa (Celery)
```
POST /attempts (multipart) → Attempt(uploaded) + upload S3 → process_attempt(attempt_id, user_id)
  0. probing      → ffprobe: duração real, container válido (rejeita vazio/corrompido); valida 3 s ≤ dur ≤ 300 s
  1. transcribing → whisper-1 (language=en, verbose_json, temperature=0, prompt 9.5) → texto, segmentos, word_count, wpm
  2. evaluating   → claude-opus-5, messages.parse() com schema 9.2 → Evaluation (sem improved_answer)
  3. scheduling   → se counts_for_scheduling: SM-2 (4.8) + ELO (4.7) na mesma transação (SELECT … FOR UPDATE em SchedulerState e User)
  4. completed | failed(failure_stage)  — retry reaproveita etapas concluídas
```
8–20 s no total; front faz polling em `GET /attempts/{id}` a cada 2 s.

**Versão melhorada sob demanda:** `POST /attempts/{id}/improved-answer/` chama Sonnet 5 de forma síncrona (3–6 s, timeout 30 s) com o prompt 9.3, grava em `Evaluation.improved_answer` e devolve; chamadas seguintes devolvem o valor guardado sem nova geração.

### 4.7 Nível adaptativo (ELO)

**4.7.1 Escala e bandas CEFR**
| Rating | Banda | Centro (rating de pergunta "típica") |
|---|---|---|
| < 1000 | A1 | 900 |
| 1000–1199 | A2 | 1100 |
| 1200–1399 | B1 | 1300 |
| 1400–1599 | B2 | 1500 |
| 1600–1799 | C1 | 1700 |
| ≥ 1800 | C2 | 1900 |

Rating inicial definido pelo admin ao criar o usuário; default **1150** (A2 alto, coerente com "A2–B1"). Limites: 600–2200.

**4.7.2 Rating da pergunta.** `difficulty_rating = centro da banda pedida + modificador` devolvido pelo gerador: `easier −60`, `typical 0`, `harder +60`. Fica fixo durante a vida do card (o rating da própria pergunta ser ajustado por resultados de muitos alunos — estilo Glicko — é backlog para quando houver grupos).

**4.7.3 Política de sondas na geração.** Banda-base = banda do `level_rating` atual. Dos `to_generate` slots, **20 % são sondas** (mínimo 1 quando `to_generate ≥ 3`), alternando `above` (+1 banda) e `below` (−1 banda), começando por `above`. Os demais ficam na banda-base. A distribuição por categoria é feita antes; as sondas são espalhadas entre as categorias. Cards `carried_over` e vencidos não são recalculados.

**4.7.4 Atualização do rating** (só em tentativas com `counts_for_scheduling=true`):
- `E = 1 / (1 + 10^((Q − S) / 400))` — resultado esperado, com `S` = rating do aluno, `Q` = rating da pergunta.
- `A = (composite − 1) / 4` ∈ [0, 1] — resultado real. Composite 3 ("está no nível da pergunta", ver régua em 9.2) ⇒ `A = 0,5`, que é exatamente o esperado quando `S = Q`.
- `ΔS = round(K × (A − E))`; `K = 40` nas primeiras 20 tentativas contadas (provisório), `24` até 100, `16` depois.

Exemplos com `S = 1150`, `K = 40`:
| Pergunta | Q | Resultado (composite) | E | A | ΔS | Leitura |
|---|---|---|---|---|---|---|
| B2 (muito acima) | 1500 | 4,2 | 0,12 | 0,80 | **+27** | acertou algo muito acima → grande recompensa |
| B1 (sonda acima) | 1300 | 4,2 | 0,30 | 0,80 | +20 | |
| B1 (sonda acima) | 1300 | 2,0 | 0,30 | 0,25 | −2 | errou algo acima → pouco punido |
| A2 (nível) | 1100 | 3,0 | 0,57 | 0,50 | −3 | no nível, resultado neutro |
| A1 (muito abaixo) | 900 | 4,6 | 0,81 | 0,90 | +4 | acertou algo fácil → pouco recompensado |
| A1 (muito abaixo) | 900 | 1,8 | 0,81 | 0,20 | **−24** | errou algo fácil → grande punição |

Cards antigos revistos meses depois continuam movendo o rating; como `E` sobe conforme o aluno evolui, o ganho por repetir perguntas fáceis decai naturalmente.

**4.7.5 Independência do SM-2.** O rating define *quais perguntas nascem*; o SM-2 define *quando cada card volta*. Nenhum ajusta o outro.

### 4.8 Agendador SM-2 por card

**Composite** = `0,40·estrutura + 0,35·gramática + 0,25·fluência` ∈ [1, 5]. **Piso:** `structure_score ≤ 2` ⇒ `quality ≤ 2` (falha).

| composite | quality |
|---|---|
| ≥ 4,6 | 5 |
| 3,8 – 4,59 | 4 |
| 3,0 – 3,79 | 3 |
| 2,2 – 2,99 | 2 |
| 1,4 – 2,19 | 1 |
| < 1,4 | 0 |

- `EF' = EF + (0,1 − (5 − q)(0,08 + (5 − q)·0,02))`, mín. 1,30, calculado sempre.
- `q < 3`: `repetitions = 0`, `interval = 1`, `lapses += 1` se não era `new`.
- `q ≥ 3`: `repetitions 0 → 1 dia`, `1 → 6 dias`, senão `round(interval × EF')`; `repetitions += 1`.
- `interval = min(interval, 180)`; `due_date = session_date + interval`.
- `maturity`: `learning` se `interval < 21`, `mature` se `≥ 21`; falha em `mature` volta a `learning`.

**Carga projetada:** card que passa sempre → ~1, 6, 15, 37, 93, 180 dias (~6 revisões/ano). Com 5 novos/dia o regime estacionário fica em 25–35 revisões/dia (40–60 min de fala); daí o default N = 3 e o painel "≈ X cards hoje (N novos + Y revisões)" antes de confirmar.

Backlog do agendador: fuzz de intervalo, learning steps intradiários, FSRS.

---

## 5. Estrutura de pastas

```
echo/
├── backend/
│   ├── manage.py  pyproject.toml            # uv; ruff; pytest-django
│   ├── config/
│   │   ├── settings/{base,dev,prod,test}.py # ECHO_* (pesos, K, bandas, modelos, limites)
│   │   └── urls.py  asgi.py  wsgi.py  celery.py
│   ├── apps/
│   │   ├── core/          # OwnedModel, TimeStampedModel, owner_context, storage paths, pagination, exceptions
│   │   ├── accounts/      # User, auth (sessão), /me, OwnedQuerySetMixin, middleware de contexto
│   │   ├── cards/         # Category (global/pessoal), Card, endpoints de categorias/cards/histórico
│   │   ├── scheduling/    # SchedulerState, ReviewLog, sm2.py (puro), services.apply_review()
│   │   ├── leveling/      # LevelLog, elo.py (puro), probes.py (distribuição de slots), services.apply_result()
│   │   ├── practice/      # DailySession, SessionNewCard, Attempt, Evaluation, queue.py, tasks.py, improved_answer service
│   │   ├── ai/            # clients (anthropic.py, transcription.py, ffprobe.py), prompts/ (generation_v1.md,
│   │   │                  #   evaluation_v1.md, improved_answer_v1.md, whisper_prompt.txt), schemas.py (Pydantic),
│   │   │                  #   AIRequestLog, pricing.py
│   │   └── stats/         # queries.py, serializers, views do dashboard
│   └── tests/             # isolation/, scheduling/, leveling/, practice/, ai/ (respostas gravadas), stats/
├── frontend/
│   ├── package.json  vite.config.ts  tailwind.config.ts  tsconfig.json
│   └── src/
│       ├── app/           # router, providers (QueryClient, Auth), shell
│       ├── api/           # client fetch (CSRF) + hooks TanStack Query por recurso; tipos gerados do OpenAPI
│       ├── features/
│       │   ├── auth/            # login
│       │   ├── day-setup/       # categorias + N, carga projetada, "continuar"
│       │   ├── practice/        # SessionRunner, CardPrompt (nível/sonda badge), Recorder (useAudioRecorder),
│       │   │                    # ProcessingSteps, EvaluationPanel, GrammarIssues, ImprovedAnswerButton,
│       │   │                    # LevelDelta, AttemptHistory
│       │   ├── cards/           # lista/filtro, detalhe com histórico, suspender
│       │   ├── dashboard/       # StatsPage + charts (ScoreTrend, LevelTrend, Activity, Forecast, Collection,
│       │   │                    # GrammarErrors, CategoryTable, Heatmap)
│       │   └── settings/        # categorias pessoais, preferências
│       ├── components/ui/       # shadcn/ui + AudioPlayer, ScorePill, MaturityBadge, LevelBadge
│       ├── lib/                 # datas/tz, cores por eixo e por maturidade, formatação
│       └── types/
├── infra/
│   ├── docker-compose.yml           # dev: postgres, redis, backend, worker, frontend
│   ├── Dockerfile.backend           # multi-arch (linux/arm64 + amd64); ffmpeg no worker
│   └── coolify/                     # notas de configuração dos serviços no Coolify
├── docs/PLAN.md  docs/prompts/
└── README.md
```

---

## 6. Design da API (`/api/v1/`)

Autenticação por sessão (cookie httpOnly + CSRF); tudo exige login exceto `login`. Usuário sempre implícito. Paginação padrão. Erros `{ "detail", "code" }`. IDs UUID.

### 6.1 Auth e perfil
| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/login/` · `/auth/logout/` | sessão Django |
| GET | `/auth/csrf/` | obtém cookie CSRF para o SPA |
| GET | `/me/` | perfil + `level: { rating, band, provisional, counted_attempts }` |
| PATCH | `/me/` | `timezone`, `feedback_language`, `default_new_cards_per_day` |

### 6.2 Categorias
| Método | Rota | Descrição |
|---|---|---|
| GET | `/categories/?active=true` | globais + pessoais, com `scope: "global"\|"personal"` e contagem de cards do usuário |
| POST | `/categories/` | cria **pessoal** (`slug, name, description, generation_hint`) |
| PATCH | `/categories/{id}/` | só pessoais; globais são 403 |

### 6.3 Sessão do dia
| Método | Rota | Descrição |
|---|---|---|
| GET | `/sessions/today/` | sessão da data local ou 404 `no_session_today` |
| POST | `/sessions/` | `{ category_ids, new_cards_target }` → 201 (`generating` ou `ready`); 409 se já existe. Inclui `projected: { carried_over, to_generate, due_today, probes }` |
| GET | `/sessions/{id}/` | sessão + `{ new_total, new_done, due_total, due_done, status }` |
| GET | `/sessions/{id}/queue/` | fila ordenada; `?limit=1` = próximo |
| POST | `/sessions/{id}/retry-generation/` | |
| POST | `/sessions/{id}/complete/` | opcional |
| GET | `/sessions/?from=&to=` | histórico |

Item da fila:
```json
{ "kind": "new", "position": 3, "origin": "generated",
  "card": { "id": "…", "question_text": "…", "scenario": "…",
            "category": { "id": "…", "slug": "job-interview", "name": "Job interview", "scope": "global" },
            "cefr_level": "B1", "probe": "above", "maturity": "new", "attempt_count": 0 } }
```

### 6.4 Cards
| Método | Rota | Descrição |
|---|---|---|
| GET | `/cards/?category=&maturity=&level=&status=&q=` | coleção |
| GET | `/cards/{id}/` | card + `scheduler` + `attempt_count` + `last_scores` |
| GET | `/cards/{id}/history/` | todas as tentativas (áudio assinado, transcrição, avaliação, `review`, `level_change`), mais recente primeiro |
| POST | `/cards/{id}/suspend/` · `/unsuspend/` | |

### 6.5 Tentativas
| Método | Rota | Descrição |
|---|---|---|
| POST | `/attempts/` | multipart `card_id, session_id?, audio, duration_seconds?, mime_type`; ≤ 25 MB; → **202** `{ id, status }` |
| GET | `/attempts/{id}/` | status + transcrição + `evaluation` + `review` + `level_change` |
| POST | `/attempts/{id}/improved-answer/` | gera (ou devolve a já gerada) a versão melhorada; síncrono |
| POST | `/attempts/{id}/retry/` | reprocessa a partir de `failure_stage` |
| GET | `/attempts/{id}/audio/` | redireciona para URL assinada |

`GET /attempts/{id}/` concluída:
```json
{ "id": "…", "status": "completed", "card_id": "…", "attempt_number": 3, "counts_for_scheduling": true,
  "transcript_text": "…", "audio_duration_seconds": 61.0, "word_count": 98, "words_per_minute": 96,
  "evaluation": { "structure": { "score": 4, "feedback": "…" },
                  "grammar":   { "score": 3, "feedback": "…", "issues": [ … ] },
                  "fluency":   { "score": 3, "feedback": "…", "markers": { "fillers": 4, "false_starts": 1, "repetitions": 2 } },
                  "composite_score": "3.40", "key_points": ["…"], "improved_answer": null },
  "review": { "quality": 3, "interval_before": 1, "interval_after": 6, "due_after": "2026-09-22", "maturity_after": "learning" },
  "level_change": { "rating_before": 1150, "rating_after": 1170, "delta": 20, "expected": 0.297, "actual": 0.80,
                    "question_rating": 1300, "band_before": "A2", "band_after": "A2" } }
```

### 6.6 Estatísticas
Todos aceitam `?from=&to=` (default 30 dias) e `&category=`; agregação na tz do usuário.

| Rota | Retorna |
|---|---|
| `GET /stats/overview/` | hoje `{ answered, new_answered, due_answered, target }`; vencendo `{ today, next_7_days }`; coleção `{ total, new, learning, mature, suspended }`; notas `{ period, previous_period }`; **nível** `{ rating, band, delta_period, provisional }` |
| `GET /stats/scores/?bucket=day\|week` | `[{ bucket_start, structure_avg, grammar_avg, fluency_avg, composite_avg, attempts }]` |
| `GET /stats/level/` | `[{ date, rating_after }]` (último do dia) + `bands: [{ label, min, max }]` + `probes: { above: {answered, avg_actual}, below: {…} }` |
| `GET /stats/activity/?bucket=` | `[{ bucket_start, new, learning, mature, total, speaking_seconds }]` |
| `GET /stats/forecast/?days=30` | `[{ date, due }]` + `{ overdue, total }` |
| `GET /stats/collection/` | `{ by_maturity, by_category: [...], by_level: [{ level, count }] }` |
| `GET /stats/grammar-issues/` | `[{ type, count, examples[≤3] }]` + comparação com período anterior |
| `GET /stats/categories/` | `[{ category, cards, attempts, structure_avg, grammar_avg, fluency_avg, trend }]` |
| `GET /stats/heatmap/?year=` | `[{ date, count }]` |

---

## 7. Fluxo de telas

1. **Login.**
2. **Início do dia** (`/today`): chips de categorias (globais e pessoais), N, painel "≈ X cards hoje: N novos (dos quais k sondas) + Y revisões (Z atrasadas)", "Começar" → estado `generating` → sessão. Se já há sessão: resumo + "Continuar".
3. **Sessão** (`/session/:id`): progresso "3 de 17 · Novos 2/5 · Revisões 1/12"; badges de categoria, maturidade e **nível (B1 · sonda ↑)**; `scenario`; pergunta; **gravador** (um botão, timer, limite visual 5 min, pré-escuta, "Regravar", "Enviar"); etapas de processamento; **painel de avaliação** (3 eixos com cor fixa, notas, feedback); erros `quote → correction` com tipo; `key_points`; **botão "Ver sugestão de resposta melhorada"** (chama o endpoint, mostra spinner, exibe); "Próxima revisão em 6 dias"; **variação de nível** ("+20 · 1.170 · A2"); histórico das tentativas anteriores desta pergunta (acordeão com player, transcrição, notas); "Tentar de novo" / "Próximo".
4. **Cards** (`/cards`): filtros por categoria, maturidade, nível; detalhe = histórico.
5. **Estatísticas** (`/stats`): seção 10.
6. **Configurações**: categorias pessoais, preferências.

---

## 8. Integrações de IA

**Anthropic.**
| Uso | Modelo | Effort | Saída |
|---|---|---|---|
| Avaliação | `claude-opus-5` | `medium` | `messages.parse()` com schema Pydantic (9.2) |
| Geração de perguntas | `claude-sonnet-5` | `medium` | `messages.parse()` (9.1) |
| Versão melhorada (sob demanda) | `claude-sonnet-5` | `low` | `messages.parse()` (9.3) |
Thinking adaptativo (default), `cache_control` no system prompt (verificar `cache_read_input_tokens`), tratar `stop_reason == "refusal"`, retries com backoff em `RateLimitError`/5xx, sem retry em 4xx. Sem `temperature` (removida nos modelos atuais).

**OpenAI transcrição.** `whisper-1`: `language="en"`, `response_format="verbose_json"`, `temperature=0`, `prompt` (9.5). Modelo em setting; A/B contra `gpt-transcribe` ($0,0045/min, só json, aceita `prompt`/`keywords`) nas primeiras ~20 gravações reais. Duração vem do ffprobe, então a troca não afeta o WPM.

**Custo estimado (30 respostas/dia):** Whisper ~$8/mês; avaliação Opus 5 ~$27–45/mês; geração Sonnet 5 < $1/mês; versão melhorada Sonnet 5 ~$0,005 por clique. Total ~$35–55/mês.

---

## 9. Prompts (texto exato, v1)

Prompts em inglês; feedback no idioma `{feedback_language}` (default "Brazilian Portuguese"). Placeholders `{}` preenchidos pelo backend.

### 9.1 Geração de perguntas — `generation_v1.md` (Sonnet 5)

**System:**
```
You are a question writer for an English speaking-practice app. The learner is a Brazilian Portuguese speaker preparing to move to Canada and find a job there. The learner will answer each question out loud, in English, in about 30 seconds to 3 minutes, without preparation, and will later be evaluated on whether the answer addresses the question, on grammar, and on fluency. Pronunciation is not evaluated.

You will receive a list of slots. Each slot specifies a category and a target CEFR level. Write exactly one question per slot, at the requested level.

## What each level means for a QUESTION
- A1: very simple, concrete, about the learner's immediate life; present tense; answerable with a few short sentences. "What do you usually have for breakfast?"
- A2: familiar everyday topics; a short description or a simple past narrative; one clear idea. "Tell me about the last time you went to a supermarket. What did you buy?"
- B1: personal experiences, opinions with reasons, plans, simple comparisons; classic interview questions. "Why do you want to work in customer service?" / "Tell me about a time you helped a colleague."
- B2: hypothetical or abstract situations, justifying trade-offs, persuading, handling conflict; behavioural interview questions with two parts. "Describe a time you disagreed with a manager. How did you handle it, and what would you do differently?"
- C1: nuanced, evaluative, multi-part questions requiring structured argument. "How do you think remote work has changed what employers expect from new hires, and how would you position yourself for that?"
- C2: like C1 with subtle framing, irony, or the need to weigh several perspectives.

## Rules for every question
- Sound like something a real person would actually say in Canada — an interviewer, a shop assistant, a neighbour, a border officer, a colleague, a landlord. Natural spoken English.
- Answerable from the learner's own life, experience and opinions. Never require specialised knowledge, invented facts, or a single "right answer".
- Open-ended: no yes/no questions, no one-word answers. Prefer questions that call for a short story, an explanation with a reason, a comparison, or a description.
- Vocabulary and structure appropriate to the slot's level. One idea per question below B2. Avoid idioms in the question itself.
- Self-contained: everything needed to understand the situation is in the scenario or the question.
- Diverse across the batch: vary situation, the tense the answer will need (past, present habit, future plan, hypothetical), and the speech act (describe, explain, compare, persuade, narrate).
- Do not repeat or closely paraphrase any question in the "already asked" list.

## For each question return
- "slot": the slot number you are answering.
- "category": the slot's category slug.
- "level": the slot's requested CEFR level (do not change it).
- "difficulty_within_level": "easier", "typical" or "harder" — how demanding this question is compared with a typical question of that level.
- "scenario": one sentence (max 25 words) setting the situation when it helps; null when the question needs no framing.
- "question": the question itself, max 30 words, exactly as the speaker would say it.
- "key_points": 2–4 short content-level points a complete, specific answer would normally cover (e.g. "describes one concrete situation", "gives a reason"). Never grammar-level. Used later by an evaluator; not shown to the learner before answering.

Respond only with JSON matching the provided schema.
```

**User:**
```
Slots:
1. category: job-interview — level: B1
2. category: shopping — level: B1
3. category: travel — level: B2 (probe: one level above the learner)
4. category: everyday-situations — level: B1
5. category: job-interview — level: A2 (probe: one level below the learner)

Categories:
- job-interview: Job interview — {description} Guidance: {generation_hint}
- …

Already asked to this learner (do not repeat or paraphrase):
[job-interview] Can you tell me about yourself?
…
(or "(none yet)")
```

**Schema de saída:**
```json
{ "questions": [ { "slot": 1, "category": "job-interview", "level": "B1", "difficulty_within_level": "typical",
                   "scenario": "You are in a job interview for a customer service position at a bank in Toronto.",
                   "question": "Can you tell me about a time you had to deal with a difficult customer?",
                   "key_points": ["describes one specific situation", "explains what they did", "says how it ended or what they learned"] } ] }
```
Validação pós-resposta: um item por slot; `category`/`level` iguais aos pedidos (o backend prevalece); dedup por normalização contra perguntas existentes; `difficulty_rating = centro(level) + {easier: −60, typical: 0, harder: +60}`.

### 9.2 Avaliação — `evaluation_v1.md` (Opus 5)

**System:**
```
You are an experienced ESL teacher evaluating one spoken answer in an English speaking-practice app. The learner is a Brazilian Portuguese speaker preparing for daily life and job interviews in Canada. The learner answered out loud; the answer was transcribed automatically by a speech-to-text system, and you are evaluating that transcript.

The question was written for CEFR level {question_level}. Score each dimension against what a typical {question_level} learner produces when answering spontaneously: 3 means "this is what a {question_level} learner normally does", 5 means clearly above that level, 1 means clearly below it. Do not compare with a native speaker. Be consistent: answers of the same quality must receive the same score every time. Score each dimension independently: a fluent answer that misses the question still gets a low structure score; an on-topic answer full of errors still gets a low grammar score.

## Dimension 1 — Structure & content
Did the answer actually answer the question? Is it specific?
5 — Fully answers the question; clearly organised (opening, development, close); specific details or a concrete example; appropriate length.
4 — Answers the question with some specific detail; minor gaps in organisation, or slightly too short or too long.
3 — Answers the question but stays generic, or covers only part of it, or is noticeably disorganised.
2 — Only loosely related to the question, or extremely short (one or two vague sentences), or mostly off-topic.
1 — Does not answer the question, or there is nothing evaluable.

## Dimension 2 — Grammar & vocabulary
Accuracy of grammar and word choice, weighted by how much errors affect understanding, relative to {question_level}.
5 — No errors, or only slips any fluent speaker could make; range of structures above the level.
4 — A few minor errors (an article, a preposition, one tense slip) that never affect meaning.
3 — Several errors, including recurring ones (verb tense, subject–verb agreement, missing articles), but the meaning is always recoverable — typical of the level.
2 — Frequent errors; some sentences are hard to understand; very limited range of structures for the level.
1 — Errors make most of the answer hard to understand, or there is too little language to evaluate.
Ignore punctuation, capitalisation and anything that is clearly a transcription artefact (a misheard word that makes no sense in context) rather than the learner's error. Ignore pronunciation entirely.

## Dimension 3 — Apparent fluency (from the transcript only)
Signs of hesitation and disorganisation visible in the text: filler words (um, uh, like, you know, so), false starts, word-for-word repetitions, self-corrections, abandoned sentences, very short fragments, long chains joined only by "and".
5 — Reads as continuous, connected speech; few or no fillers or restarts; linking words used naturally.
4 — Occasional filler or restart; ideas flow.
3 — Noticeable hesitation markers or repetitions, but the thread is easy to follow — typical of the level.
2 — Frequent fillers, restarts and fragments; the thread is hard to follow.
1 — Mostly fragments and fillers, or too little speech to judge.
The transcription system may have removed some fillers, so absence of fillers alone does not prove fluency. Use the speaking rate given with the transcript only as a weak secondary signal (below ~70 words per minute suggests heavy hesitation; 100–150 is typical relaxed conversation).

## Feedback rules
- Write all feedback text in {feedback_language}. Quote the learner's English exactly as it appears in the transcript when giving examples.
- Each dimension's feedback: 1–3 short sentences, concrete, focused on the single most useful thing to improve next time. When something worked, say that first.
- "issues" (grammar): the most important errors, at most 5, each with the exact quote, a corrected version, one error type from the allowed list, and a one-sentence explanation in {feedback_language}. Prioritise recurring errors and errors that change meaning. Never list transcription artefacts.
- "markers" (fluency): your best count of filler words, false starts/self-corrections, and word-for-word repetitions in the transcript.
- Do not mention this rubric, the numeric criteria, the CEFR level or the scoring formula in the feedback.
- If the transcript is empty or has fewer than 5 words, score every dimension 1, set each feedback to one sentence saying there was not enough speech to evaluate, and leave "issues" empty.

Respond only with JSON matching the provided schema.
```

**User:**
```
Category: {category_name}
Question level: {question_level}
Scenario: {scenario or "(none)"}
Question: {question_text}
What a complete answer usually covers:
- {key_point}
- …

Learner's answer — automatic transcript ({duration_seconds} s, {word_count} words, {words_per_minute} words per minute):
"""
{transcript_text}
"""
```

**Schema de saída:**
```json
{ "structure": { "score": 4, "feedback": "…" },
  "grammar":   { "score": 3, "feedback": "…",
                 "issues": [ { "quote": "I have work there for two years", "correction": "I have worked there for two years",
                               "type": "verb_tense", "explanation": "…" } ] },
  "fluency":   { "score": 3, "feedback": "…", "markers": { "fillers": 4, "false_starts": 1, "repetitions": 2 } } }
```
`type` ∈ `verb_tense, subject_verb_agreement, article, preposition, word_order, plural, pronoun, word_choice, missing_word, extra_word, other`.

### 9.3 Versão melhorada sob demanda — `improved_answer_v1.md` (Sonnet 5)

**System:**
```
You are an experienced ESL teacher. Rewrite a learner's spoken answer so it becomes a model of what the learner could have said. The learner is a Brazilian Portuguese speaker; the question was written for CEFR level {question_level}.

Rules:
- Keep the learner's ideas, facts, opinions and approximate length. Do not add content the learner did not say. If the answer did not address the question, stay faithful to what was said anyway.
- Write natural spoken English one step above {question_level}: fix grammar and word choice, remove fillers, false starts and repetitions, add linking words, organise into a clear opening, development and close.
- Then list 2–4 short notes in {feedback_language} explaining the most useful changes you made, quoting the learner's original words.

Respond only with JSON matching the provided schema.
```

**User:**
```
Question: {question_text}
Scenario: {scenario or "(none)"}
Learner's transcript:
"""
{transcript_text}
"""
Grammar issues already identified (for reference): {issues as "quote → correction" lines, or "(none)"}
```

**Schema:** `{ "improved_answer": "…", "notes": ["…", "…"] }`

### 9.4 Categorias-semente globais

| slug | name | description | generation_hint |
|---|---|---|---|
| `everyday-situations` | Everyday situations | Daily life in Canada: neighbours, appointments, the bank, the doctor, public transport, weather, small talk, housing. | Alternate between questions someone asks the learner and situations where the learner must explain or describe something. |
| `shopping` | Shopping | Stores, groceries, returns and exchanges, prices, comparing products, asking staff for help, online orders and deliveries. | Include both the learner as customer and the learner describing habits or preferences. |
| `job-interview` | Job interview | Interview questions for entry and mid-level jobs in Canada (customer service, administration, hospitality, retail, tech support): classic, behavioural ("tell me about a time…") and situational. | Phrase questions exactly as an interviewer would. Vary classic / behavioural / situational. |
| `travel` | Travel | Airports, border and immigration questions, hotels, directions, public transport, describing trips and plans. | Include realistic officer and staff questions as well as questions about the learner's own travel experiences. |

### 9.5 Prompt do Whisper — `whisper_prompt.txt`
```
Um, uh, so, like... I think, hmm, you know, I mean, well... Let me think. Okay, so basically...
```
Heurística para preservar fillers (o guia da OpenAI lista esse uso do `prompt`, mas o exemplo textual saiu da documentação); validar nas primeiras transcrições reais.

---

## 10. Dashboard — estrutura de informação e layout

### 10.1 Princípios
- Dois gráficos-herói acima da dobra: **evolução das notas** (3 eixos) e **evolução do nível** (rating com faixas CEFR).
- Cores **fixas por entidade** no app inteiro: Estrutura, Gramática e Fluência com um matiz cada (mesmas cores no painel de avaliação, histórico e gráficos). Maturidade em **um matiz em rampa** (novo claro → maduro escuro). Nível em cor neutra de destaque, faixas CEFR como bandas de fundo.
- Um eixo Y por gráfico; legenda + rótulos diretos; tooltip em tudo; alternância "ver tabela" em cada bloco.
- Identidade própria: superfícies neutras quentes, números grandes, grid discreto, dark mode das mesmas rampas. Paleta validada com o validador do skill `dataviz` na implementação.

### 10.2 Layout (desktop, 12 colunas; mobile empilha)

```
┌─ Estatísticas ────────────────────────────  Período [7d|30d|90d|1a|tudo]   Categoria [todas ▾] ─┐

A · KPIs (5 tiles)
┌ Hoje ──────────┐ ┌ Nível ─────────────┐ ┌ Vencem em 7 dias ┐ ┌ Coleção ─────────────┐ ┌ Nota média ─────┐
│ 12 / 17 cards   │ │ B1 · 1.240  ▲ +35  │ │ 43 cards          │ │ 128 cards            │ │ 3,6   ▲ +0,4     │
│ 5 novos · 7 rev.│ │ 40 pts p/ B2       │ │ ▁▂▃▅▂▁▃           │ │ ████▒▒░░ novo/apr/mad│ │ vs período ant.  │
└─────────────────┘ └────────────────────┘ └───────────────────┘ └──────────────────────┘ └──────────────────┘

B · Evolução das notas (7 col)                              │ Evolução do nível (5 col)
┌──────────────────────────────────────────────────────┐    │ ┌────────────────────────────────────────┐
│ Linhas Estrutura · Gramática · Fluência (média       │    │ │ Linha do rating (último de cada dia)   │
│ semanal; diária com média móvel 7d). Y fixo 1–5.     │    │ │ sobre faixas horizontais A2/B1/B2.     │
│ Clique num eixo = ênfase. Rótulo direto no fim.      │    │ │ Marcadores nas sondas (↑ acerto, ↓ erro)│
│ Sub-linha: 3 mini-tiles por eixo (média, Δ, sparkline)│   │ │ Rodapé: "sondas acima: 4/7 acertos"    │
└──────────────────────────────────────────────────────┘    │ └────────────────────────────────────────┘

C · Atividade (7 col)                                       │ Próximas revisões (5 col)
│ Colunas empilhadas/dia: novos / aprendendo / maduros.      │ │ Colunas/dia, 30 dias; atrasados à esquerda;
│ Alternância [barras] [calendário 12 meses]                 │ │ tooltip com acumulado; rodapé "143 · 12 atrasados"

D · Coleção (5 col)                                         │ Erros de gramática mais frequentes (7 col)
│ Barras horizontais empilhadas por categoria (maturidade)   │ │ Barras horizontais por tipo (top 8) com Δ vs
│ + mini-barra por nível CEFR                                │ │ período anterior; clique → exemplos quote→correção

E · Por categoria (tabela, 12 col)
│ Categoria │ Cards │ Respostas │ Estrutura │ Gramática │ Fluência │ Tendência (sparkline) │

F · Avançado (acordeão fechado): facilidade (ease), intervalos, duração das respostas
```

### 10.3 Dado → forma → endpoint
| Bloco | Forma | Endpoint |
|---|---|---|
| A | stat tiles com delta/sparkline | `/stats/overview/`, `/stats/forecast/?days=7` |
| B-esq | linhas, 3 séries categóricas, ênfase | `/stats/scores/?bucket=week` |
| B-dir | linha única sobre bandas de referência + marcadores | `/stats/level/` |
| C-esq | colunas empilhadas (rampa) + heatmap | `/stats/activity/`, `/stats/heatmap/` |
| C-dir | colunas sequenciais | `/stats/forecast/?days=30` |
| D-esq | barras horizontais empilhadas | `/stats/collection/` |
| D-dir | barras horizontais + delta | `/stats/grammar-issues/` |
| E | tabela com micro-barras | `/stats/categories/` |

### 10.4 Correspondência com o Anki
| Anki | Aqui |
|---|---|
| Today | tile Hoje |
| Future Due | Próximas revisões |
| Calendar | alternância em Atividade |
| Reviews (por tipo) | Atividade (por maturidade) |
| Card Counts | tile Coleção + bloco D-esq (com categoria e nível) |
| Review Intervals, Card Ease | acordeão Avançado |
| Answer Buttons | substituído por Evolução das notas |
| Hourly Breakdown | fora do MVP |
| — | **Evolução das notas**, **Evolução do nível**, **Erros frequentes** (exclusivos) |

---

## 11. Deploy: Oracle Cloud Free Tier + Coolify

- **VM**: Ampere A1 (ARM64, até 4 OCPU / 24 GB RAM no Always Free), Ubuntu; Coolify instalado na VM gerencia containers, TLS (Traefik/Let's Encrypt) e deploy por Git/Dockerfile.
- **Serviços no Coolify**: `postgres:16`, `redis:7`, `backend` (gunicorn + WhiteNoise servindo o build do Vite → **mesmo domínio**, cookies de sessão funcionam), `worker` (Celery; imagem do backend com `ffmpeg`), opcional `beat`.
- **Imagens multi-arch** (`linux/arm64` + `amd64`) via `docker buildx`; psycopg 3 e ffmpeg têm binários ARM64.
- **Áudios**: Oracle Object Storage (20 GB Always Free) pela API de compatibilidade S3 (`django-storages` + `boto3`, endpoint `<namespace>.compat.objectstorage.<region>.oraclecloud.com`, Customer Secret Key); URLs assinadas.
- **Backups**: backup agendado do Postgres pelo Coolify para um bucket S3 (o mesmo Object Storage); snapshot semanal do boot volume.
- **Caveat conhecido**: a Oracle pode **recuperar instâncias Always Free ociosas** (uso baixo de CPU/rede por 7 dias). Mitigação: converter a conta para Pay As You Go mantendo-se dentro dos limites gratuitos (custo zero), o que remove a regra de recuperação.
- Secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, credenciais S3, `SECRET_KEY`) como variáveis do Coolify; nunca no repositório.

---

## 12. Decisões

### 12.1 Tomadas no chat (2026-09-16)
| # | Tema | Decisão |
|---|---|---|
| 1 | Nome | **Echo** |
| 2 | Multi-tenant | Isolamento por linha + manager fail-closed agora; RLS na fase 2 |
| 3 | Tenant | **Sem organização**: tenant = usuário. `StudyGroup` N:N no backlog para competição |
| 4 | Categorias | **Globais** (admin) **+ pessoais** (criadas pelo usuário) |
| 5 | Onboarding | Usuários criados por você no Django admin |
| 6 | Hospedagem | **Oracle Cloud Free Tier + Coolify** |
| 7 | Auth | Sessão + cookie httpOnly + CSRF (mesmo domínio) |
| 8 | Fila | **Celery + Redis** |
| 9 | Áudio | **Oracle Object Storage via S3 API**; reter todos |
| 10 | Gravador | Hook próprio sobre `MediaRecorder` |
| 11 | Transcrição | `whisper-1`, com A/B contra `gpt-transcribe` |
| 12 | Modelo Anthropic | **Opus 5 avalia, Sonnet 5 gera** (e gera a versão melhorada) |
| 13 | Notas | 1–5 por eixo; pesos 0,40 / 0,35 / 0,25; piso estrutura ≤ 2 ⇒ falha |
| 14 | Repetição no dia | Só a primeira tentativa move agendador e rating |
| 15 | Carry-over | Novos não respondidos voltam e contam para N |
| 16 | Sem fala | Notas 1, não move agendador nem rating |
| 17 | Duração | **3 s a 5 min** |
| 18 | Gráficos | Recharts via shadcn/ui charts |
| 19 | Frontend | Vite + React 19 + TS + TanStack Query + React Router + shadcn/ui; tipos do OpenAPI |
| 20 | Idioma | UI em pt-BR; feedback pt-BR alternável para inglês |
| 21 | Nível | **Adaptativo, ELO** (seção 4.7); régua da avaliação = **nível da pergunta** |
| 22 | Extras IA | `key_points` sempre; **versão melhorada só sob demanda** (botão) |
| 23 | Versões | Python 3.12, Django 5.2 LTS, DRF 3.16, PostgreSQL 16 |
| 24 | Privacidade | Apagar/exportar dados na fase 2 |

### 12.2 Parâmetros que eu defini e você pode ajustar (sem impacto estrutural)
| Parâmetro | Valor | Onde |
|---|---|---|
| Rating inicial default | 1150 (admin pode mudar por usuário) | `ECHO_LEVEL_INITIAL_RATING` |
| Bandas CEFR | 200 pontos cada, A2 começa em 1000 | `ECHO_LEVEL_BANDS` |
| Modificador de dificuldade dentro da banda | −60 / 0 / +60 | `ECHO_LEVEL_DIFFICULTY_OFFSETS` |
| Proporção de sondas | 20 % (mín. 1 quando ≥ 3 geradas), alternando acima/abaixo | `ECHO_PROBE_RATIO` |
| Fator K | 40 (≤ 20 tentativas) → 24 (≤ 100) → 16 | `ECHO_LEVEL_K_SCHEDULE` |
| Limites do rating | 600–2200 | |
| Intervalo máximo SM-2 | 180 dias | `ECHO_SM2_MAX_INTERVAL_DAYS` |
| Limiar "maduro" | intervalo ≥ 21 dias | |
| N novos default | 3 | `User.default_new_cards_per_day` |
| Perguntas recentes enviadas ao gerador para dedup | 80 | |
| Effort Anthropic | medium (avaliar/gerar), low (versão melhorada) | |

### 12.3 Backlog (fora do MVP)
`StudyGroup` N:N e placares opt-in · RLS no Postgres · apagar/exportar dados · `PATCH` de sessão (adicionar novos no mesmo dia) · perguntas manuais · flag "transcrição errada" · ajuste do rating das perguntas por resultados de muitos alunos (Glicko) · fuzz de intervalo, learning steps, FSRS · SSE em vez de polling · export de custo por usuário.

---

## 13. Roadmap de implementação

| Fase | Entrega | Verificação |
|---|---|---|
| 0 | Repo, Docker Compose (Postgres, Redis), Django + DRF, Vite, CI (ruff, pytest, vitest, tsc), Dockerfiles multi-arch | `docker compose up` sobe tudo; suites vazias verdes; imagem builda em arm64 |
| 1 | `core` (OwnedModel, contexto fail-closed), `accounts` (User, sessão, `/me`, mixin), `cards.Category` global/pessoal + seed, testes de isolamento com 2 usuários | suite `tests/isolation` passa; login e `/me` funcionam na UI |
| 2 | `cards.Card`, `scheduling` (`sm2.py` + tabela de casos), `leveling` (`elo.py` + tabela de casos da seção 4.7.4, `probes.py`) | testes parametrizados de SM-2 e ELO reproduzem as tabelas do plano |
| 3 | `practice`: sessão, slots + geração (Sonnet 5, respostas gravadas para teste), fila novos→vencidos, telas Início do dia e Sessão (sem áudio) | criar sessão gera N perguntas nas categorias/níveis certos com sondas; fila na ordem; carry-over ao virar o dia (tz e data congeladas) |
| 4 | `useAudioRecorder`, upload S3, pipeline Celery (ffprobe → whisper → Opus → SM-2 + ELO), painel de avaliação, `level_change`, botão de versão melhorada, polling | tentativa real ponta a ponta em Chrome e Safari; `ReviewLog` e `LevelLog` coerentes; retry após falha simulada; versão melhorada gerada só ao clicar e cacheada |
| 5 | Histórico por card (áudios + análises), tela de cards, suspender | histórico mostra todas as tentativas com player e variação de nível |
| 6 | `stats` + dashboard (incl. evolução do nível), paleta validada com `dataviz` | números batem com SQL manual em dados de teste; validador de paleta passa em claro e escuro |
| 7 | Deploy no Oracle + Coolify, Object Storage, domínio/TLS, backups, `AIRequestLog` com custo | sessão completa em produção; custo/dia visível no admin |
| 8 | Fase 2 / backlog (12.3) | — |

Estimativa grosseira: fases 0–7 em 5–7 semanas de trabalho de uma pessoa em tempo parcial (o ELO e a geração por slots acrescentam ~1 semana ao plano original).

---

## 14. Notas técnicas e riscos

### 14.1 Isolamento
- `ATOMIC_REQUESTS = True` desde o dia 1 (consistência de SM-2 + ELO na mesma transação; pré-requisito da RLS).
- Pool nativo do psycopg 3 (`OPTIONS: {"pool": True}`) em vez de `CONN_MAX_AGE`. Na RLS, `SET LOCAL` dentro da transação; `SET` de sessão vazaria o usuário para o próximo request.
- Admin do Django é acesso global (`is_staff`); comandos e tasks abrem `owner_context(user_id)` explicitamente.

### 14.2 Transcrição
- Whisper tende a limpar fillers → sinal de fluência limitado; o rubric já diz que ausência de fillers não prova fluência; WPM entra como sinal fraco.
- Sotaque + A2 podem gerar palavras erradas; o rubric instrui a ignorar artefatos; a UI mostra a transcrição. Flag "transcrição errada" no backlog.
- Só `whisper-1` devolve `verbose_json`; a duração vem do ffprobe, logo trocar o modelo não quebra WPM.

### 14.3 Gravação
- Formatos 2026: Chrome/Edge `audio/webm;codecs=opus`; Firefox default `audio/ogg;codecs=opus` mas aceita webm/opus; Safari/iOS **18.4+** grava webm/opus, 14.1–18.3 só `audio/mp4`. Hook tenta webm/opus → mp4 → ogg/opus via `isTypeSupported()` e envolve `start()` em try/catch (iOS pode dizer sim e falhar). OpenAI aceita todos.
- Blobs WebM vêm sem duração (`Infinity`) e MP4 do Chrome/Safari com `moov.duration = 0` → **ffprobe no worker é a fonte da verdade**; o timer do cliente é fallback e validação. `fix-webm-duration` opcional para a pré-escuta.
- HTTPS e gesto do usuário obrigatórios; pedir microfone no clique em "Gravar".
- Wrappers React dormentes → hook próprio.

### 14.4 Qualidade da avaliação e do nível
- Variância entre chamadas é o maior risco para "ver progresso real". Mitigações: rubric por nota ancorado no nível da pergunta, `key_points`, eixos independentes, `raw_response` guardado para re-avaliar em lote com `prompt_version` novo.
- O ELO herda o ruído das notas: `K` provisório alto converge rápido no início, e depois `K = 16` amortece. Se o rating oscilar demais, reduzir K ou usar média das últimas 3 tentativas como `A`.
- Montar um **conjunto de calibração** (10–15 transcrições reais com nota "justa" definida por vocês) antes de trocar prompt ou modelo.
- Sondas são a única forma de o rating subir de banda com perguntas "no nível" produzindo `A ≈ E`; por isso a proporção de 20 % é importante — se a evolução parecer lenta, subir para 30 %.

### 14.5 Custos e limites
- 5 min em Opus ≈ 4 MB (limite Whisper 25 MB); transcrição de 5 min ≈ 10–15 s.
- Rate limits irrelevantes neste volume; retries com backoff mesmo assim.
- `AIRequestLog` permite tile de custo mensal no admin.
