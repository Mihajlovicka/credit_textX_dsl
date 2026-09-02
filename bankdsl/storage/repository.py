"""
Repository sloj - jedina tacka koja govori SQL. Ostatak sistema
(generatori, CLI, buduci API) zove samo ove funkcije.
"""
import json
from bankdsl.storage.db import get_connection


def save_product_version(conn, product, dsl_text, source_file=None):
    """Cuva/azurira sirov DSL tekst tacne verzije proizvoda - trajni zapis pravila
    koja vaze za svaki ugovor potpisan pod tom verzijom."""
    conn.execute(
        """INSERT INTO product_versions (name, version, valid_from, valid_to, dsl_text, source_file)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(name, version) DO UPDATE SET
             valid_from=excluded.valid_from, valid_to=excluded.valid_to,
             dsl_text=excluded.dsl_text, source_file=excluded.source_file""",
        (product.name, product.version, product.valid_from, product.valid_to,
         dsl_text, source_file),
    )
    conn.commit()


def get_product_version(conn, name, version):
    row = conn.execute(
        "SELECT * FROM product_versions WHERE name=? AND version=?",
        (name, version),
    ).fetchone()
    return dict(row) if row else None


def list_product_versions(conn, name=None):
    if name:
        rows = conn.execute(
            "SELECT * FROM product_versions WHERE name=? ORDER BY valid_from", (name,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM product_versions ORDER BY name, valid_from").fetchall()
    return [dict(r) for r in rows]


def save_application(conn, application):
    cur = conn.execute(
        """INSERT INTO applications
           (applicant_name, product_name, product_version, requested_amount, requested_term, data_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (application.applicant_name, application.product_name, application.product_version,
         application.requested_amount, application.requested_term, json.dumps(application.data)),
    )
    conn.commit()
    return cur.lastrowid


def save_decision(conn, application_id, result):
    conn.execute(
        """INSERT INTO decisions (application_id, mode, decision, score, explanation_json)
           VALUES (?, ?, ?, ?, ?)""",
        (application_id, result["mode"], result["decision"], result.get("score"),
         json.dumps(result["explanation"], ensure_ascii=False)),
    )
    conn.commit()


def get_application_history(conn, applicant_name):
    rows = conn.execute(
        """SELECT a.*, d.decision, d.score, d.created_at as decided_at
           FROM applications a JOIN decisions d ON d.application_id = a.id
           WHERE a.applicant_name = ? ORDER BY a.created_at""",
        (applicant_name,),
    ).fetchall()
    return [dict(r) for r in rows]
