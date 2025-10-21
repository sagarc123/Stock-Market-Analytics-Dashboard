import logging
import os
from datetime import datetime
from io import StringIO

import dash
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from dash import Dash, Input, Output, State, dash_table, dcc, html, no_update
from dash.dash_table import Format, FormatTemplate

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
API = "https://stock-market-analytics-dashboard.onrender.com"
DEFAULT_PORT = 8050

# App and server initialization
app = Dash(
    __name__, title="Enhanced Stock Market Analytics", suppress_callback_exceptions=True
)
server = app.server

# --- COLOR PALETTES ---
THEME = {
    "primary": "#007BFF",
    "secondary": "#28A745",
    "bullish": "#28A745",
    "bearish": "#DC3545",
    "stable": "#ADB5BD",
    "text": "#343A40",
    "background": "#F8F9FA",
    "card_bg": "#FFFFFF",
    "card_shadow": "0 4px 12px rgba(0, 0, 0, 0.08)",
    "grid": "rgba(0, 0, 0, 0.05)",
}


# --- UI helpers ---
def create_card(title, value, subtitle=None, wide=False):
    """Generates a styled KPI card."""
    v = value if value is not None else "N/A"
    card_style = {
        "flex": "1 1 %s" % ("320px" if wide else "220px"),
        "padding": "24px",
        "backgroundColor": THEME["card_bg"],
        "borderRadius": "12px",
        "boxShadow": THEME["card_shadow"],
        "textAlign": "left",
        "transition": "all 0.5s ease",
    }
    children = [
        html.Div(
            title,
            style={
                "fontSize": "0.9rem",
                "color": THEME["text"],
                "opacity": 0.6,
                "marginBottom": "8px",
                "fontWeight": 600,
            },
        ),
        html.Div(
            str(v),
            style={
                "fontSize": "1.8rem",
                "fontWeight": 700,
                "color": THEME["primary"],
                "lineHeight": 1.1,
            },
        ),
    ]
    if subtitle:
        children.append(
            html.Div(
                subtitle,
                style={"fontSize": "0.75rem", "color": THEME["text"], "opacity": 0.5},
            )
        )

    return html.Div(children, style=card_style)


def create_empty_figure(title, message="No data available for current selection"):
    """Creates an empty figure with a message."""
    fig = go.Figure()
    fig.update_layout(
        title={
            "text": title,
            "font": {"size": 20, "color": THEME["primary"], "family": "Inter"},
        },
        plot_bgcolor=THEME["card_bg"],
        paper_bgcolor=THEME["card_bg"],
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
        font={"size": 16, "color": THEME["stable"], "family": "Inter"},
    )
    return fig


