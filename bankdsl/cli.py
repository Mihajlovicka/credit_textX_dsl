import click

from bankdsl.parser import bankdsl_language
from bankdsl.semantic.validation import validate_model


def _load_and_validate(file):
    model = bankdsl_language().model_from_file(file)
    validate_model(model)
    return model


@click.group()
def main():
    """Command-line tools for Bank Credit DSL."""


@main.command()
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False),
)
def validate(file):
    """Parse and semantically validate a .credit model."""

    _load_and_validate(file)

    click.echo("DSL is valid!")


@main.command()
@click.argument(
    "credit_file",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "--application",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the client application JSON file.",
)
@click.option(
    "--output-path",
    "output_path",
    default=None,
    type=click.Path(),
    help="Output path.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Allow overwriting existing output files.",
)
def report(credit_file, application, output_path, overwrite):
    from bankdsl.generators.decision_report import decision_report_generator

    model = _load_and_validate(credit_file)

    decision_report_generator.generator(
        bankdsl_language(),
        model,
        output_path,
        overwrite,
        False,
        application=application,
    )


@main.command()
@click.argument(
    "credit_file",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "--application",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the client application JSON file.",
)
@click.option(
    "--output-path",
    "output_path",
    default=None,
    type=click.Path(),
    help="Output path.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Allow overwriting existing output files.",
)
def amortization(credit_file, application, output_path, overwrite):
    from bankdsl.generators.amortization_schedule import amortization_generator

    model = _load_and_validate(credit_file)

    amortization_generator.generator(
        bankdsl_language(),
        model,
        output_path,
        overwrite,
        False,
        application=application,
    )


from bankdsl.process_cli import cli as process

main.add_command(process, name="process")

@main.command(name="workflow-report")
@click.argument(
    "credit_file",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "--application",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the client application JSON file.",
)
@click.option(
    "--output-path",
    "output_path",
    default=None,
    type=click.Path(),
    help="Output path.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Allow overwriting existing output files.",
)
def workflow_report(credit_file, application, output_path, overwrite):
    from bankdsl.generators.workflow_report import workflow_report_generator

    model = _load_and_validate(credit_file)

    workflow_report_generator.generator(
        bankdsl_language(),
        model,
        output_path,
        overwrite,
        False,
        application=application,
    )

if __name__ == "__main__":
    main()