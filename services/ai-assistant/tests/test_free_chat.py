"""Tests for free chat module — intent detection and context gathering."""

from __future__ import annotations

from q3_ai_assistant.modules.free_chat import _detect_intent


class TestDetectIntent:
    def test_general_query(self):
        intent = _detect_intent("O que e a Magic Formula?")
        assert intent["type"] == "strategy"
        assert intent["tickers"] == []

    def test_ticker_detection_single(self):
        intent = _detect_intent("Me fale sobre WEGE3")
        assert "WEGE3" in intent["tickers"]
        assert intent["type"] == "company"

    def test_ticker_detection_multiple(self):
        intent = _detect_intent("Compare BBAS3 e ITUB4")
        assert "BBAS3" in intent["tickers"]
        assert "ITUB4" in intent["tickers"]

    def test_lineage_query(self):
        intent = _detect_intent("De onde vem o ROIC de WEGE3?")
        assert intent["type"] == "lineage"
        assert "WEGE3" in intent["tickers"]

    def test_strategy_keyword(self):
        intent = _detect_intent("Como funciona a estrategia de ranking?")
        assert intent["type"] == "strategy"

    def test_metric_concept_no_ticker(self):
        intent = _detect_intent("O que e ROIC?")
        assert intent["type"] == "metric_concept"
        assert "roic" in intent["metrics"]

    def test_metric_with_ticker(self):
        intent = _detect_intent("Qual o ROIC de RENT3?")
        assert "RENT3" in intent["tickers"]
        assert "roic" in intent["metrics"]
        assert intent["type"] == "company"

    def test_no_false_positives(self):
        intent = _detect_intent("Bom dia, tudo bem?")
        assert intent["type"] == "general"
        assert intent["tickers"] == []
        assert intent["metrics"] == []

    def test_greenblatt_is_strategy(self):
        intent = _detect_intent("Explique a formula do Greenblatt")
        assert intent["type"] == "strategy"

    def test_multiple_metrics(self):
        intent = _detect_intent("O que e melhor entre ROE e margem EBIT?")
        assert "roe" in intent["metrics"]
        assert "ebit" in intent["metrics"]

    def test_origem_fonte_triggers_lineage(self):
        intent = _detect_intent("Qual a fonte dos dados de TAEE11?")
        assert intent["type"] == "lineage"
        assert "TAEE11" in intent["tickers"]

    def test_ticker_4_digits(self):
        intent = _detect_intent("Analise PETR4")
        assert "PETR4" in intent["tickers"]

    def test_ticker_11_suffix(self):
        intent = _detect_intent("O que voce acha de TAEE11?")
        assert "TAEE11" in intent["tickers"]
