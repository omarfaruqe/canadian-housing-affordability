from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json

import requests


# Resolve paths relative to the project, regardless of where we run the script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

DOWNLOAD_URL = (
    "https://www150.statcan.gc.ca/n1/tbl/csv/46100092-eng.zip"
)
TABLE_URL = (
    "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=4610009201"
)
CSV_NAME = "46100092.csv"


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading Statistics Canada rental data...")

    response = requests.get(DOWNLOAD_URL, timeout=120)
    response.raise_for_status()

    # Check the archive before saving anything.
    with ZipFile(BytesIO(response.content)) as archive:
        print("Files inside the download:")
        for name in archive.namelist():
            print(f"  {name}")

        if CSV_NAME not in archive.namelist():
            raise RuntimeError(
                f"Expected {CSV_NAME} was not found. "
                "Check the filenames printed above."
            )

        csv_content = archive.read(CSV_NAME)

    zip_path = RAW_DIR / "46100092-eng.zip"
    csv_path = RAW_DIR / CSV_NAME

    zip_path.write_bytes(response.content)
    csv_path.write_bytes(csv_content)

    # Record the source and download time for reproducibility.
    metadata = {
        "table_id": "46-10-0092-01",
        "table_url": TABLE_URL,
        "download_url": DOWNLOAD_URL,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "csv_filename": CSV_NAME,
        "csv_sha256": hashlib.sha256(csv_content).hexdigest(),
    }

    metadata_path = RAW_DIR / "download_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print(f"\nSaved archive: {zip_path}")
    print(f"Saved dataset: {csv_path}")
    print(f"Saved source information: {metadata_path}")


if __name__ == "__main__":
    main()