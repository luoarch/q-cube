# Plan 4 — Investable Universe Classification Engine

## Status: BUILD COMPLETE — Awaiting Tech Lead review

---

## 1. Micro Feature

**Universe Classification Engine** — Classify each issuer as `CORE_ELIGIBLE`, `DEDICATED_STRATEGY_ONLY`, or `PERMANENTLY_EXCLUDED` based on CVM sector taxonomy. Persist classification in a governed table with supersede pattern. Make it queryable via SQL and internal repository.

This does NOT include:
- Wiring into the ranking pipeline (micro feature B)
- API endpoints (micro feature B/C)
- Dashboard UI

---

## 2. Problem

The Q3 Core ranking currently excludes issuers via ad-hoc sector checks scattered across the codebase:

- `ranking.py:28-29`: `EXCLUDED_SECTORS = {"financeiro", "utilidade pública"}` — but CVM cadastro uses specific sector names (`Bancos`, `Energia Elétrica`, etc.), NOT "financeiro"
- Plan 2 thesis: inherits exclusion via `passed_core_screening` flag — no independent sector gate
- Refiner: `issuer_classification` (bank/insurer/utility/holding/non_financial) — scoring only, not filtering
- FII detection: absent (but validated as unnecessary — see FII evidence below)

Problems:
1. No single source of truth for "should this issuer be in the Core?"
2. Different pipelines apply different rules (or none)
3. No formal distinction between "excluded from Core but investable elsewhere" vs "permanently excluded"
4. Sector matching in ranking.py uses lowercase strings that don't match actual CVM `SETOR_ATIV` values

---

## 3. Outcome

After this micro feature:
- Every issuer has a persisted, typed classification (`CORE_ELIGIBLE`, `DEDICATED_STRATEGY_ONLY`, `PERMANENTLY_EXCLUDED`)
- Classification stored in governed `universe_classifications` table with supersede pattern and check constraints
- Classification based on a versioned, typed sector → class mapping dictionary in code
- Queryable via SQL and internal Python repository layer
- **No API endpoints** in this micro feature
- Existing pipelines NOT wired to this yet (micro feature B)

---

## 4. Corpus Audit (S0) — DB Evidence

### 4.1 DB State

| Metric | Value |
|--------|-------|
| Total issuers | 741 |
| With active securities | 356 |
| Orphan issuers (no securities) | 385 |
| Issuers with NULL sector | 8 |
| Distinct non-null sectors in DB | 56 |

### 4.2 FII Evidence — ZERO FIIs in DB

**All 13 suffix-11 active securities are UNITs (combined ON+PN certificates), NOT FIIs:**

| Ticker | Class | Sector | Company |
|--------|-------|--------|---------|
| ALUP11 | UNIT | Emp. Adm. Part. - Energia Elétrica | Alupar |
| AZEV11 | UNIT | Construção Civil... | Azevedo e Travassos |
| BRBI11 | UNIT | Emp. Adm. Part. - Bancos | BR Partners |
| CALI11 | UNIT | Construção Civil... | Construtora Adolpho Lindenberg |
| ENGI11 | UNIT | Emp. Adm. Part. - Energia Elétrica | Energisa |
| IFCM11 | UNIT | Comércio (Atacado e Varejo) | Infracommerce |
| IGTI11 | UNIT | Emp. Adm. Part. - Comércio... | Iguatemi |
| KLBN11 | UNIT | Papel e Celulose | Klabin |
| MOVI11 | UNIT | Serviços Transporte e Logística | Movida |
| RNEW11 | UNIT | Energia Elétrica | Renova Energia |
| SANB11 | UNIT | Bancos | Santander Brasil |
| SAPR11 | UNIT | Saneamento, Serv. Água e Gás | Sanepar |
| TAEE11 | UNIT | Emp. Adm. Part. - Energia Elétrica | TAESA |

**Conclusion: FIIs do not exist in the Q3 issuer population.** The DB is sourced from CVM `cad_cia_aberta.csv` which covers publicly traded companies (CIA_ABERTA), not investment funds. FII detection is NOT needed for v1. This is verified against live DB data, not just the cadastro CSV.

### 4.3 NULL Sector Issuers (8 total)

| CVM Code | Company | Nature |
|----------|---------|--------|
| 080225 | ALMACENES ÉXITO S.A. | Colombian retailer (Grupo Éxito) |
| 080187 | AURA MINERALS INC. | Canadian mining company |
| 080195 | G2D INVESTMENTS, LTD. | Foreign investment vehicle |
| 080020 | GP INVESTMENTS, LTD. | Foreign PE fund |
| 080217 | INTER & CO, INC. | US-listed fintech (Banco Inter) |
| IBOV | Ibovespa Index | Index, not a company |
| 080233 | JBS N.V. | Netherlands holding (JBS Global) |
| 080152 | PPLA PARTICIPATIONS LTD. | Foreign investment vehicle |

