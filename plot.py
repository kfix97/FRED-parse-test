from pathlib import Path

import matplotlib

# Force a headless backend so plots can be saved without a display.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from fiscal_data_call import get_debt_subject_to_limit_df
from fred_data_call import get_fred_series_df


def build_combined_df(series_id="DGS10"):
    """Merge yield and debt series on date for plotting."""
    yield_df = get_fred_series_df(series_id).rename(columns={"value": "yield_percent"})
    debt_df = get_debt_subject_to_limit_df()

    # Normalize dates to pandas datetime for a clean merge.
    yield_df["date"] = pd.to_datetime(yield_df["date"])
    debt_df["date"] = pd.to_datetime(debt_df["date"])

    merged = (
        pd.merge(yield_df, debt_df, on="date", how="inner")
        .sort_values("date")
        .reset_index(drop=True)
    )
    if merged.empty:
        raise RuntimeError("No overlapping dates between yield and debt series")
    return merged


def main():
    df = build_combined_df()

    output_dir = Path("images")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "yield_vs_debt.png"

    fig, ax_left = plt.subplots(figsize=(12, 6))
    ax_right = ax_left.twinx()

    ax_left.plot(df["date"], df["yield_percent"], color="tab:blue", label="10Y Yield (%)")
    ax_left.set_ylabel("10Y Yield (%)", color="tab:blue")
    ax_left.tick_params(axis="y", labelcolor="tab:blue")

    ax_right.plot(
        df["date"],
        df["debt_subject_to_limit"],
        color="tab:red",
        label="Debt Subject to Limit",
    )
    ax_right.set_ylabel("Debt Subject to Limit (USD)", color="tab:red")
    ax_right.tick_params(axis="y", labelcolor="tab:red")

    ax_left.set_title("10-year Treasury Yield vs Debt Subject to Limit")
    ax_left.set_xlabel("Date")

    # Build a unified legend from both axes.
    lines = ax_left.get_lines() + ax_right.get_lines()
    labels = [line.get_label() for line in lines]
    ax_left.legend(lines, labels, loc="upper left")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Chart saved to {output_path}")


if __name__ == "__main__":
    main()