def apply_chart_style(fig, title, xaxis_title, yaxis_title, height=450):
    """Applies consistent styling to charts."""
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
            "tickfont": {"size": 12, "color": THEME["text"], "family": "Inter"},
            "showline": True,
            "linecolor": THEME["stable"],
            "linewidth": 1,
        },
        yaxis={
            "title": {
                "text": yaxis_title,
                "font": {"size": 14, "color": THEME["text"], "family": "Inter"},
            },
            "gridcolor": THEME["grid"],
            "gridwidth": 1,
            "tickfont": {"size": 12, "color": THEME["text"], "family": "Inter"},
            "showline": True,
            "linecolor": THEME["stable"],
            "linewidth": 1,
        },
        plot_bgcolor=THEME["card_bg"],
        paper_bgcolor=THEME["card_bg"],
        font={"family": "Inter", "color": THEME["text"]},
        height=height,
        margin={"t": 100, "b": 100, "l": 80, "r": 40},
        hoverlabel={
            "bgcolor": THEME["card_bg"],
            "font_size": 12,
            "font_family": "Inter",
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


# --- Layout ---
app.layout = html.Div(
    id="root",
    style={
        "fontFamily": "Inter, sans-serif",
        "backgroundColor": THEME["background"],
        "minHeight": "100vh",
        "padding": "24px",
        "transition": "all 0.5s ease",
        "color": THEME["text"],
    },
    children=[
        html.Div(
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "gap": "16px",
                "flexWrap": "wrap",
                "marginBottom": "16px",
            },
            children=[
                html.H1(
                    "Stock Market Analytics",
                    id="main-title",
                    style={
                        "margin": 0,
                        "color": THEME["primary"],
                        "transition": "color 0.5s ease",
                        "fontSize": "2.5rem",
                        "fontWeight": "700",
                        "fontFamily": "Inter",
                    },
                ),
                html.Div(
                    style={
                        "display": "flex",
                        "gap": "16px",
                        "alignItems": "center",
                        "flexWrap": "wrap",
                    },
                    children=[
                        html.Label(
                            "Select Period (YYYY or YYYY-MM):",
                            style={
                                "fontWeight": 600,
                                "color": THEME["text"],
                                "fontFamily": "Inter",
                            },
                        ),
                        dcc.Input(
                            id="date-input",
                            type="text",
                            placeholder="YYYY or YYYY-MM",
                            value="2023",
                            debounce=True,
                            style={
                                "width": "240px",
                                "padding": "10px",
                                "borderRadius": "8px",
                                "border": "1px solid " + THEME["stable"],
                                "backgroundColor": THEME["card_bg"],
                                "fontFamily": "Inter",
                                "fontSize": "14px",
                            },
                        ),
                        dcc.Dropdown(
                            id="sector-filter",
                            placeholder="All Sectors",
                            style={"width": "200px", "fontFamily": "Inter"},
                            clearable=True,
                        ),
                        dcc.Dropdown(
                            id="company-filter",
                            placeholder="All Companies",
                            style={"width": "200px", "fontFamily": "Inter"},
                            clearable=True,
                        ),
                    ],
                ),
            ],
        ),
        html.Hr(style={"borderColor": THEME["stable"] + "55"}),
        # Status and refresh
        html.Div(
            style={
                "display": "flex",
                "gap": "12px",
                "alignItems": "center",
                "flexWrap": "wrap",
                "marginBottom": "24px",
            },
            children=[
                dcc.Interval(id="auto-refresh", interval=60 * 1000 * 5, n_intervals=0),
                html.Div(
                    id="last-refresh",
                    style={
                        "color": THEME["stable"],
                        "fontSize": "0.85rem",
                        "fontFamily": "Inter",
                    },
                ),
                html.Div(
                    id="api-status",
                    style={
                        "fontSize": "0.85rem",
                        "fontWeight": "bold",
                        "fontFamily": "Inter",
                    },
                ),
                html.Div(
                    id="data-status",
                    style={"fontSize": "0.85rem", "fontFamily": "Inter"},
                ),
            ],
        ),
        # Summary Cards
        html.Div(
            id="summary-cards-row",
            style={
                "display": "flex",
                "gap": "20px",
                "flexWrap": "wrap",
                "marginBottom": "20px",
            },
        ),
        # Main content
        html.Div(
            id="main-content",
            children=[
                dcc.Tabs(
                    id="main-tabs",
                    value="overview",
                    children=[
                        dcc.Tab(
                            label="📊 Overview & Summary",
                            value="overview",
                            style={"fontFamily": "Inter"},
                        ),
                        dcc.Tab(
                            label="🏢 Sectors & Correlation",
                            value="sectors",
                            style={"fontFamily": "Inter"},
                        ),
                        dcc.Tab(
                            label="💰 Valuation & Metrics",
                            value="valuation",
                            style={"fontFamily": "Inter"},
                        ),
                        dcc.Tab(
                            label="📈 Comparison & Trends",
                            value="comparison",
                            style={"fontFamily": "Inter"},
                        ),
                    ],
                    style={"fontFamily": "Inter", "marginBottom": "20px"},
                ),
                html.Div(id="tab-content"),
            ],
        ),
        # Data stores
        dcc.Store(id="daily-prices-data", storage_type="memory"),
        dcc.Store(id="sector-summary-data", storage_type="memory"),
        dcc.Store(id="comparison-data", storage_type="memory"),
        html.Div(id="container-style-setter", style={"display": "none"}),
    ],
)


