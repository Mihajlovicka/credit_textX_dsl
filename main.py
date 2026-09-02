from pathlib import Path

from textx import metamodel_from_file

from bankdsl.scope import register_scopes

ROOT = Path(__file__).resolve().parent


def main():
    grammar_path = ROOT / "bankdsl" / "grammar" / "credit.tx"
    example_path = ROOT / "examples" / "stambeni_kredit.credit"

    metamodel = metamodel_from_file(str(grammar_path))
    register_scopes(metamodel)
    metamodel.model_from_file(str(example_path))

    print("DSL is valid!")


if __name__ == "__main__":
    main()