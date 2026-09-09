"""
CLI za interaktivni proces odobravanja - svaki poziv je NEZAVISAN pokretanje
programa (kao sto bi bilo da ga zovu razliciti ljudi u razlicito vreme).
Stanje se cuva u bankdsl/storage/bankdsl.sqlite3 izmedju poziva.

Koriscenje:
    bankdsl-process start <fajl.credit> --application <zahtev.json>
    bankdsl-process advance <process_id> --role <ImeUloge> <fajl.credit>
    bankdsl-process status <process_id>
"""
import json
import click

from bankdsl.storage.db import get_connection
from bankdsl.interpreter.loader import load_model, find_product, resolve_product_workflow
from bankdsl.interpreter.application import Application
from bankdsl.interpreter.process_session import start_process, advance_process, get_process_status


@click.group()
def cli():
    """Interaktivni procesni motor za BankCreditDSL."""


@cli.command()
@click.argument("credit_file")
@click.option("--application", required=True, help="Putanja do JSON zahteva klijenta.")
def start(credit_file, application):
    """Pokrece nov proces odobravanja za dati zahtev - staje na prvi korak."""
    conn = get_connection()
    model = load_model(credit_file)
    app = Application.from_json_file(application)
    product = find_product(model, app.product_name, app.product_version)
    workflow = resolve_product_workflow(model, product)

    process_id = start_process(conn, product, workflow, app)
    first_step = workflow.steps[0]
    click.echo(f"Proces #{process_id} pokrenut za '{app.applicant_name}'.")
    click.echo(f"Ceka se korak '{first_step.name}' (uloga: {first_step.role.name}).")
    conn.close()


@cli.command()
@click.argument("credit_file")
@click.argument("process_id", type=int)
@click.option("--role", required=True, help="Ime uloge koja pokusava da izvrsi trenutni korak.")
def advance(credit_file, process_id, role):
    """Pokusava da odradi TRENUTNI korak procesa u datoj ulozi."""
    conn = get_connection()
    model = load_model(credit_file)
    actor_role = next((r for r in model.roles if r.name == role), None)
    if actor_role is None:
        raise click.ClickException(f"Uloga '{role}' ne postoji u modelu.")

    instance = get_process_status(conn, process_id)
    product = find_product(
        model,
        instance["product"].split(" v")[0],
        instance["product"].split(" v")[1],
    )
    workflow = resolve_product_workflow(model, product)

    try:
        result = advance_process(conn, process_id, workflow, actor_role)
    except PermissionError as e:
        raise click.ClickException(str(e))

    if result["finished"]:
        click.echo(
            f"Korak '{result['executed_step']}' izvrsen. "
            f"Proces #{process_id} ZAVRSEN -> {result['final_state']}."
        )
    else:
        click.echo(
            f"Korak '{result['executed_step']}' izvrsen. "
            f"Sledeci korak: '{result['next_step']}'."
        )
    conn.close()


@cli.command()
@click.argument("process_id", type=int)
def status(process_id):
    """Prikazuje trenutno stanje i istoriju procesa."""
    conn = get_connection()
    info = get_process_status(conn, process_id)
    click.echo(json.dumps(info, indent=2, ensure_ascii=False))
    conn.close()


if __name__ == "__main__":
    cli()