# --- Tab Content Callback ---
@app.callback(Output("tab-content", "children"), Input("main-tabs", "value"))
def render_tab(tab):
    """Renders the content based on the selected tab."""
    if tab == "overview":
        return html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            dcc.Graph(id="top-market-cap-chart"),
                            className="graph-container",
                        ),
                        html.Div(
                            dcc.Graph(id="mini-metrics"), className="graph-container"
                        ),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(400px, 1fr))",
                        "gap": "20px",
                        "marginTop": "16px",
                    },
                ),
                html.Div(
                    [
                        html.Div(
                            dcc.Graph(id="top-volatility-chart"),
                            className="graph-container",
                        ),
                        html.Div(
                            dcc.Graph(id="price-volume-scatter"),
                            className="graph-container",
                        ),
                        html.Div(
                            dcc.Graph(id="trend-distribution-chart"),
                            className="graph-container",
                        ),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(320px, 1fr))",
                        "gap": "20px",
                        "marginTop": "20px",
                    },
                ),
                dash_table.DataTable(
                    id="data-table",
                    page_size=10,
                    sort_action="native",
                    style_cell={"fontFamily": "Inter", "fontSize": "14px"},
                    style_header={
                        "backgroundColor": THEME["card_bg"],
                        "fontWeight": "600",
                        "fontFamily": "Inter",
                    },
                ),
            ]
        )
    elif tab == "sectors":
        return html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            dcc.Graph(id="sector-volume-chart"),
                            className="graph-container",
                        ),
                        html.Div(
                            dcc.Graph(id="sector-liquidity-chart"),
                            className="graph-container",
                        ),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(400px, 1fr))",
                        "gap": "20px",
                        "marginTop": "16px",
                    },
                ),
                html.Div(
                    dcc.Graph(id="correlation-heatmap"),
                    className="graph-container",
                    style={"marginTop": "20px"},
                ),
            ]
        )
    elif tab == "valuation":
        return html.Div(
            [
                html.Div(
                    dcc.Graph(id="valuation-scatter-chart"),
                    className="graph-container",
                    style={"marginTop": "16px"},
                ),
                html.Div(
                    dcc.Graph(id="pe-distribution"),
                    className="graph-container",
                    style={"marginTop": "20px"},
                ),
            ]
        )
    else:  # comparison
        return html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label(
                                    "Compare Year 1:",
                                    style={
                                        "fontWeight": "600",
                                        "fontFamily": "Inter",
                                        "marginBottom": "8px",
                                    },
                                ),
                                dcc.Input(
                                    id="compare-year-1",
                                    type="text",
                                    placeholder="YYYY",
                                    value="2022",
                                    style={
                                        "width": "100%",
                                        "padding": "10px",
                                        "borderRadius": "8px",
                                        "border": "1px solid " + THEME["stable"],
                                        "backgroundColor": THEME["card_bg"],
                                        "fontFamily": "Inter",
                                    },
                                ),
                            ],
                            style={"flex": "1", "minWidth": "150px"},
                        ),
                        html.Div(
                            [
                                html.Label(
                                    "Compare Year 2:",
                                    style={
                                        "fontWeight": "600",
                                        "fontFamily": "Inter",
                                        "marginBottom": "8px",
                                    },
                                ),
                                dcc.Input(
                                    id="compare-year-2",
                                    type="text",
                                    placeholder="YYYY",
                                    value="2023",
                                    style={
                                        "width": "100%",
                                        "padding": "10px",
                                        "borderRadius": "8px",
                                        "border": "1px solid " + THEME["stable"],
                                        "backgroundColor": THEME["card_bg"],
                                        "fontFamily": "Inter",
                                    },
                                ),
                            ],
                            style={"flex": "1", "minWidth": "150px"},
                        ),
                        html.Div(
                            [
                                html.Label(
                                    "Metric:",
                                    style={
                                        "fontWeight": "600",
                                        "fontFamily": "Inter",
                                        "marginBottom": "8px",
                                    },
                                ),
                                dcc.Dropdown(
                                    id="compare-metric",
                                    options=[
                                        {
                                            "label": "Average Close Price",
                                            "value": "Close",
                                        },
                                        {"label": "Total Volume", "value": "Volume"},
                                        {"label": "Market Cap", "value": "Market_Cap"},
                                        {"label": "Volatility", "value": "Volatility"},
                                        {"label": "P/E Ratio", "value": "PE_Ratio"},
                                    ],
                                    value="Close",
                                    style={"fontFamily": "Inter"},
                                ),
                            ],
                            style={"flex": "1", "minWidth": "200px"},
                        ),
                    ],
                    style={
                        "display": "flex",
                        "gap": "20px",
                        "flexWrap": "wrap",
                        "marginBottom": "20px",
                        "padding": "20px",
                        "backgroundColor": THEME["card_bg"],
                        "borderRadius": "12px",
                        "boxShadow": THEME["card_shadow"],
                    },
                ),
                html.Div(
                    [
                        html.Div(
                            dcc.Graph(id="year-comparison-bar"),
                            className="graph-container",
                        ),
                        html.Div(
                            dcc.Graph(id="sector-growth-line"),
                            className="graph-container",
                        ),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(500px, 1fr))",
                        "gap": "20px",
                        "marginTop": "16px",
                    },
                ),
                html.Div(
                    [
                        html.Div(
                            dcc.Graph(id="performance-trend"),
                            className="graph-container",
                        ),
                        html.Div(
                            dcc.Graph(id="metric-distribution-comparison"),
                            className="graph-container",
                        ),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(500px, 1fr))",
                        "gap": "20px",
                        "marginTop": "20px",
                    },
                ),
            ]
        )


# --- Helper to validate period input ---
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


# --- API Health Check ---
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


