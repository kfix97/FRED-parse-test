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
            "value": [1.0, 1.2, 1.4],
        }
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(plot, "get_fred_series_df", lambda series_id: fake_df)

    plot.main()

    output_path = Path("images") / "dgs10_yield.png"
    assert output_path.exists()
    assert output_path.stat().st_size > 0
