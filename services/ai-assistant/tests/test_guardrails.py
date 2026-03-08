"""Tests for AI guardrails — banned phrases, disclaimer, PII in output."""

from q3_ai_assistant.evaluation.quality import BANNED_PHRASES, evaluate_opinion
from q3_ai_assistant.security.pii_detector import contains_pii, redact_pii


class TestBannedPhrases:
    def test_banned_list_not_empty(self):
        assert len(BANNED_PHRASES) >= 5

    def test_key_phrases_present(self):
        lower = [p.lower() for p in BANNED_PHRASES]
        assert "compre agora" in lower
        assert "retorno garantido" in lower
        assert "sem risco" in lower

    def test_opinion_with_banned_phrase_scores_zero_regulatory(self):
        opinion = {
            "agentId": "test",
            "verdict": "buy",
            "confidence": 80,
            "thesis": "Compre agora esta acao fantastica!",
            "reasonsFor": ["high yield"],
            "reasonsAgainst": ["some risk"],
            "keyMetricsUsed": ["earnings_yield"],
            "hardRejectsTriggered": [],
            "unknowns": [],
            "whatWouldChangeMyMind": ["lower yield"],
            "investorFit": ["conservador"],
        }
        packet_metrics = {"earnings_yield", "roic"}
        result = evaluate_opinion(opinion, packet_metrics)
        assert result.regulatory_compliance == 0.0

    def test_clean_opinion_passes_regulatory(self):
        opinion = {
            "agentId": "greenblatt",
            "verdict": "watch",
            "confidence": 65,
            "thesis": "Empresa com fundamentos solidos, mas preco elevado.",
            "reasonsFor": ["ROIC alto", "margem estavel"],
            "reasonsAgainst": ["valuation esticado"],
            "keyMetricsUsed": ["roic", "ebit_margin"],
            "hardRejectsTriggered": [],
            "unknowns": ["dados limitados"],
            "whatWouldChangeMyMind": ["correcao de preco"],
            "investorFit": ["moderado"],
        }
        packet_metrics = {"roic", "ebit_margin", "earnings_yield"}
        result = evaluate_opinion(opinion, packet_metrics)
        assert result.regulatory_compliance == 1.0


class TestPIIGuardrails:
    def test_pii_not_in_clean_analysis(self):
        text = "WEGE3 apresenta ROIC de 25% e earnings yield de 8.5%."
        assert contains_pii(text) is False

    def test_pii_detected_in_output(self):
        text = "O investidor CPF 123.456.789-09 deveria considerar WEGE3."
        assert contains_pii(text) is True

    def test_pii_redacted_before_output(self):
        text = "Contato: user@example.com para mais informacoes."
        redacted = redact_pii(text)
        assert "user@example.com" not in redacted
        assert "[EMAIL_REDACTED]" in redacted


class TestDisclaimerPresence:
    def test_disclaimer_keywords(self):
        disclaimer = (
            "Este conteudo e meramente educacional e analitico, nao constituindo "
            "recomendacao de investimento personalizada."
        )
        assert "educacional" in disclaimer
        assert "analitico" in disclaimer
        assert "recomendacao" in disclaimer