# --- API Fetching Callback ---
@app.callback(
    Output("daily-prices-data", "data"),
    Output("sector-summary-data", "data"),
    Output("last-refresh", "children"),
    Output("summary-cards-row", "children"),
    Output("api-status", "children"),
    Output("data-status", "children"),
    Input("date-input", "value"),
    Input("auto-refresh", "n_intervals"),
)
def fetch_data_and_store(period_input, n_intervals):
    """Fetches data from the API."""

    # Check API health first
    api_healthy, api_status, data_status = check_api_health()
    if not api_healthy:
        error_card = create_card(
            "API Server Not Running",
            "Start backend first",
            "Run: python api.py",
        )
        return None, None, "Last Refreshed: N/A", [error_card], api_status, data_status

    # Check if data is loaded
    if "Data: Loaded" not in data_status and "rows loaded" not in data_status:
        error_card = create_card(
            "Data Not Available", data_status, "Check database setup"
        )
        return None, None, "Last Refreshed: N/A", [error_card], api_status, data_status

    valid_period = validate_period(period_input)
    if valid_period is None:
        msg = "Enter valid Period (YYYY or YYYY-MM)"
        no_date_card = create_card("Input Required", msg)
        return (
            None,
            None,
            "Last Refreshed: N/A",
            [no_date_card],
            api_status,
            data_status,
        )

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
        error_detail = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                error_json = e.response.json()
                error_detail = error_json.get("detail", str(e))
            except:
                error_detail = f"HTTP {e.response.status_code}"

        error_card = create_card("API Error", error_detail)
        return (
            None,
            None,
            f"Last Refreshed: {datetime.now().strftime('%H:%M:%S')} (Error)",
            [error_card],
            api_status,
            data_status,
        )

    # Process data
    df_prices = pd.DataFrame(prices_data)
    if df_prices.empty:
        no_data_card = create_card("No Data", f"No data for {valid_period}")
        return (
            None,
            None,
            f"Last Refreshed: {datetime.now().strftime('%H:%M:%S')}",
            [no_data_card],
            api_status,
            data_status,
        )

    # Calculate summary metrics
    total_companies = len(df_prices)
    numeric_cols = ["Close", "Volume", "Volatility"]
    for col in numeric_cols:
        df_prices[col] = pd.to_numeric(df_prices[col], errors="coerce").fillna(0)

    avg_close = df_prices["Close"].mean()
    total_volume_sum = df_prices["Volume"].sum()
    avg_volatility = df_prices["Volatility"].mean() * 100

    summary_cards = [
        create_card("Period", valid_period, f"Total Companies: {total_companies}"),
        create_card("Avg Close", f"${avg_close:,.2f}"),
        create_card("Total Volume", f"{total_volume_sum:,.0f}"),
        create_card("Avg Volatility", f"{avg_volatility:,.2f}%"),
    ]

    # Store data
    df_prices["Relative_Liquidity"] = df_prices["Close"] * df_prices["Volume"]
    prices_json = df_prices.to_json(orient="split", date_format="iso")
    sectors_json = pd.DataFrame(sectors_data).to_json(orient="split")

    return (
        prices_json,
        sectors_json,
        f"Last Refreshed: {datetime.now().strftime('%H:%M:%S')}",
        summary_cards,
        api_status,
        data_status,
    )


# --- Populate dropdowns ---
@app.callback(
    Output("sector-filter", "options"),
    Output("company-filter", "options"),
    Input("daily-prices-data", "data"),
)
def populate_filters(prices_json):
    """Dynamically populates filter dropdowns."""
    if not prices_json:
        return [], []

    try:
        df = pd.read_json(StringIO(prices_json), orient="split")
        sectors = [
            {"label": s, "value": s} for s in sorted(df["Sector"].dropna().unique())
        ]
        companies = [
            {"label": c, "value": c} for c in sorted(df["Company"].dropna().unique())
        ]
        return sectors, companies
    except Exception as e:
        logging.error(f"Error populating filters: {e}")
        return [], []