All are **foreign-listed entities** (CVM codes starting with 080xxx) or the **Ibovespa index** (a non-company). None are Brazilian operational companies with CVM cadastro data.

### 4.4 Construção Civil Split (49 + 11 holding = 60 issuers in DB)

By name analysis against the 49 issuers in `Construção Civil, Mat. Constr. e Decoração`:

**Incorporadoras (24):** Belora, BRZ, Cury, Cyrela, Emccamp, Even, EZ Inc, Fica, HBR, Helbor, INC, Kallas, Lavvi, Melnick, Mitre, PDG, Plano&Plano, RNI, Rossi, Tegra, Urba, Viver, You Inc, Yuny

**Materials/Industrial (12):** Dexco, Eternit, Eucatex, Intercement, LPS, Portuense, Priner, Salus, Sondotecnica, Tigre, Unicasa, Votorantim Cimentos

**Ambiguous (24):** Alphaville, Azevedo e Travassos, Adolpho Lindenberg, Metrocasa, Sultepa, Tenda, Direcional, EzTec, Gafisa, JHSF, João Fortes, Log CP, Mendes Junior, Moura Dubeux, MRV, Multiplan, Nexpe, Pacaembu, Patrimar, PBG, Sugoi, SYN, Tecnisa, Trisul

**The 24 ambiguous companies are predominantly incorporadoras/developers** (MRV, Tenda, Direcional, Gafisa, EzTec, Trisul, etc.). Very few are pure construction services.

### 4.5 `Emp. Adm. Part. - Sem Setor Principal` (33 issuers in DB)

By name analysis:

**Likely financial (9):** Alvarez & Marsal Investimentos, BNDESPAR, BTG Quartzo, BTG Safira, CEMEPE Investimentos, REAG Capital, Trevisa Investimentos, XP Investimentos, XX de Novembro Investimentos

**Likely operational (24):** 524 Participações, Cabinda/Caconde/Caianda (trio), CIA Aliança da Bahia, CSU Digital, Dexxos, Embpar, Gama, GPS, Hauscenter, HMOBI, Longdis, MLOG, MNLT, Monteiro Aranha, OSX, Polpar, Porto Serviço, Prompt, R/Holdings, São Carlos, Sudeste, Ybyrá Capital

### 4.6 Airlines in Transport

Only **2 airlines** found in 110 transport issuers:
- **019569** — GOL Linhas Aéreas Inteligentes S.A.
- **024112** — Azul S.A.

No other passenger transport companies (bus, rail) found. The one false positive ("Concessionária do Sistema Rodoviário Rio-São Paulo") is a highway concessionaire, not passenger transport.

### 4.7 Distinct Sectors in DB

```sql
SELECT count(DISTINCT sector) FROM issuers WHERE sector IS NOT NULL;
-- Result: 56
```

**56 distinct non-null sector values in DB.** The DB includes 3 sectors not found in the CVM cadastro active list (issuers were active at import time but may now be inactive in CVM):
- `Emp. Adm. Part. - Têxtil e Vestuário` (2 issuers)
- `Emp. Adm. Part. - Securitização de Recebíveis` (1 issuer)
- `Crédito Imobiliário` (1 issuer)

The mapping must cover all 56 values.

---

## 5. Requirements

### R1 — Classification persistence
Each issuer gets a persisted, typed classification. Enums for all key fields.

### R2 — Sector mapping dictionary
Versioned, typed mapping covering all 56 distinct `SETOR_ATIV` values in the DB. Code-only (git versioned). Full coverage test.

### R3 — Fail-closed for ALL unmapped cases
- Unmatched non-null sector = batch error (cannot commit)
- NULL sector without explicit override = batch error (cannot commit)
- **No implicit fallback to CORE_ELIGIBLE for any ambiguous case**

### R4 — Classification reason
Typed `classification_rule_code` enum + free-text `classification_reason`.

### R5 — Backfill all 741 issuers

### R6 — True idempotency
- If active classification exists with identical fields and same policy_version → **no-op** (0 inserts, 0 supersedes)
- If classification changed (different class, reason, etc.) or new policy_version → supersede old, insert new
- Rerun with no changes = 0 writes

### R7 — No pipeline wiring

### R8 — Check constraints on table
- `CORE_ELIGIBLE` → `dedicated_strategy_type IS NULL AND permanent_exclusion_reason IS NULL`
- `DEDICATED_STRATEGY_ONLY` → `dedicated_strategy_type IS NOT NULL AND permanent_exclusion_reason IS NULL`
- `PERMANENTLY_EXCLUDED` → `dedicated_strategy_type IS NULL AND permanent_exclusion_reason IS NOT NULL`
- `SECTOR_MAP` rule → `matched_sector_key IS NOT NULL`

---

## 6. Tech Lead Decisions (recorded)

