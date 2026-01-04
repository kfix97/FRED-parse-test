import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time
from pandas.testing import assert_frame_equal
import requests

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
            "debt_catg": "Debt Subject to Limit",
            "statutory_debt_limit": "35,000",
            "total_public_debt_outstanding": "33000",
        },
        {"record_date": "", "debt_subject_to_limit": "100.0"},  # missing date dropped
        {"record_date": "2024-01-02", "debt_subject_to_limit": ""},  # missing value dropped
        {"record_date": "2024-01-03", "debt_subject_to_limit": "10", "debt_catg": "Other"},  # filtered by category
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


def test_parse_debt_subject_to_limit_supports_close_today_bal():
    records = [
        {"record_date": "2024-01-01", "close_today_bal": "10", "debt_catg": "Debt Subject to Limit"},
        {"record_date": "2024-01-01", "close_today_bal": "5", "debt_catg": "Debt Subject to Limit"},
        {"record_date": "2024-01-01", "close_today_bal": "7", "debt_catg": "Other"},
    ]
    cleaned = parse_debt_subject_to_limit(records)
    assert cleaned == [
        {"date": date(2024, 1, 1), "debt_subject_to_limit": 10.0},
        {"date": date(2024, 1, 1), "debt_subject_to_limit": 5.0},
    ]


@freeze_time("2024-01-10 12:00:00")
def test_get_debt_subject_to_limit_df_fetches_and_caches(monkeypatch, tmp_path):
    sample_records = [
        {
            "record_date": "2024-01-01",
            "debt_subject_to_limit_amt": "34000.0",
            "statutory_debt_limit_amt": "35000",
            "debt_catg": "Debt Subject to Limit",
        },
        {
            "record_date": "2024-01-02",
            "debt_subject_to_limit": "34100.0",
            "total_public_debt_outstanding_amt": "33900",
            "debt_catg": "Debt Subject to Limit",
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
            "debt_subject_to_limit_trillions": [0.034, 0.0341],
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


def test_fetch_debt_subject_to_limit_handles_query_only_next(monkeypatch):
    calls = {"count": 0}

    class DummyResponse:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

        def raise_for_status(self):
            if self.payload.get("status_code", 200) >= 400:
                raise requests.HTTPError("bad")

    def fake_get(url, params=None, headers=None):
        calls["count"] += 1
        if calls["count"] == 1:
            assert "page[number]" in params
            return DummyResponse(
                {
                    "data": [
                        {
                            "record_date": "2024-01-01",
                            "debt_subject_to_limit": "1",
                            "debt_catg": "Debt Subject to Limit",
                        }
                    ],
                    "links": {"next": "&page[number]=2&page[size]=1"},
                }
            )
        assert params is None  # second call should follow link without params
        assert url.endswith("debt_subject_to_limit?page[number]=2&page[size]=1")
        return DummyResponse(
            {
                "data": [
                    {
                        "record_date": "2024-01-02",
                        "close_today_bal": "2",
                        "debt_catg": "Debt Subject to Limit",
                    }
                ],
                "links": {"next": None},
            }
        )

    monkeypatch.setattr(fiscal_data_call.requests, "get", fake_get)

    records = fiscal_data_call.fetch_debt_subject_to_limit()
    assert len(records) == 2


def test_load_debt_cache_df_backfills_trillions(tmp_path):
    csv_path = tmp_path / "treasury_debt_subject_to_limit.csv"
    pd.DataFrame(
        {"date": [pd.Timestamp("2024-01-01")], "debt_subject_to_limit": [34000.0]}
    ).to_csv(csv_path, index=False)

    loaded = load_debt_cache_df(csv_path)

    assert "debt_subject_to_limit_trillions" in loaded.columns
    assert loaded["debt_subject_to_limit_trillions"].iloc[0] == 0.034