# --- Overview Tab Callback ---
@app.callback(
    Output("top-market-cap-chart", "figure"),
    Output("mini-metrics", "figure"),
    Output("top-volatility-chart", "figure"),
    Output("price-volume-scatter", "figure"),
    Output("trend-distribution-chart", "figure"),
    Output("data-table", "data"),
    Output("data-table", "columns"),
    Input("sector-filter", "value"),
    Input("company-filter", "value"),
    Input("daily-prices-data", "data"),
    Input("main-tabs", "value"),
)
def update_overview_charts(sector, company, prices_json, current_tab):
    """Generates all charts and the main table for overview tab."""
    if current_tab != "overview":
        return [no_update] * 7

    if not prices_json:
        empty_fig = create_empty_figure("No Data")
        return empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, [], []

    try:
        df = pd.read_json(StringIO(prices_json), orient="split")
    except Exception as e:
        logging.error(f"Error reading prices data: {e}")
        empty_fig = create_empty_figure("Data Error")
        return empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, [], []

    # Ensure numeric columns with proper error handling
    numeric_cols = ["Close", "Volume", "PE_Ratio", "Volatility", "Market_Cap"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Apply filters
    df_filtered = df.copy()
    if sector:
        df_filtered = df_filtered[df_filtered["Sector"] == sector]
    if company:
        df_filtered = df_filtered[df_filtered["Company"] == company]

    if df_filtered.empty:
        empty_fig = create_empty_figure("No Data for Selection")
        return empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, [], []

    # Chart 1: Top Market Cap
    try:
        df_cap = df_filtered[df_filtered["Market_Cap"] > 0].nlargest(10, "Market_Cap")
        if df_cap.empty:
            fig_cap = create_empty_figure("Top Companies by Market Cap")
        else:
            fig_cap = px.bar(
                df_cap,
                x="Company",
                y="Market_Cap",
                color="Market_Cap",
                color_continuous_scale="Viridis",
            )
            fig_cap = apply_chart_style(
                fig_cap,
                "Top Companies by Market Cap",
                "Company",
                "Market Cap ($)",
            )
    except Exception as e:
        logging.error(f"Error creating market cap chart: {e}")
        fig_cap = create_empty_figure("Chart Error")

    # Chart 2: Sector Liquidity Pie
    try:
        if "Sector" in df_filtered.columns:
            sector_liq = df_filtered.groupby("Sector")["Close"].mean().reset_index()
            sector_liq = sector_liq[sector_liq["Close"] > 0]
            if sector_liq.empty:
                mini_fig = create_empty_figure("Sector Performance")
            else:
                mini_fig = px.pie(
                    sector_liq,
                    names="Sector",
                    values="Close",
                    hole=0.6,
                )
                mini_fig = apply_chart_style(
                    mini_fig, "Sector Performance Distribution", "", ""
                )
        else:
            mini_fig = create_empty_figure("Sector Data Missing")
    except Exception as e:
        logging.error(f"Error creating sector pie chart: {e}")
        mini_fig = create_empty_figure("Chart Error")

    # Chart 3: Top Volatility
    try:
        if "Volatility" in df_filtered.columns:
            df_vol = df_filtered[df_filtered["Volatility"] > 0].nlargest(
                10, "Volatility"
            )
            if df_vol.empty:
                fig_vol = create_empty_figure("Top Volatile Stocks")
            else:
                volatility_pct = df_vol["Volatility"] * 100
                fig_vol = px.bar(
                    df_vol,
                    x="Company",
                    y=volatility_pct,
                    color=volatility_pct,
                    color_continuous_scale="Reds",
                )
                fig_vol = apply_chart_style(
                    fig_vol, "Top Volatile Stocks", "Company", "Volatility (%)"
                )
        else:
            fig_vol = create_empty_figure("Volatility Data Missing")
    except Exception as e:
        logging.error(f"Error creating volatility chart: {e}")
        fig_vol = create_empty_figure("Chart Error")

    # Chart 4: Price vs Volume Scatter
    try:
        df_scatter = df_filtered[
            (df_filtered["Volume"] > 0)
            & (df_filtered["Close"] > 0)
            & (df_filtered["Market_Cap"] > 0)
        ]
        if df_scatter.empty:
            fig_scatter = create_empty_figure("Price vs Volume")
        else:
            fig_scatter = px.scatter(
                df_scatter,
                x="Volume",
                y="Close",
                size="Market_Cap",
                color="Sector",
                hover_name="Company",
                size_max=30,
            )
            fig_scatter = apply_chart_style(
                fig_scatter,
                "Price vs Volume Analysis",
                "Trading Volume",
                "Close Price ($)",
            )
    except Exception as e:
        logging.error(f"Error creating scatter chart: {e}")
        fig_scatter = create_empty_figure("Chart Error")

    # Chart 5: Trend Distribution
    try:
        if "Trend" in df_filtered.columns:
            trend_counts = (
                df_filtered["Trend"].fillna("Neutral").value_counts().reset_index()
            )
            trend_counts.columns = ["Trend", "Count"]
            if trend_counts.empty:
                trend_fig = create_empty_figure("Trend Distribution")
            else:
                trend_fig = px.bar(trend_counts, x="Trend", y="Count", color="Trend")
                trend_fig = apply_chart_style(
                    trend_fig,
                    "Market Trend Distribution",
                    "Trend",
                    "Number of Companies",
                )
        else:
            trend_fig = create_empty_figure("Trend Data Missing")
    except Exception as e:
        logging.error(f"Error creating trend chart: {e}")
        trend_fig = create_empty_figure("Chart Error")

    # Data Table
    try:
        table_df = df_filtered.sort_values("Close", ascending=False)
        columns = []
        for col in table_df.columns:
            if col in [
                "Date",
                "Company",
                "Sector",
                "Close",
                "Volume",
                "Trend",
                "PE_Ratio",
                "Volatility",
                "Market_Cap",
            ]:
                col_def = {"name": col, "id": col}
                if col == "Close":
                    col_def["type"] = "numeric"
                    col_def["format"] = FormatTemplate.money(2)
                elif col == "Market_Cap":
                    col_def["type"] = "numeric"
                    col_def["format"] = FormatTemplate.money(0)
                elif col == "PE_Ratio":
                    col_def["type"] = "numeric"
                    col_def["format"] = Format(precision=2)
                elif col == "Volatility":
                    col_def["type"] = "numeric"
                    col_def["format"] = FormatTemplate.percentage(4)
                elif col == "Volume":
                    col_def["type"] = "numeric"
                    col_def["format"] = Format(precision=0)
                columns.append(col_def)

        table_data = table_df.to_dict("records")
    except Exception as e:
        logging.error(f"Error creating data table: {e}")
        table_data = []
        columns = []

    return fig_cap, mini_fig, fig_vol, fig_scatter, trend_fig, table_data, columns


# --- Sectors Tab Callback ---
@app.callback(
    Output("sector-volume-chart", "figure"),
    Output("sector-liquidity-chart", "figure"),
    Output("correlation-heatmap", "figure"),
    Input("sector-filter", "value"),
    Input("company-filter", "value"),
    Input("daily-prices-data", "data"),
    Input("sector-summary-data", "data"),
    Input("main-tabs", "value"),
)
def update_sector_charts(
    sector_filter, company_filter, prices_json, sectors_json, current_tab
):
    """Updates graphs on the Sectors tab."""
    if current_tab != "sectors":
        return [no_update] * 3

    if not prices_json:
        empty_fig = create_empty_figure("No Data")
        return empty_fig, empty_fig, empty_fig

    try:
        df_prices = pd.read_json(StringIO(prices_json), orient="split")
    except Exception as e:
        logging.error(f"Error reading prices data: {e}")
        empty_fig = create_empty_figure("Data Error")
        return empty_fig, empty_fig, empty_fig

    # Apply filters
    df_filtered = df_prices.copy()
    if sector_filter:
        df_filtered = df_filtered[df_filtered["Sector"] == sector_filter]
    if company_filter:
        df_filtered = df_filtered[df_filtered["Company"] == company_filter]

    if df_filtered.empty:
        empty_fig = create_empty_figure("No Data for Selection")
        return empty_fig, empty_fig, empty_fig

    # Ensure numeric columns
    numeric_cols = ["Close", "Volume", "PE_Ratio", "Volatility", "Market_Cap"]
    for col in numeric_cols:
        if col in df_filtered.columns:
            df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce").fillna(
                0
            )

    # Sector Volume Chart
    try:
        if "Sector" in df_filtered.columns and "Volume" in df_filtered.columns:
            sector_volume = df_filtered.groupby("Sector")["Volume"].sum().reset_index()
            sector_volume = sector_volume[sector_volume["Volume"] > 0]
            if sector_volume.empty:
                fig_vol = create_empty_figure("Sector Volume")
            else:
                fig_vol = px.bar(sector_volume, x="Sector", y="Volume", color="Volume")
                fig_vol = apply_chart_style(
                    fig_vol,
                    "Sector Trading Volume Comparison",
                    "Sector",
                    "Total Volume",
                )
        else:
            fig_vol = create_empty_figure("Volume Data Missing")
    except Exception as e:
        logging.error(f"Error creating sector volume chart: {e}")
        fig_vol = create_empty_figure("Chart Error")

    # Sector Liquidity Chart
    try:
        if (
            "Sector" in df_filtered.columns
            and "Close" in df_filtered.columns
            and "Volume" in df_filtered.columns
        ):
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
                fig_liq = create_empty_figure("Sector Liquidity")
            else:
                fig_liq = px.scatter(
                    sector_liquidity,
                    x="Close",
                    y="Liquidity",
                    size="Volume",
                    hover_name="Sector",
                    color="Sector",
                )
                fig_liq = apply_chart_style(
                    fig_liq,
                    "Sector Liquidity Analysis",
                    "Average Close Price ($)",
                    "Liquidity (Close × Volume)",
                )
        else:
            fig_liq = create_empty_figure("Liquidity Data Missing")
    except Exception as e:
        logging.error(f"Error creating sector liquidity chart: {e}")
        fig_liq = create_empty_figure("Chart Error")

    # Correlation Heatmap
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
            corr_fig = apply_chart_style(corr_fig, "Feature Correlation Matrix", "", "")
        else:
            corr_fig = create_empty_figure("Insufficient Data for Correlation")
    except Exception as e:
        logging.error(f"Error creating correlation heatmap: {e}")
        corr_fig = create_empty_figure("Correlation Error")

    return fig_vol, fig_liq, corr_fig


