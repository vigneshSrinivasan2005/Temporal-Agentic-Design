import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Output Aligned Queryable Data"))

from typing import Any

import db as storage_db

mcp_app: Any = None
try:
    from fastmcp import FastMCP

    mcp_app = FastMCP("Query-Normalized-Output-MCP")
except ImportError:
    pass


def run_duckdb_sql(query: str) -> str:
    """Executes a SQL SELECT query against the normalized DuckDB database and returns JSON rows."""
    # Safety: reject destructive statements
    forbidden = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER"]
    upper_q = query.strip().upper()
    for verb in forbidden:
        if upper_q.startswith(verb) or f" {verb} " in upper_q:
            return json.dumps({"error": f"Disallowed destructive SQL operation: {verb}. Read-only queries permitted."})

    try:
        results = storage_db.run_query(query)
        return json.dumps(results[:200], default=str, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_table_schemas() -> str:
    """Returns database tables and column definitions from the DuckDB output store."""
    try:
        schemas = storage_db.get_table_schemas()
        return json.dumps(schemas, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def verify_deidentification_compliance() -> str:
    """Audits DuckDB output tables to confirm HIPAA Safe Harbor de-identification rules were strictly enforced."""
    try:
        audit = storage_db.audit_deidentification()
        return json.dumps(audit, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_clinical_summary_stats() -> str:
    """Retrieves high-level summary analytics of patients, visits, costs, and demographic distribution."""
    try:
        sql = """
            SELECT
                COUNT(*) AS total_patients,
                COUNT(DISTINCT age_bucket) AS age_bucket_count,
                COUNT(DISTINCT gender) AS gender_count,
                SUM(total_encounters) AS aggregated_encounters,
                ROUND(SUM(total_clinical_cost), 2) AS aggregated_clinical_cost,
                ROUND(AVG(total_clinical_cost), 2) AS avg_cost_per_patient
            FROM clinical_summary
        """
        results = storage_db.run_query(sql)
        return json.dumps(results, default=str, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


if mcp_app:
    mcp_app.tool()(run_duckdb_sql)
    mcp_app.tool()(get_table_schemas)
    mcp_app.tool()(verify_deidentification_compliance)
    mcp_app.tool()(get_clinical_summary_stats)


def run():
    if mcp_app:
        mcp_app.run()
    else:
        print(
            "Query Normalized Output MCP Direct CLI. Available tools: run_duckdb_sql, get_table_schemas, verify_deidentification_compliance, get_clinical_summary_stats"
        )
        print(get_table_schemas())


if __name__ == "__main__":
    run()