| # | Decision | Answer |
|---|----------|--------|
| Q1 | Where | Separate table with supersede pattern |
| Q2 | Mapping | Code-only, git versioned |
| Q3 | Reuse issuer_classification | No, new system |
| Q4 | FII | NOT needed — 0 FIIs in DB (evidence in 4.2) |
| Q5 | Timing | Before Plan 3A coverage re-evaluation |

---

## 7. Methodology Decisions

### D1 — `Comércio (Atacado e Varejo)` → `PERMANENTLY_EXCLUDED`

CVM groups atacado and varejo into one sector. No subsector split available. **Entire group excluded.**

### D2 — Utilities (`Energia Elétrica`, `Saneamento`) → `CORE_ELIGIBLE`

Utility operational companies are eligible per investable universe matrix. Legacy ranking.py exclusion remains until micro feature B.

### D3 — `Construção Civil, Mat. Constr. e Decoração` → **`DEDICATED_STRATEGY_ONLY` by default**

Per Tech Lead decision: **ambiguous defaults to outside the Core**.

The sector mixes incorporadoras (majority) and materials/industrial companies. CVM provides no subsector to split them.

**Default**: `DEDICATED_STRATEGY_ONLY` with `dedicated_strategy_type = REAL_ESTATE_DEVELOPMENT`

**Allowlist for CORE_ELIGIBLE** (materials/industrial companies with clear non-development activity):

| CVM | Company | Justification |
|-----|---------|---------------|
| 021091 | Dexco S.A. | Painéis de madeira, louças, metais — indústria |
| 005762 | Eternit S.A. | Telhas, caixas d'água — indústria |
| 005770 | Eucatex S.A. | Painéis, pisos, tintas — indústria |
| 025992 | Intercement Brasil S.A. | Cimento — indústria |
| 009717 | Portuense Ferragens S/A | Ferragens — indústria |
| 024236 | Priner Serviços Industriais S.A. | Serviços industriais |
| 010880 | Sondotecnica Eng. Solos S.A. | Engenharia geotécnica — serviços técnicos |
| 026255 | Tigre S.A. | Tubos, conexões — indústria |
| 022780 | Unicasa Ind. Móveis S.A. | Indústria moveleira |
| 027189 | Votorantim Cimentos S.A. | Cimento — indústria |

Same logic for `Emp. Adm. Part. - Const. Civil, Mat. Const. e Decoração`: default `DEDICATED_STRATEGY_ONLY`, allowlist for known industrial holdings.

### D4 — Holdings (`Emp. Adm. Part.` variants)

Sector operacional prevalece. Holdings classified by suffix sector:
- `Emp. Adm. Part. - Energia Elétrica` → same as `Energia Elétrica` → CORE_ELIGIBLE
- `Emp. Adm. Part. - Bancos` → same as `Bancos` → DEDICATED_STRATEGY_ONLY
- etc.

### D5 — `Emp. Adm. Part. - Sem Setor Principal` → **`DEDICATED_STRATEGY_ONLY / UNCLASSIFIED_HOLDING`**

Per Tech Lead decision: **ambiguous holdings do NOT default to CORE_ELIGIBLE**. And they must NOT be labeled `FINANCIAL` either — that would be writing false data.

Default: `DEDICATED_STRATEGY_ONLY` with `dedicated_strategy_type = UNCLASSIFIED_HOLDING`

This is semantically honest: the holding has no clear sector, so it's kept outside the Core without asserting a nature it may not have. The `UNCLASSIFIED_HOLDING` type explicitly signals "needs individual review to enter Core or be reclassified."

**Allowlist for CORE_ELIGIBLE** (issuers with clear operational activity):

| CVM | Company | Justification |
|-----|---------|---------------|
| 020044 | CSU Digital S.A. | Serviços digitais — operacional |
| 016632 | Dexxos Participações S.A. | Indústria química — operacional |
| 025712 | GPS Participações S.A. | Serviços de facilities — operacional |
| 022586 | MLOG S.A. | Logística — operacional |
| 027600 | Porto Serviço S.A. | Serviços — operacional |

The remaining ~24 holdings stay in `DEDICATED_STRATEGY_ONLY / UNCLASSIFIED_HOLDING` until individual review promotes them. **False negative (missing from Core) is safer than false positive (leaking into Core).**

### D6 — `Hospedagem e Turismo` → `PERMANENTLY_EXCLUDED`

Tourism/hospitality. Reason: `TOURISM_HOSPITALITY`.

### D7 — Financial sectors → `DEDICATED_STRATEGY_ONLY`

All financial CVM sectors:
- `Bancos` (25)
- `Seguradoras e Corretoras` (4)
- `Intermediação Financeira` (4)
- `Securitização de Recebíveis` (21)
- `Bolsas de Valores/Mercadorias e Futuros` (1)
- `Arrendamento Mercantil` (3)
- `Crédito Imobiliário` (1)
- All `Emp. Adm. Part.` variants of the above

All with `dedicated_strategy_type = FINANCIAL`.

### D8 — Airlines → `PERMANENTLY_EXCLUDED` via override

