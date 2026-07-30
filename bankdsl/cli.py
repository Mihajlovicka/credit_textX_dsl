import click

from bankdsl.parser import bankdsl_language
from bankdsl.semantic.validation import validate_model


@click.command()
@click.argument("file")
def main(file):
    metamodel = bankdsl_language()

    model = metamodel.model_from_file(file)

    validate_model(model)

    click.echo("DSL is valid!")


if __name__ == "__main__":
    main()