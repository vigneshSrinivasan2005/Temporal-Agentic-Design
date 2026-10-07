#!/usr/bin/env python3
"""
Clinical Dataset Downloader

Downloads real clinical datasets (Synthea synthetic health records) from Kaggle
(or direct public official mirror) and extracts patients.csv into 'Input Data Format 1/'
and encounters.csv into 'Input Data Format 2/'.
"""

import argparse
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FORMAT_1_DIR = BASE_DIR / "Input Data Format 1"
FORMAT_2_DIR = BASE_DIR / "Input Data Format 2"
TEMP_DOWNLOAD_DIR = BASE_DIR / ".download_temp"

KAGGLE_DATASET = "cpluzsh/synthea-synthetic-health-data"
SYNTHEA_DIRECT_URL = "https://raw.githubusercontent.com/synthetichealth/synthea-sample-data/main/downloads/synthea_sample_data_csv_apr2020.zip"


def check_kaggle_credentials() -> bool:
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    env_creds = os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY")
    return kaggle_json.exists() or bool(env_creds)


def download_via_kaggle(dataset: str):
    print(f"[*] Downloading dataset '{dataset}' via Kaggle CLI...")
    TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["kaggle", "datasets", "download", "-d", dataset, "-p", str(TEMP_DOWNLOAD_DIR), "--unzip"]
    subprocess.run(cmd, check=True)


def download_via_direct_url(url: str):
    print(f"[*] Downloading official Synthea clinical dataset from mirror: {url}...")
    TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = TEMP_DOWNLOAD_DIR / "synthea.zip"
    urllib.request.urlretrieve(url, zip_path)
    print("[*] Extracting zip archive...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(TEMP_DOWNLOAD_DIR)


def organize_files():
    print("[*] Organizing files into Input Data Format directories...")
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
    parser = argparse.ArgumentParser(description="Download clinical datasets for Temporal Agentic Pipeline.")
    parser.add_argument("--dataset", default=KAGGLE_DATASET, help="Kaggle dataset handle")
    parser.add_argument("--mirror", action="store_true", help="Force direct public Synthea mirror download")
    args = parser.parse_args()

    if not args.mirror and check_kaggle_credentials():
        try:
            download_via_kaggle(args.dataset)
        except Exception as e:
            print(f"[!] Kaggle download failed ({e}), falling back to direct Synthea mirror...")
            download_via_direct_url(SYNTHEA_DIRECT_URL)
    else:
        print("[*] Kaggle API credentials not found in ~/.kaggle/kaggle.json.")
        print("[*] Fetching official Synthea dataset via public mirror...")
        download_via_direct_url(SYNTHEA_DIRECT_URL)

    organize_files()
    print("[+] Done! Input data directories are ready.")


if __name__ == "__main__":
    main()
