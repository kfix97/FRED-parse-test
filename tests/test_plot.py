from pathlib import Path
import sys

import pandas as pd

# Support pytest discovery and direct file runs by ensuring repo root is importable.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plot


def test_plot_main_saves_chart(monkeypatch, tmp_path):
    fake_df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "yield_percent": [1.0, 1.2, 1.4],
            "debt_subject_to_limit": [34000, 34100, 34200],
            # Intentionally omit trillions column to exercise backfill in plot.main
        }
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(plot, "build_combined_df", lambda: fake_df)

    plot.main()

    output_path = Path("images") / "yield_vs_debt.png"
    assert output_path.exists()
    assert output_path.stat().st_size > 0
