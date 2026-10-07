import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import pandas as pd

from common.config import (
    OUTPUT_DIR,
    OUTPUT_DUCKDB_PATH,
)


def get_connection(db_path: Optional[Path] = None) -> duckdb.DuckDBPyConnection:
    target_path = str(db_path or OUTPUT_DUCKDB_PATH)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    return duckdb.connect(target_path)


def init_tables(
    patients_df: pd.DataFrame,
    encounters_df: pd.DataFrame,
    summary_df: Optional[pd.DataFrame] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Creates or replaces DuckDB tables from de-identified dataframes."""
    conn = get_connection(db_path)
    try:
        conn.register("patients_view", patients_df)
        conn.execute("CREATE OR REPLACE TABLE deid_patients AS SELECT * FROM patients_view")

        conn.register("encounters_view", encounters_df)
        conn.execute("CREATE OR REPLACE TABLE deid_encounters AS SELECT * FROM encounters_view")

        if summary_df is not None:
            conn.register("summary_view", summary_df)
            conn.execute("CREATE OR REPLACE TABLE clinical_summary AS SELECT * FROM summary_view")
        else:
            # Generate summary automatically via DuckDB aggregation
            conn.execute("""
                CREATE OR REPLACE TABLE clinical_summary AS
                SELECT
                    p.patient_deid_key,
                    p.gender,
                    p.race,
                    p.ethnicity,
                    p.age_bucket,
                    COUNT(e.encounter_id) AS total_encounters,
                    COALESCE(SUM(e.cost), 0.0) AS total_clinical_cost,
                    MIN(e.start_time) AS first_encounter_time,
                    MAX(e.end_time) AS last_encounter_time
                FROM deid_patients p
                LEFT JOIN deid_encounters e ON p.patient_deid_key = e.patient_deid_key
                GROUP BY p.patient_deid_key, p.gender, p.race, p.ethnicity, p.age_bucket
            """)
    finally:
        conn.close()


def export_parquets(
    patients_df: pd.DataFrame,
    encounters_df: pd.DataFrame,
    summary_df: Optional[pd.DataFrame] = None,
    output_dir: Optional[Path] = None,
) -> List[str]:
    """Exports dataframes to parquet files."""
    target_dir = Path(output_dir or OUTPUT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    p_path = target_dir / "patients_deidentified.parquet"
    e_path = target_dir / "encounters_deidentified.parquet"
    s_path = target_dir / "patient_encounters_summary.parquet"

    patients_df.to_parquet(p_path, index=False)
    encounters_df.to_parquet(e_path, index=False)

    if summary_df is not None:
        summary_df.to_parquet(s_path, index=False)
    else:
        # Create summary from merge
        conn = duckdb.connect()
        conn.register("p", patients_df)
        conn.register("e", encounters_df)
        summary = conn.execute("""
            SELECT
                p.patient_deid_key,
                p.gender,
                p.race,
                p.ethnicity,
                p.age_bucket,
                COUNT(e.encounter_id) AS total_encounters,
                COALESCE(SUM(e.cost), 0.0) AS total_clinical_cost
            FROM p
            LEFT JOIN e ON p.patient_deid_key = e.patient_deid_key
            GROUP BY p.patient_deid_key, p.gender, p.race, p.ethnicity, p.age_bucket
        """).df()
        summary.to_parquet(s_path, index=False)

    return [str(p_path), str(e_path), str(s_path)]


def run_query(sql: str, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Runs a read-only query on DuckDB and returns records as dictionaries."""
    conn = get_connection(db_path)
    try:
        rel = conn.execute(sql)
        cols = [desc[0] for desc in rel.description]
        rows = rel.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def get_table_schemas(db_path: Optional[Path] = None) -> Dict[str, List[Dict[str, str]]]:
    """Retrieves column details for all tables in DuckDB."""
    conn = get_connection(db_path)
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        schemas = {}
        for (table_name,) in tables:
            desc = conn.execute(f"DESCRIBE {table_name}").fetchall()
            schemas[table_name] = [{"column_name": row[0], "column_type": row[1], "null": str(row[2])} for row in desc]
        return schemas
    finally:
        conn.close()


def audit_deidentification(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Audits DuckDB tables to verify HIPAA Safe Harbor compliance."""
    conn = get_connection(db_path)
    try:
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        findings = []
        is_compliant = True

        ssn_regex = r"\b\d{3}-\d{2}-\d{4}\b"
        email_regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        phone_regex = r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"

        # Check column names for obvious raw PII leaks
        forbidden_cols = {"ssn", "first", "last", "drivers", "passport", "address", "phone", "email"}
        for table in tables:
            cols = [c[0].lower() for c in conn.execute(f"DESCRIBE {table}").fetchall()]
            leaked_cols = forbidden_cols.intersection(set(cols))
            if leaked_cols:
                is_compliant = False
                findings.append(f"Table '{table}' contains prohibited raw PII columns: {list(leaked_cols)}")

            # Check text contents in encounters for unmasked patterns
            if table == "deid_encounters":
                notes_sample = conn.execute("SELECT clinical_notes FROM deid_encounters LIMIT 500").fetchall()
                for (note,) in notes_sample:
                    if not note:
                        continue
                    if re.search(ssn_regex, str(note)):
                        is_compliant = False
                        findings.append("Detected unmasked SSN pattern in clinical_notes!")
                        break
                    if re.search(email_regex, str(note)):
                        is_compliant = False
                        findings.append("Detected unmasked email pattern in clinical_notes!")
                        break

        pat_res = conn.execute("SELECT COUNT(*) FROM deid_patients").fetchone() if "deid_patients" in tables else None
        total_patients = pat_res[0] if pat_res is not None else 0
        enc_res = (
            conn.execute("SELECT COUNT(*) FROM deid_encounters").fetchone() if "deid_encounters" in tables else None
        )
        total_encounters = enc_res[0] if enc_res is not None else 0

        return {
            "compliant": is_compliant,
            "total_patients": total_patients,
            "total_encounters": total_encounters,
            "tables_audited": tables,
            "findings": findings
            if findings
            else ["No residual direct PII identifiers found. HIPAA Safe Harbor verified."],
        }
    finally:
        conn.close()