# --- Valuation Tab Callback ---
@app.callback(
    Output("valuation-scatter-chart", "figure"),
    Output("pe-distribution", "figure"),
    Input("sector-filter", "value"),
    Input("company-filter", "value"),
    Input("daily-prices-data", "data"),
    Input("main-tabs", "value"),
)
def update_valuation_charts(sector_filter, company_filter, prices_json, current_tab):
    """Updates graphs on the Valuation tab."""
    if current_tab != "valuation":
        return [no_update] * 2

    if not prices_json:
        empty_fig = create_empty_figure("No Data")
        return empty_fig, empty_fig

    try:
        df_prices = pd.read_json(StringIO(prices_json), orient="split")
    except Exception as e:
        logging.error(f"Error reading prices data: {e}")
        empty_fig = create_empty_figure("Data Error")
        return empty_fig, empty_fig

    # Apply filters
    df_filtered = df_prices.copy()
    if sector_filter:
        df_filtered = df_filtered[df_filtered["Sector"] == sector_filter]
    if company_filter:
        df_filtered = df_filtered[df_filtered["Company"] == company_filter]

    if df_filtered.empty:
        empty_fig = create_empty_figure("No Data for Selection")
        return empty_fig, empty_fig

    # Ensure numeric columns
    numeric_cols = ["Close", "Volume", "PE_Ratio", "Volatility", "Market_Cap"]
    for col in numeric_cols:
        if col in df_filtered.columns:
            df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce").fillna(
                0
            )

    # Valuation Scatter Chart
    try:
        valuation_df = df_filtered[
            (df_filtered["PE_Ratio"] > 0)
            & (df_filtered["PE_Ratio"] < 1000)
            & (df_filtered["Close"] > 0)
        ]
        if valuation_df.empty:
            val_fig = create_empty_figure("Valuation Analysis")
        else:
            val_fig = px.scatter(
                valuation_df,
                x="PE_Ratio",
                y="Close",
                color="Sector",
                hover_name="Company",
                size="Market_Cap",
                size_max=30,
            )
            val_fig = apply_chart_style(
                val_fig,
                "P/E Ratio vs Close Price Analysis",
                "P/E Ratio",
                "Close Price ($)",
            )
    except Exception as e:
        logging.error(f"Error creating valuation scatter: {e}")
        val_fig = create_empty_figure("Chart Error")

    # P/E Distribution
    try:
        pe_df = df_filtered[
            (df_filtered["PE_Ratio"] > 0) & (df_filtered["PE_Ratio"] < 1000)
        ]
        if pe_df.empty:
            pe_fig = create_empty_figure("P/E Distribution")
        else:
            pe_fig = px.histogram(pe_df, x="PE_Ratio", nbins=20)
            pe_fig = apply_chart_style(
                pe_fig, "P/E Ratio Distribution", "P/E Ratio", "Frequency"
            )
    except Exception as e:
        logging.error(f"Error creating P/E distribution: {e}")
        pe_fig = create_empty_figure("Chart Error")

    return val_fig, pe_fig