Only GOL (019569) and Azul (024112). Override list. Reason: `AIRLINE`.

### D9 — NULL sector → **fail-closed, override required**

8 issuers with NULL sector. All are foreign-listed entities or the Ibovespa index.

**No implicit fallback.** Each must have an explicit override in `ISSUER_OVERRIDES`:

| CVM | Company | Override |
|-----|---------|---------|
| 080225 | Almacenes Éxito | PERMANENTLY_EXCLUDED (foreign retail) |
| 080187 | Aura Minerals | CORE_ELIGIBLE (mining, operational) |
| 080195 | G2D Investments | DEDICATED_STRATEGY_ONLY (investment vehicle) |
| 080020 | GP Investments | DEDICATED_STRATEGY_ONLY (PE fund) |
| 080217 | Inter & Co | DEDICATED_STRATEGY_ONLY (fintech/bank) |
| IBOV | Ibovespa Index | PERMANENTLY_EXCLUDED (not a company) |
| 080233 | JBS N.V. | CORE_ELIGIBLE (global food/protein, operational) |
| 080152 | PPLA Participations | DEDICATED_STRATEGY_ONLY (investment vehicle) |

### D10 — Passenger transport policy alignment

The investable universe matrix declares "aéreo / turismo / passageiros" as permanently excluded.

**Corpus evidence**: The only passenger transport companies in the DB are the 2 airlines (GOL, Azul). No bus operators, rail passenger companies, or other passenger transport entities exist in the CVM-sourced issuer population. Highway concessionaires (which make up the bulk of the transport sector) are infrastructure, not passenger transport.

**Implementation**: The `AIRLINE` and `TOURISM_HOSPITALITY` exclusion reasons cover all actual cases in the corpus. If a passenger transport company enters the DB in the future (e.g., bus operator), it would need to be added to `ISSUER_OVERRIDES` — same mechanism as airlines.

**Policy scope declaration**: v1 implements exclusion for `AIRLINE` and `TOURISM_HOSPITALITY`. The broader "passageiros" policy is satisfied because the corpus contains no other passenger transport companies. If new ones appear, the fail-closed mechanism (unmatched sector or missing override) would catch them before they could enter the Core.

---

## 8. Schema

### Enums

```python
class UniverseClass(str, Enum):
    CORE_ELIGIBLE = "CORE_ELIGIBLE"
    DEDICATED_STRATEGY_ONLY = "DEDICATED_STRATEGY_ONLY"
    PERMANENTLY_EXCLUDED = "PERMANENTLY_EXCLUDED"

class DedicatedStrategyType(str, Enum):
    FINANCIAL = "FINANCIAL"
    REAL_ESTATE_DEVELOPMENT = "REAL_ESTATE_DEVELOPMENT"
    UNCLASSIFIED_HOLDING = "UNCLASSIFIED_HOLDING"

class PermanentExclusionReason(str, Enum):
    RETAIL_WHOLESALE = "RETAIL_WHOLESALE"
    AIRLINE = "AIRLINE"
    TOURISM_HOSPITALITY = "TOURISM_HOSPITALITY"
    FOREIGN_RETAIL = "FOREIGN_RETAIL"
    NOT_A_COMPANY = "NOT_A_COMPANY"

class ClassificationRuleCode(str, Enum):
    SECTOR_MAP = "SECTOR_MAP"
    ISSUER_OVERRIDE = "ISSUER_OVERRIDE"
```

### Table: `universe_classifications`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | PK | |
| `issuer_id` | UUID FK→issuers | NOT NULL | |
| `universe_class` | enum UniverseClass | NOT NULL | |
| `dedicated_strategy_type` | enum DedicatedStrategyType | NULL | |
| `permanent_exclusion_reason` | enum PermanentExclusionReason | NULL | |
| `classification_rule_code` | enum ClassificationRuleCode | NOT NULL | |
| `classification_reason` | TEXT | NOT NULL | |
| `matched_sector_key` | TEXT | NULL | the SETOR_ATIV that matched (null for overrides) |
| `policy_version` | VARCHAR(20) | NOT NULL | |
| `classified_at` | TIMESTAMPTZ | NOT NULL | |
| `superseded_at` | TIMESTAMPTZ | NULL | NULL = active |

### Constraints

