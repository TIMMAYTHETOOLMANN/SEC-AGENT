"""
JLAW Visualization — Static Chart Generator
Produces all 6 investigation chart types as PNG files for embedding.

Output: data/viz/charts/*.png (300 DPI, transparent-ready)

Charts:
1. Parker cumulative sales timeline ($565M+)
2. Swoosh 13D staleness timeline (share count erosion)
3. Section 16(a) toggle heatmap (7-year proxy pattern)
4. Buy/sell divergence (FY2025 directors vs Parker)
5. Anomaly severity scatter (23 items × year × severity)
6. Securities fraud litigation timeline
"""

import json
import os
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import numpy as np

# ═══════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════

COLORS = {
    "navy": "#0F1B2D",
    "red": "#B91C1C",
    "amber": "#D97706",
    "green": "#059669",
    "emerald": "#047857",
    "blue": "#1E40AF",
    "gold": "#854D0E",
    "grey": "#6B7280",
    "light": "#F3F4F6",
    "white": "#FFFFFF",
    "purple": "#7C3AED",
    "black": "#1F2937",
}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.facecolor": COLORS["white"],
    "axes.edgecolor": "#E5E7EB",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.color": "#D1D5DB",
    "figure.facecolor": COLORS["white"],
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.2,
})

DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))
VIZ_DIR = DATA_DIR / "viz" / "charts"
VIZ_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════
# CHART 1: Parker Cumulative Sales Timeline
# ═══════════════════════════════════════════════

def chart_parker_cumulative():
    """Parker $565M+ cumulative sales by fiscal year with stock price overlay."""
    years = ["FY2019", "FY2020", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025"]
    sales_m = [78, 37, 125, 82, 44, 44, 57.5]
    cumulative = np.cumsum(sales_m)
    # NKE approximate year-end close prices
    stock_prices = [85, 98, 133, 117, 109, 95, 62]

    fig, ax1 = plt.subplots(figsize=(10, 5.5))

    # Bar chart — annual sales
    bars = ax1.bar(years, sales_m, color=COLORS["red"], alpha=0.85, width=0.55,
                   label="Annual Sales ($M)", zorder=3)
    ax1.set_ylabel("Annual Sales ($M)", color=COLORS["red"], fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=COLORS["red"])
    ax1.set_ylim(0, 150)

    # Annotate bars
    for bar, val in zip(bars, sales_m):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f"${val:.0f}M", ha="center", va="bottom", fontsize=8,
                color=COLORS["red"], fontweight="bold")

    # Cumulative line on same axis (scaled)
    ax_cum = ax1.twinx()
    ax_cum.plot(years, cumulative, color=COLORS["navy"], linewidth=2.5,
               marker="o", markersize=7, zorder=5, label="Cumulative ($M)")
    ax_cum.set_ylabel("Cumulative Sales ($M)", color=COLORS["navy"], fontweight="bold")
    ax_cum.tick_params(axis="y", labelcolor=COLORS["navy"])
    ax_cum.set_ylim(0, 600)

    for i, (yr, cum) in enumerate(zip(years, cumulative)):
        ax_cum.annotate(f"${cum:.0f}M", (yr, cum), textcoords="offset points",
                       xytext=(0, 12), ha="center", fontsize=8,
                       color=COLORS["navy"], fontweight="bold")

    # Stock price as secondary overlay
    ax_stock = ax1.twinx()
    ax_stock.spines["right"].set_position(("axes", 1.12))
    ax_stock.plot(years, stock_prices, color=COLORS["grey"], linewidth=1.5,
                 linestyle="--", marker="s", markersize=5, alpha=0.6)
    ax_stock.set_ylabel("NKE Stock Price ($)", color=COLORS["grey"])
    ax_stock.tick_params(axis="y", labelcolor=COLORS["grey"])
    ax_stock.set_ylim(40, 170)

    ax1.set_title("Mark Parker Cumulative Stock Sales vs. NKE Price\n"
                  "Executive Chairman | $565M+ Through Self-Approval Pre-Clearance Pathway",
                  pad=15)

    # Legend
    legend_elements = [
        mpatches.Patch(color=COLORS["red"], alpha=0.85, label="Annual Sales ($M)"),
        plt.Line2D([0], [0], color=COLORS["navy"], linewidth=2.5, marker="o", label="Cumulative ($M)"),
        plt.Line2D([0], [0], color=COLORS["grey"], linewidth=1.5, linestyle="--", marker="s", label="NKE Price ($)"),
    ]
    ax1.legend(handles=legend_elements, loc="upper left", framealpha=0.9, fontsize=8)

    fig.tight_layout()
    path = VIZ_DIR / "01_parker_cumulative_sales.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ═══════════════════════════════════════════════
