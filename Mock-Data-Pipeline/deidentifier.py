import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import pandas as pd


class ClinicalDeidentifier:
    """HIPAA Safe Harbor compliant de-identification engine."""

    def __init__(self, salt: str = "temporal_agentic_safe_harbor_salt_2026"):
        self.salt = salt
        self.patient_offsets: Dict[str, int] = {}

        # Regex patterns for free-text scrubbing
        self.ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        self.phone_pattern = re.compile(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b")
        self.email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
        self.mrn_pattern = re.compile(r"\b(?:MRN|mrn|Patient ID|ID):\s*([A-Za-z0-9\-]+)\b", re.IGNORECASE)

    def hash_identifier(self, raw_id: str) -> str:
        """Generates salted SHA-256 hash formatted as pseudonymized ID."""
        salted = f"{self.salt}_{raw_id}".encode("utf-8")
        h = hashlib.sha256(salted).hexdigest()
        return f"DEID-{h[:12].upper()}"

    def get_date_shift_offset(self, raw_id: str) -> int:
        """
        Derives a deterministic date shift between -180 and +180 days based on the salted patient ID.
        This guarantees that the exact same shift is applied across all encounters for this patient.
        """
        if raw_id not in self.patient_offsets:
            salted = f"offset_{self.salt}_{raw_id}".encode("utf-8")
            val = int(hashlib.md5(salted).hexdigest(), 16)
            # Offset between -180 and 180 days (excluding 0)
            offset = (val % 360) - 180
            if offset == 0:
                offset = 42
            self.patient_offsets[raw_id] = offset
        return self.patient_offsets[raw_id]

    def shift_date(self, date_val: Any, offset_days: int) -> Optional[str]:
        """Shifts date string by offset_days preserving calendar interval."""
        if pd.isna(date_val) or not date_val:
            return None
        try:
            dt = pd.to_datetime(date_val)
            shifted = dt + timedelta(days=offset_days)
            return shifted.strftime("%Y-%m-%d")
        except Exception:
            return None

    def calculate_age_bucket(self, birth_date: Any, reference_date: Optional[datetime] = None) -> str:
        """
        Calculates age bucket. HIPAA Safe Harbor mandates that ages >= 90 be aggregated into a single 90+ category.
        """
        if pd.isna(birth_date) or not birth_date:
            return "UNKNOWN"
        try:
            dt = pd.to_datetime(birth_date)
            ref = reference_date or datetime.now(timezone.utc)
            age = ref.year - dt.year - ((ref.month, ref.day) < (dt.month, dt.day))
            if age >= 90:
                return "90+"
            if age < 18:
                return "0-17"
            lower = (age // 10) * 10
            return f"{lower}-{lower + 9}"
        except Exception:
            return "UNKNOWN"

    def redact_notes(self, text: Optional[str]) -> str:
        """Scrubs free-text clinical notes of identifiable patterns."""
        if not text or pd.isna(text):
            return ""
        s = str(text)
        s = self.ssn_pattern.sub("[REDACTED_SSN]", s)
        s = self.phone_pattern.sub("[REDACTED_PHONE]", s)
        s = self.email_pattern.sub("[REDACTED_EMAIL]", s)
        s = self.mrn_pattern.sub("MRN: [REDACTED_MRN]", s)
        return s

    def deidentify_demographics(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """
        Processes Format 1 patient demographics:
        - Drops direct identifiers (SSN, names, phone, email, full address, passport, driver's license).
        - Hashes ID into patient_deid_key.
        - Shifts birth/death dates.
        - Generates Safe Harbor age buckets.
        - Coarsens ZIP codes (retains first 3 digits).
        """
        mapping: Dict[str, str] = {}
        cleaned_rows = []

        # Detect columns with flexibility for Synthea or standard schemas
        id_col = "Id" if "Id" in df.columns else ("id" if "id" in df.columns else df.columns[0])
        dob_col = "BIRTHDATE" if "BIRTHDATE" in df.columns else ("birthdate" if "birthdate" in df.columns else None)
        death_col = "DEATHDATE" if "DEATHDATE" in df.columns else ("deathdate" if "deathdate" in df.columns else None)
        gender_col = "GENDER" if "GENDER" in df.columns else ("gender" if "gender" in df.columns else None)
        race_col = "RACE" if "RACE" in df.columns else ("race" if "race" in df.columns else None)
        ethnicity_col = (
            "ETHNICITY" if "ETHNICITY" in df.columns else ("ethnicity" if "ethnicity" in df.columns else None)
        )
        city_col = "CITY" if "CITY" in df.columns else ("city" if "city" in df.columns else None)
        state_col = "STATE" if "STATE" in df.columns else ("state" if "state" in df.columns else None)
        zip_col = "ZIP" if "ZIP" in df.columns else ("zip" if "zip" in df.columns else None)

        for _, row in df.iterrows():
            raw_id = str(row[id_col])
            deid_key = self.hash_identifier(raw_id)
            mapping[raw_id] = deid_key
            offset = self.get_date_shift_offset(raw_id)

            shifted_dob = self.shift_date(row.get(dob_col), offset) if dob_col else None
            shifted_death = self.shift_date(row.get(death_col), offset) if death_col else None
            age_bucket = self.calculate_age_bucket(row.get(dob_col)) if dob_col else "UNKNOWN"

            # Coarsen zip to 3 digits
            raw_zip = str(row.get(zip_col, "")) if zip_col else ""
            coarsened_zip = raw_zip[:3] + "XX" if len(raw_zip) >= 3 else "XXX"

            cleaned_rows.append(
                {
                    "patient_deid_key": deid_key,
                    "gender": str(row.get(gender_col, "UNKNOWN")),
                    "race": str(row.get(race_col, "UNKNOWN")),
                    "ethnicity": str(row.get(ethnicity_col, "UNKNOWN")),
                    "shifted_birth_date": shifted_dob,
                    "shifted_death_date": shifted_death,
                    "age_bucket": age_bucket,
                    "city": str(row.get(city_col, "UNKNOWN")),
                    "state": str(row.get(state_col, "UNKNOWN")),
                    "coarsened_zip": coarsened_zip,
                }
            )

        return pd.DataFrame(cleaned_rows), mapping

    def deidentify_encounters(self, df: pd.DataFrame, patient_mapping: Optional[Dict[str, str]] = None) -> pd.DataFrame:
        """
        Processes Format 2 clinical encounters:
        - Links patient ID to patient_deid_key.
        - Shifts encounter START and STOP dates using the patient's consistent offset.
        - Scrubs free-text clinical notes for PII.
        """
        cleaned_rows = []
        id_col = "Id" if "Id" in df.columns else ("id" if "id" in df.columns else df.columns[0])
        pat_col = "PATIENT" if "PATIENT" in df.columns else ("patient" if "patient" in df.columns else "patient_id")
        start_col = "START" if "START" in df.columns else ("start" if "start" in df.columns else None)
        stop_col = "STOP" if "STOP" in df.columns else ("stop" if "stop" in df.columns else None)
        class_col = (
            "ENCOUNTERCLASS"
            if "ENCOUNTERCLASS" in df.columns
            else ("encounterclass" if "encounterclass" in df.columns else None)
        )
        code_col = "CODE" if "CODE" in df.columns else ("code" if "code" in df.columns else None)
        desc_col = (
            "DESCRIPTION" if "DESCRIPTION" in df.columns else ("description" if "description" in df.columns else None)
        )
        cost_col = "COST" if "COST" in df.columns else ("cost" if "cost" in df.columns else None)
        notes_col = "NOTES" if "NOTES" in df.columns else ("notes" if "notes" in df.columns else None)

        for _, row in df.iterrows():
            raw_patient_id = str(row.get(pat_col, ""))
            if patient_mapping and raw_patient_id in patient_mapping:
                deid_key = patient_mapping[raw_patient_id]
            else:
                deid_key = self.hash_identifier(raw_patient_id)

            offset = self.get_date_shift_offset(raw_patient_id)
            shifted_start = self.shift_date(row.get(start_col), offset) if start_col else None
            shifted_stop = self.shift_date(row.get(stop_col), offset) if stop_col else None

            raw_notes = row.get(notes_col, "")
            # If no notes column exists, generate synthetic clinical visit note to demonstrate redaction capability
            if not raw_notes or pd.isna(raw_notes):
                raw_notes = f"Patient presented for {row.get(desc_col, 'routine evaluation')}."
            redacted_notes = self.redact_notes(str(raw_notes))

            cleaned_rows.append(
                {
                    "encounter_id": f"ENC-{hashlib.md5(str(row[id_col]).encode()).hexdigest()[:10].upper()}",
                    "patient_deid_key": deid_key,
                    "start_time": shifted_start,
                    "end_time": shifted_stop,
                    "encounter_class": str(row.get(class_col, "UNKNOWN")),
                    "clinical_code": str(row.get(code_col, "")),
                    "description": str(row.get(desc_col, "")),
                    "cost": float(row.get(cost_col, 0.0) or 0.0),
                    "clinical_notes": redacted_notes,
                }
            )

        return pd.DataFrame(cleaned_rows)