```sql
-- Only 1 active row per issuer
CREATE UNIQUE INDEX uq_universe_class_active
  ON universe_classifications (issuer_id)
  WHERE superseded_at IS NULL;

-- CORE_ELIGIBLE: no dedicated type, no exclusion reason
ALTER TABLE universe_classifications ADD CONSTRAINT chk_core_eligible
  CHECK (universe_class != 'CORE_ELIGIBLE'
    OR (dedicated_strategy_type IS NULL AND permanent_exclusion_reason IS NULL));

-- DEDICATED_STRATEGY_ONLY: must have dedicated type, no exclusion reason
ALTER TABLE universe_classifications ADD CONSTRAINT chk_dedicated
  CHECK (universe_class != 'DEDICATED_STRATEGY_ONLY'
    OR (dedicated_strategy_type IS NOT NULL AND permanent_exclusion_reason IS NULL));

-- PERMANENTLY_EXCLUDED: must have exclusion reason, no dedicated type
ALTER TABLE universe_classifications ADD CONSTRAINT chk_excluded
  CHECK (universe_class != 'PERMANENTLY_EXCLUDED'
    OR (dedicated_strategy_type IS NULL AND permanent_exclusion_reason IS NOT NULL));

-- SECTOR_MAP rule must have matched_sector_key
ALTER TABLE universe_classifications ADD CONSTRAINT chk_sector_map_key
  CHECK (classification_rule_code != 'SECTOR_MAP'
    OR matched_sector_key IS NOT NULL);
```

---

## 9. Idempotency Semantics

### Equality definition

The following 6 fields form the **identity tuple** for idempotency comparison:

1. `universe_class`
2. `dedicated_strategy_type`
3. `permanent_exclusion_reason`
4. `classification_rule_code`
5. `matched_sector_key`
6. `policy_version`

**`classification_reason` does NOT participate in the equality check.** It is a derived, deterministic, human-readable description computed from the identity tuple. It is always recomputed on insert but never triggers a supersede by itself. This is **Option A** — reason is output, not input.

### Algorithm

1. **Load all active classifications** (where `superseded_at IS NULL`) into a lookup by `issuer_id`
2. **For each issuer, compute the expected classification** (override or sector map)
3. **Compare the 6-field identity tuple with existing active row** (if any):
   - If no active row exists → INSERT new row
   - If active row exists with **identical identity tuple** → **NO-OP** (0 writes)
   - If active row exists but **any identity field differs** → SET `superseded_at = now()` on old row, INSERT new row
4. **After processing all issuers:**
   - If any unmatched sectors → raise `UnmatchedSectorBatchError` (nothing committed)
   - If any NULL-sector issuers without override → raise `MissingOverrideError` (nothing committed)
   - Otherwise → commit

**Rerun guarantee:** Running the classifier twice with the same policy version and no data changes produces **0 inserts and 0 supersedes**.

---

## 10. Complete Sector Mapping (v1)

### Reconciliation proof

| Group | Issuers | Sector values |
|-------|--------:|--------------:|
| CORE_ELIGIBLE (by sector) | 506 | 37 |
| DEDICATED_STRATEGY_ONLY / FINANCIAL | 72 | 12 |
| DEDICATED_STRATEGY_ONLY / REAL_ESTATE_DEVELOPMENT | 60 | 2 |
| DEDICATED_STRATEGY_ONLY / UNCLASSIFIED_HOLDING | 33 | 1 |
| PERMANENTLY_EXCLUDED | 62 | 4 |
| **Subtotal (non-null sector)** | **733** | **56** |
| NULL sector (override required) | 8 | n/a |
| **TOTAL** | **741** | — |

Verified: `SELECT count(*) FROM issuers` = 741. `SELECT count(DISTINCT sector) FROM issuers WHERE sector IS NOT NULL` = 56.

### Coverage

- **Non-null sectors**: 56/56 distinct values mapped (37 CORE + 12 FINANCIAL + 2 REAL_ESTATE + 1 UNCLASSIFIED_HOLDING + 4 EXCLUDED)
- **Null-sector issuers**: 8/8 covered by explicit `ISSUER_OVERRIDES`

### CORE_ELIGIBLE sectors (37 values, 506 issuers)

| SETOR_ATIV | Count |
|-----------|------:|
| Serviços Transporte e Logística | 89 |
| Energia Elétrica | 86 |
| Emp. Adm. Part. - Energia Elétrica | 32 |
| Saneamento, Serv. Água e Gás | 30 |
| Máquinas, Equipamentos, Veículos e Peças | 25 |
| Têxtil e Vestuário | 23 |
| Emp. Adm. Part. - Serviços Transporte e Logística | 21 |
| Metalurgia e Siderurgia | 17 |
| Comunicação e Informática | 17 |
| Serviços Médicos | 16 |
| Telecomunicações | 16 |
| Alimentos | 14 |
| Agricultura (Açúcar, Álcool e Cana) | 13 |
| Petróleo e Gás | 11 |
| Farmacêutico e Higiene | 11 |
| Petroquímicos e Borracha | 8 |
| Educação | 7 |
| Emp. Adm. Part. - Petróleo e Gás | 7 |
| Emp. Adm. Part. - Telecomunicações | 7 |
| Emp. Adm. Part. - Saneamento, Serv. Água e Gás | 6 |
| Brinquedos e Lazer | 5 |
| Emp. Adm. Part. - Educação | 5 |
| Emp. Adm. Part. - Comunicação e Informática | 5 |
| Emp. Adm. Part. - Alimentos | 4 |
| Papel e Celulose | 4 |
| Emp. Adm. Part. - Metalurgia e Siderurgia | 4 |
| Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças | 4 |
| Extração Mineral | 4 |
| Emp. Adm. Part. - Extração Mineral | 3 |
| Bebidas e Fumo | 2 |
| Emp. Adm. Part. - Agricultura (Açúcar, Álcool e Cana) | 2 |
| Emp. Adm. Part. - Têxtil e Vestuário | 2 |
| Embalagens | 2 |
| Emp. Adm. Part. - Serviços médicos | 1 |
| Reflorestamento | 1 |
| Emp. Adm. Part. - Brinquedos e Lazer | 1 |
| Emp. Adm. Part. - Papel e Celulose | 1 |
| **Subtotal** | **506** |