# CHART 2: Swoosh 13D Staleness Timeline
# ═══════════════════════════════════════════════

def chart_swoosh_staleness():
    """Swoosh share count erosion vs 13D amendment deadlines."""
    years = ["2016\n(Last 13D/A)", "FY2019", "FY2020", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025", "Q1 2026"]
    shares_m = [257, 248, 236, 233.5, 233.5, 230.75, 225.75, 221.75, 221.75]
    staleness_years = [0, 3, 4, 5, 6, 7, 8, 9, 9.7]

    fig, ax1 = plt.subplots(figsize=(10, 5.5))

    # Share count area
    ax1.fill_between(range(len(years)), shares_m, alpha=0.15, color=COLORS["navy"])
    ax1.plot(range(len(years)), shares_m, color=COLORS["navy"], linewidth=2.5,
            marker="o", markersize=7, zorder=5)
    ax1.set_ylabel("Swoosh Class A Shares (Millions)", color=COLORS["navy"], fontweight="bold")
    ax1.set_xticks(range(len(years)))
    ax1.set_xticklabels(years, fontsize=8)
    ax1.set_ylim(210, 265)

    # Annotate share counts
    for i, (s, yr) in enumerate(zip(shares_m, years)):
        ax1.annotate(f"{s:.1f}M", (i, s), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=7, color=COLORS["navy"])

    # Staleness bars
    ax2 = ax1.twinx()
    bar_colors = [COLORS["green"] if s <= 2 else COLORS["amber"] if s <= 5
                  else COLORS["red"] for s in staleness_years]
    ax2.bar(range(len(years)), staleness_years, alpha=0.3, color=bar_colors, width=0.4, zorder=2)
    ax2.set_ylabel("Years Since Last 13D/A", color=COLORS["red"], fontweight="bold")
    ax2.set_ylim(0, 12)

    # 2-day rule line (post-Feb 2024)
    ax1.axvline(x=7, color=COLORS["purple"], linewidth=1.5, linestyle=":", alpha=0.7)
    ax1.text(7.1, 260, "SEC 2-Day Rule\nEffective Feb 2024", fontsize=7,
            color=COLORS["purple"], va="top")

    # Distribution annotations
    ax1.annotate("2.75M distributed\n(Jul 2023)", xy=(5, 230.75),
                xytext=(5, 245), fontsize=7, color=COLORS["red"],
                arrowprops=dict(arrowstyle="->", color=COLORS["red"], lw=1),
                ha="center")
    ax1.annotate("9.5M distributed\n(Dec 2025)", xy=(7, 221.75),
                xytext=(7, 238), fontsize=7, color=COLORS["red"],
                arrowprops=dict(arrowstyle="->", color=COLORS["red"], lw=1),
                ha="center")

    ax1.set_title("Swoosh LLC: Share Count Erosion vs. 13D Staleness\n"
                  "35.25M Shares (13.7%) Unreported | 9.7 Years Without Amendment",
                  pad=15)

    fig.tight_layout()
    path = VIZ_DIR / "02_swoosh_13d_staleness.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ═══════════════════════════════════════════════
# CHART 3: Section 16(a) Toggle Heatmap
# ═══════════════════════════════════════════════

def chart_section16a_toggle():
    """7-year proxy Section 16(a) disclosure on/off pattern."""
    years = ["FY2019", "FY2020", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025"]
    # 0=Omitted, 1=Present, -1=Absent (different from omitted — it was there then removed)
    status = [0, 0, 1, -1, 1, 1, 1]
    named = ["—", "—", "Friend\n(1 day late)", "—", "Swan\n(Form 3/A)", "Nielsen\n(late Form 4)", "TBD\n(p.75)"]
    colors_map = {0: COLORS["amber"], 1: COLORS["green"], -1: COLORS["red"]}
    labels_map = {0: "OMITTED", 1: "PRESENT", -1: "ABSENT\n(Removed)"}

    fig, ax = plt.subplots(figsize=(10, 3.5))

    for i, (yr, s) in enumerate(zip(years, status)):
        color = colors_map[s]
        ax.barh(0, 1, left=i, color=color, edgecolor=COLORS["white"], linewidth=2, height=0.7)
        ax.text(i + 0.5, 0, labels_map[s], ha="center", va="center",
               fontsize=9, fontweight="bold", color=COLORS["white"])
        ax.text(i + 0.5, -0.6, named[i], ha="center", va="center",
               fontsize=7, color=COLORS["black"])

    ax.set_xlim(-0.1, len(years) + 0.1)
    ax.set_ylim(-1.2, 0.8)
    ax.set_xticks([i + 0.5 for i in range(len(years))])
    ax.set_xticklabels(years, fontsize=9, fontweight="bold")
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.grid(False)

    ax.set_title("Section 16(a) Delinquency Disclosure Toggle Pattern\n"
                 "OMIT → OMIT → PRESENT → ABSENT → PRESENT → PRESENT → PRESENT",
                 pad=15, fontsize=12)

    # Legend
    legend_elements = [
        mpatches.Patch(color=COLORS["green"], label="PRESENT (delinquency disclosed)"),
        mpatches.Patch(color=COLORS["amber"], label="OMITTED (section not in proxy)"),
        mpatches.Patch(color=COLORS["red"], label="ABSENT (previously present, then removed)"),
    ]
    ax.legend(handles=legend_elements, loc="lower center", ncol=3, fontsize=7,
             bbox_to_anchor=(0.5, -0.35), framealpha=0.9)

    fig.tight_layout()
    path = VIZ_DIR / "03_section16a_toggle.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ═══════════════════════════════════════════════
# CHART 4: Buy/Sell Divergence (FY2025)
# ═══════════════════════════════════════════════

def chart_buy_sell_divergence():
    """Directors buying vs Parker selling — FY2025 signal inversion."""
    # Buyers (positive values)
    buyers = {
        "Cook\n(Lead Dir.)": 2.95,
        "Hill\n(CEO)": 1.0,
        "Knudstorp\n(Director)": 1.0,
        "Swan\n(Audit Chair)": 1.23,
        "Rogers\n(Director)": 0.19,
    }
    # Sellers (negative values)
    sellers = {
        "Parker\n(Exec Chair)": -57.5,
        "O'Neill\n(Former Pres.)": -1.0,
        "Friend\n(CFO)": -1.3,
        "Leinwand\n(CLO)": -1.1,
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5),
                                     gridspec_kw={"width_ratios": [1, 1.5]})

    # Left panel: Buyers
    names_b = list(buyers.keys())
    vals_b = list(buyers.values())
    bars_b = ax1.barh(names_b, vals_b, color=COLORS["emerald"], height=0.55, zorder=3)
    ax1.set_xlabel("Open-Market Purchases ($M)", fontweight="bold", color=COLORS["emerald"])
    ax1.set_xlim(0, 3.5)
    ax1.invert_yaxis()
    for bar, val in zip(bars_b, vals_b):
        ax1.text(val + 0.05, bar.get_y() + bar.get_height()/2,
                f"${val:.2f}M", va="center", fontsize=8, color=COLORS["emerald"], fontweight="bold")
    ax1.set_title("BUYERS (Discretionary)", color=COLORS["emerald"], fontweight="bold")
    ax1.axvline(x=0, color=COLORS["black"], linewidth=0.5)

    # Right panel: Sellers
    names_s = list(sellers.keys())
    vals_s = [abs(v) for v in sellers.values()]
    bars_s = ax2.barh(names_s, vals_s, color=COLORS["red"], height=0.55, zorder=3)
    ax2.set_xlabel("10b5-1 Plan Sales ($M)", fontweight="bold", color=COLORS["red"])
    ax2.set_xlim(0, 65)
    ax2.invert_yaxis()
    for bar, val in zip(bars_s, vals_s):
        ax2.text(val + 0.5, bar.get_y() + bar.get_height()/2,
                f"${val:.1f}M", va="center", fontsize=8, color=COLORS["red"], fontweight="bold")
    ax2.set_title("SELLERS (10b5-1 Plans)", color=COLORS["red"], fontweight="bold")

    fig.suptitle("FY2025 Insider Buy/Sell Divergence\n"
                 "$6.4M Discretionary Purchases vs. $60.9M Plan-Based Sales",
                 fontsize=13, fontweight="bold", y=1.02)

    fig.tight_layout()
    path = VIZ_DIR / "04_buy_sell_divergence.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ═══════════════════════════════════════════════
# CHART 5: Anomaly Severity Scatter
# ═══════════════════════════════════════════════

def chart_anomaly_scatter():
    """23 micro-forensic anomalies plotted by year × severity × category."""
    # Representative anomaly data
    anomalies = [
        ("FY2019", 4, "insider_trading", "Parker blackout trade Dec 2019"),
        ("FY2019", 3, "section_16", "Sprunk gift deferred to Form 5"),
        ("FY2019", 2, "proxy", "§16(a) section omitted"),
        ("FY2020", 4, "governance", "Triple-insider Swoosh board formed"),
        ("FY2020", 3, "proxy", "Say-on-pay crashes to 54%"),
        ("FY2020", 2, "proxy", "§16(a) section omitted (2nd yr)"),
        ("FY2020", 2, "disclosure", "Sprunk/Hill separation: no 8-K exhibits"),
        ("FY2021", 3, "section_16", "Friend 1-day late Form 4"),
        ("FY2021", 2, "proxy", "§16(a) restored — Friend named"),
        ("FY2022", 4, "insider_trading", "Parker $82M at ATH zone"),
        ("FY2022", 3, "swoosh", "Travis Knight trust restructuring, no 13D/A"),
        ("FY2022", 3, "proxy", "§16(a) section REMOVED"),
        ("FY2023", 4, "regulatory", "10b5-1 checkbox — first mandatory disclosure"),
        ("FY2023", 3, "swoosh", "First Swoosh distribution (2.75M shares)"),
        ("FY2023", 2, "proxy", "Swan amended Form 3 — §16(a) restored"),
        ("FY2024", 5, "insider_trading", "Exhibit 19 reveals self-approval loophole"),
        ("FY2024", 5, "governance", "Bylaws rewritten 1 day before CEO firing"),
        ("FY2024", 4, "litigation", "Securities fraud class action filed"),
        ("FY2024", 3, "section_16", "Nielsen late Form 4"),
        ("FY2025", 5, "swoosh", "9.5M mega-distribution, no 13D/A"),
        ("FY2025", 4, "insider_trading", "Buy/sell divergence: $6.4M vs $60.9M"),
        ("FY2025", 3, "section_16", "Travis Knight ~10 days late Form 4"),
        ("Q1 2026", 4, "insider_trading", "Named defendant Friend adopts 10b5-1 plan"),
    ]

    year_map = {"FY2019": 0, "FY2020": 1, "FY2021": 2, "FY2022": 3,
                "FY2023": 4, "FY2024": 5, "FY2025": 6, "Q1 2026": 7}
    cat_colors = {
        "insider_trading": COLORS["red"],
        "swoosh": COLORS["purple"],
        "governance": COLORS["navy"],
        "section_16": COLORS["amber"],
        "proxy": COLORS["gold"],
        "regulatory": COLORS["blue"],
        "litigation": COLORS["black"],
        "disclosure": COLORS["grey"],
    }

    fig, ax = plt.subplots(figsize=(12, 6))

    for year, severity, category, label in anomalies:
        x = year_map[year] + np.random.uniform(-0.15, 0.15)
        y = severity + np.random.uniform(-0.1, 0.1)
        color = cat_colors.get(category, COLORS["grey"])
        size = severity * 40
        ax.scatter(x, y, s=size, c=color, alpha=0.75, edgecolors="white",
                  linewidths=0.5, zorder=5)

    ax.set_xticks(range(len(year_map)))
    ax.set_xticklabels(list(year_map.keys()), fontsize=9, fontweight="bold")
    ax.set_ylabel("Severity (5=STRUCTURAL, 1=LOW)", fontweight="bold")
    ax.set_ylim(0.5, 5.8)
    ax.set_xlim(-0.5, 7.5)

    # Severity bands
    ax.axhspan(4.5, 5.5, alpha=0.05, color=COLORS["red"])
    ax.axhspan(3.5, 4.5, alpha=0.03, color=COLORS["amber"])
    ax.text(7.6, 5.0, "STRUCTURAL", fontsize=7, color=COLORS["red"], va="center", fontweight="bold")
    ax.text(7.6, 4.0, "HIGH", fontsize=7, color=COLORS["amber"], va="center", fontweight="bold")
    ax.text(7.6, 3.0, "MEDIUM", fontsize=7, color=COLORS["gold"], va="center")
    ax.text(7.6, 2.0, "LOW", fontsize=7, color=COLORS["grey"], va="center")

    # Category legend
    legend_elements = [mpatches.Patch(color=c, label=k.replace("_", " ").title())
                       for k, c in cat_colors.items()]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=7, ncol=2, framealpha=0.9)

    ax.set_title("Micro-Forensic Anomaly Map: 23 Items Across 7 Fiscal Years\n"
                 "Size = Severity | Color = Category | Position = Fiscal Year",
                 pad=15)

    fig.tight_layout()
    path = VIZ_DIR / "05_anomaly_scatter.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ═══════════════════════════════════════════════
