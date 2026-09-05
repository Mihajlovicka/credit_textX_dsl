"""
Sloj skladistenja. Koristi SQLite (dovoljno za projekat/odbranu; u produkciji
bi ovo bio Postgres, ali API ostaje isti preko repository.py).

Cuva:
  - product_versions: sirov DSL tekst svake verzije proizvoda + metapodaci
    (ovo resava profesorovu primedbu o verzionisanju - ugovor uvek moze
    da dohvati TACAN tekst pravila koji je vazio kad je potpisan)
  - applications: zahtevi klijenata (JSON, van DSL-a)
  - decisions: rezultat evaluacije za svaki zahtev (audit trag)
"""
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "bankdsl.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS product_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    dsl_text TEXT NOT NULL,
    source_file TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_version TEXT NOT NULL,
    requested_amount REAL NOT NULL,
    requested_term INTEGER NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    mode TEXT NOT NULL,
    decision TEXT NOT NULL,
    score REAL,
    explanation_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection(db_path=None):
    db_path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