### DEDICATED_STRATEGY_ONLY sectors (15 values, 165 issuers)

| SETOR_ATIV | Count | dedicated_strategy_type |
|-----------|------:|------------------------|
| Construção Civil, Mat. Constr. e Decoração | 49 | REAL_ESTATE_DEVELOPMENT |
| Emp. Adm. Part. - Sem Setor Principal | 33 | UNCLASSIFIED_HOLDING |
| Bancos | 25 | FINANCIAL |
| Securitização de Recebíveis | 21 | FINANCIAL |
| Emp. Adm. Part. - Const. Civil, Mat. Const. e Decoração | 11 | REAL_ESTATE_DEVELOPMENT |
| Emp. Adm. Part. - Intermediação Financeira | 5 | FINANCIAL |
| Intermediação Financeira | 4 | FINANCIAL |
| Seguradoras e Corretoras | 4 | FINANCIAL |
| Emp. Adm. Part. - Crédito Imobiliário | 3 | FINANCIAL |
| Emp. Adm. Part. - Seguradoras e Corretoras | 3 | FINANCIAL |
| Arrendamento Mercantil | 3 | FINANCIAL |
| Crédito Imobiliário | 1 | FINANCIAL |
| Bolsas de Valores/Mercadorias e Futuros | 1 | FINANCIAL |
| Emp. Adm. Part. - Securitização de Recebíveis | 1 | FINANCIAL |
| Emp. Adm. Part. - Bancos | 1 | FINANCIAL |
| **Subtotal** | **165** |

### PERMANENTLY_EXCLUDED sectors (4 values, 62 issuers)

| SETOR_ATIV | Count | permanent_exclusion_reason |
|-----------|------:|--------------------------|
| Comércio (Atacado e Varejo) | 46 | RETAIL_WHOLESALE |
| Emp. Adm. Part. - Comércio (Atacado e Varejo) | 10 | RETAIL_WHOLESALE |
| Hospedagem e Turismo | 5 | TOURISM_HOSPITALITY |
| Emp. Adm. Part. - Hospedagem e Turismo | 1 | TOURISM_HOSPITALITY |
| **Subtotal** | **62** |

### NULL sector (8 issuers, handled by ISSUER_OVERRIDES)

See section 11.

---

## 11. Issuer Overrides

### Airlines (PERMANENTLY_EXCLUDED)

| CVM | Company | Reason |
|-----|---------|--------|
| 019569 | GOL Linhas Aéreas Inteligentes S.A. | AIRLINE |
| 024112 | Azul S.A. | AIRLINE |

### NULL sector (mandatory overrides)

**Note:** `ISSUER_OVERRIDES` is keyed by `cvm_code: str` (not int). All CVM codes are strings, including non-numeric ones like `"IBOV"`.

| CVM Code (str) | Company | Class | Type/Reason |
|----------------|---------|-------|-------------|
| "080225" | Almacenes Éxito S.A. | PERMANENTLY_EXCLUDED | FOREIGN_RETAIL |
| "080187" | Aura Minerals Inc. | CORE_ELIGIBLE | — |
| "080195" | G2D Investments, Ltd. | DEDICATED_STRATEGY_ONLY | FINANCIAL |
| "080020" | GP Investments, Ltd. | DEDICATED_STRATEGY_ONLY | FINANCIAL |
| "080217" | Inter & Co, Inc. | DEDICATED_STRATEGY_ONLY | FINANCIAL |
| "IBOV" | Ibovespa Index | PERMANENTLY_EXCLUDED | NOT_A_COMPANY |
| "080233" | JBS N.V. | CORE_ELIGIBLE | — |
| "080152" | PPLA Participations Ltd. | DEDICATED_STRATEGY_ONLY | FINANCIAL |

### Construção Civil allowlist (CORE_ELIGIBLE overrides)

These companies are reclassified from the sector default (`DEDICATED_STRATEGY_ONLY`) to `CORE_ELIGIBLE` because they are materials/industrial, not incorporadoras:

