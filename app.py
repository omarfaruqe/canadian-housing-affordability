from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analyze_data import ANALYSIS_SQL


PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "processed" / "housing.db"

st.set_page_config(
    page_title="Canadian Housing Affordability Explorer",
    page_icon="🏠",
    layout="wide",
)


@st.cache_data
def load_data(database_path, modification_time):
    # modification_time refreshes the cache when the database changes.
    with sqlite3.connect(
        Path(database_path).as_uri() + "?mode=ro",
        uri=True,
    ) as connection:
        return pd.read_sql_query(
            ANALYSIS_SQL,
            connection,
            parse_dates=["reference_date"],
        )


def format_money(value):
    return "Unavailable" if pd.isna(value) else f"${value:,.0f}"


def format_change(value):
    return "Unavailable" if pd.isna(value) else f"{value:+.2f}%"


st.title("🏠 Canadian Housing Affordability Explorer")
st.write(
    "Explore apartment rental estimates across Canadian metropolitan "
    "regions, compare trends, and inspect data quality."
)
st.caption(
    "Source: Statistics Canada, Table 46-10-0092-01. "
    "Experimental estimates; regions represent metropolitan areas "
    "or metropolitan-area parts."
)

if not DB_PATH.exists():
    st.error(
        "Database not found. Run: python src/build_database.py"
    )
    st.stop()

data = load_data(str(DB_PATH), DB_PATH.stat().st_mtime_ns)

# -------------------- Filters --------------------

st.sidebar.header("Explore the data")

rent_measure = st.sidebar.selectbox(
    "Rent measure",
    options=["asking", "paid"],
    format_func=lambda value: {
        "asking": "Average asking rent",
        "paid": "Average paid rent",
    }[value],
)

preferred_order = [
    "Studio", "1 bedroom", "2 bedrooms", "3+ bedrooms"
]
available_types = set(
    data.loc[
        data["rent_measure"].eq(rent_measure),
        "apartment_type",
    ]
)
type_options = [
    value for value in preferred_order if value in available_types
]

if not type_options:
    st.info("No apartment categories are available for this measure.")
    st.stop()

apartment_type = st.sidebar.selectbox(
    "Apartment type",
    options=type_options,
    index=(
        type_options.index("2 bedrooms")
        if "2 bedrooms" in type_options else 0
    ),
)

base = data.loc[
    data["rent_measure"].eq(rent_measure)
    & data["apartment_type"].eq(apartment_type)
].copy()

# Show all project regions, including those without this category.
region_options = sorted(data["region"].unique())

selected_regions = st.sidebar.multiselect(
    "Metropolitan regions",
    options=region_options,
    default=region_options,
)

if not selected_regions:
    st.info("Select at least one metropolitan region.")
    st.stop()

periods = sorted(base["period"].unique().tolist())

if len(periods) > 1:
    start_period, end_period = st.sidebar.select_slider(
        "Quarter range",
        options=periods,
        value=(periods[0], periods[-1]),
    )
else:
    start_period = end_period = periods[0]
    st.sidebar.caption(f"Available quarter: {end_period}")

exclude_caution = st.sidebar.checkbox(
    "Exclude estimates flagged 'use with caution'",
    value=False,
)

selected = base.loc[
    base["region"].isin(selected_regions)
    & base["period"].between(start_period, end_period)
].copy()

# Mask flagged values instead of removing rows, preserving chart gaps.
if exclude_caution:
    selected.loc[
        selected["use_with_caution"].eq(1),
        "monthly_rent_cad",
    ] = float("nan")

    for prefix in ["qoq", "yoy"]:
        selected.loc[
            selected[f"{prefix}_use_with_caution"].eq(1),
            f"{prefix}_change_pct",
        ] = float("nan")

st.sidebar.caption(
    "Asking rent is an advertised price. Paid rent reflects rent "
    "actually paid. Their coverage and populations can differ."
)

# -------------------- Region summary --------------------

st.subheader(f"{apartment_type} · Average {rent_measure} rent")
st.caption(f"Selected period: {start_period} to {end_period}")

focus_region = st.selectbox(
    "Region for summary",
    options=selected_regions,
    index=(
        selected_regions.index("Montréal")
        if "Montréal" in selected_regions else 0
    ),
)

