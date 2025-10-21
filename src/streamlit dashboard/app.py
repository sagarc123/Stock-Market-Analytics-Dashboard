import logging
import os
from datetime import datetime
from io import StringIO

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
API = "https://stock-market-analytics-dashboard.onrender.com"

# --- DARK THEME COLORS ---
THEME = {
    "primary": "#00D4AA",  # Teal accent
    "secondary": "#FF6B9D",  # Pink accent
    "bullish": "#00D4AA",  # Green for bullish
    "bearish": "#FF6B9D",  # Red for bearish
    "stable": "#6C757D",  # Gray
    "text": "#E9ECEF",  # Light text
    "text_muted": "#ADB5BD",  # Muted text
    "background": "#0D1117",  # Dark background
    "card_bg": "#161B22",  # Card background
    "card_border": "#30363D",  # Card border
    "card_shadow": "0 4px 12px rgba(0, 0, 0, 0.3)",
    "grid": "rgba(255, 255, 255, 0.1)",
    "hover": "#1C2128",  # Hover state
}

# --- Streamlit Page Config ---
st.set_page_config(
    page_title="Enhanced Stock Market Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Helper Functions ---
def validate_period(period):
    """Validates if the input is a valid YYYY or YYYY-MM string."""
    if not period:
        return None

    period = period.strip()

    if len(period) == 7 and period.count("-") == 1:
        try:
            year, month = map(int, period.split("-"))
            if 1 <= month <= 12 and 1900 < year < 2100:
                return period
        except ValueError:
            pass
    elif len(period) == 4 and period.isdigit():
        try:
            year = int(period)
            if 1900 < year < 2100:
                return period
        except ValueError:
            pass

    return None


def check_api_health():
    """Check if the API server is running and healthy."""
    try:
        response = requests.get(f"{API}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("data_loaded"):
                return True, "🟢 API: Connected", "🟢 Data: Loaded"
            else:
                db_exists = data.get("database_exists", False)
                data_rows = data.get("data_rows", 0)
                if db_exists and data_rows > 0:
                    return (
                        True,
                        "🟢 API: Connected",
                        f"🟢 Data: {data_rows} rows loaded",
                    )
                elif db_exists:
                    return True, "🟢 API: Connected", "🔴 Data: Table empty or missing"
                else:
                    return (
                        True,
                        "🟢 API: Connected",
                        "🔴 Data: Database file not found",
                    )
        else:
            return False, f"🔴 API: HTTP {response.status_code}", ""
    except requests.exceptions.RequestException as e:
        logging.error(f"Health check failed: {e}")
        return False, "🔴 API: Not Connected", ""


def fetch_data(period_input):
    """Fetches data from the API."""
    # Check API health first
    api_healthy, api_status, data_status = check_api_health()
    if not api_healthy:
        return None, None, None, api_status, data_status

    valid_period = validate_period(period_input)
    if valid_period is None:
        return None, None, None, api_status, "🔴 Invalid period format"

    # Fetch data from API
    try:
        prices_response = requests.get(
            f"{API}/data/daily_prices",
            params={"period": valid_period, "limit": 500},
            timeout=10,
        )
        prices_response.raise_for_status()
        prices_data = prices_response.json()

        sectors_response = requests.get(
            f"{API}/metrics/sector_summary", params={"period": valid_period}, timeout=10
        )
        sectors_response.raise_for_status()
        sectors_data = sectors_response.json()

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data: {e}")
        return None, None, None, api_status, f"🔴 Error fetching data: {str(e)}"

    # Process data
    df_prices = pd.DataFrame(prices_data)
    if df_prices.empty:
        return None, None, None, api_status, "🔴 No data available for period"

    # Calculate summary metrics
    total_companies = len(df_prices)

    # Ensure numeric columns
    numeric_cols = ["Close", "Volume", "Volatility"]
    for col in numeric_cols:
        if col in df_prices.columns:
            df_prices[col] = pd.to_numeric(df_prices[col], errors="coerce").fillna(0)

    avg_close = df_prices["Close"].mean() if "Close" in df_prices.columns else 0
    total_volume_sum = df_prices["Volume"].sum() if "Volume" in df_prices.columns else 0
    avg_volatility = (
        df_prices["Volatility"].mean() * 100 if "Volatility" in df_prices.columns else 0
    )

    summary_data = {
        "period": valid_period,
        "total_companies": total_companies,
        "avg_close": avg_close,
        "total_volume": total_volume_sum,
        "avg_volatility": avg_volatility,
    }

    # Store data
    if "Close" in df_prices.columns and "Volume" in df_prices.columns:
        df_prices["Relative_Liquidity"] = df_prices["Close"] * df_prices["Volume"]

    df_sectors = pd.DataFrame(sectors_data)

    return (
        df_prices,
        df_sectors,
        summary_data,
        api_status,
        "🟢 Data loaded successfully",
    )


def fetch_comparison_data(year1, year2):
    """Fetch data for year comparison."""
    try:
        data_year1 = requests.get(
            f"{API}/data/daily_prices",
            params={"period": str(year1), "limit": 500},
            timeout=10,
        ).json()
        data_year2 = requests.get(
            f"{API}/data/daily_prices",
            params={"period": str(year2), "limit": 500},
            timeout=10,
        ).json()

        df_year1 = pd.DataFrame(data_year1)
        df_year2 = pd.DataFrame(data_year2)

        return df_year1, df_year2, None
    except Exception as e:
        logging.error(f"Error fetching comparison data: {e}")
        return pd.DataFrame(), pd.DataFrame(), str(e)


def create_empty_figure(title, message="No data available for current selection"):
    """Creates an empty figure with a message."""
    fig = go.Figure()
    fig.update_layout(
        title={
            "text": title,
            "font": {"size": 20, "color": THEME["primary"], "family": "Inter"},
        },
        plot_bgcolor=THEME["card_bg"],
        paper_bgcolor=THEME["background"],
        font={"family": "Inter", "color": THEME["text"]},
        height=400,
        margin={"t": 60, "b": 40, "l": 60, "r": 40},
    )
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        xanchor="center",
        yanchor="middle",
        showarrow=False,
        font={"size": 16, "color": THEME["text_muted"], "family": "Inter"},
    )
    return fig


def apply_chart_style(fig, title, xaxis_title, yaxis_title, height=450):
    """Applies consistent dark theme styling to charts."""
    fig.update_layout(
        title={
            "text": title,
            "font": {
                "size": 20,
                "color": THEME["primary"],
                "family": "Inter",
                "weight": "bold",
            },
            "x": 0.05,
            "y": 0.95,
        },
        xaxis={
            "title": {
                "text": xaxis_title,
                "font": {"size": 14, "color": THEME["text"], "family": "Inter"},
            },
            "gridcolor": THEME["grid"],
            "gridwidth": 1,
            "tickfont": {"size": 12, "color": THEME["text_muted"], "family": "Inter"},
            "showline": True,
            "linecolor": THEME["card_border"],
            "linewidth": 1,
            "zerolinecolor": THEME["card_border"],
        },
        yaxis={
            "title": {
                "text": yaxis_title,
                "font": {"size": 14, "color": THEME["text"], "family": "Inter"},
            },
            "gridcolor": THEME["grid"],
            "gridwidth": 1,
            "tickfont": {"size": 12, "color": THEME["text_muted"], "family": "Inter"},
            "showline": True,
            "linecolor": THEME["card_border"],
            "linewidth": 1,
            "zerolinecolor": THEME["card_border"],
        },
        plot_bgcolor=THEME["card_bg"],
        paper_bgcolor=THEME["background"],
        font={"family": "Inter", "color": THEME["text"]},
        height=height,
        margin={"t": 100, "b": 100, "l": 80, "r": 40},
        hoverlabel={
            "bgcolor": THEME["card_bg"],
            "bordercolor": THEME["card_border"],
            "font_size": 12,
            "font_family": "Inter",
            "font_color": THEME["text"],
        },
        legend={
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"size": 12, "color": THEME["text"], "family": "Inter"},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )
    return fig


# --- Chart Creation Functions ---
def create_market_cap_chart(df_filtered):
    """Creates market cap chart."""
    try:
        if (
            "Market_Cap" not in df_filtered.columns
            or "Company" not in df_filtered.columns
        ):
            return create_empty_figure("Market Cap Data Missing")

        df_cap = df_filtered[df_filtered["Market_Cap"] > 0].nlargest(10, "Market_Cap")
        if df_cap.empty:
            return create_empty_figure("Top Companies by Market Cap")
        else:
            fig_cap = px.bar(
                df_cap,
                x="Company",
                y="Market_Cap",
                color="Market_Cap",
                color_continuous_scale="Viridis",
            )
            return apply_chart_style(
                fig_cap,
                "Top Companies by Market Cap",
                "Company",
                "Market Cap ($)",
            )
    except Exception as e:
        logging.error(f"Error creating market cap chart: {e}")
        return create_empty_figure("Chart Error")


def create_sector_pie_chart(df_filtered):
    """Creates sector pie chart."""
    try:
        if "Sector" not in df_filtered.columns or "Close" not in df_filtered.columns:
            return create_empty_figure("Sector Data Missing")

        sector_liq = df_filtered.groupby("Sector")["Close"].mean().reset_index()
        sector_liq = sector_liq[sector_liq["Close"] > 0]
        if sector_liq.empty:
            return create_empty_figure("Sector Performance")
        else:
            mini_fig = px.pie(
                sector_liq,
                names="Sector",
                values="Close",
                hole=0.6,
                color_discrete_sequence=px.colors.qualitative.Dark24,
            )
            return apply_chart_style(
                mini_fig, "Sector Performance Distribution", "", ""
            )
    except Exception as e:
        logging.error(f"Error creating sector pie chart: {e}")
        return create_empty_figure("Chart Error")


def create_volatility_chart(df_filtered):
    """Creates volatility chart."""
    try:
        if (
            "Volatility" not in df_filtered.columns
            or "Company" not in df_filtered.columns
        ):
            return create_empty_figure("Volatility Data Missing")

        df_vol = df_filtered[df_filtered["Volatility"] > 0].nlargest(10, "Volatility")
        if df_vol.empty:
            return create_empty_figure("Top Volatile Stocks")
        else:
            volatility_pct = df_vol["Volatility"] * 100
            fig_vol = px.bar(
                df_vol,
                x="Company",
                y=volatility_pct,
                color=volatility_pct,
                color_continuous_scale="reds",
            )
            return apply_chart_style(
                fig_vol, "Top Volatile Stocks", "Company", "Volatility (%)"
            )
    except Exception as e:
        logging.error(f"Error creating volatility chart: {e}")
        return create_empty_figure("Chart Error")


def create_scatter_chart(df_filtered):
    """Creates scatter chart."""
    try:
        required_cols = ["Volume", "Close", "Market_Cap", "Sector", "Company"]
        missing_cols = [col for col in required_cols if col not in df_filtered.columns]
        if missing_cols:
            return create_empty_figure(f"Missing columns: {', '.join(missing_cols)}")

        df_scatter = df_filtered[
            (df_filtered["Volume"] > 0)
            & (df_filtered["Close"] > 0)
            & (df_filtered["Market_Cap"] > 0)
        ]
        if df_scatter.empty:
            return create_empty_figure("Price vs Volume")
        else:
            fig_scatter = px.scatter(
                df_scatter,
                x="Volume",
                y="Close",
                size="Market_Cap",
                color="Sector",
                hover_name="Company",
                size_max=30,
                color_discrete_sequence=px.colors.qualitative.Dark24,
            )
            return apply_chart_style(
                fig_scatter,
                "Price vs Volume Analysis",
                "Trading Volume",
                "Close Price ($)",
            )
    except Exception as e:
        logging.error(f"Error creating scatter chart: {e}")
        return create_empty_figure("Chart Error")


def create_trend_chart(df_filtered):
    """Creates trend chart."""
    try:
        if "Trend" not in df_filtered.columns:
            return create_empty_figure("Trend Data Missing")

        trend_counts = (
            df_filtered["Trend"].fillna("Neutral").value_counts().reset_index()
        )
        trend_counts.columns = ["Trend", "Count"]
        if trend_counts.empty:
            return create_empty_figure("Trend Distribution")
        else:
            trend_fig = px.bar(
                trend_counts,
                x="Trend",
                y="Count",
                color="Trend",
                color_discrete_sequence=px.colors.qualitative.Dark24,
            )
            return apply_chart_style(
                trend_fig,
                "Market Trend Distribution",
                "Trend",
                "Number of Companies",
            )
    except Exception as e:
        logging.error(f"Error creating trend chart: {e}")
        return create_empty_figure("Chart Error")


def create_sector_volume_chart(df_filtered):
    """Creates sector volume chart."""
    try:
        if "Sector" not in df_filtered.columns or "Volume" not in df_filtered.columns:
            return create_empty_figure("Sector Volume Data Missing")

        sector_volume = df_filtered.groupby("Sector")["Volume"].sum().reset_index()
        sector_volume = sector_volume[sector_volume["Volume"] > 0]
        if sector_volume.empty:
            return create_empty_figure("Sector Volume")
        else:
            fig_vol = px.bar(
                sector_volume,
                x="Sector",
                y="Volume",
                color="Volume",
                color_continuous_scale="blues",
            )
            return apply_chart_style(
                fig_vol,
                "Sector Trading Volume Comparison",
                "Sector",
                "Total Volume",
            )
    except Exception as e:
        logging.error(f"Error creating sector volume chart: {e}")
        return create_empty_figure("Chart Error")


def create_sector_liquidity_chart(df_filtered):
    """Creates sector liquidity chart."""
    try:
        required_cols = ["Sector", "Close", "Volume"]
        missing_cols = [col for col in required_cols if col not in df_filtered.columns]
        if missing_cols:
            return create_empty_figure(f"Missing columns: {', '.join(missing_cols)}")

        sector_liquidity = (
            df_filtered.groupby("Sector")
            .agg({"Close": "mean", "Volume": "sum"})
            .reset_index()
        )
        sector_liquidity["Liquidity"] = (
            sector_liquidity["Close"] * sector_liquidity["Volume"]
        )
        sector_liquidity = sector_liquidity[sector_liquidity["Liquidity"] > 0]

        if sector_liquidity.empty:
            return create_empty_figure("Sector Liquidity")
        else:
            fig_liq = px.scatter(
                sector_liquidity,
                x="Close",
                y="Liquidity",
                size="Volume",
                hover_name="Sector",
                color="Sector",
                color_discrete_sequence=px.colors.qualitative.Dark24,
            )
            return apply_chart_style(
                fig_liq,
                "Sector Liquidity Analysis",
                "Average Close Price ($)",
                "Liquidity (Close × Volume)",
            )
    except Exception as e:
        logging.error(f"Error creating sector liquidity chart: {e}")
        return create_empty_figure("Chart Error")


def create_correlation_heatmap(df_filtered):
    """Creates correlation heatmap."""
    try:
        numeric_df = df_filtered.select_dtypes(include=[np.number])
        if len(numeric_df.columns) > 1:
            correlation_matrix = numeric_df.corr()
            corr_fig = px.imshow(
                correlation_matrix,
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="RdBu_r",
            )
            return apply_chart_style(corr_fig, "Feature Correlation Matrix", "", "")
        else:
            return create_empty_figure("Insufficient Data for Correlation")
    except Exception as e:
        logging.error(f"Error creating correlation heatmap: {e}")
        return create_empty_figure("Correlation Error")


def create_valuation_chart(df_filtered):
    """Creates valuation scatter chart."""
    try:
        required_cols = ["PE_Ratio", "Close", "Sector", "Company", "Market_Cap"]
        missing_cols = [col for col in required_cols if col not in df_filtered.columns]
        if missing_cols:
            return create_empty_figure(f"Missing columns: {', '.join(missing_cols)}")

        valuation_df = df_filtered[
            (df_filtered["PE_Ratio"] > 0)
            & (df_filtered["PE_Ratio"] < 1000)
            & (df_filtered["Close"] > 0)
        ]
        if valuation_df.empty:
            return create_empty_figure("Valuation Analysis")
        else:
            val_fig = px.scatter(
                valuation_df,
                x="PE_Ratio",
                y="Close",
                color="Sector",
                hover_name="Company",
                size="Market_Cap",
                size_max=30,
                color_discrete_sequence=px.colors.qualitative.Dark24,
            )
            return apply_chart_style(
                val_fig,
                "P/E Ratio vs Close Price Analysis",
                "P/E Ratio",
                "Close Price ($)",
            )
    except Exception as e:
        logging.error(f"Error creating valuation scatter: {e}")
        return create_empty_figure("Chart Error")


def create_pe_distribution(df_filtered):
    """Creates P/E distribution chart."""
    try:
        if "PE_Ratio" not in df_filtered.columns:
            return create_empty_figure("P/E Ratio Data Missing")

        pe_df = df_filtered[
            (df_filtered["PE_Ratio"] > 0) & (df_filtered["PE_Ratio"] < 1000)
        ]
        if pe_df.empty:
            return create_empty_figure("P/E Distribution")
        else:
            pe_fig = px.histogram(
                pe_df,
                x="PE_Ratio",
                nbins=20,
                color_discrete_sequence=[THEME["primary"]],
            )
            return apply_chart_style(
                pe_fig, "P/E Ratio Distribution", "P/E Ratio", "Frequency"
            )
    except Exception as e:
        logging.error(f"Error creating P/E distribution: {e}")
        return create_empty_figure("Chart Error")


# --- Comparison Chart Functions ---
def create_year_comparison_bar(year1, year2, metric, df_year1, df_year2):
    """Creates year comparison bar chart."""
    try:
        metric_names = {
            "Close": "Average Close Price ($)",
            "Volume": "Total Volume",
            "Market_Cap": "Market Capitalization ($)",
            "Volatility": "Average Volatility (%)",
            "PE_Ratio": "Average P/E Ratio",
        }

        if metric in ["Close", "Volatility", "PE_Ratio"]:
            y1_value = df_year1[metric].mean() if not df_year1.empty else 0
            y2_value = df_year2[metric].mean() if not df_year2.empty else 0
        else:  # Volume, Market_Cap
            y1_value = df_year1[metric].sum() if not df_year1.empty else 0
            y2_value = df_year2[metric].sum() if not df_year2.empty else 0

        if metric == "Volatility":
            y1_value *= 100
            y2_value *= 100

        comparison_df = pd.DataFrame(
            {"Year": [str(year1), str(year2)], "Value": [y1_value, y2_value]}
        )

        fig_bar = px.bar(
            comparison_df,
            x="Year",
            y="Value",
            color="Year",
            color_discrete_sequence=[THEME["primary"], THEME["secondary"]],
        )
        fig_bar = apply_chart_style(
            fig_bar,
            f"{metric_names.get(metric, metric)} Comparison",
            "Year",
            metric_names.get(metric, metric),
        )
        return fig_bar
    except Exception as e:
        logging.error(f"Error creating year comparison chart: {e}")
        return create_empty_figure("Chart Error")


def create_sector_growth_line(year1, year2, metric, df_year1, df_year2):
    """Creates sector growth line chart."""
    try:
        if "Sector" not in df_year1.columns or "Sector" not in df_year2.columns:
            return create_empty_figure("Sector data not available")

        sector_growth = []
        sectors = set(df_year1["Sector"].dropna().unique()) | set(
            df_year2["Sector"].dropna().unique()
        )

        for sector in sectors:
            sector_data1 = df_year1[df_year1["Sector"] == sector]
            sector_data2 = df_year2[df_year2["Sector"] == sector]

            if metric in ["Close", "Volatility", "PE_Ratio"]:
                val1 = sector_data1[metric].mean() if not sector_data1.empty else 0
                val2 = sector_data2[metric].mean() if not sector_data2.empty else 0
            else:
                val1 = sector_data1[metric].sum() if not sector_data1.empty else 0
                val2 = sector_data2[metric].sum() if not sector_data2.empty else 0

            if metric == "Volatility":
                val1 *= 100
                val2 *= 100

            if val1 > 0 and val2 > 0:
                growth = ((val2 - val1) / val1) * 100
                sector_growth.append(
                    {
                        "Sector": sector,
                        "Growth (%)": growth,
                        f"{year1}": val1,
                        f"{year2}": val2,
                    }
                )

        if sector_growth:
            growth_df = pd.DataFrame(sector_growth)
            fig_line = px.line(
                growth_df.sort_values("Growth (%)"),
                x="Sector",
                y="Growth (%)",
                markers=True,
                color_discrete_sequence=[THEME["primary"]],
            )
            fig_line = apply_chart_style(
                fig_line,
                f"Sector Growth Rate ({year1} to {year2})",
                "Sector",
                "Growth Rate (%)",
            )
            return fig_line
        else:
            return create_empty_figure("No sector growth data available")
    except Exception as e:
        logging.error(f"Error creating sector growth chart: {e}")
        return create_empty_figure("Chart Error")


def create_performance_trend(year1, year2, metric):
    """Creates performance trend chart."""
    try:
        years = [year1, year2]
        avg_values = []
        metric_names = {
            "Close": "Average Close Price ($)",
            "Volume": "Total Volume",
            "Market_Cap": "Market Capitalization ($)",
            "Volatility": "Average Volatility (%)",
            "PE_Ratio": "Average P/E Ratio",
        }

        for year in years:
            try:
                year_data = requests.get(
                    f"{API}/data/daily_prices",
                    params={"period": str(year), "limit": 500},
                    timeout=10,
                ).json()
                year_df = pd.DataFrame(year_data)
                if not year_df.empty and metric in year_df.columns:
                    year_df[metric] = pd.to_numeric(year_df[metric], errors="coerce")
                    if metric in ["Close", "Volatility", "PE_Ratio"]:
                        avg_val = year_df[metric].mean()
                    else:
                        avg_val = year_df[metric].sum()

                    if metric == "Volatility":
                        avg_val *= 100

                    avg_values.append(avg_val)
                else:
                    avg_values.append(0)
            except:
                avg_values.append(0)

        trend_df = pd.DataFrame(
            {"Year": [str(year) for year in years], "Value": avg_values}
        )

        fig_trend = px.line(
            trend_df,
            x="Year",
            y="Value",
            markers=True,
            line_shape="linear",
            color_discrete_sequence=[THEME["primary"]],
        )
        fig_trend = apply_chart_style(
            fig_trend,
            f"{metric_names.get(metric, metric)} Trend",
            "Year",
            metric_names.get(metric, metric),
        )
        return fig_trend
    except Exception as e:
        logging.error(f"Error creating performance trend chart: {e}")
        return create_empty_figure("Chart Error")


def create_distribution_comparison(year1, year2, metric, df_year1, df_year2):
    """Creates distribution comparison chart."""
    try:
        metric_names = {
            "Close": "Average Close Price ($)",
            "Volume": "Total Volume",
            "Market_Cap": "Market Capitalization ($)",
            "Volatility": "Average Volatility (%)",
            "PE_Ratio": "Average P/E Ratio",
        }

        if (
            not df_year1.empty
            and not df_year2.empty
            and metric in df_year1.columns
            and metric in df_year2.columns
        ):
            df_year1["Year"] = str(year1)
            df_year2["Year"] = str(year2)
            combined_df = pd.concat(
                [df_year1[["Year", metric]], df_year2[["Year", metric]]]
            )

            fig_dist = px.box(
                combined_df,
                x="Year",
                y=metric,
                color="Year",
                color_discrete_sequence=[THEME["primary"], THEME["secondary"]],
            )
            fig_dist = apply_chart_style(
                fig_dist,
                f"{metric_names.get(metric, metric)} Distribution Comparison",
                "Year",
                metric_names.get(metric, metric),
            )
            return fig_dist
        else:
            return create_empty_figure("No distribution data available")
    except Exception as e:
        logging.error(f"Error creating distribution comparison chart: {e}")
        return create_empty_figure("Chart Error")


# --- Custom KPI Cards with Dark Theme ---
def create_kpi_card(title, value, subtitle=None):
    """Creates a styled KPI card with dark theme."""
    card_html = f"""
    <div style="
        background: {THEME['card_bg']};
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: {THEME['card_shadow']};
        border: 1px solid {THEME['card_border']};
        text-align: center;
        margin: 0.5rem;
        transition: all 0.3s ease;
    ">
        <div style="
            font-size: 0.9rem;
            color: {THEME['text_muted']};
            margin-bottom: 0.5rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        ">
            {title}
        </div>
        <div style="
            font-size: 1.8rem;
            font-weight: 700;
            color: {THEME['primary']};
            line-height: 1.2;
            margin-bottom: 0.5rem;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        ">
            {value}
        </div>
        {f'<div style="font-size: 0.75rem; color: {THEME["text_muted"]};">{subtitle}</div>' if subtitle else ''}
    </div>
    """
    return card_html


# --- Main Application ---
def main():
    # Initialize session state
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = "Never"
    if "current_period" not in st.session_state:
        st.session_state.current_period = "2023"
    if "comparison_data" not in st.session_state:
        st.session_state.comparison_data = {}

    # Custom CSS for Dark Theme
    st.markdown(
        f"""
    <style>
    /* Main background */
    .main .block-container {{
        background-color: {THEME['background']};
        padding-top: 2rem;
    }}
    
    /* Streamlit app background */
    .stApp {{
        background-color: {THEME['background']};
    }}
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {{
        color: {THEME['text']} !important;
    }}
    
    /* Text color */
    .stMarkdown, .stText, .stAlert {{
        color: {THEME['text']} !important;
    }}
    
    /* Sidebar */
    .css-1d391kg, .css-1lcbmhc {{
        background-color: {THEME['card_bg']} !important;
    }}
    
    /* Input fields */
    .stTextInput>div>div>input {{
        background-color: {THEME['card_bg']} !important;
        color: {THEME['text']} !important;
        border: 1px solid {THEME['card_border']} !important;
    }}
    
    .stSelectbox>div>div {{
        background-color: {THEME['card_bg']} !important;
        color: {THEME['text']} !important;
        border: 1px solid {THEME['card_border']} !important;
    }}
    
    /* Buttons */
    .stButton>button {{
        background-color: {THEME['primary']} !important;
        color: {THEME['background']} !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }}
    
    .stButton>button:hover {{
        background-color: #00B894 !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 212, 170, 0.3);
    }}
    
    /* Tabs */
    .stTabs {{
        background-color: {THEME['background']};
    }}
    
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        background-color: {THEME['card_bg']} !important;
        color: {THEME['text_muted']} !important;
        border: 1px solid {THEME['card_border']} !important;
        border-radius: 8px 8px 0 0 !important;
        padding: 12px 24px !important;
    }}
    
    .stTabs [aria-selected="true"] {{
        background-color: {THEME['primary']} !important;
        color: {THEME['background']} !important;
        border-color: {THEME['primary']} !important;
    }}
    
    /* Dataframes */
    .dataframe {{
        background-color: {THEME['card_bg']} !important;
        color: {THEME['text']} !important;
    }}
    
    /* Metric cards */
    .stMetric {{
        background-color: {THEME['card_bg']} !important;
        border: 1px solid {THEME['card_border']} !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        box-shadow: {THEME['card_shadow']} !important;
    }}
    
    .stMetric label {{
        color: {THEME['text_muted']} !important;
        font-weight: 600 !important;
    }}
    
    .stMetric div {{
        color: {THEME['primary']} !important;
        font-weight: 700 !important;
        font-size: 1.5rem !important;
    }}
    
    /* Info, success, warning boxes */
    .stAlert {{
        background-color: {THEME['card_bg']} !important;
        border: 1px solid {THEME['card_border']} !important;
        color: {THEME['text']} !important;
    }}
    
    /* Spinner */
    .stSpinner>div {{
        border-color: {THEME['primary']} !important;
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Header
    st.markdown(
        f"""
    <h1 style="color: {THEME['primary']}; text-align: center; margin-bottom: 2rem; 
                font-size: 2.5rem; font-weight: 700; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);">
        📈 Stock Market Analytics Dashboard
    </h1>
    """,
        unsafe_allow_html=True,
    )

    # Sidebar
    with st.sidebar:
        st.markdown(
            f"""
        <div style="background: {THEME['card_bg']}; padding: 1.5rem; border-radius: 12px; 
                    border: 1px solid {THEME['card_border']}; margin-bottom: 1rem;">
            <h2 style="color: {THEME['primary']}; margin-bottom: 1rem;">🔧 Controls</h2>
        """,
            unsafe_allow_html=True,
        )

        period_input = st.text_input(
            "**Select Period** (YYYY or YYYY-MM):",
            value=st.session_state.current_period,
            placeholder="e.g., 2023 or 2023-12",
            key="period_input",
        )

        if st.button("🚀 Load Data", type="primary", use_container_width=True):
            with st.spinner("Loading data..."):
                result = fetch_data(period_input)
                if result[0] is not None:
                    st.session_state.df_prices = result[0]
                    st.session_state.df_sectors = result[1]
                    st.session_state.summary_data = result[2]
                    st.session_state.data_loaded = True
                    st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
                    st.session_state.current_period = period_input
                    st.rerun()
                else:
                    st.error(f"Failed to load data: {result[4]}")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            f"""
        <div style="background: {THEME['card_bg']}; padding: 1.5rem; border-radius: 12px; 
                    border: 1px solid {THEME['card_border']}; margin-bottom: 1rem;">
            <h2 style="color: {THEME['primary']}; margin-bottom: 1rem;">📊 Filters</h2>
        """,
            unsafe_allow_html=True,
        )

        if st.session_state.data_loaded:
            # Sector filter
            sectors = ["All"] + sorted(
                st.session_state.df_prices["Sector"].dropna().unique().tolist()
            )
            selected_sector = st.selectbox(
                "**Sector Filter**", sectors, key="sector_filter"
            )

            # Company filter
            companies = ["All"] + sorted(
                st.session_state.df_prices["Company"].dropna().unique().tolist()
            )
            selected_company = st.selectbox(
                "**Company Filter**", companies, key="company_filter"
            )
        else:
            selected_sector = "All"
            selected_company = "All"

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            f"""
        <div style="background: {THEME['card_bg']}; padding: 1.5rem; border-radius: 12px; 
                    border: 1px solid {THEME['card_border']};">
            <h2 style="color: {THEME['primary']}; margin-bottom: 1rem;">🔍 Status</h2>
        """,
            unsafe_allow_html=True,
        )

        api_healthy, api_status, data_status = check_api_health()
        st.write(f"**API Status:** {api_status}")
        if st.session_state.data_loaded:
            st.success(
                f"**Data Status:** {st.session_state.summary_data.get('total_companies', 0)} companies loaded"
            )
        else:
            st.warning("**Data Status:** No data loaded")
        st.write(f"**Last Refresh:** {st.session_state.last_refresh}")
        st.markdown("</div>", unsafe_allow_html=True)

    # Main content area
    if not st.session_state.data_loaded:
        st.info(
            "👆 Please enter a period and click 'Load Data' in the sidebar to start analyzing stock data."
        )
        st.markdown(
            f"""
        <div style="background: {THEME['card_bg']}; padding: 2rem; border-radius: 12px; 
                    border: 1px solid {THEME['card_border']}; color: {THEME['text']};">
            <h3 style="color: {THEME['primary']};">📖 How to use:</h3>
            <ol style="color: {THEME['text']};">
                <li>Enter a period in <strong>YYYY</strong> (e.g., 2023) or <strong>YYYY-MM</strong> (e.g., 2023-12) format</li>
                <li>Click the <strong>'Load Data'</strong> button</li>
                <li>Use filters in the sidebar to refine your analysis</li>
                <li>Explore different tabs for various analyses</li>
            </ol>
        </div>
        """,
            unsafe_allow_html=True,
        )
        return

    # Apply filters
    df_filtered = st.session_state.df_prices.copy()
    if selected_sector != "All":
        df_filtered = df_filtered[df_filtered["Sector"] == selected_sector]
    if selected_company != "All":
        df_filtered = df_filtered[df_filtered["Company"] == selected_company]

    # Summary metrics with custom styling
    st.subheader("📈 Summary Metrics")

    # Create columns for KPI cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            create_kpi_card(
                "Period",
                st.session_state.summary_data["period"],
                f"{st.session_state.summary_data['total_companies']} companies",
            ),
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            create_kpi_card(
                "Avg Close Price", f"${st.session_state.summary_data['avg_close']:,.2f}"
            ),
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            create_kpi_card(
                "Total Volume", f"{st.session_state.summary_data['total_volume']:,.0f}"
            ),
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            create_kpi_card(
                "Avg Volatility",
                f"{st.session_state.summary_data['avg_volatility']:.2f}%",
            ),
            unsafe_allow_html=True,
        )

    # Tabs for different analyses
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📊 Overview & Summary",
            "🏢 Sectors & Correlation",
            "💰 Valuation & Metrics",
            "📈 Comparison & Trends",
            "🔍 Data Explorer",
        ]
    )

    with tab1:
        st.subheader("Market Overview")

        col1, col2 = st.columns(2)

        with col1:
            st.plotly_chart(
                create_market_cap_chart(df_filtered), use_container_width=True
            )

        with col2:
            st.plotly_chart(
                create_sector_pie_chart(df_filtered), use_container_width=True
            )

        col3, col4 = st.columns(2)

        with col3:
            st.plotly_chart(
                create_volatility_chart(df_filtered), use_container_width=True
            )

        with col4:
            st.plotly_chart(create_trend_chart(df_filtered), use_container_width=True)

        st.plotly_chart(create_scatter_chart(df_filtered), use_container_width=True)

    with tab2:
        st.subheader("Sector Analysis")

        col1, col2 = st.columns(2)

        with col1:
            st.plotly_chart(
                create_sector_volume_chart(df_filtered), use_container_width=True
            )

        with col2:
            st.plotly_chart(
                create_sector_liquidity_chart(df_filtered), use_container_width=True
            )

        st.plotly_chart(
            create_correlation_heatmap(df_filtered), use_container_width=True
        )

    with tab3:
        st.subheader("Valuation Analysis")

        col1, col2 = st.columns(2)

        with col1:
            st.plotly_chart(
                create_valuation_chart(df_filtered), use_container_width=True
            )

        with col2:
            st.plotly_chart(
                create_pe_distribution(df_filtered), use_container_width=True
            )

    with tab4:
        st.subheader("Year Comparison Analysis")

        # Comparison controls
        st.markdown("### 🔄 Comparison Settings")
        comp_col1, comp_col2, comp_col3 = st.columns(3)

        with comp_col1:
            compare_year_1 = st.text_input(
                "Compare Year 1:", value="2022", placeholder="YYYY", key="year1"
            )

        with comp_col2:
            compare_year_2 = st.text_input(
                "Compare Year 2:", value="2023", placeholder="YYYY", key="year2"
            )

        with comp_col3:
            compare_metric = st.selectbox(
                "Metric:",
                options=["Close", "Volume", "Market_Cap", "Volatility", "PE_Ratio"],
                index=0,
                key="compare_metric",
            )

        if st.button("📊 Compare Years", type="primary", key="compare_button"):
            with st.spinner("Loading comparison data..."):
                try:
                    year1 = int(compare_year_1)
                    year2 = int(compare_year_2)

                    df_year1, df_year2, error = fetch_comparison_data(year1, year2)

                    if error:
                        st.error(f"Error loading comparison data: {error}")
                    else:
                        st.session_state.comparison_data = {
                            "year1": year1,
                            "year2": year2,
                            "metric": compare_metric,
                            "df_year1": df_year1,
                            "df_year2": df_year2,
                        }
                        st.success("Comparison data loaded successfully!")

                except ValueError:
                    st.error("Please enter valid years (e.g., 2022, 2023)")

        # Display comparison charts if data is available
        if st.session_state.comparison_data:
            comp_data = st.session_state.comparison_data
            year1 = comp_data["year1"]
            year2 = comp_data["year2"]
            metric = comp_data["metric"]
            df_year1 = comp_data["df_year1"]
            df_year2 = comp_data["df_year2"]

            if not df_year1.empty and not df_year2.empty:
                st.markdown("---")
                st.subheader("Comparison Results")

                # First row of comparison charts
                col1, col2 = st.columns(2)

                with col1:
                    st.plotly_chart(
                        create_year_comparison_bar(
                            year1, year2, metric, df_year1, df_year2
                        ),
                        use_container_width=True,
                    )

                with col2:
                    st.plotly_chart(
                        create_sector_growth_line(
                            year1, year2, metric, df_year1, df_year2
                        ),
                        use_container_width=True,
                    )

                # Second row of comparison charts
                col3, col4 = st.columns(2)

                with col3:
                    st.plotly_chart(
                        create_performance_trend(year1, year2, metric),
                        use_container_width=True,
                    )

                with col4:
                    st.plotly_chart(
                        create_distribution_comparison(
                            year1, year2, metric, df_year1, df_year2
                        ),
                        use_container_width=True,
                    )
            else:
                st.warning("No comparison data available for the selected years.")
        else:
            st.info(
                "👆 Enter years and click 'Compare Years' to see comparison analysis."
            )

    with tab5:
        st.subheader("Data Explorer")

        # Show raw data
        st.dataframe(df_filtered, use_container_width=True, height=400)

        # Data summary
        st.subheader("Data Summary")
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Column Information:**")
            column_info = pd.DataFrame(
                {
                    "Column": df_filtered.columns,
                    "Data Type": df_filtered.dtypes.astype(str),
                    "Non-Null Count": df_filtered.count(),
                    "Null Count": df_filtered.isnull().sum(),
                }
            )
            st.dataframe(column_info, use_container_width=True)

        with col2:
            st.write("**Numeric Columns Summary:**")
            numeric_cols = df_filtered.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                st.dataframe(
                    df_filtered[numeric_cols].describe(), use_container_width=True
                )
            else:
                st.info("No numeric columns available")


if __name__ == "__main__":
    main()