| CVM | Company | Justification |
|-----|---------|---------------|
| 021091 | Dexco S.A. | Painéis de madeira, louças — indústria |
| 005762 | Eternit S.A. | Telhas, caixas d'água — indústria |
| 005770 | Eucatex S.A. | Painéis, pisos, tintas — indústria |
| 025992 | Intercement Brasil S.A. | Cimento — indústria |
| 009717 | Portuense Ferragens S/A | Ferragens — indústria |
| 024236 | Priner Serviços Industriais S.A. | Serviços industriais |
| 010880 | Sondotecnica Eng. Solos S.A. | Engenharia geotécnica |
| 026255 | Tigre S.A. | Tubos, conexões — indústria |
| 022780 | Unicasa Ind. Móveis S.A. | Indústria moveleira |
| 027189 | Votorantim Cimentos S.A. | Cimento — indústria |

### Sem Setor Principal allowlist (CORE_ELIGIBLE overrides)

These companies are reclassified from the sector default (`DEDICATED_STRATEGY_ONLY / UNCLASSIFIED_HOLDING`) to `CORE_ELIGIBLE` because they are clearly operational:

| CVM | Company | Justification |
|-----|---------|---------------|
| 020044 | CSU Digital S.A. | Serviços digitais |
| 016632 | Dexxos Participações S.A. | Indústria química |
| 025712 | GPS Participações S.A. | Facilities management |
| 022586 | MLOG S.A. | Logística |
| 027600 | Porto Serviço S.A. | Serviços |

---

## 12. Appetite

**Level: Small (S)** — 4 build scopes

### Must-fit:
- Migration + models + dual ORM + check constraints
- Policy module (56 sectors + all overrides)
- Classifier with fail-closed + idempotency
- Backfill + validation

### First cuts:
- API endpoints → micro feature B
- Dashboard UI → micro feature B/C
- Historical policy comparison → future

---

## 13. Boundaries / No-Gos / Out of Scope

### Boundaries
- New `universe_classifications` table + 4 enums
- fundamentals-engine: new `universe/` package
- shared-models-py: new model
- Drizzle schema: new table + enums

### No-Gos
- Do NOT change ranking.py, thesis pipeline, refiner
- Do NOT create API endpoints
- Do NOT modify `issuer_classification` enum
- Do NOT implicitly classify any ambiguous case as CORE_ELIGIBLE

### Out of Scope
- Ranking pre-filter wiring (micro feature B)
- API endpoints (micro feature B)
- Parent-subsidiary propagation
- Dedicated strategy engines
- Manual override UI

---

## 14. Rabbit Holes / Hidden Risks

### RH1 — Sector value drift
New issuers may have sector values not in the mapping. **Fail-closed protects.**

### RH2 — Construção Civil false negatives
Some ambiguous companies (MRV, Tenda, Direcional) are large and operationally investable, but stay in DEDICATED_STRATEGY_ONLY in v1. **Acceptable — false negative safer than false positive. Can be promoted via allowlist update.**

### RH3 — Sem Setor Principal false negatives
Some operational holdings may be stuck in DEDICATED_STRATEGY_ONLY. **Same principle — promote via allowlist when individually verified.**

### RH4 — Ranking.py sector strings mismatch
Current `EXCLUDED_SECTORS = {"financeiro", "utilidade pública"}` doesn't match CVM values. Not touched in this micro feature. **Fixed in micro feature B.**

---

## 15. Build Scopes

### S1 — Migration + models + dual ORM
**Objective:** Create `universe_classifications` table, 4 pgEnums, partial unique index, check constraints. SQLAlchemy model + Drizzle schema.
**Done criteria:** Migration applies cleanly. Check constraints work. Both ORMs aligned.
**Validation:** `up` + `down` + `up`. Typecheck passes. Insert violating check constraint → error.

### S2 — Policy module + types
**Objective:** Create `universe/` package. All 56 sectors mapped. All overrides defined. `POLICY_VERSION = "v1"`.
**Done criteria:** `SECTOR_UNIVERSE_MAP` covers all 56 DB sectors. `ISSUER_OVERRIDES` covers 8 null-sector + 2 airlines + 10 construction allowlist + 5 sem-setor allowlist. Unit tests for every sector lookup, override, normalization, and error case.
**Validation:** Test asserts mapping covers every sector in the DB. Test asserts fail-closed on unknown sector.

### S3 — Classifier
**Objective:** Implement `classify_issuer()`, `classify_all()`, idempotency/supersede logic.
**Done criteria:** Fail-closed on unmatched. Fail-closed on null sector without override. Idempotent rerun = 0 writes. Supersede on policy change.
**Validation:** Unit tests for classify, idempotency, supersede, fail-closed errors.

### S4 — Backfill + validation report
**Objective:** Run classifier on all 741 issuers. Produce distribution report.
**Done criteria:** All issuers classified. Reports printed.
**Validation:**

