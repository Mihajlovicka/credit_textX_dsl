"""
Ucitavanje BankCreditDSL modela. Koristi textX metamodel registrovan
u bankdsl.grammar preko @language dekoratora, tako da vazi ista
gramatika koju koristi i CLI 'textx' alat.
"""

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
