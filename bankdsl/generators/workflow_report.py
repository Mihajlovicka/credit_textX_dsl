"""
textX generator: 'workflow-report'

Koriscenje:
    textx generate examples/stambeni_kredit.credit --target workflow-report \
        --application examples/aplikacije/marko.json
"""
from os.path import dirname, join, basename, splitext
from pathlib import Path

import jinja2
from textx import generator

from bankdsl.interpreter.loader import find_product, resolve_product_workflow
from bankdsl.interpreter.application import Application
from bankdsl.interpreter.process_engine import run_process

TEMPLATES_DIR = join(dirname(dirname(__file__)), "templates")
CSS_PATH = join(dirname(dirname(__file__)), "css", "report.css")


def _try_pdf(html_path, pdf_path):
    try:
        from xhtml2pdf import pisa

        with open(html_path, "r", encoding="utf-8") as html_file:
            html = html_file.read()

        with open(pdf_path, "wb") as pdf_file:
            result = pisa.CreatePDF(html, dest=pdf_file)

        if result.err:
            raise RuntimeError("xhtml2pdf failed to generate PDF.")

        return True

    except Exception as e:
        print(f"[workflow-report] PDF generisanje preskoceno ({e}).")
        return False


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


@generator("BankCreditDSL", "workflow-report")
def workflow_report_generator(metamodel, model, output_path, overwrite, debug, **custom_args):
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
    workflow = resolve_product_workflow(model, product)

    result = run_process(workflow, product, application)

    out_dir = output_path if output_path else dirname(model._tx_filename)
    base_name = splitext(basename(application_path))[0]
    html_path = join(out_dir, f"{base_name}_tok.html")
    pdf_path = join(out_dir, f"{base_name}_tok.pdf")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True
    )
    template = env.get_template("workflow_report.j2")
    html = template.render(
        result=result, application=application, product=product,
        workflow=workflow, css_path=CSS_PATH,
    )
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    _try_pdf(html_path, pdf_path)

    print(f"[workflow-report] Konacno stanje: {result['final']} -> {html_path}")
    print(f"[workflow-report] Trag: {' -> '.join(result['trail'])}")
    return html_path