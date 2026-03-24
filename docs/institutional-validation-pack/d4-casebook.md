# Casebook — 5 Studies + 1 Appendix

---

## Case 1: VLID3 — Approved (correct)

**Thesis**: Valid (formerly Idwall) shows strong quality with high EY and consistent operations.

**Inputs**: Quality 0.71 (HIGH) | EY 23.6% | Sector pctl 93 | Yield 42.1% (outlier flagged) | Confidence MEDIUM | 4 drivers, 0 risks

**Decision**: APPROVED — "Qualidade adequada, valuation favorável, yield acima do mínimo"

**Drivers**: ROIC crescente, margem em expansão, forte geração de caixa, dividendos consistentes

**Human counterargument**: Yield of 42.1% is flagged as outlier. An analyst might question whether this reflects genuine value or EV distortion. The sector pctl of 93 is very high — is the sector comparison valid?

**Validation proxy**: Quality score 0.71 is the highest among APPROVED names. Zero risks. The outlier flag on yield is informational, not blocking — correctly distinguished from proxy suppression.

**Lesson**: High-quality names with outlier yields should be flagged but not rejected. The system correctly separates "unusual" from "wrong."

---

## Case 2: CMIG3 — Approved (correct)

**Thesis**: CEMIG (utility) shows solid quality with large DY and cheap valuation despite sector fallback.

**Inputs**: Quality 0.61 (MEDIUM) | EY 17.7% | Sector pctl 85.9 | DY 9.5% | Yield 27.2% | Confidence MEDIUM (sector fallback penalty) | 3 drivers, 0 risks

**Decision**: APPROVED — quality adequate, valuation favorable

**Drivers**: ROIC crescente (+353% — base effect), dividendos consistentes (DY 9.5%), margem líquida em compressão (-3.5%)

**Human counterargument**: ROIC increase of 353% is likely base effect (low prior period), not sustainable improvement. Margin compression is actually a negative signal included as a driver — should it reduce confidence? Sector fallback means utility sector has < 5 comparable issuers.

**Validation proxy**: Despite mixed drivers, the core thesis is sound: cheap utility with high DY and acceptable quality. The system correctly approved despite imperfect evidence.

**Lesson**: Base effects in YoY metrics need future classification (e.g., flag when prior period was abnormally low). Driver quality ≠ driver quantity.

---

## Case 3: SNSY3 — Rejected (correct)

**Thesis**: Sansuy has extreme EY (110.7%) but critical financial risk.

**Inputs**: Quality 0.34 (LOW) | EY 110.7% (outlier) | Yield 110.7% (outlier) | Interest coverage 0.9x | 1 driver, 1 critical risk

**Decision**: REJECTED — "Risco crítico: Cobertura de juros baixa (0.9x)"

**Drivers**: Only 1 (margem em expansão)

**Risk**: Interest coverage below 1.0x — the company cannot cover its debt service from operating income.

**Human counterargument**: An aggressive analyst might argue the extreme cheapness (110% EY) compensates for the risk. The company could refinance or restructure.

**Validation proxy**: Interest coverage < 1.0x is a hard rejection gate. This is correct — at 0.9x, the company is structurally impaired regardless of valuation.

**Lesson**: Extreme cheapness and critical risk often coexist. The system correctly prioritizes solvency over valuation.

---

## Case 4: ABEV3 — Blocked (correct)

**Thesis**: Ambev is a high-quality blue chip (quality 0.64) with FAIR valuation, but blocked by LOW_CONFIDENCE.

**Inputs**: Quality 0.64 (MEDIUM) | EY 10.3% | Valuation FAIR | Yield 12.5% | Confidence LOW (thesis missing) | 3 drivers, 0 risks

**Decision**: BLOCKED (LOW_CONFIDENCE) — "Evidência insuficiente para decisão"

**Block cause**: Confidence score penalized because thesis data is missing (no Plan 2 commodity/fragility assessment).

**Human counterargument**: Ambev is one of the most well-known companies in Brazil. An analyst would have strong priors. The quality score is adequate. Why block?

**Validation proxy**: The system is correct to block: without thesis data, the confidence framework can't assess fragility. A company with hidden USD debt exposure or import dependence might look safe on fundamentals alone. Blocking is prudent, not wrong.

**Lesson**: The system treats "unknown" as different from "safe." This is the right institutional behavior. BLOCKED ≠ bad; BLOCKED = insufficient evidence.

---

## Case 5: KEPL3 — Blocked (debatable)

**Thesis**: Kepler Weber shows decent quality (0.58) and strong yield (35.9%) but is BLOCKED by LOW_CONFIDENCE.

**Inputs**: Quality 0.58 (MEDIUM) | EY 24.9% | Sector pctl 91.8 | Yield 35.9% | Confidence LOW | 3 drivers, 0 risks

**Decision**: BLOCKED (LOW_CONFIDENCE)

**Block cause**: Thesis data missing → confidence penalized below MEDIUM threshold.

**Human counterargument**: Quality 0.58 is reasonable. Yield 35.9% is strong. Zero risks. The company has refiner data (unlike many BLOCKEDs). An analyst would likely APPROVE this. The block seems overly cautious.

**System's defense**: Without thesis assessment, the system can't rule out fragility risks (USD debt, import dependence). The 0.10 thesis penalty pushes confidence from ~0.45 to ~0.35, crossing the MEDIUM→LOW boundary.

**Validation proxy**: This is a **prudent false negative** — the system errs on the side of caution. If thesis data were available (coverage expansion), this would likely flip to APPROVED.

**Lesson**: The confidence penalty system is calibrated conservatively. When multiple small penalties stack (sector fallback + thesis missing), they can block fundamentally sound names. This is acceptable for a research tool but could be recalibrated if coverage expands.

---

## Appendix: CEDO3 — Approved with Suppressed Valuation

**Thesis**: Cedro Cachoeira shows good quality but extreme EY normalization distortion.

**Inputs**: Quality 0.60 (MEDIUM) | EY 34.8% | Sector pctl 95.8 | Yield 34.8% | Implied price R$237 vs current R$10 | Confidence MEDIUM

**Decision**: APPROVED — quality + valuation + yield all pass thresholds

**Suppression**: Implied value range SUPPRESSED (upside 2,258% exceeds 300% sanity limit).

**What the UI shows**: Valuation label "CHEAP" preserved. Implied value range shows "Proxy valuation unavailable" with hover tooltip explaining: "Proxy suppressed: implied upside 2258% exceeds sanity limit. Likely EV distortion."

**Human counterargument**: If the proxy says R$237 and the stock trades at R$10, either the proxy is wrong or the stock is extraordinarily cheap. The system can't distinguish — so it suppresses the number and lets the label speak.

**Validation proxy**: The sector median EY of 9.6% vs CEDO3's 34.8% creates extreme normalization. The suppression is correct: showing R$237 as "implied value" for a R$10 stock would be misleading.

**Lesson**: Suppression is not failure — it's honesty. The system preserves the qualitative signal (CHEAP) while hiding the quantitatively distorted number. This is the correct behavior for a financial product.
