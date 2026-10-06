from pathlib import Path
import sqlite3

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CSV_PATH = PROCESSED_DIR / "rent_clean.csv"
DB_PATH = PROCESSED_DIR / "housing.db"

COLUMNS = [
    "reference_date",
    "year",
    "quarter",
    "period",
    "region",
    "source_geography",
    "apartment_type",
    "rent_measure",
    "monthly_rent_cad",
    "quality_flag",
    "quality_note",
    "is_available",
    "use_with_caution",
    "source_vector",
]

CREATE_TABLE_SQL = """
CREATE TABLE rent_observations (
    reference_date TEXT NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    period TEXT NOT NULL,
    region TEXT NOT NULL,
    source_geography TEXT NOT NULL,
    apartment_type TEXT NOT NULL,
    rent_measure TEXT NOT NULL CHECK (rent_measure IN ('asking', 'paid')),
    monthly_rent_cad REAL CHECK (monthly_rent_cad > 0),
    quality_flag TEXT NOT NULL CHECK (quality_flag IN ('', 'E', 'F', '..')),
    quality_note TEXT NOT NULL,
    is_available INTEGER NOT NULL CHECK (is_available IN (0, 1)),
    use_with_caution INTEGER NOT NULL CHECK (use_with_caution IN (0, 1)),
    source_vector TEXT NOT NULL,

    PRIMARY KEY (
        reference_date,
        region,
        apartment_type,
        rent_measure
    ),

    CHECK (
        (is_available = 1 AND monthly_rent_cad IS NOT NULL)
        OR
        (is_available = 0 AND monthly_rent_cad IS NULL)
    ),

    CHECK (
        quality_flag NOT IN ('F', '..') OR is_available = 0
    ),

    CHECK (
        (quality_flag = 'E' AND use_with_caution = 1)
        OR
        (quality_flag <> 'E' AND use_with_caution = 0)
    )
)
"""


def parse_boolean(series, name):
    """Convert CSV boolean values into SQLite's 0 and 1."""
    normalized = series.astype(str).str.strip().str.lower()
    converted = normalized.map({"true": 1, "false": 0})

    if converted.isna().any():
        raise ValueError(f"Unexpected boolean value in {name}")

    return converted.astype(int)


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            "Cleaned data not found. Run src/clean_data.py first."
        )

    # Preserve blank quality flags as empty strings.
    df = pd.read_csv(
        CSV_PATH,
        keep_default_na=False,
        dtype={"source_vector": str},
    )

    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    for name in ["year", "quarter"]:
        df[name] = pd.to_numeric(df[name], errors="raise").astype(int)

    # Only empty rent fields become missing; invalid text raises an error.
    df["monthly_rent_cad"] = pd.to_numeric(
        df["monthly_rent_cad"].replace("", float("nan")),
        errors="raise",
    )

    for name in ["is_available", "use_with_caution"]:
        df[name] = parse_boolean(df[name], name)

    # SQLite stores missing numeric values as NULL.
    records = [
        tuple(None if pd.isna(value) else value for value in row)
        for row in df[COLUMNS].itertuples(index=False, name=None)
    ]

    placeholders = ", ".join(["?"] * len(COLUMNS))
    insert_sql = (
        f"INSERT INTO rent_observations ({', '.join(COLUMNS)}) "
        f"VALUES ({placeholders})"
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        # Rebuild this derived table atomically.
        # If loading fails, the previous table is restored by rollback.
        connection.execute("BEGIN")
        connection.execute("DROP VIEW IF EXISTS available_rents")
        connection.execute("DROP TABLE IF EXISTS rent_observations")
        connection.execute(CREATE_TABLE_SQL)
        connection.executemany(insert_sql, records)

        connection.execute("""
            CREATE INDEX idx_rent_filters
            ON rent_observations (
                region,
                apartment_type,
                rent_measure,
                reference_date
            )
        """)

        connection.execute("""
            CREATE VIEW available_rents AS
            SELECT *
            FROM rent_observations
            WHERE is_available = 1
        """)

        row_count = connection.execute(
            "SELECT COUNT(*) FROM rent_observations"
        ).fetchone()[0]

        available_count = connection.execute(
            "SELECT COUNT(*) FROM available_rents"
        ).fetchone()[0]

        if row_count != len(df):
            raise ValueError("Database row count does not match the CSV.")

        if available_count != int(df["is_available"].sum()):
            raise ValueError("Available row count does not match the CSV.")

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            raise ValueError(f"Database integrity check failed: {integrity}")

    print(f"Database created: {DB_PATH}")
    print(f"Total observations: {row_count:,}")
    print(f"Available observations: {available_count:,}")
    print("Database validation passed.")


if __name__ == "__main__":
    main()