# --- Comparison Tab Callback ---
@app.callback(
    Output("year-comparison-bar", "figure"),
    Output("sector-growth-line", "figure"),
    Output("performance-trend", "figure"),
    Output("metric-distribution-comparison", "figure"),
    Input("compare-year-1", "value"),
    Input("compare-year-2", "value"),
    Input("compare-metric", "value"),
    Input("sector-filter", "value"),
    Input("company-filter", "value"),
    Input("main-tabs", "value"),
)
def update_comparison_charts(
    year1, year2, metric, sector_filter, company_filter, current_tab
):
    """Updates graphs on the Comparison tab."""
    if current_tab != "comparison":
        return [no_update] * 4

    # Validate years
    if not year1 or not year2 or not metric:
        empty_fig = create_empty_figure("Please select years and metric")
        return empty_fig, empty_fig, empty_fig, empty_fig

    try:
        year1 = int(year1)
        year2 = int(year2)
    except ValueError:
        empty_fig = create_empty_figure("Please enter valid years")
        return empty_fig, empty_fig, empty_fig, empty_fig

    # Fetch data for both years
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
    except Exception as e:
        logging.error(f"Error fetching comparison data: {e}")
        empty_fig = create_empty_figure("Error fetching comparison data")
        return empty_fig, empty_fig, empty_fig, empty_fig

    df_year1 = pd.DataFrame(data_year1)
    df_year2 = pd.DataFrame(data_year2)

    if df_year1.empty or df_year2.empty:
        empty_fig = create_empty_figure("No data for selected years")
        return empty_fig, empty_fig, empty_fig, empty_fig

    # Apply filters
    for col in [metric, "Sector", "Company"]:
        if col in df_year1.columns:
            df_year1[col] = (
                pd.to_numeric(df_year1[col], errors="coerce")
                if col == metric
                else df_year1[col]
            )
        if col in df_year2.columns:
            df_year2[col] = (
                pd.to_numeric(df_year2[col], errors="coerce")
                if col == metric
                else df_year2[col]
            )

    df1_filtered = df_year1.copy()
    df2_filtered = df_year2.copy()

    if sector_filter:
        df1_filtered = df1_filtered[df1_filtered["Sector"] == sector_filter]
        df2_filtered = df2_filtered[df2_filtered["Sector"] == sector_filter]
    if company_filter:
        df1_filtered = df1_filtered[df1_filtered["Company"] == company_filter]
        df2_filtered = df2_filtered[df2_filtered["Company"] == company_filter]

    # Chart 1: Year Comparison Bar
    try:
        metric_names = {
            "Close": "Average Close Price ($)",
            "Volume": "Total Volume",
            "Market_Cap": "Market Capitalization ($)",
            "Volatility": "Average Volatility (%)",
            "PE_Ratio": "Average P/E Ratio",
        }

        if metric in ["Close", "Volatility", "PE_Ratio"]:
            y1_value = df1_filtered[metric].mean() if not df1_filtered.empty else 0
            y2_value = df2_filtered[metric].mean() if not df2_filtered.empty else 0
        else:  # Volume, Market_Cap
            y1_value = df1_filtered[metric].sum() if not df1_filtered.empty else 0
            y2_value = df2_filtered[metric].sum() if not df2_filtered.empty else 0

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
    except Exception as e:
        logging.error(f"Error creating year comparison chart: {e}")
        fig_bar = create_empty_figure("Chart Error")

    # Chart 2: Sector Growth Line
    try:
        if "Sector" in df1_filtered.columns and "Sector" in df2_filtered.columns:
            sector_growth = []
            sectors = set(df1_filtered["Sector"].unique()) | set(
                df2_filtered["Sector"].unique()
            )

            for sector in sectors:
                sector_data1 = df1_filtered[df1_filtered["Sector"] == sector]
                sector_data2 = df2_filtered[df2_filtered["Sector"] == sector]

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
                )
                fig_line = apply_chart_style(
                    fig_line,
                    f"Sector Growth Rate ({year1} to {year2})",
                    "Sector",
                    "Growth Rate (%)",
                )
            else:
                fig_line = create_empty_figure("No sector growth data available")
        else:
            fig_line = create_empty_figure("Sector data not available")
    except Exception as e:
        logging.error(f"Error creating sector growth chart: {e}")
        fig_line = create_empty_figure("Chart Error")

    # Chart 3: Performance Trend
    try:
        years = [year1, year2]
        avg_values = []

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
            trend_df, x="Year", y="Value", markers=True, line_shape="linear"
        )
        fig_trend = apply_chart_style(
            fig_trend,
            f"{metric_names.get(metric, metric)} Trend",
            "Year",
            metric_names.get(metric, metric),
        )
    except Exception as e:
        logging.error(f"Error creating performance trend chart: {e}")
        fig_trend = create_empty_figure("Chart Error")

    # Chart 4: Metric Distribution Comparison
    try:
        if (
            not df1_filtered.empty
            and not df2_filtered.empty
            and metric in df1_filtered.columns
            and metric in df2_filtered.columns
        ):
            df1_filtered["Year"] = str(year1)
            df2_filtered["Year"] = str(year2)
            combined_df = pd.concat(
                [df1_filtered[["Year", metric]], df2_filtered[["Year", metric]]]
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
        else:
            fig_dist = create_empty_figure("No distribution data available")
    except Exception as e:
        logging.error(f"Error creating distribution comparison chart: {e}")
        fig_dist = create_empty_figure("Chart Error")

    return fig_bar, fig_line, fig_trend, fig_dist


# --- Run server ---
if __name__ == "__main__":
    print("=" * 50)
    print("Starting Stock Market Analytics Dashboard...")
    print("=" * 50)

    # Check API health
    api_healthy, api_status, data_status = check_api_health()
    if not api_healthy:
        print("❌ WARNING: API server is not running!")
        print("💡 Please start the API first: python api.py")
    else:
        print(f"✅ {api_status}")
        print(f"📊 {data_status}")

    print(f"🌐 Dashboard will be available at: http://127.0.0.1:{DEFAULT_PORT}")
    print("=" * 50)

    app.run(debug=True, port=DEFAULT_PORT)
