
import json
from bankdsl.storage.db import get_connection


def save_product_version(conn, product, dsl_text, source_file=None):
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
    existing = conn.execute(
        """SELECT id FROM applications
           WHERE applicant_name=? AND product_name=? AND product_version=?
             AND requested_amount=? AND requested_term=?
           ORDER BY id DESC LIMIT 1""",
        (application.applicant_name, application.product_name, application.product_version,
         application.requested_amount, application.requested_term),
    ).fetchone()
    if existing is not None:
        return existing["id"]

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

def get_application_by_id(conn, application_id):
    from bankdsl.interpreter.application import Application

    row = conn.execute(
        "SELECT * FROM applications WHERE id=?", (application_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Aplikacija sa id={application_id} ne postoji.")
    return Application(
        applicant_name=row["applicant_name"],
        product_name=row["product_name"],
        product_version=row["product_version"],
        requested_amount=row["requested_amount"],
        requested_term=row["requested_term"],
        data=json.loads(row["data_json"]),
    )


# PROCESS INSTANCES

def create_process_instance(conn, application_id, product, workflow, entry_step_name):
    cur = conn.execute(
        """INSERT INTO process_instances
           (application_id, product_name, product_version, workflow_name,
            workflow_version, status, current_step)
           VALUES (?, ?, ?, ?, ?, 'in_progress', ?)""",
        (application_id, product.name, product.version,
         workflow.name, workflow.version, entry_step_name),
    )
    conn.commit()
    return cur.lastrowid


def get_process_instance(conn, process_id):
    row = conn.execute(
        "SELECT * FROM process_instances WHERE id=?", (process_id,)
    ).fetchone()
    return dict(row) if row else None


def update_process_instance(conn, process_id, *, current_step=None,
                             status=None, final_state=None, evaluation_json=None):
    fields, values = [], []
    if current_step is not None or status == "in_progress":
        fields.append("current_step=?"); values.append(current_step)
    if status is not None:
        fields.append("status=?"); values.append(status)
    if final_state is not None:
        fields.append("final_state=?"); values.append(final_state)
    if evaluation_json is not None:
        fields.append("evaluation_json=?"); values.append(evaluation_json)
    fields.append("updated_at=CURRENT_TIMESTAMP")
    values.append(process_id)
    conn.execute(f"UPDATE process_instances SET {', '.join(fields)} WHERE id=?", values)
    conn.commit()


def log_process_step(conn, process_id, step_name, required_role, executed_by_role, output):
    conn.execute(
        """INSERT INTO process_step_log
           (process_id, step_name, required_role, executed_by_role, output_json)
           VALUES (?, ?, ?, ?, ?)""",
        (process_id, step_name, required_role, executed_by_role,
         json.dumps(output, ensure_ascii=False)),
    )
    conn.commit()


def get_process_log(conn, process_id):
    rows = conn.execute(
        "SELECT * FROM process_step_log WHERE process_id=? ORDER BY id",
        (process_id,),
    ).fetchall()
    return [dict(r) for r in rows]