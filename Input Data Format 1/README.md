# Input Data Format 1: Patient Demographics & Registry

This directory contains raw, identifiable patient demographic records (Format 1).

## Recommended Kaggle Datasets
1. **Synthea Synthetic Health Data**: `cpluzsh/synthea-synthetic-health-data`
2. **Synthea Massachusetts Records**: `eeshawn/synthea-massachusetts-records`
3. **Hospital Readmission & Patient Demographics**: `praveengovi/hospital-readmission-dataset`

## Schema Specification (`patients.csv`)

| Column Name | Type | Description | PII Category (HIPAA Safe Harbor) |
|---|---|---|---|
| `Id` | UUID / String | Unique patient identifier / MRN | Direct Identifier (to be salted & hashed) |
| `BIRTHDATE` | Date (YYYY-MM-DD) | Date of birth | Protected (shift date, bucketize if age > 89) |
| `DEATHDATE` | Date (YYYY-MM-DD) | Date of death (nullable) | Protected (shift date) |
| `SSN` | String | Social Security Number | Direct Identifier (must be scrubbed/removed) |
| `DRIVERS` | String | Driver's license number | Direct Identifier (must be removed) |
| `PASSPORT` | String | Passport number | Direct Identifier (must be removed) |
| `PREFIX` | String | Honorific (e.g. Mr., Ms., Dr.) | Neutral |
| `FIRST` | String | First name | Direct Identifier (must be removed) |
| `LAST` | String | Last name | Direct Identifier (must be removed) |
| `MAIDEN` | String | Maiden name | Direct Identifier (must be removed) |
| `MARITAL` | String | Marital status (M, S, D, etc.)| Demographics |
| `RACE` | String | Racial category | Demographics |
| `ETHNICITY` | String | Ethnicity category | Demographics |
| `GENDER` | String | Gender (M, F) | Demographics |
| `BIRTHPLACE` | String | Place of birth | Geographic (coarsened) |
| `ADDRESS` | String | Street address | Direct Identifier (must be removed) |
| `CITY` | String | City | Geographic |
| `STATE` | String | State | Geographic |
| `ZIP` | String | 5-digit postal code | Geographic (retain 3-digit prefix if pop > 20k) |
| `PHONE` | String | Contact telephone | Direct Identifier (must be removed) |
| `EMAIL` | String | Email address | Direct Identifier (must be removed) |

## Kaggle CLI Download Command

```bash
# Set up Kaggle credentials in ~/.kaggle/kaggle.json
kaggle datasets download -d cpluzsh/synthea-synthetic-health-data --file patients.csv --unzip -p "Input Data Format 1/"
```
Or execute the automated helper:
```bash
python scripts/download_kaggle_data.py
```