current = selected.loc[
    selected["region"].eq(focus_region)
    & selected["period"].eq(end_period)
]

st.caption(f"Summary for {focus_region} — {end_period}")

if current.empty:
    st.info(
        "No observation exists for this region, apartment type, "
        "rent measure, and quarter."
    )
else:
    row = current.iloc[0]
    first, second, third = st.columns(3)

    first.metric(
        "Monthly rent",
        format_money(row["monthly_rent_cad"]),
    )
    second.metric(
        "Quarter-over-quarter change",
        format_change(row["qoq_change_pct"]),
    )
    third.metric(
        "Year-over-year change",
        format_change(row["yoy_change_pct"]),
    )

    if row["use_with_caution"] == 1:
        st.warning("The current rent estimate is flagged: use with caution.")

    caution_comparisons = [
        label
        for prefix, label in [
            ("qoq", "quarter-over-quarter"),
            ("yoy", "year-over-year"),
        ]
        if row[f"{prefix}_use_with_caution"] == 1
    ]

    if caution_comparisons:
        st.warning(
            "Use caution for these comparisons: "
            + ", ".join(caution_comparisons)
            + ". At least one underlying estimate carries an E flag."
        )

    if exclude_caution:
        st.caption(
            "Caution-flagged rents and changes involving a flagged "
            "estimate are displayed as unavailable."
        )

st.caption(
    "Changes compare exact calendar quarters and may use an earlier "
    "observation outside the displayed date range."
)

# -------------------- Trend chart --------------------

period_dates = pd.period_range(
    start_period,
    end_period,
    freq="Q",
).to_timestamp()

grid = pd.MultiIndex.from_product(
    [selected_regions, period_dates],
    names=["region", "reference_date"],
)

trend_data = (
    selected.set_index(["region", "reference_date"])
    .reindex(grid)
    .reset_index()
)

st.subheader("Rent trends")

if trend_data["monthly_rent_cad"].notna().any():
    trend = px.line(
        trend_data,
        x="reference_date",
        y="monthly_rent_cad",
        color="region",
        markers=True,
        hover_data=["quality_note"],
        labels={
            "reference_date": "Quarter",
            "monthly_rent_cad": "Monthly rent (CAD)",
            "region": "Metropolitan region",
        },
    )
    trend.update_traces(connectgaps=False)
    trend.update_layout(
        template="plotly_white",
        hovermode="x unified",
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
    )
    st.plotly_chart(trend, width="stretch")
else:
    st.info("No displayable rents match the selected filters.")

st.caption(
    "Gaps represent missing observations or estimates excluded "
    "by the caution filter."
)

# -------------------- Common-quarter comparison --------------------

st.subheader(f"Region comparison — {end_period}")

latest = selected.loc[
    selected["period"].eq(end_period)
].copy()

displayable = latest.loc[
    latest["monthly_rent_cad"].notna()
].sort_values("monthly_rent_cad", ascending=False)

if not displayable.empty:
    comparison = px.bar(
        displayable,
        x="region",
        y="monthly_rent_cad",
        color="region",
        text="monthly_rent_cad",
        hover_data=["quality_note"],
        labels={
            "region": "Metropolitan region",
            "monthly_rent_cad": "Monthly rent (CAD)",
        },
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
        xaxis_tickangle=-25,
    )
    st.plotly_chart(comparison, width="stretch")
else:
    st.info("No displayable rents exist for the selected end quarter.")

missing_regions = sorted(
    set(selected_regions) - set(displayable["region"])
)
if missing_regions:
    st.info(
        f"No displayable estimate for {end_period}: "
        + ", ".join(missing_regions)
    )

# -------------------- Affordability calculator --------------------

st.divider()
st.subheader("Housing budget calculator")

st.write(
    f"Compare {apartment_type.lower()} {rent_measure} rents for "
    f"{end_period} with your household housing budget."
)

income_column, target_column, costs_column = st.columns(3)

with income_column:
    annual_income = st.number_input(
        "Annual household income before tax (CAD)",
        min_value=0.0,
        value=80000.0,
        step=1000.0,
        format="%.2f",
        key="calculator_annual_income",
    )

