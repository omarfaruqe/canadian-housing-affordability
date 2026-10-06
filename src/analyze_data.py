from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "housing.db"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
CHART_DIR = PROJECT_ROOT / "outputs" / "charts"

ANALYSIS_SQL = """
SELECT
    current.reference_date,
    current.period,
    current.region,
    current.apartment_type,
    current.rent_measure,
    current.monthly_rent_cad,
    current.is_available,
    current.quality_note,
    current.use_with_caution,

    CASE WHEN previous_quarter.is_available = 1
         THEN previous_quarter.monthly_rent_cad
    END AS previous_quarter_rent,

    CASE WHEN previous_year.is_available = 1
         THEN previous_year.monthly_rent_cad
    END AS previous_year_rent,

    CASE
        WHEN current.is_available = 1
         AND previous_quarter.is_available = 1
        THEN 100.0 * (
            current.monthly_rent_cad
            / previous_quarter.monthly_rent_cad - 1
        )
    END AS qoq_change_pct,

    CASE
        WHEN current.is_available = 1
         AND previous_year.is_available = 1
        THEN 100.0 * (
            current.monthly_rent_cad
            / previous_year.monthly_rent_cad - 1
        )
    END AS yoy_change_pct,

    CASE
        WHEN current.is_available = 1
         AND previous_quarter.is_available = 1
        THEN (
            current.use_with_caution = 1
            OR previous_quarter.use_with_caution = 1
        )
    END AS qoq_use_with_caution,

    CASE
        WHEN current.is_available = 1
         AND previous_year.is_available = 1
        THEN (
            current.use_with_caution = 1
            OR previous_year.use_with_caution = 1
        )
    END AS yoy_use_with_caution

FROM rent_observations AS current

LEFT JOIN rent_observations AS previous_quarter
    ON previous_quarter.region = current.region
   AND previous_quarter.apartment_type = current.apartment_type
   AND previous_quarter.rent_measure = current.rent_measure
   AND previous_quarter.reference_date =
       date(current.reference_date, '-3 months')

LEFT JOIN rent_observations AS previous_year
    ON previous_year.region = current.region
   AND previous_year.apartment_type = current.apartment_type
   AND previous_year.rent_measure = current.rent_measure
   AND previous_year.reference_date =
       date(current.reference_date, '-12 months')

ORDER BY
    current.region,
    current.apartment_type,
    current.rent_measure,
    current.reference_date
"""


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            "Database not found. Run src/build_database.py first."
        )

    with sqlite3.connect(DB_PATH) as connection:
        analysis = pd.read_sql_query(ANALYSIS_SQL, connection)

    analysis["reference_date"] = pd.to_datetime(
        analysis["reference_date"]
    )

    # Check that joins did not introduce duplicate observations.
    key = [
        "reference_date", "region", "apartment_type", "rent_measure"
    ]
    if analysis.duplicated(key).any():
        raise ValueError("Analysis contains duplicate observations.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    analysis_path = OUTPUT_DIR / "rent_analysis.csv"
    analysis.to_csv(
        analysis_path,
        index=False,
        date_format="%Y-%m-%d",
    )

    # Focus the first analysis on two-bedroom asking rent.
    focus = analysis.loc[
        analysis["apartment_type"].eq("2 bedrooms")
        & analysis["rent_measure"].eq("asking")
    ].copy()

    if focus.empty:
        raise ValueError("No two-bedroom asking rent observations.")

    latest_date = focus["reference_date"].max()
    latest = focus.loc[
        focus["reference_date"].eq(latest_date)
    ].copy()

    latest = latest.sort_values(
        "monthly_rent_cad",
        ascending=False,
        na_position="last",
    )

    print("\nLATEST TWO-BEDROOM ASKING RENT COMPARISON")
    columns = [
        "region",
        "period",
        "monthly_rent_cad",
        "qoq_change_pct",
        "yoy_change_pct",
        "quality_note",
        "yoy_use_with_caution",
    ]
    print(latest[columns].round(2).to_string(index=False))

    comparison_path = OUTPUT_DIR / "latest_two_bedroom_comparison.csv"
    latest.to_csv(
        comparison_path,
        index=False,
        date_format="%Y-%m-%d",
    )

    # Include every quarter for each region so missing data creates gaps.
    quarters = pd.date_range(
        start=focus["reference_date"].min(),
        end=latest_date,
        freq="QS",
    )

    grid = pd.MultiIndex.from_product(
        [sorted(focus["region"].unique()), quarters],
        names=["region", "reference_date"],
    )

    trend_data = (
        focus.set_index(["region", "reference_date"])
        .reindex(grid)
        .reset_index()
    )

    trend = px.line(
        trend_data,
        x="reference_date",
        y="monthly_rent_cad",
        color="region",
        markers=True,
        hover_data=["quality_note"],
        labels={
            "reference_date": "Quarter",
            "monthly_rent_cad": "Monthly asking rent (CAD)",
            "region": "Metropolitan region",
        },
        title="Two-bedroom apartment asking rent over time",
    )
    trend.update_traces(connectgaps=False)
    trend.update_layout(
        template="plotly_white",
        hovermode="x unified",
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
    )
    trend_path = CHART_DIR / "two_bedroom_rent_trends.html"
    trend.write_html(trend_path, include_plotlyjs=True)

    available_latest = latest.loc[
        latest["is_available"].eq(1)
    ].copy()

    if available_latest.empty:
        raise ValueError("No available rents for the latest quarter.")

    latest_period = latest["period"].iloc[0]

    comparison = px.bar(
        available_latest,
        x="region",
        y="monthly_rent_cad",
        color="region",
        text="monthly_rent_cad",
        hover_data=["quality_note"],
        labels={
            "region": "Metropolitan region",
            "monthly_rent_cad": "Monthly asking rent (CAD)",
        },
        title=f"Two-bedroom apartment asking rent — {latest_period}",
    )
    comparison.update_traces(
        texttemplate="$%{y:,.0f}",
        textposition="outside",
        cliponaxis=False,
    )
    comparison.update_layout(
        template="plotly_white",
        showlegend=False,
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
        xaxis_tickangle=-25,
    )
    comparison_path_html = CHART_DIR / "latest_rent_comparison.html"
    comparison.write_html(
        comparison_path_html,
        include_plotlyjs=True,
    )

    unavailable_count = int(latest["is_available"].eq(0).sum())
    print(
        f"\nRegions unavailable in the latest comparison: "
        f"{unavailable_count}"
    )

    print(f"\nSaved analysis: {analysis_path}")
    print(f"Saved latest comparison: {comparison_path}")
    print(f"Saved trend chart: {trend_path}")
    print(f"Saved comparison chart: {comparison_path_html}")


if __name__ == "__main__":
    main()