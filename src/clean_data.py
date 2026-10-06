from pathlib import Path
import json

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "raw" / "46100092.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

REGIONS = {
    "Montréal, Census metropolitan area (CMA)": "Montréal",
    "Toronto, Census metropolitan area (CMA)": "Toronto",
    "Vancouver, Census metropolitan area (CMA)": "Vancouver",
    "Calgary, Census metropolitan area (CMA)": "Calgary",
    "Ottawa - Gatineau (Ontario part), Census metropolitan area (CMA)":
        "Ottawa–Gatineau (Ontario)",
    "Ottawa - Gatineau (Quebec part), Census metropolitan area (CMA)":
        "Ottawa–Gatineau (Quebec)",
}

APARTMENTS = {
    "Apartment - No bedroom": "Studio",
    "Apartment - 1 bedroom": "1 bedroom",
    "Apartment - 2 bedrooms": "2 bedrooms",
    "Apartment - 3 or more bedrooms": "3+ bedrooms",
}

RENT_MEASURES = {
    "Average asking rent": "asking",
    "Average paid rent": "paid",
}

QUALITY_LABELS = {
    "": "No caution flag",
    "E": "Use with caution",
    "F": "Too unreliable to publish",
    "..": "Unavailable for this period",
}


def require(condition, message):
    """Stop the pipeline if a validation rule fails."""
    if not condition:
        raise ValueError(message)


def main():
    raw = pd.read_csv(
        INPUT_PATH,
        encoding="utf-8-sig",
        low_memory=False,
    )

    required_columns = {
        "REF_DATE", "GEO", "Rental unit type", "Estimates",
        "UOM", "SCALAR_FACTOR", "VALUE", "STATUS", "VECTOR",
    }

    require(
        required_columns.issubset(raw.columns),
        f"Missing columns: {required_columns - set(raw.columns)}",
    )

    require(
        set(REGIONS).issubset(set(raw["GEO"])),
        "One or more target regions are missing from the source.",
    )

    # Select exact geographic and apartment categories.
    selected = raw.loc[
        raw["GEO"].isin(REGIONS)
        & raw["Rental unit type"].isin(APARTMENTS)
        & raw["Estimates"].isin(RENT_MEASURES)
    ].copy()

    require(not selected.empty, "No rows matched our selection.")

    # Confirm that values are already expressed in dollars.
    require(
        selected["UOM"].eq("Dollars").all(),
        "Unexpected unit of measurement.",
    )
    require(
        selected["SCALAR_FACTOR"].eq("units").all(),
        "Unexpected scale multiplier.",
    )

    # Parse the reference month and verify quarterly alignment.
    dates = pd.to_datetime(
        selected["REF_DATE"],
        format="%Y-%m",
        errors="raise",
    )

    require(
        dates.dt.month.isin([1, 4, 7, 10]).all(),
        "Unexpected reference month for quarterly data.",
    )

    status = selected["STATUS"].fillna("").astype(str).str.strip()

    require(
        status.isin(QUALITY_LABELS).all(),
        f"Unrecognized quality flags: "
        f"{status.loc[~status.isin(QUALITY_LABELS)].unique().tolist()}",
    )

    values = pd.to_numeric(selected["VALUE"], errors="raise")

    require(
        values.dropna().gt(0).all(),
        "Found zero or negative published rent values.",
    )

    # Suppressed and unavailable observations cannot supply rent values.
    unavailable_status = status.isin(["F", ".."])

    require(
        not (unavailable_status & values.notna()).any(),
        "An unavailable observation unexpectedly contains a value.",
    )

    clean = pd.DataFrame({
        "reference_date": dates.dt.strftime("%Y-%m-%d"),
        "year": dates.dt.year,
        "quarter": dates.dt.quarter,
        "period": dates.dt.to_period("Q").astype(str),
        "region": selected["GEO"].map(REGIONS),
        "source_geography": selected["GEO"],
        "apartment_type": selected["Rental unit type"].map(APARTMENTS),
        "rent_measure": selected["Estimates"].map(RENT_MEASURES),
        "monthly_rent_cad": values,
        "quality_flag": status,
        "quality_note": status.map(QUALITY_LABELS),
        "is_available": values.notna() & ~unavailable_status,
        "use_with_caution": status.eq("E"),
        "source_vector": selected["VECTOR"],
    })

    # Each combination should identify a single observation.
    observation_key = [
        "reference_date",
        "region",
        "apartment_type",
        "rent_measure",
    ]

    require(
        not clean.duplicated(observation_key).any(),
        "Duplicate observations found. Investigate before continuing.",
    )

    clean = clean.sort_values(observation_key).reset_index(drop=True)

    # Check that filtering did not lose a target region.
    require(
        set(clean["region"]) == set(REGIONS.values()),
        "A target region has no apartment observations.",
    )

    report = {
        "source_rows": len(raw),
        "selected_rows": len(clean),
        "available_rows": int(clean["is_available"].sum()),
        "unavailable_rows": int((~clean["is_available"]).sum()),
        "available_caution_rows": int(
            (clean["is_available"] & clean["use_with_caution"]).sum()
        ),
        "first_period": clean["period"].min(),
        "latest_period": clean["period"].max(),
        "regions": sorted(clean["region"].unique().tolist()),
        "quality_flag_counts": {
            str(flag): int(count)
            for flag, count in clean["quality_flag"].value_counts().items()
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUTPUT_DIR / "rent_clean.csv"
    report_path = OUTPUT_DIR / "cleaning_report.json"

    clean.to_csv(csv_path, index=False)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Validation passed.")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    print("\nCoverage by region and rent measure:")
    coverage = (
        clean.groupby(["region", "rent_measure"])
        .agg(
            observations=("is_available", "size"),
            available=("is_available", "sum"),
        )
    )
    print(coverage.to_string())

    print(f"\nSaved: {csv_path}")
    print(f"Saved: {report_path}")


if __name__ == "__main__":
    main()