from pathlib import Path

import matplotlib

# Force a headless backend so plots can be saved without a display.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fred_data_call import get_fred_series_df


def main():
    df = get_fred_series_df("DGS10")  # series ID for the 10-yr treasury yield

    output_dir = Path("images")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "dgs10_yield.png"

    plt.figure(figsize=(10, 5))
    plt.scatter(
        df["date"],
        df["value"],
        s=1,
        alpha=0.2,
    )
    plt.title("10-year treasury yield over time")
    plt.xlabel("Date")
    plt.ylabel("Yield (%)")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Chart saved to {output_path}")


if __name__ == "__main__":
    main()
