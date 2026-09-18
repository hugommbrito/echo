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

## Nível
Linha do rating em tinta primária (`#0b0b0b` / `#ffffff`) sobre faixas CEFR alternadas
(`--chart-band` `#f3f2ee` / superfície). Sondas usam **status**, com ícone + rótulo:
acerto ▲ `#006300` (claro) / `#0ca30c` (escuro); erro ▼ `#d03b3b`.

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
