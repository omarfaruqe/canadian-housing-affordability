from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "raw" / "46100092.csv"


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {CSV_PATH}\n"
            "Run python src/download_data.py first."
        )

    df = pd.read_csv(
        CSV_PATH,
        encoding="utf-8-sig",
        low_memory=False,
    )

    print("\n1. DATASET SIZE")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    print("\n2. COLUMN NAMES AND DATA TYPES")
    print(df.dtypes.to_string())

    print("\n3. FIRST FIVE ROWS")
    print(df.head().to_string(index=False))

    print("\n4. REFERENCE PERIODS")
    if "REF_DATE" in df.columns:
        periods = sorted(df["REF_DATE"].dropna().astype(str).unique())
        if periods:
            print(f"First period: {periods[0]}")
            print(f"Latest period: {periods[-1]}")
            print(f"Number of periods: {len(periods)}")
            print(f"Examples: {periods[:8]}")

    print("\n5. GEOGRAPHIES MATCHING OUR TARGET CITIES")
    if "GEO" in df.columns:
        city_names = [
            "Montréal",
            "Montreal",
            "Toronto",
            "Vancouver",
            "Ottawa",
            "Calgary",
        ]
        geography = df["GEO"].dropna().astype(str)
        matches = geography[
            geography.str.contains(
                "|".join(city_names),
                case=False,
                regex=True,
            )
        ]

        for name in sorted(matches.unique()):
            print(f"  {name}")

    print("\n6. DIMENSIONS, UNITS, AND QUALITY FLAGS")
    # Print category labels without assuming their exact column names.
    technical_columns = {
        "REF_DATE",
        "GEO",
        "DGUID",
        "VECTOR",
        "COORDINATE",
        "VALUE",
    }

    for column in df.columns:
        if column in technical_columns:
            continue

        values = df[column].dropna().astype(str).unique()

        if len(values) <= 60:
            print(f"\n{column}:")
            print(values.tolist())

    print("\n7. MISSING VALUES BY COLUMN")
    print(df.isna().sum().to_string())

    print("\n8. RENT VALUE SUMMARY")
    if "VALUE" in df.columns:
        values = pd.to_numeric(df["VALUE"], errors="coerce")
        print(values.describe().to_string())
        print(f"Missing or nonnumeric values: {values.isna().sum():,}")


if __name__ == "__main__":
    main()