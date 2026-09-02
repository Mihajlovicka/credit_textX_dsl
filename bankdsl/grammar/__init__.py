from os.path import dirname, join
from textx import language, metamodel_from_file

from bankdsl.scope import register_scopes


@language("BankCreditDSL", "*.credit")
def bank_credit_language():
    "DSL za definisanje bankarskih kreditnih proizvoda, uloga i procesa odobravanja."
    current_dir = dirname(__file__)
    mm = metamodel_from_file(join(current_dir, "credit.tx"))
    register_scopes(mm)
    return mm