with target_column:
    target_percentage = st.number_input(
        "Target share of income for housing (%)",
        min_value=1.0,
        max_value=100.0,
        value=30.0,
        step=1.0,
        format="%.1f",
        key="calculator_target_percentage",
    )

with costs_column:
    extra_monthly_costs = st.number_input(
        "Extra monthly housing costs (CAD)",
        min_value=0.0,
        value=150.0,
        step=25.0,
        format="%.2f",
        key="calculator_extra_costs",
        help=(
            "Add costs such as utilities or tenant insurance only "
            "when they are not already included in rent. "
            "The same assumed amount applies to every selected region."
        ),
    )

st.caption(
    "Income is before tax. Enter extra costs not already included "
    "in rent. The target percentage is adjustable; this calculator "
    "does not assess official core housing need."
)

if annual_income <= 0:
    st.info("Enter an annual household income greater than zero.")
else:
    monthly_income = annual_income / 12
    target_fraction = target_percentage / 100
    monthly_budget = monthly_income * target_fraction
    rent_budget = monthly_budget - extra_monthly_costs

    budget_column, rent_column = st.columns(2)

    budget_column.metric(
        "Monthly housing budget",
        f"${monthly_budget:,.2f}",
    )
    rent_column.metric(
        "Budget remaining for rent",
        f"${max(rent_budget, 0):,.2f}",
    )

    if rent_budget < 0:
        st.warning(
            "Extra housing costs alone exceed your selected "
            "monthly housing budget."
        )

    # latest already reflects the selected quarter and caution filter.
    # Reindex so every selected region appears, including missing ones.
    scenario = (
        latest.set_index("region")
        .reindex(selected_regions)
        .rename_axis("region")
        .reset_index()
    )

    scenario["period"] = end_period
    scenario["apartment_type"] = apartment_type
    scenario["rent_measure"] = rent_measure

    scenario["annual_household_income_cad"] = annual_income
    scenario["target_percentage"] = target_percentage
    scenario["extra_monthly_costs_cad"] = extra_monthly_costs
    scenario["monthly_housing_budget_cad"] = monthly_budget

    scenario["estimated_monthly_housing_cost_cad"] = (
        scenario["monthly_rent_cad"] + extra_monthly_costs
    )
    scenario["housing_share_of_income_pct"] = (
        scenario["estimated_monthly_housing_cost_cad"]
        / monthly_income
        * 100
    )
    scenario["monthly_budget_balance_cad"] = (
        monthly_budget
        - scenario["estimated_monthly_housing_cost_cad"]
    )
    scenario["annual_income_needed_at_target_cad"] = (
        scenario["estimated_monthly_housing_cost_cad"]
        / target_fraction
        * 12
    )

    has_rent = scenario["monthly_rent_cad"].notna()
    within_target = (
        scenario["estimated_monthly_housing_cost_cad"]
        <= monthly_budget + 1e-9
    )

    scenario["budget_result"] = "Unavailable"
    scenario.loc[
        has_rent & within_target, "budget_result"
    ] = "Within target"
    scenario.loc[
        has_rent & ~within_target, "budget_result"
    ] = "Above target"

    scenario["quality_note"] = scenario["quality_note"].fillna(
        "No observation for this selection"
    )

    if exclude_caution:
        scenario.loc[
            scenario["use_with_caution"].eq(1),
            "quality_note",
        ] = "Caution-flagged estimate excluded"

    st.markdown(f"**Budget result for {focus_region}**")

    focus_scenario = scenario.loc[
        scenario["region"].eq(focus_region)
    ].iloc[0]

    if pd.isna(focus_scenario["monthly_rent_cad"]):
        st.info(
            "No displayable rent estimate exists for this selection. "
            "Choose another quarter, category, or region."
        )
    else:
        cost_column, share_column, needed_column = st.columns(3)

        cost_column.metric(
            "Estimated monthly housing cost",
            f"${focus_scenario['estimated_monthly_housing_cost_cad']:,.2f}",
        )
        share_column.metric(
            "Share of before-tax income",
            f"{focus_scenario['housing_share_of_income_pct']:.2f}%",
        )
        needed_column.metric(
            "Annual income needed at target",
            f"${focus_scenario['annual_income_needed_at_target_cad']:,.0f}",
        )

        balance = focus_scenario["monthly_budget_balance_cad"]

        if focus_scenario["budget_result"] == "Within target":
            st.success(
                f"Within your {target_percentage:.1f}% target, "
                f"with ${max(balance, 0):,.2f} remaining in the "
                "monthly housing budget."
            )
        else:
            st.warning(
                f"Above your {target_percentage:.1f}% target "
                f"by ${abs(balance):,.2f} per month."
            )

        if focus_scenario["use_with_caution"] == 1:
            st.warning(
                "This budget calculation uses a rent estimate "
                "flagged 'use with caution'."
            )

    st.markdown("**Compare selected regions**")

    scenario_columns = [
        "region",
        "monthly_rent_cad",
        "estimated_monthly_housing_cost_cad",
        "housing_share_of_income_pct",
        "monthly_budget_balance_cad",
        "annual_income_needed_at_target_cad",
        "budget_result",
        "quality_note",
    ]

    st.dataframe(
        scenario[scenario_columns].round(2),
        hide_index=True,
        width="stretch",
    )

    chart_data = scenario.loc[has_rent].sort_values(
        "housing_share_of_income_pct"
    )

    if not chart_data.empty:
        budget_chart = px.bar(
            chart_data,
            x="region",
            y="housing_share_of_income_pct",
            color="budget_result",
            color_discrete_map={
                "Within target": "#228B69",
                "Above target": "#C56729",
            },
            hover_data=["quality_note"],
            labels={
                "region": "Metropolitan region",
                "housing_share_of_income_pct": "Share of income (%)",
                "budget_result": "Budget result",
            },
            title=f"Estimated housing cost as a share of income — {end_period}",
        )
        budget_chart.add_hline(
            y=target_percentage,
            line_dash="dash",
            annotation_text=f"Your target: {target_percentage:.1f}%",
        )
        budget_chart.update_layout(
            template="plotly_white",
            yaxis_ticksuffix="%",
            xaxis_tickangle=-25,
        )
        st.plotly_chart(budget_chart, width="stretch")

    st.download_button(
        label="Download housing budget scenario (CSV)",
        data=scenario.to_csv(index=False).encode("utf-8-sig"),
        file_name="housing_budget_scenario.csv",
        mime="text/csv",
        key="download_budget_scenario",
    )

    st.caption(
        "The scenario download includes your entered income and cost "
        "assumptions. Positive budget balance means room within the "
        "housing budget; it is not total household disposable income."
    )

