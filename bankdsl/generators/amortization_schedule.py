"""
textX generator: 'amortization'

Koriscenje:
    textx generate examples/stambeni_kredit.credit --target amortization \
        --application examples/aplikacije/marko.json
"""
from os.path import dirname, join, basename, splitext
from pathlib import Path
import csv
import jinja2
from textx import generator

from bankdsl.interpreter.loader import find_product
from bankdsl.interpreter.application import Application
from bankdsl.interpreter.amortization import amortization_schedule

TEMPLATES_DIR = join(dirname(dirname(__file__)), "templates")
CSS_PATH = join(dirname(dirname(__file__)), "css", "report.css")


def _normalize_custom_args(custom_args):
    normalized = {}
    if not custom_args:
        return normalized

    for key, value in custom_args.items():
        if key == "custom_args" and isinstance(value, str):
            for raw in value.split():
                if "=" not in raw:
                    continue
                item_key, item_value = raw.split("=", 1)
                normalized[item_key.strip().replace("-", "_")] = item_value.strip("\"'")
            continue

        if isinstance(key, str) and "=" in key:
            left, right = key.split("=", 1)
            normalized[left.strip().replace("-", "_")] = right.strip("\"'")
            continue

        if key is not None:
            normalized[str(key).strip().replace("-", "_")] = value

    return normalized


def _jinja_env():
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        trim_blocks=True, lstrip_blocks=True,
    )


def _try_pdf(html_path, pdf_path):
    try:
        from xhtml2pdf import pisa

        with open(html_path, "r", encoding="utf-8") as html_file:
            html = html_file.read()

        with open(pdf_path, "wb") as pdf_file:
            result = pisa.CreatePDF(
                html,
                dest=pdf_file
            )

        if result.err:
            raise RuntimeError("xhtml2pdf failed to generate PDF.")

        return True

    except Exception as e:
        print(f"[amortization] PDF generisanje preskoceno ({e}).")
        return False


@generator("BankCreditDSL", "amortization")
def amortization_generator(metamodel, model, output_path, overwrite, debug, **custom_args):
    """Generise CSV i HTML amortizacioni plan za dati zahtev klijenta."""
    
    normalized_custom_args = _normalize_custom_args(custom_args)
    application_path = normalized_custom_args.get("application")
    if not application_path:
        raise ValueError(
            "Nedostaje application=<putanja_do_json_aplikacije> "
            "(podrzano i kao --custom-args application=... )"
        )

    application_path = str(Path(application_path).expanduser())
    if not Path(application_path).is_absolute():
        application_path = str((Path.cwd() / application_path).resolve())

    application = Application.from_json_file(application_path)
    product = find_product(model, application.product_name, version=application.product_version)
    
    result = amortization_schedule(
        product, 
        principal=application.requested_amount, 
        n_months=application.requested_term
    )

    out_dir = output_path if output_path else dirname(model._tx_filename)
    base_name = splitext(basename(application_path))[0]
    csv_path = join(out_dir, f"{base_name}_amortizacija.csv")
    html_path = join(out_dir, f"{base_name}_amortizacija.html")
    pdf_path = join(out_dir, f"{base_name}_amortizacija.pdf")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        schedule_sr = []
        for row in result["schedule"]:
            schedule_sr.append({
                "mesec": row["month"],
                "rata": row["payment"],
                "kamata": row["interest"],
                "glavnica": row["principal"],
                "preostalo": row["balance"]
            })
        
        writer = csv.DictWriter(f, fieldnames=["mesec", "rata", "kamata", "glavnica", "preostalo"])
        writer.writeheader()
        writer.writerows(schedule_sr)

    env = _jinja_env()
    template = env.get_template("amortization.j2")
    html = template.render(result=result, css_path=CSS_PATH)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    _try_pdf(html_path, pdf_path)

    output_files = f"{csv_path}, {html_path}"
    if Path(pdf_path).exists():
        output_files += f", {pdf_path}"

    print(f"[amortization] Mesečna rata: {result['regular_installment']} | Generisani fajlovi: {output_files}")
    return html_path