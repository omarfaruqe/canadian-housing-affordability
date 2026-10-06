from pathlib import Path
import sqlite3

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "housing.db"


def show_query(connection, title, sql, params=()):
    print(f"\n{title}")
    result = pd.read_sql_query(sql, connection, params=params)

    if result.empty:
        print("No matching observations.")
    else:
        print(result.to_string(index=False))


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            "Database not found. Run src/build_database.py first."
        )

    with sqlite3.connect(DB_PATH) as connection:
        show_query(
            connection,
            "1. Latest-quarter two-bedroom asking rents",
            """
            SELECT
                region,
                period,
                monthly_rent_cad,
                quality_flag,
                quality_note
            FROM rent_observations
            WHERE rent_measure = 'asking'
              AND apartment_type = '2 bedrooms'
              AND reference_date = (
                  SELECT MAX(reference_date)
                  FROM rent_observations
                  WHERE rent_measure = 'asking'
                    AND apartment_type = '2 bedrooms'
              )
            ORDER BY monthly_rent_cad DESC, region
            """,
        )

        show_query(
            connection,
            "2. Montréal two-bedroom asking rent: latest eight observations",
            """
            SELECT
                period,
                monthly_rent_cad,
                quality_flag,
                is_available
            FROM rent_observations
            WHERE region = ?
              AND apartment_type = ?
              AND rent_measure = ?
            ORDER BY reference_date DESC
            LIMIT 8
            """,
            params=("Montréal", "2 bedrooms", "asking"),
        )

        show_query(
            connection,
            "3. Data availability and caution flags",
            """
            SELECT
                region,
                rent_measure,
                COUNT(*) AS total_observations,
                SUM(is_available) AS available_observations,
                SUM(
                    CASE
                        WHEN is_available = 1 AND use_with_caution = 1
                        THEN 1 ELSE 0
                    END
                ) AS available_caution_observations
            FROM rent_observations
            GROUP BY region, rent_measure
            ORDER BY region, rent_measure
            """,
        )


if __name__ == "__main__":
    main()