# Q3 — Research Validation Protocol

## 1. Objetivo

Validar estrategias quantitativas com rigor suficiente para reduzir:

- look-ahead bias
- survivorship bias
- data snooping
- backtest overfitting
- conclusoes falsas por multiplos testes

### Referencias-base

| Conceito | Referencia |
|---|---|
| Data snooping / Reality Check | White (2000) — [A Reality Check for Data Snooping](https://www.ssc.wisc.edu/~bhansen/718/White2000.pdf) |
| Deflated Sharpe Ratio / PBO | Bailey & Lopez de Prado (2014) — [The Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) |
| Purging / Embargo em validacao temporal | Lopez de Prado (2018) — [Advances in Financial Machine Learning, Lecture 10](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3637114_code434076.pdf?abstractid=3447398) |
| Momentum (2-12) | Kenneth French Data Library — [Monthly Momentum Factor](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html) |

---

## 2. Criterios minimos para chamar uma estrategia de "validada"

Uma estrategia so pode ser promovida se passar por **todos** estes blocos:

### A. Integridade dos dados

- Dados **point-in-time**
- Filings com **lag contabil explicito**
- Snapshots de mercado com timestamp real
- Retificacoes respeitando data de disponibilidade
- Sem uso de informacao que nao existia na data do rebalanceamento

### B. Backtest honesto

- Calendario de rebalance realista
- Execution lag
- Custos + slippage
- Regras de liquidez
- Universo elegivel reproduzivel

### C. Validacao fora da amostra

- In-sample
- Validation
- Out-of-sample congelado
- Walk-forward obrigatorio

### D. Controle estatistico

- Correcao para multiplas hipoteses
- Metricas ajustadas por selecao
- Robustez em subperiodos
- Sensibilidade a parametros

### E. Reprodutibilidade

- Experimento versionado
- Parametros congelados
- Artefatos persistidos
- Rerun deterministico

---

## 3. Protocolo de dados point-in-time

### Regras

- `reference_date` != `filing_delivered_at` != `snapshot_fetched_at`
- Metrica contabil so pode entrar no ranking **apos** sua data de disponibilidade
- Snapshot de mercado so pode ser usado se estiver valido pela politica de staleness
- Restatements so podem alterar simulacoes **de datas futuras a retificacao**, nao reescrever o passado "como se ja soubessemos"

### Backlog

- [x] Criar suite `test_point_in_time_integrity`
- [x] Criar fixture com filing original + restatement posterior
- [x] Testar que rebalance anterior a retificacao usa apenas o filing antigo
- [x] Testar que snapshot velho e excluido do calculo
- [x] Testar mudanca de ticker / primary security sem vazamento temporal

---

## 4. Protocolo de backtest

### Regras

- Rebalanceamento definido por calendario
- Ranking formado em `t`
- Execucao em `t+lag`
- Custos e slippage obrigatorios
- Sem "preco magico" de fechamento indisponivel

### Backlog

- [x] Implementar engine de rebalance mensal
- [x] Implementar engine trimestral
- [x] Definir regra padrao de execucao
- [x] Aplicar custo fixo + custo proporcional
- [x] Aplicar slippage parametrizavel
- [ ] Modelar arredondamento e cash residual
- [ ] Definir benchmark oficial

---

## 5. Protocolo de split temporal

### Regras

Separar o historico em:

- **train / in-sample**
- **validation**
- **out-of-sample final**

O OOS final nao pode ser usado para escolher peso, filtro ou janela.

Para tuning mais serio, usar validacao temporal com **purging/embargo** para reduzir leakage entre observacoes dependentes no tempo (Lopez de Prado, 2018).

### Backlog

- [ ] Definir janelas oficiais do Q3
- [x] Implementar walk-forward runner
- [x] Implementar purged temporal split
- [ ] Bloquear uso do OOS em tuning
- [x] Persistir metadado indicando qual split gerou o experimento

---

## 6. Controle de data snooping

White (2000) mostra que reutilizar o mesmo conjunto de dados para testar muitas variacoes infla a chance de "descobertas" espurias; o **Reality Check** foi proposto exatamente para isso.

### Regras

- Toda variante testada conta como hipotese testada
- Mudar peso, filtro ou janela cria novo experimento
- Nao promover estrategia com base so no melhor backtest bruto

### Backlog

- [x] Criar registro obrigatorio de hipoteses testadas
- [x] Salvar numero de variantes avaliadas por familia
- [x] Implementar pipeline de `RealityCheckReport`
- [x] Reportar p-value corrigido para selecao multipla
- [ ] Impedir merge de "nova estrategia" sem manifest de pesquisa

---

## 7. Metricas estatisticas obrigatorias

Bailey & Lopez de Prado (2014) propoem o **Deflated Sharpe Ratio** para corrigir vies de selecao, multiplos testes e nao normalidade; o paper tambem referencia o uso do **Probabilistic Sharpe Ratio**.

### Report padrao

| Metrica | Descricao |
|---|---|
| CAGR | Retorno anualizado composto |
| Volatility | Desvio-padrao anualizado dos retornos |
| Max Drawdown | Maior queda pico-a-vale |
| Sharpe | Retorno excedente / volatilidade |
| Sortino | Retorno excedente / downside deviation |
| Information Ratio | Alpha / tracking error vs benchmark |
| Turnover | Rotacao media da carteira |
| Hit Rate | % de periodos com retorno positivo |
| PSR | Probabilistic Sharpe Ratio |
| DSR | Deflated Sharpe Ratio |

### Backlog

- [x] Implementar `ProbabilisticSharpeRatio`
- [x] Implementar `DeflatedSharpeRatio`
- [x] Reportar assimetria e curtose dos retornos
- [x] Reportar numero efetivo de testes/modelos
- [ ] Nunca exibir Sharpe isolado como "selo de qualidade"

---

## 8. Robustez fora da amostra

### Regras

A estrategia precisa ser analisada por regimes:

- **bull**
- **bear**
- **stress**
- **recovery**

E nao pode depender de um unico subperiodo excepcional.

### Backlog

- [x] Criar relatorio por subperiodo
- [x] Criar heatmap rolling de performance
- [x] Medir degradacao IS -> OOS
- [x] Definir limite maximo aceitavel de degradacao
- [x] Criar flag `fragile_strategy` quando OOS colapsar

---

## 9. Sensitivity analysis

### Regras

Uma estrategia robusta nao deve depender de um parametro exato demais.

### Backlog

- [x] Variar frequencia de rebalance
- [ ] Variar liquidez minima
- [ ] Variar market cap minimo
- [x] Variar custos
- [x] Variar slippage
- [ ] Variar winzorizacao
- [ ] Variar tratamento de missing values
- [x] Variar lag de filing
- [x] Gerar relatorio de sensibilidade

---

## 10. Testes de especificacao da estrategia

### Objetivo

Garantir que a implementacao bate com a definicao teorica.

### Backlog

- [x] Testar que Brazil gates sao filtros, nao score
- [x] Testar que core usa `EY + ROC` com pesos iguais
- [ ] Testar que quality overlay usa apenas sinais disponiveis
- [ ] Testar que ausencia de overlay nao corrompe score
- [x] Testar ordenacao asc/desc correta por metrica
- [ ] Testar exclusao de financeiras/utilities
- [x] Testar exclusao de `EBIT <= 0`
- [x] Testar casos `EV <= 0`, `equity <= 0`, `net_income <= 0`

---

## 11. Testes de contribuicao marginal

### Objetivo

Provar que o overlay adiciona valor de verdade.

### Backlog

- [ ] Backtest `core only`
- [ ] Backtest `core + leverage`
- [ ] Backtest `core + cash conversion`
- [ ] Backtest `core + full quality overlay`
- [ ] Medir contribuicao marginal em:
  - retorno
  - drawdown
  - turnover
  - estabilidade OOS
- [ ] Proibir novo fator sem evidencia incremental clara

---

## 12. Reprodutibilidade total

### Manifest obrigatorio

Cada experimento deve persistir:

| Campo | Descricao |
|---|---|
| `strategy` | Identificador da estrategia |
| `variant` | Variante especifica testada |
| `dates` | Periodo coberto (start/end) |
| `universe` | Criterios de elegibilidade |
| `costs` | Modelo de custos aplicado |
| `slippage` | Modelo de slippage aplicado |
| `parameters` | Todos os parametros da estrategia |
| `commit_hash` | Hash do commit do codigo |
| `formula_version` | Versao das formulas usadas |
| `seed` | Seed para reprodutibilidade |
| `split` | Split temporal usado (IS/VAL/OOS) |

### Backlog

- [x] Criar schema `research_manifest.json`
- [ ] Persistir constituents por rebalance
- [ ] Persistir returns da carteira
- [x] Persistir metricas agregadas
- [ ] Persistir logs de dados usados
- [x] Garantir rerun deterministico

---

## 13. Criterios formais de promocao

Uma estrategia so sobe para "candidate" se:

- [x] OOS aceitavel
- [x] DSR acima do threshold
- [x] Sem dependencia critica de um unico subperiodo
- [x] Robusta a custos
- [x] Robusta a pequenas variacoes de parametros
- [x] Sem violacao de point-in-time
- [x] Com documentacao completa do experimento

### Backlog

- [x] Definir thresholds oficiais
- [x] Automatizar `promotion_check`
- [ ] Bloquear promocao manual sem checklist completo

---

## 14. Ordem recomendada de implementacao

### Sprint R1

- [x] Point-in-time tests
- [x] Backtest engine minimo honesto
- [x] Custos/slippage
- [x] Walk-forward basico
- [x] Strategy specification tests

### Sprint R2

- [x] OOS report
- [x] Subperiod report
- [x] Sensitivity report
- [x] Manifest reproduzivel
- [x] PSR / DSR

### Sprint R3

- [x] Reality Check
- [x] Purged temporal validation
- [x] Promotion pipeline
- [x] PBO / overfitting diagnostics

---

## 15. Nota especifica para momentum

Se momentum entrar depois, ele deve usar retorno passado **(2-12)**, como na convencao classica da biblioteca do Kenneth French, e ser validado primeiro como **gate**, nao como pilar principal.

---

## 16. Regra final do Q3

> **Backtest nao e prova.**

No Q3, prova minima significa:

1. Point-in-time correto
2. OOS real
3. Custos reais
4. Correcao para multiplos testes
5. Metricas ajustadas por selecao
6. Reprodutibilidade total

Nenhuma estrategia pode ser promovida sem cumprir os 6 requisitos acima.