| Check | Pass criteria |
|-------|---------------|
| V1 — Coverage | 741/741 issuers classified |
| V2 — Unmatched | 0 unmatched sectors |
| V3 — Idempotency | Rerun = 0 inserts, 0 supersedes |
| V4 — Policy version | All rows: policy_version='v1' |
| V5 — Distribution | Report: count per universe_class |
| V6 — Override spot-check | GOL=EXCLUDED, Azul=EXCLUDED, Cyrela=DEDICATED, Dexco=CORE, BNDESPAR=DEDICATED |
| V7 — Partial unique | Cannot insert 2 active rows for same issuer |
| V8 — Check constraints | CORE+dedicated_type → error. EXCLUDED+no_reason → error |

---

## 16. Close Summary

### Delivered

1. **S1 — Migration + models + dual ORM**: Migration `20260322_0020`, 4 pgEnums, `universe_classifications` table with partial unique index + 4 check constraints. SQLAlchemy model in shared-models-py. Drizzle schema aligned.
2. **S2 — Policy module**: `universe/` package in fundamentals-engine with `types.py` (4 enums), `policy.py` (56-sector mapping + 25 issuer overrides + fail-closed errors + lookup helper). `POLICY_VERSION = "v1"`.
3. **S3 — Classifier**: `classifier.py` with `classify_all()` — fail-closed, idempotent supersede, 6-field identity tuple.
4. **S4 — Backfill + validation**: `classify_universe.py` CLI. All 741 issuers classified. Distribution report.
5. **Tests**: 32 new tests (policy map counts, override spot-checks, normalization, lookup priority, error cases).

### Validation Evidence

| Check | Result |
|-------|--------|
| V1 — Coverage | **PASS**: 741/741 issuers classified |
| V2 — Unmatched | **PASS**: 0 unmatched sectors |
| V3 — Idempotency | **PASS**: Rerun = 0 inserts, 0 supersedes, 741 unchanged |
| V4 — Policy version | **PASS**: All rows policy_version='v1' |
| V5 — Distribution | **PASS**: 521 CORE + 154 DEDICATED + 66 EXCLUDED = 741 |
| V6 — Spot-checks | **PASS**: GOL=EXCLUDED/AIRLINE, Azul=EXCLUDED/AIRLINE, IBOV=EXCLUDED/NOT_A_COMPANY, Dexco=CORE, BNDESPAR=DEDICATED/UNCLASSIFIED_HOLDING, Cyrela=DEDICATED/REAL_ESTATE_DEVELOPMENT |
| V7 — Partial unique | **PASS**: Duplicate active row blocked |
| V8 — Check constraints | **PASS**: CORE+dedicated_type blocked, EXCLUDED without reason blocked |

### Distribution

| Class | Count | Breakdown |
|-------|------:|-----------|
| CORE_ELIGIBLE | 521 | 506 by sector + 15 overrides |
| DEDICATED_STRATEGY_ONLY | 154 | 76 FINANCIAL + 50 REAL_ESTATE_DEVELOPMENT + 28 UNCLASSIFIED_HOLDING |
| PERMANENTLY_EXCLUDED | 66 | 56 RETAIL_WHOLESALE + 6 TOURISM_HOSPITALITY + 2 AIRLINE + 1 FOREIGN_RETAIL + 1 NOT_A_COMPANY |
| **Total** | **741** | 716 SECTOR_MAP + 25 ISSUER_OVERRIDE |

### Known Limitations (from Tech Lead non-blocking observations)

1. G2D/GP/PPLA classified as `FINANCIAL` — could be `UNCLASSIFIED_HOLDING` in v2
2. D10 fail-closed only catches new/unmatched sectors — a new passenger company under `Serviços Transporte e Logística` would need manual override
3. R6 wording says "different class, reason, etc." but `classification_reason` does NOT participate in equality (source of truth is section 9)

### Tests

252 fundamentals-engine tests passing (220 existing + 32 new). 0 regressions.

---

## 17. Tech Lead Handoff

### What changed
- New table: `universe_classifications` with 4 pgEnums, partial unique index, 4 check constraints
- New package: `fundamentals-engine/src/.../universe/` (types, policy, classifier)
- New script: `fundamentals-engine/scripts/classify_universe.py`
- New tests: `tests/test_universe_classification.py` (32 tests)
- Models: `UniverseClassification` in shared-models-py
- Drizzle: `universeClassifications` + 4 enum exports in schema.ts

### What did NOT change
- ranking.py — no filter changes
- thesis pipeline — no filter changes
- refiner — no changes
- No API endpoints created

### Residual risks
- Construção Civil: 24 ambiguous issuers (MRV, Tenda, etc.) are in DEDICATED/REAL_ESTATE_DEVELOPMENT — may be false negatives for Core
- Sem Setor Principal: 24 issuers in UNCLASSIFIED_HOLDING — may include operational companies
- Sector drift: new CVM sectors will fail-closed, requiring policy update

### Where to start review
1. `universe/policy.py` — the 56-sector mapping and 25 overrides
2. `universe/classifier.py` — idempotency/supersede logic
3. Migration `20260322_0020` — check constraints
4. Distribution report output (section 16)
