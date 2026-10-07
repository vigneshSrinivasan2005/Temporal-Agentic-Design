import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Mock-Data-Pipeline"))

from deidentifier import ClinicalDeidentifier


@pytest.fixture
def deidentifier():
    return ClinicalDeidentifier(salt="test_salt_123")


def test_hash_identifier(deidentifier):
    raw_id = "patient-001"
    hashed = deidentifier.hash_identifier(raw_id)
    assert hashed.startswith("DEID-")
    assert len(hashed) == 17
    # Determinism check
    assert deidentifier.hash_identifier(raw_id) == hashed


def test_deterministic_date_shift_consistency(deidentifier):
    raw_id = "patient-xyz-42"
    offset_1 = deidentifier.get_date_shift_offset(raw_id)
    offset_2 = deidentifier.get_date_shift_offset(raw_id)
    assert offset_1 == offset_2
    assert -180 <= offset_1 <= 180

    # Ensure different patients get distinct deterministic offsets
    offset_other = deidentifier.get_date_shift_offset("patient-abc-99")
    assert isinstance(offset_other, int)


def test_age_bucketization_safe_harbor(deidentifier):
    # Under 18
    assert deidentifier.calculate_age_bucket("2015-05-10", reference_date=datetime(2026, 1, 1)) == "0-17"
    # Adult bucket
    assert deidentifier.calculate_age_bucket("1985-05-10", reference_date=datetime(2026, 1, 1)) == "40-49"
    # HIPAA Safe Harbor rule: age >= 90 must be aggregated to 90+
    assert deidentifier.calculate_age_bucket("1930-01-01", reference_date=datetime(2026, 1, 1)) == "90+"
    assert deidentifier.calculate_age_bucket("1910-01-01", reference_date=datetime(2026, 1, 1)) == "90+"


def test_clinical_note_redaction(deidentifier):
    raw_note = (
        "Patient John Doe with SSN 123-45-6789 and phone (555) 019-2834, email john.doe@example.com, MRN: MRN-99887."
    )
    redacted = deidentifier.redact_notes(raw_note)
    assert "123-45-6789" not in redacted
    assert "[REDACTED_SSN]" in redacted
    assert "(555) 019-2834" not in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "john.doe@example.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "MRN: [REDACTED_MRN]" in redacted


def test_deidentify_demographics_dataframe(deidentifier):
    data = {
        "Id": ["pat-1", "pat-2"],
        "FIRST": ["Alice", "Bob"],
        "LAST": ["Smith", "Jones"],
        "SSN": ["111-22-3333", "444-55-6666"],
        "BIRTHDATE": ["1990-06-15", "1925-03-20"],
        "GENDER": ["F", "M"],
        "RACE": ["white", "asian"],
        "ZIP": ["02138", "90210"],
    }
    df = pd.DataFrame(data)
    deid_df, mapping = deidentifier.deidentify_demographics(df)

    assert len(deid_df) == 2
    assert "FIRST" not in deid_df.columns
    assert "LAST" not in deid_df.columns
    assert "SSN" not in deid_df.columns
    assert "patient_deid_key" in deid_df.columns
    assert deid_df.loc[1, "age_bucket"] == "90+"
    assert deid_df.loc[0, "coarsened_zip"] == "021XX"