# CHART 6: Securities Fraud Litigation Timeline
# ═══════════════════════════════════════════════

def chart_litigation_timeline():
    """Securities fraud class action procedural timeline."""
    events = [
        ("2021-03-19", "Class period\nBEGINS", COLORS["navy"]),
        ("2024-06-20", "Complaint\nFILED", COLORS["red"]),
        ("2024-06-27", "NKE −20%\n(Q4 earnings)", COLORS["red"]),
        ("2024-10-01", "Class period\nENDS", COLORS["navy"]),
        ("2024-10-25", "Lead plaintiffs\nappointed", COLORS["blue"]),
        ("2025-02-10", "Amended\ncomplaint\n(292 pages)", COLORS["red"]),
        ("2025-06-15", "MTD filed\n(estimated)", COLORS["amber"]),
        ("2025-08-11", "Plaintiffs'\nopposition", COLORS["green"]),
        ("2026-03-13", "MTD PENDING\n(~6 months)", COLORS["purple"]),
    ]

    fig, ax = plt.subplots(figsize=(14, 4))

    dates = [datetime.strptime(d, "%Y-%m-%d") for d, _, _ in events]
    labels = [l for _, l, _ in events]
    colors = [c for _, _, c in events]

    # Timeline base
    ax.plot(dates, [0]*len(dates), color=COLORS["grey"], linewidth=2, zorder=1)

    for i, (date, label, color) in enumerate(zip(dates, labels, colors)):
        direction = 1 if i % 2 == 0 else -1
        ax.scatter(date, 0, s=80, c=color, zorder=5, edgecolors="white", linewidths=1.5)
        ax.annotate(label, (date, 0),
                   xytext=(0, direction * 40), textcoords="offset points",
                   ha="center", va="center" if direction > 0 else "center",
                   fontsize=7, fontweight="bold", color=color,
                   arrowprops=dict(arrowstyle="-", color=color, lw=0.8))

    # Class period shading
    ax.axvspan(dates[0], dates[3], alpha=0.05, color=COLORS["navy"])
    ax.text(datetime(2022, 10, 1), -0.04, "CLASS PERIOD ($245M insider sales alleged)",
           fontsize=7, ha="center", color=COLORS["navy"], style="italic")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.xticks(rotation=30, fontsize=8)
    ax.set_ylim(-0.08, 0.08)
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    ax.set_title("In Re Nike, Inc. Securities Litigation (D. Or. 3:24-cv-00974-AN)\n"
                 "Procedural Timeline | Lead Plaintiffs: CDPQ + Deka | Counsel: Labaton Keller Sucharow",
                 pad=15, fontsize=11)

    fig.tight_layout()
    path = VIZ_DIR / "06_litigation_timeline.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ═══════════════════════════════════════════════
# MAIN — Generate All Charts
# ═══════════════════════════════════════════════

def generate_all_charts():
    """Generate all 6 investigation charts and return file paths."""
    print(f"  Generating charts to: {VIZ_DIR}/")
    charts = {}

    generators = [
        ("parker_cumulative", chart_parker_cumulative),
        ("swoosh_staleness", chart_swoosh_staleness),
        ("section16a_toggle", chart_section16a_toggle),
        ("buy_sell_divergence", chart_buy_sell_divergence),
        ("anomaly_scatter", chart_anomaly_scatter),
        ("litigation_timeline", chart_litigation_timeline),
    ]

    for name, func in generators:
        try:
            path = func()
            charts[name] = str(path)
            print(f"  ✓ {name}: {path.name}")
        except Exception as e:
            charts[name] = f"ERROR: {e}"
            print(f"  ✗ {name}: {e}")

    # Save manifest
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "chart_dir": str(VIZ_DIR),
        "charts": charts,
    }
    manifest_path = VIZ_DIR / "chart_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Manifest: {manifest_path}")
    return charts


if __name__ == "__main__":
    generate_all_charts()
