from textx import metamodel_for_language

"""
Ucitavanje BankCreditDSL modela. Koristi textX metamodel registrovan
u bankdsl.grammar preko @language dekoratora, tako da vazi ista
gramatika koju koristi i CLI 'textx' alat.
"""

LANGUAGE_NAME = "BankCreditDSL"

def find_product(model, name, version=None):
    """
    Vraca proizvod po imenu i (opciono) verziji.
    Bez eksplicitne verzije vraca najnoviju po valid_from - ali u praksi
    ugovor UVEK treba da salje eksplicitnu verziju (vidi README - verzionisanje).
    """
    candidates = [p for p in model.products if p.name == name]
    if not candidates:
        raise ValueError(f"Proizvod '{name}' ne postoji.")
    if version:
        for p in candidates:
            if p.version == version:
                return p
        raise ValueError(f"Proizvod '{name}' nema verziju '{version}'.")
    return sorted(candidates, key=lambda p: p.valid_from or "")[-1]

def get_metamodel():
    return metamodel_for_language(LANGUAGE_NAME)


def load_model(path):
    mm = get_metamodel()
    return mm.model_from_file(path)

def find_workflow(model, name, version=None):
    """
    Vraca workflow po imenu i (opciono) verziji, analogno find_product.
    """
    candidates = [w for w in model.workflows if w.name == name]
    if not candidates:
        raise ValueError(f"Workflow '{name}' ne postoji.")
    if version:
        for w in candidates:
            if w.version == version:
                return w
        raise ValueError(f"Workflow '{name}' nema verziju '{version}'.")
    return candidates[-1]


def resolve_product_workflow(model, product):
    """
    Product.workflow je samo (workflow_name, workflow_version) par - nije
    textX referenca - pa ga rucno razresavamo na WorkflowDef objekat.
    """
    ref = product.workflow
    return find_workflow(model, ref.workflow_name, ref.workflow_version)