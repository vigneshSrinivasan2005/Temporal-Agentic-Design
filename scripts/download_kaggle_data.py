#!/usr/bin/env python3
"""
Kaggle Clinical Dataset Downloader

Downloads clinical datasets (such as Synthea synthetic health records) from Kaggle
and extracts patients.csv into 'Input Data Format 1/' and encounters.csv into 'Input Data Format 2/'.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FORMAT_1_DIR = BASE_DIR / "Input Data Format 1"
FORMAT_2_DIR = BASE_DIR / "Input Data Format 2"
TEMP_DOWNLOAD_DIR = BASE_DIR / ".kaggle_download_temp"

KAGGLE_DATASET = "cpluzsh/synthea-synthetic-health-data"


def check_kaggle_credentials() -> bool:
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    env_creds = os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY")
    return kaggle_json.exists() or bool(env_creds)


def download_via_kaggle_cli(dataset: str):
    print(f"[*] Downloading dataset '{dataset}' via Kaggle CLI...")
    TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["kaggle", "datasets", "download", "-d", dataset, "-p", str(TEMP_DOWNLOAD_DIR), "--unzip"]
    try:
        subprocess.run(cmd, check=True)
        print("[+] Download and extraction complete.")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[-] Failed to download using Kaggle CLI: {e}")
        print("[-] Ensure 'kaggle' is installed (`pip install kaggle`) and ~/.kaggle/kaggle.json exists.")
        sys.exit(1)


def organize_files():
    print("[*] Organizing files into Input Data Format directories...")
    # Search for patients.csv and encounters.csv
    found_patients = list(TEMP_DOWNLOAD_DIR.rglob("patients.csv")) or list(TEMP_DOWNLOAD_DIR.rglob("*patient*.csv"))
    found_encounters = list(TEMP_DOWNLOAD_DIR.rglob("encounters.csv")) or list(
        TEMP_DOWNLOAD_DIR.rglob("*encounter*.csv")
    )

    if found_patients:
        src = found_patients[0]
        dst = FORMAT_1_DIR / "patients.csv"
        shutil.copy2(src, dst)
        print(f"[+] Placed patients dataset -> {dst}")
    else:
        print("[-] patients.csv not found in downloaded archive.")

    if found_encounters:
        src = found_encounters[0]
        dst = FORMAT_2_DIR / "encounters.csv"
        shutil.copy2(src, dst)
        print(f"[+] Placed encounters dataset -> {dst}")
    else:
        print("[-] encounters.csv not found in downloaded archive.")

    # Cleanup temp
    shutil.rmtree(TEMP_DOWNLOAD_DIR, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Download clinical datasets from Kaggle for Temporal Agentic Pipeline."
    )
    parser.add_argument("--dataset", default=KAGGLE_DATASET, help="Kaggle dataset handle (default: %(default)s)")
    args = parser.parse_args()

    if not check_kaggle_credentials():
        print("[!] Warning: Kaggle API credentials not found.")
        print("    Please place your kaggle.json in ~/.kaggle/kaggle.json or set KAGGLE_USERNAME & KAGGLE_KEY.")
        print("    See 'Input Data Format 1/README.md' and 'Input Data Format 2/README.md' for details.")
        sys.exit(1)

    download_via_kaggle_cli(args.dataset)
    organize_files()
    print("[+] Done! Input data directories are ready.")


if __name__ == "__main__":
    main()
