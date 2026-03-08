"""Tests for PII detection module."""

from q3_ai_assistant.security.pii_detector import contains_pii, detect_pii, redact_pii


class TestDetectPII:
    def test_detects_cpf_formatted(self):
        matches = detect_pii("CPF do cliente: 123.456.789-09")
        assert len(matches) == 1
        assert matches[0].pii_type == "cpf"
        assert matches[0].value == "123.456.789-09"

    def test_detects_cpf_unformatted(self):
        matches = detect_pii("CPF 12345678909")
        assert len(matches) == 1
        assert matches[0].pii_type == "cpf"

    def test_detects_cnpj_formatted(self):
        matches = detect_pii("CNPJ: 12.345.678/0001-90")
        assert len(matches) == 1
        assert matches[0].pii_type == "cnpj"

    def test_detects_cnpj_unformatted(self):
        matches = detect_pii("CNPJ 12345678000190")
        assert len(matches) == 1
        assert matches[0].pii_type == "cnpj"

    def test_detects_email(self):
        matches = detect_pii("Contato: user@example.com")
        assert len(matches) == 1
        assert matches[0].pii_type == "email"

    def test_detects_phone(self):
        matches = detect_pii("Telefone: (11) 99999-1234")
        assert len(matches) == 1
        assert matches[0].pii_type == "phone"

    def test_detects_credit_card(self):
        matches = detect_pii("Cartao: 4111 1111 1111 1111")
        assert len(matches) == 1
        assert matches[0].pii_type == "credit_card"

    def test_no_pii_in_clean_text(self):
        matches = detect_pii("WEGE3 tem earnings_yield de 8.5% e ROIC de 25%")
        assert len(matches) == 0

    def test_multiple_pii_types(self):
        text = "CPF 12345678909 e email user@test.com"
        matches = detect_pii(text)
        types = {m.pii_type for m in matches}
        assert "cpf" in types
        assert "email" in types

    def test_match_positions(self):
        text = "abc 123.456.789-09 xyz"
        matches = detect_pii(text)
        assert matches[0].start == 4
        assert matches[0].end == 18


class TestContainsPII:
    def test_true_when_pii_present(self):
        assert contains_pii("CPF: 123.456.789-09") is True

    def test_false_when_clean(self):
        assert contains_pii("Analise fundamentalista de WEGE3") is False


class TestRedactPII:
    def test_redacts_cpf(self):
        result = redact_pii("CPF: 123.456.789-09")
        assert "[CPF_REDACTED]" in result
        assert "123.456.789-09" not in result

    def test_redacts_email(self):
        result = redact_pii("Email: user@test.com aqui")
        assert "[EMAIL_REDACTED]" in result
        assert "user@test.com" not in result

    def test_no_change_when_clean(self):
        text = "ROIC de 25%"
        assert redact_pii(text) == text

    def test_redacts_multiple(self):
        text = "CPF 12345678909 e email user@test.com"
        result = redact_pii(text)
        assert "[CPF_REDACTED]" in result
        assert "[EMAIL_REDACTED]" in result

    def test_frozen_match(self):
        matches = detect_pii("CPF: 123.456.789-09")
        try:
            matches[0].pii_type = "hacked"  # type: ignore[misc]
            assert False, "PIIMatch should be frozen"
        except AttributeError:
            pass
