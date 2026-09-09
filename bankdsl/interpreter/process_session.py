"""
Interaktivni procesni motor - za razliku od process_engine.run_process()
(koji simulira ceo tok u JEDNOM pozivu), ovaj modul čuva stanje procesa u
bazi (storage/), tako da se proces zaista "zamrzava" između koraka: jedan
akter pozove start_process(), neko sasvim drugi (druga uloga, drugi poziv
programa, drugi dan) kasnije pozove advance_process() da odradi SVOJ korak.

Ovo je runtime kontrola pristupa: ako pogresna uloga pokusa da odradi
trenutni korak, advance_process() baca PermissionError i NISTA se ne
menja u bazi (stanje ostaje kakvo je bilo pre poziva).
"""
import json

from bankdsl.interpreter.evaluator import evaluate
from bankdsl.interpreter.process_engine import entry_step, is_decision_point, find_step
from bankdsl.storage.repository import (
    save_application, get_application_by_id,
    create_process_instance, get_process_instance, update_process_instance,
    log_process_step, get_process_log,
)


def start_process(conn, product, workflow, application):
    """
    Registruje NOV zahtev i pokrece za njega proces odobravanja - proces
    stoji na pocetnom koraku i CEKA da ga neko sa odgovarajucom ulogom
    odradi (start ne izvrsava nijedan korak sam).

    Vraca process_id (koristi se u svim narednim pozivima).
    """
    application_id = save_application(conn, application)
    step = entry_step(workflow)
    process_id = create_process_instance(conn, application_id, product, workflow, step.name)
    return process_id


def get_process_status(conn, process_id):
    """Trenutno stanje procesa + istorija odradjenih koraka (za prikaz/UI)."""
    instance = get_process_instance(conn, process_id)
    if instance is None:
        raise ValueError(f"Proces sa id={process_id} ne postoji.")
    log = get_process_log(conn, process_id)
    return {
        "process_id": process_id,
        "status": instance["status"],
        "current_step": instance["current_step"],
        "final_state": instance["final_state"],
        "product": f"{instance['product_name']} v{instance['product_version']}",
        "workflow": f"{instance['workflow_name']} v{instance['workflow_version']}",
        "history": [
            {
                "step": row["step_name"],
                "required_role": row["required_role"],
                "executed_by_role": row["executed_by_role"],
                "output": json.loads(row["output_json"]),
                "executed_at": row["executed_at"],
            }
            for row in log
        ],
    }


def advance_process(conn, process_id, workflow, actor_role):
    """
    Pokusava da odradi TRENUTNI korak procesa u ulozi 'actor_role'.

    - Ako je proces vec zavrsen -> ValueError (nema se sta odraditi).
    - Ako 'actor_role' NIJE uloga koju trenutni korak zahteva -> PermissionError,
      i stanje procesa OSTAJE NEPROMENJENO (mozes probati ponovo, sa pravom ulogom,
      makar to bio sasvim drugi poziv programa/drugog dana).
    - Ako jeste ispravna uloga -> korak se izvrsava, stanje se pamti u bazi,
      i vraca se info o tome sta je sledece (naredni korak, ili kraj procesa).

    Product se ne prosledjuje direktno - potreban je samo za evaluate(), a
    application/product referenca vec je sacuvana u bazi preko process_id-a,
    zato ovde product mora eksplicitno da se ucita/prosledi od strane pozivaoca
    (loader.find_product + loader.resolve_product_workflow daju i product i workflow).
    """
    instance = get_process_instance(conn, process_id)
    if instance is None:
        raise ValueError(f"Proces sa id={process_id} ne postoji.")
    if instance["status"] == "finished":
        raise ValueError(
            f"Proces #{process_id} je vec zavrsen (konacno stanje: {instance['final_state']})."
        )

    current = find_step(workflow, instance["current_step"])

    if actor_role.name != current.role.name:
        raise PermissionError(
            f"Korak '{current.name}' zahteva ulogu '{current.role.name}', "
            f"a pokusava da ga izvrsi '{actor_role.name}'. Proces #{process_id} "
            f"ostaje na istom koraku - probaj ponovo sa ispravnom ulogom."
        )

    application = get_application_by_id(conn, instance["application_id"])

    # 'product' je potreban samo za evaluate() - loader ga daje pozivaocu
    # zajedno sa workflow-om, pa ga ovde rekonstruisemo iz iste baze bez
    # da pozivalac mora rucno da ga prenosi kroz svaki advance() poziv.
    from bankdsl.interpreter.loader import find_product
    from textx import get_model
    model = get_model(workflow)
    product = find_product(model, application.product_name, application.product_version)

    on_reject = getattr(current, "on_reject", None)
    on_success = getattr(current, "on_success", None)
    next_node = getattr(current, "next", None)

    if is_decision_point(current):
        if instance["evaluation_json"] is not None:
            evaluation = json.loads(instance["evaluation_json"])
        else:
            evaluation = evaluate(product, application)
            update_process_instance(
                conn, process_id,
                evaluation_json=json.dumps(evaluation, ensure_ascii=False),
            )
        output = evaluation
        passed = evaluation["decision"] == "ODOBREN"
    else:
        output = {
            "step": current.name, "role": current.role.name,
            "action": current.action, "applicant": application.applicant_name,
        }
        passed = True

    log_process_step(conn, process_id, current.name, current.role.name, actor_role.name, output)

    finished, final_state, next_step_name = False, None, None

    if is_decision_point(current):
        if not passed and on_reject is not None:
            finished, final_state = True, on_reject.name
        elif passed and next_node is None and on_success is not None:
            finished, final_state = True, on_success.name

    if not finished:
        if next_node is None:
            finished, final_state = True, current.name
        else:
            next_step_name = next_node.name

    if finished:
        update_process_instance(conn, process_id, status="finished", final_state=final_state, current_step=None)
    else:
        update_process_instance(conn, process_id, current_step=next_step_name)

    return {
        "process_id": process_id,
        "executed_step": current.name,
        "finished": finished,
        "final_state": final_state,
        "next_step": next_step_name,
        "output": output,
    }
