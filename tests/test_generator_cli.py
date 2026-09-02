from bankdsl.generators.decision_report import _normalize_custom_args
from bankdsl.grammar import bank_credit_language


def test_language_registration_object_matches_textx_contract():
    assert bank_credit_language.name == "BankCreditDSL"
    assert bank_credit_language.pattern == "*.credit"
    assert callable(bank_credit_language.metamodel)


def test_normalize_custom_args_accepts_legacy_and_native_forms():
    legacy = {"custom_args": "application=examples/aplikacije/marko.json"}
    native = {"application": "examples/aplikacije/marko.json"}
    eq_style = {"application=examples/aplikacije/marko.json": True}

    assert _normalize_custom_args(legacy)["application"] == "examples/aplikacije/marko.json"
    assert _normalize_custom_args(native)["application"] == "examples/aplikacije/marko.json"
    assert _normalize_custom_args(eq_style)["application"] == "examples/aplikacije/marko.json"


def test_normalize_custom_args_rejects_missing_application():
    assert _normalize_custom_args({}) == {}
