from textx import metamodel_from_file
from bankdsl.scope import register_scopes

def main():
    metamodel = metamodel_from_file(
        "bankdsl/grammar/credit.tx"
    )


    register_scopes(metamodel)


    model = metamodel.model_from_file(
        "examples/stambeni_kredit.credit"
    )

    print("DSL is valid!")

if __name__ == "__main__":
    main()