import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time
from pandas.testing import assert_frame_equal

# Support pytest discovery and direct file runs by ensuring repo root is importable.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fiscal_data_call
from fiscal_data_call import (
    get_debt_subject_to_limit_df,
    load_debt_cache_df,
    parse_debt_subject_to_limit,
)


def test_parse_debt_subject_to_limit_filters_and_coerces():
    records = [
        {
            "record_date": "2024-01-01",
            "debt_subject_to_limit": "34,000.5",
            "statutory_debt_limit": "35,000",
            "total_public_debt_outstanding": "33000",
        },
        {"record_date": "", "debt_subject_to_limit": "100.0"},  # missing date dropped
        {"record_date": "2024-01-02", "debt_subject_to_limit": ""},  # missing value dropped
    ]

    cleaned = parse_debt_subject_to_limit(records)

    assert cleaned == [
        {
            "date": date(2024, 1, 1),
            "debt_subject_to_limit": 34000.5,
            "statutory_debt_limit": 35000.0,
            "total_public_debt_outstanding": 33000.0,
        }
    ]


def test_parse_debt_subject_to_limit_raises_on_bad_date():
    records = [{"record_date": "bad-date", "debt_subject_to_limit": "1.0"}]
    with pytest.raises(ValueError):
        parse_debt_subject_to_limit(records)


@freeze_time("2024-01-10 12:00:00")
def test_get_debt_subject_to_limit_df_fetches_and_caches(monkeypatch, tmp_path):
    sample_records = [
        {
            "record_date": "2024-01-01",
            "debt_subject_to_limit": "34000.0",
            "statutory_debt_limit": "35000",
        },
        {
            "record_date": "2024-01-02",
            "debt_subject_to_limit": "34100.0",
            "total_public_debt_outstanding": "33900",
        },
    ]

    monkeypatch.setenv("FISCAL_API_KEY", "dummy-key")
    monkeypatch.setattr(
        fiscal_data_call,
        "fetch_debt_subject_to_limit",
        lambda api_key=None, page_size=1000, max_pages=100: sample_records,
    )

    result = get_debt_subject_to_limit_df(cache_ttl_seconds=1, cache_dir=tmp_path, page_size=2)

    expected = pd.DataFrame(
        {
            "date": [date(2024, 1, 1), date(2024, 1, 2)],
            "debt_subject_to_limit": [34000.0, 34100.0],
            "statutory_debt_limit": [35000.0, np.nan],
            "total_public_debt_outstanding": [np.nan, 33900.0],
        }
    )

    assert_frame_equal(
        result.reset_index(drop=True),
        expected.reset_index(drop=True),
        check_dtype=False,
        check_like=True,
    )

    csv_path = tmp_path / "treasury_debt_subject_to_limit.csv"
    meta_path = tmp_path / "treasury_debt_subject_to_limit_meta.json"
    assert csv_path.exists()
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["dataset"] == "debt_subject_to_limit"
    assert meta["row_count"] == 2
    assert meta["max_record_date"] == "2024-01-02"


@freeze_time("2024-01-10 12:00:00")
def test_get_debt_subject_to_limit_df_falls_back_to_stale_cache(monkeypatch, tmp_path):
    csv_path = tmp_path / "treasury_debt_subject_to_limit.csv"
    meta_path = tmp_path / "treasury_debt_subject_to_limit_meta.json"

    cached_df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
            "debt_subject_to_limit": [34000.0, 34100.0],
        }
    )
    cached_df.to_csv(csv_path, index=False)

    stale_meta = {
        "dataset": "debt_subject_to_limit",
        "pulled_at": (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds"),
        "max_record_date": "2024-01-02",
        "row_count": 2,
    }
    meta_path.write_text(json.dumps(stale_meta))

    def failing_fetch(**kwargs):
        raise RuntimeError("API unavailable")

    monkeypatch.setattr(fiscal_data_call, "fetch_debt_subject_to_limit", failing_fetch)

    with pytest.warns(UserWarning, match="Using stale Treasury cached data"):
        result = get_debt_subject_to_limit_df(cache_ttl_seconds=1, cache_dir=tmp_path)

    assert_frame_equal(result.reset_index(drop=True), load_debt_cache_df(csv_path))
