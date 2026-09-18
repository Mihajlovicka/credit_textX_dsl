"""
textX generator 'decision-report': evaluira zahtev (application JSON)
protiv proizvoda, upisuje rezultat u bazu i generise HTML/PDF izvestaj.

Koriscenje:
    textx generate examples/stambeni_kredit.credit --target decision-report \
        --application examples/aplikacije/marko.json
"""
from os.path import dirname, join, basename, splitext
from pathlib import Path

import jinja2
from textx import generator

from bankdsl.interpreter.loader import find_product
from bankdsl.interpreter.application import Application
from bankdsl.interpreter.evaluator import evaluate
from bankdsl.interpreter.fees import calculate_fees
from bankdsl.storage.db import get_connection
from bankdsl.storage.repository import save_product_version, save_application, save_decision

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


def _try_pdf(html_content, pdf_path):
    try:
        from xhtml2pdf import pisa

        char_map = {
            'č': 'c', 'ć': 'c', 'ž': 'z', 'š': 's', 'đ': 'd',
            'Č': 'C', 'Ć': 'C', 'Ž': 'Z', 'Š': 'S', 'Đ': 'D'
        }
        for sr_char, ascii_char in char_map.items():
            html_content = html_content.replace(sr_char, ascii_char)

        with open(pdf_path, "wb") as pdf_file:
            result = pisa.CreatePDF(
                html_content,
                dest=pdf_file
            )

        if result.err:
            raise RuntimeError("xhtml2pdf failed to generate PDF.")

        return True

    except Exception as e:
        print(f"[decision-report] PDF generisanje preskoceno ({e}).")
        return False


@generator("BankCreditDSL", "decision-report")
def decision_report_generator(metamodel, model, output_path, overwrite, debug, **custom_args):
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
    result = evaluate(product, application)

    fees_summary = calculate_fees(
        product, 
        application.requested_amount, 
        application.requested_term
    )

    conn = get_connection()
    with open(model._tx_filename, "r", encoding="utf-8") as f:
        dsl_text = f.read()
    save_product_version(conn, product, dsl_text, source_file=model._tx_filename)
    app_id = save_application(conn, application)
    save_decision(conn, app_id, result)
    conn.close()

    out_dir = output_path if output_path else dirname(model._tx_filename)
    base_name = splitext(basename(application_path))[0]
    html_path = join(out_dir, f"{base_name}_odluka.html")
    pdf_path = join(out_dir, f"{base_name}_odluka.pdf")

    env = _jinja_env()
    template = env.get_template("decision_report.j2")
    html = template.render(
        result=result, application=application,
        currency=product.currency, css_path=CSS_PATH, extra_notes=[],
        fees=fees_summary,
    )
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    _try_pdf(html, pdf_path)

    print(f"[decision-report] Odluka: {result['decision']} -> {html_path}")
    return html_path
