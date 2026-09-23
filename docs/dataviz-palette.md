# Paleta do app e dos gráficos (validada com o skill `dataviz`)

Superfícies: claro `#fcfcfb` (plano `#f9f9f7`), escuro `#1a1a19` (plano `#0d0d0d`).
Validador: `validate_palette.js` (OKLab, CVD Machado 2009) — resultados abaixo.

## Eixos da avaliação (categórico, ordem fixa, 3 séries) — mesma cor no app inteiro
| Eixo | Claro | Escuro |
|---|---|---|
| Estrutura | `#2a78d6` | `#3987e5` |
| Gramática | `#eb6834` | `#d95926` |
| Fluência | `#1baf7a` | `#199e70` |

`--pairs all`, claro: CVD pior par ΔE 9,2 · visão normal 24,0 · **WARN** contraste do aqua (2,74:1)
→ obrigação de rótulos visíveis ou tabela (todo gráfico tem "Ver tabela" e rótulos diretos).
Escuro: todos PASS (CVD 9,4 · normal 20,9 · contraste ≥ 3:1).

## Maturidade (ordinal, um matiz violeta)
| | Novo | Aprendendo | Maduro |
|---|---|---|---|
| Claro (claro → escuro) | `#a49ce8` | `#7466d2` | `#4a3aa7` |
| Escuro (recessivo → destaque) | `#5a4db5` | `#8479df` | `#b3aaf3` |

`--ordinal`: monotonia, ΔL ≥ 0,06 e extremo claro ≥ 2:1 — PASS nos dois modos (extremo 2,41:1 claro, 2,62:1 escuro).
Sequencial do calendário (respostas/dia): rampa violeta `#c9c3f3 → #a49ce8 → #7466d2 → #4a3aa7` sobre a faixa de fundo.

## Idiomas (categórico, slots 4 e 5) — mesma cor no app inteiro
| Idioma | Claro | Escuro |
|---|---|---|
| Inglês (`en`) | `#eda100` (âmbar) | `#c98500` |
| Francês (`fr`) | `#e87ba4` (magenta) | `#d55181` |

Validados contra as superfícies reais (`#fffdfa` claro, `#1f1b16` escuro): claro PASS em CVD (ΔE 16,3) e
visão normal (19,6), **WARN** de contraste (2,1–2,7:1) → mesma obrigação dos eixos (legenda + rótulo direto
no fim da linha + "Ver tabela"); escuro tudo PASS. Rejeitados: verde (ΔE 10 do ▲ de sonda acertada),
vermelho (colide com `--status-critical`), violeta (maturidade). **Regra**: séries de eixo e séries de idioma
nunca dividem um gráfico — o seletor de idioma *filtra* os gráficos de eixo, nunca acrescenta séries. Um
terceiro idioma não ganha o slot 6 (verde): o gráfico de nível passa a facetar. Tokens `--language-en` /
`--language-fr` em `frontend/src/index.css`.

## Nível
Uma linha por idioma **na cor do idioma** (um idioma só continua na cor dele; a legenda só aparece com
≥ 2 séries e o subtítulo nomeia o idioma) sobre faixas CEFR alternadas (`--chart-band` `#f3f2ee` /
superfície). Sondas usam **status**, com ícone + rótulo, sobre a própria linha:
acerto ▲ `#006300` (claro) / `#0ca30c` (escuro); erro ▼ `#d03b3b`. Coleção "Por nível CEFR": mini-barras
agrupadas lado a lado por idioma (distribuições independentes; nunca empilhadas).

## Tinta e cromo
| Papel | Claro | Escuro |
|---|---|---|
| Tinta primária | `#0b0b0b` | `#ffffff` |
| Tinta secundária | `#52514e` | `#c3c2b7` |
| Eixos/rótulos (muted) | `#898781` | `#898781` |
| Grade (hairline sólida) | `#e1e0d9` | `#2c2c2a` |
| Linha de base | `#c3c2b7` | `#383835` |

Regras aplicadas: um eixo Y por gráfico; texto sempre em tinta (nunca na cor da série);
marcas finas (barras ≤ 24 px, linhas 2 px, marcadores ≥ 8 px) com gap de 2 px na cor da
superfície; legenda sempre presente para ≥ 2 séries e rótulo direto só no fim da linha;
tooltip em tudo; alternância "ver tabela" em cada bloco; refetch mantém o render anterior a 60 %.
