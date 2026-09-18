# Prompts

O texto exato dos prompts (versionado) fica junto do código, em `backend/apps/ai/prompts/`:

- `generation_v1.md` — geração de perguntas por slot (Sonnet 5)
- `evaluation_v1.md` — avaliação em três eixos, régua = nível da pergunta (Opus 5)
- `improved_answer_v1.md` — versão melhorada sob demanda (Sonnet 5)
- `whisper_prompt.txt` — dica para preservar fillers na transcrição

As mensagens de usuário são montadas em `backend/apps/ai/prompts/__init__.py`. Para mudar um
prompt, crie `*_v2.md` e mude `ECHO_PROMPT_VERSION`; `Evaluation.prompt_version` e
`raw_response` permitem reavaliar em lote.
