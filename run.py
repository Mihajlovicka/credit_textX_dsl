"""
Jednostavne precice za najcesce komande - da ne moras da pamtis dugacke
'textx generate ...' linije. Pokreni iz korena projekta:

    python run.py report marko    -> HTML+PDF izvestaj o odluci
    python run.py process marko   -> ceo interaktivni proces, automatski,
                                      uz ispis koja uloga radi koji korak
    python run.py demo marko      -> isto, ali na svakom koraku PRVO
                                      proba pogresnu ulogu (da vidis
                                      da je odbijena), pa onda ispravnu
"""
import sys

from bankdsl.interpreter.loader import load_model, find_product, resolve_product_workflow, get_metamodel
from bankdsl.interpreter.application import Application

CREDIT_FILE = "examples/stambeni_kredit.credit"
OUT_DIR = "examples"


def cmd_report(name):
    """
    TESTIRA: eligibility logiku (evaluate()) direktno, bez procesa/uloga.
    Samo racuna ODOBREN/ODBIJEN i pravi HTML+PDF izvestaj sa objasnjenjem
    svakog pravila (koje je prosao, koje nije, koliki je skor).
    Koristi za: brzu proveru da li DSL pravila i dalje rade kako treba,
    nezavisno od procesa sa ulogama.
    """
    from bankdsl.generators.decision_report import decision_report_generator
    metamodel = get_metamodel()
    model = metamodel.model_from_file(CREDIT_FILE)
    decision_report_generator.generator(
        metamodel, model, OUT_DIR, True, False,
        application=f"examples/aplikacije/{name}.json",
    )


def cmd_process(name):
    """
    TESTIRA: da li ceo tok procesa (Prijem -> Analiza -> Odluka -> stanje)
    ispravno prolazi kad SVAKI korak odmah dobije TACNU ulogu.
    Ne testira sta se desava kad neko pogresi ulogu - za to koristi 'demo'.
    Koristi za: brzu proveru da proces uopste radi od pocetka do kraja,
    bez sumnje da li je neka veza (next/on_reject/on_success) pogresno
    povezana u DSL-u.
    """
    from bankdsl.storage.db import get_connection
    from bankdsl.interpreter.process_session import start_process, advance_process, get_process_status

    conn = get_connection()
    model = load_model(CREDIT_FILE)
    app = Application.from_json_file(f"examples/aplikacije/{name}.json")
    product = find_product(model, app.product_name, app.product_version)
    workflow = resolve_product_workflow(model, product)

    pid = start_process(conn, product, workflow, app)
    print(f"Pokrenut proces #{pid} za '{app.applicant_name}'.")

    while True:
        status = get_process_status(conn, pid)
        if status["status"] == "finished":
            print(f"  -> ZAVRSENO: {status['final_state']}")
            break
        step = next(s for s in workflow.steps if s.name == status["current_step"])
        result = advance_process(conn, pid, workflow, step.role)
        if result["finished"]:
            print(f"  [{result['executed_step']}] (uloga: {step.role.name}) -> ZAVRSENO: {result['final_state']}")
        else:
            print(f"  [{result['executed_step']}] (uloga: {step.role.name}) -> sledeci: {result['next_step']}")
    conn.close()


def cmd_demo(name):
    """
    TESTIRA: STVARNU proveru permisija (runtime access control) - glavnu
    poentu process_session.py. Na SVAKOM koraku:
      1) prvo namerno pokusava sa POGRESNOM ulogom
         -> OCEKIVANO: PermissionError, stanje procesa se NE menja
      2) tek onda pokusava sa ISPRAVNOM ulogom (onom iz 'handled_by' u DSL-u)
         -> OCEKIVANO: korak prolazi, proces ide na sledeci korak/stanje

    Za Marka (ispunjava sve uslove): ocekuj sva 3 koraka (Prijem, Analiza,
    Odluka) da prodju, zavrsno stanje 'Odobreno'.

    Za Anu (NE ispunjava uslove): ocekuj da se proces zavrsi vec posle
    koraka 'Analiza' (grana direktno na 'Odbijeno') - korak 'Odluka' se
    NIKAD ne pokusava, jer vise nema potrebe (kratak spoj u granjenju).

    Koristi za: demonstraciju na odbrani/prezentaciji - ovo najbolje
    pokazuje da uloge/permisije nisu samo tekst u gramatici, nego se
    stvarno primenjuju dok proces radi.
    """
    from bankdsl.storage.db import get_connection
    from bankdsl.interpreter.process_session import start_process, advance_process, get_process_status

    conn = get_connection()
    model = load_model(CREDIT_FILE)
    app = Application.from_json_file(f"examples/aplikacije/{name}.json")
    product = find_product(model, app.product_name, app.product_version)
    workflow = resolve_product_workflow(model, product)

    pid = start_process(conn, product, workflow, app)
    print(f"Pokrenut proces #{pid} za '{app.applicant_name}'.\n")

    while True:
        status = get_process_status(conn, pid)
        if status["status"] == "finished":
            print(f"\n>>> PROCES ZAVRSEN -> {status['final_state']}")
            break

        step = next(s for s in workflow.steps if s.name == status["current_step"])
        correct_role = step.role

        # Namerno biramo BILO KOJU drugu ulogu (ne onu koju korak trazi),
        # da testiramo da je sistem stvarno odbija.
        wrong_role = next(r for r in model.roles if r.name != correct_role.name)

        print(f"Trenutni korak: '{step.name}' (zahteva ulogu: {correct_role.name})")

        # TEST 1: pogresna uloga -> MORA da baci PermissionError,
        # a stanje procesa MORA da ostane nepromenjeno (proveravano u
        # process_session.advance_process - baca gresku PRE ikakvog upisa u bazu).
        print(f"  Pokusaj sa POGRESNOM ulogom '{wrong_role.name}'...")
        try:
            advance_process(conn, pid, workflow, wrong_role)
            print("  !!! GRESKA - ovo NIJE trebalo da prodje !!!")
        except PermissionError as e:
            print(f"  -> odbijeno, kao sto treba: {e}")

        # TEST 2: ispravna uloga -> MORA da prodje, proces ide dalje
        # (ili se zavrsava, ako je ovo poslednji/odlucujuci korak).
        print(f"  Pokusaj sa ISPRAVNOM ulogom '{correct_role.name}'...")
        result = advance_process(conn, pid, workflow, correct_role)
        if result["finished"]:
            print(f"  -> prosao, korak ZAVRSAVA proces: {result['final_state']}\n")
        else:
            print(f"  -> prosao, sledeci korak: {result['next_step']}\n")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Koristi: python run.py <report|process|demo> [ime]")
        sys.exit(1)

    action = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else None

    if action == "report":
        cmd_report(name)
    elif action == "process":
        cmd_process(name)
    elif action == "demo":
        cmd_demo(name)
    else:
        print(f"Nepoznata akcija: '{action}'. Koristi report/process/demo.")