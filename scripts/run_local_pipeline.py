import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Mock-Data-Pipeline"))
sys.path.insert(0, str(BASE_DIR / "Output Aligned Queryable Data"))

from pipeline_activities import (
    deidentify_demographics_activity,
    deidentify_encounters_activity,
    export_duckdb_parquet_activity,
    merge_and_normalize_activity,
    validate_inputs_activity,
)


async def run():
    print("[*] Validating inputs...")
    v = await validate_inputs_activity({})
    print(f"    Validation status: {v['status']}")

    print("[*] De-identifying demographics (HIPAA Safe Harbor)...")
    d = await deidentify_demographics_activity({})
    print(f"    Processed {d['processed_patients']} patients ({d['unique_pseudonyms']} pseudonyms)")
    print(f"    Age distribution: {d['age_buckets']}")

    print("[*] De-identifying encounters & date-shifting...")
    e = await deidentify_encounters_activity({})
    print(f"    Processed {e['processed_encounters']} encounters (Total Cost: ${e['total_clinical_cost']:,.2f})")

    print("[*] Merging & normalizing...")
    m = await merge_and_normalize_activity({})
    print(f"    Merged {m['total_merged_records']} records")

    print("[*] Exporting to DuckDB & Parquet...")
    exp = await export_duckdb_parquet_activity({})
    print(f"    Exported to DuckDB: {exp['duckdb_file']}")
    for pf in exp["parquet_files"]:
        print(f"    - {pf}")
    print("[+] Pipeline run complete!")


if __name__ == "__main__":
    asyncio.run(run())
