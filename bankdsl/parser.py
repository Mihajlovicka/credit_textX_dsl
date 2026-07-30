from pathlib import Path

from textx import metamodel_from_file

from bankdsl.scope import register_scopes


GRAMMAR_PATH = Path(__file__).parent / "grammar" / "credit.tx"


def bankdsl_language():
    metamodel = metamodel_from_file(str(GRAMMAR_PATH))

    register_scopes(metamodel)

    return metamodel