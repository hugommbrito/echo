# Echo — frontend

Interface web do Echo (prática de inglês falado com repetição espaçada e nível CEFR adaptativo).
React 19 + TypeScript + Vite 8, Tailwind CSS v4, TanStack Query, React Router v7. Todo o texto da UI é em pt-BR.

## Rodando em desenvolvimento

1. Suba o backend Django em `http://localhost:8000` (veja `../backend`).
2. Instale e rode:

```bash
npm install
npm run dev        # http://localhost:5173
```

O dev server faz proxy de `/api`, `/media`, `/admin` e `/static` para `:8000` mantendo os cookies
(sessão + CSRF são same-origin), então não há configuração de CORS.

## Scripts

| comando              | o que faz                                                              |
| -------------------- | ---------------------------------------------------------------------- |
| `npm run dev`        | Vite com HMR                                                           |
| `npm run build`      | `tsc -b` (zero erros de tipo) + `vite build` → `dist/`                 |
| `npm run preview`    | serve o `dist/`                                                        |
| `npm run lint`       | `oxlint src`                                                           |
| `npm test`           | `vitest run` (jsdom + jest-dom)                                        |
| `npm run gen:types`  | gera `src/types/api.generated.d.ts` a partir de `/api/schema/` (opcional; os tipos usados estão em `src/types/api.ts`) |

## Estrutura

```
src/
├── app/           router, providers, AppShell (nav + badge de nível), RequireAuth
├── api/           client.ts (fetch + CSRF + ApiError), queryClient, hooks por recurso
├── components/ui/ primitivos (Button, Card, Dialog…) + ScorePill, MaturityBadge, LevelBadge, AudioPlayer, ScoreBar
├── features/
│   ├── auth/         LoginPage
│   ├── day-setup/    TodayPage (categorias, N, projeção, começar/continuar)
│   ├── practice/     SessionPage, CardPrompt, Recorder (useAudioRecorder), ProcessingSteps,
│   │                 EvaluationPanel, ImprovedAnswerButton, LevelDelta, AttemptHistory
│   ├── cards/        CardsPage, CardDetailPage
│   ├── dashboard/    StatsPage (placeholder)
│   └── settings/     SettingsPage (preferências + categorias pessoais)
├── lib/           cn, colors (eixos/maturidade), format (pt-BR), levels, labels
└── types/         api.ts (contrato da API)
```

Tokens de design (cores dos eixos, maturidade, superfícies) ficam em `src/index.css`
e são expostos ao Tailwind via `@theme inline` (`bg-surface`, `text-axis-structure`, …).
Dark mode segue `prefers-color-scheme` (ou a classe `.dark` no `<html>`).

## Smoke test no navegador (Playwright)

Com o backend servindo a SPA compilada em `http://localhost:8000` (`npm run build` + `runserver`,
ou a imagem de produção) e um usuário criado com `python manage.py create_user`:

```bash
npx playwright install chromium          # uma vez
E2E_EMAIL=aluna@example.com E2E_PASSWORD=... npm run e2e   # screenshots em e2e/screenshots/
```

O roteiro faz login, cria/continua a sessão do dia, grava 4 s com o microfone falso do Chromium,
envia, espera a avaliação, pede a versão melhorada, avança, e fotografa cards, estatísticas
(claro e escuro) e configurações. Falha se houver erro de console/página ou resposta 5xx.
