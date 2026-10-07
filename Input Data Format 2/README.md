# Input Data Format 2: Clinical Encounters & Prescriptions

This directory contains raw clinical encounter data (Format 2), linking to patients via `PATIENT` foreign key.

## Recommended Kaggle Datasets
1. **Synthea Synthetic Health Data**: `cpluzsh/synthea-synthetic-health-data`
2. **Synthea Massachusetts Records**: `eeshawn/synthea-massachusetts-records`

## Schema Specification (`encounters.csv`)

| Column Name | Type | Description | De-identification Action |
|---|---|---|---|
| `Id` | UUID / String | Unique encounter identifier | Pseudonymized / preserved |
| `START` | Timestamp | Encounter admission / start time | Date-shifted by patient's random delta |
| `STOP` | Timestamp | Encounter discharge / end time | Date-shifted by patient's random delta |
| `PATIENT` | UUID / String | Foreign key to `patients.csv (Id)` | Replaced with salted hash `patient_deid_key` |
| `ORGANIZATION` | UUID / String | Healthcare facility identifier | Preserved / coarsened |
| `PROVIDER` | UUID / String | Attending physician identifier | Pseudonymized |
| `PAYER` | UUID / String | Insurance provider | Preserved |
| `ENCOUNTERCLASS` | String | Class (e.g., ambulatory, emergency, inpatient) | Preserved |
| `CODE` | String | ICD-10 / SNOMED encounter code | Preserved (clinical research code) |
| `DESCRIPTION` | String | Description of encounter | Preserved |
| `COST` | Float | Total encounter cost | Preserved |
| `REASONCODE` | String | SNOMED reason code | Preserved |
| `REASONDESCRIPTION` | String | Reason description | Preserved |
| `NOTES` | String | Clinical provider notes | Free-text PII redacted (NER / regex scrubber) |

## Kaggle CLI Download Command

```bash
# Set up Kaggle credentials in ~/.kaggle/kaggle.json
kaggle datasets download -d cpluzsh/synthea-synthetic-health-data --file encounters.csv --unzip -p "Input Data Format 2/"
```
Or execute the automated helper:
```bash
python scripts/download_kaggle_data.py
```