# -------------------- Table and export --------------------

st.subheader("Explore and download observations")

table_columns = [
    "period",
    "region",
    "apartment_type",
    "rent_measure",
    "monthly_rent_cad",
    "qoq_change_pct",
    "yoy_change_pct",
    "quality_note",
    "qoq_use_with_caution",
    "yoy_use_with_caution",
]

table = selected.sort_values(
    ["reference_date", "region"],
    ascending=[False, True],
)[table_columns]

st.dataframe(table.round(2), hide_index=True, width="stretch")

# Export original observations, including flags, for transparency.
export = base.loc[
    base["region"].isin(selected_regions)
    & base["period"].between(start_period, end_period)
].copy()

st.download_button(
    label="Download selected source observations (CSV)",
    data=export.to_csv(index=False).encode("utf-8-sig"),
    file_name="selected_rental_observations.csv",
    mime="text/csv",
)

st.caption(
    "The download preserves original values and quality flags, "
    "including estimates hidden by the caution filter."
)

with st.expander("Data quality and interpretation"):
    st.markdown(
        """
        - **E:** Use with caution.
        - **F:** Too unreliable to publish.
        - **..:** Unavailable for the reference period.
        - Missing values remain missing and are never treated as zero.
        - Changes are unavailable when either required rent is missing.
        - Ottawa–Gatineau's Ontario and Quebec parts remain separate.
        - Published averages describe rental categories, not individual
          apartment listings.
        - Rents are shown in nominal Canadian dollars, without an
          inflation adjustment.
        """
    )
    st.markdown(
        "[View the Statistics Canada source table]"
        "(https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=4610009201)"
    )