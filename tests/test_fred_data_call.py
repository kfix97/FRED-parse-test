import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

# Support pytest discovery and direct file runs by ensuring repo root is importable.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fred_data_call
from fred_data_call import (
    get_fred_series_df,
    is_cache_fresh,
    load_cache_df,
    parse_observations,
    save_cache,
)


def test_parse_observations_filters_and_coerces():
    observations = [
        {"date": "2024-01-01", "value": "3.5", "other": "ignore"},
        {"date": "2024-01-02", "value": "."},  # dropped null marker
        {"date": "", "value": "1.0"},  # dropped missing date
    ]

    cleaned = parse_observations(observations)

    assert cleaned == [{"date": date(2024, 1, 1), "value": 3.5}]


def test_parse_observations_raises_on_bad_date():
    observations = [{"date": "bad-date", "value": "1.0"}]
    with pytest.raises(ValueError):
        parse_observations(observations)


def test_is_cache_fresh_respects_ttl():
    now = datetime.now()
    meta = {"pulled_at": (now - timedelta(minutes=10)).isoformat(timespec="seconds")}

    assert is_cache_fresh(meta, ttl_seconds=3600)
    assert not is_cache_fresh(meta, ttl_seconds=1)


def test_load_cache_df_validates_and_sorts(tmp_path):
    csv_path = tmp_path / "fred_SER.csv"
    unsorted = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-01")],
            "value": [2.0, 1.0],
        }
    )
    unsorted.to_csv(csv_path, index=False)

    loaded = load_cache_df(csv_path)

    assert list(loaded["date"].dt.date) == [date(2024, 1, 1), date(2024, 1, 2)]
    assert list(loaded["value"]) == [1.0, 2.0]


@pytest.mark.parametrize(
    "df,expected_message",
    [
        (pd.DataFrame(), "Cache DF is empty"),
        (pd.DataFrame({"date": [pd.Timestamp("2024-01-01")]}), "missing required columns"),
        (
            pd.DataFrame({"date": [pd.NaT], "value": [1.0]}),
            "contains missing date/value",
        ),
        (
            pd.DataFrame({"date": [pd.Timestamp("2024-01-01")], "value": [pd.NA]}),
            "contains missing date/value",
        ),
    ],
)
def test_load_cache_df_rejects_invalid(tmp_path, df, expected_message):
    csv_path = tmp_path / "fred_SER.csv"
    df.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match=expected_message):
        load_cache_df(csv_path)


def test_save_cache_writes_files_and_meta(tmp_path):
    df = pd.DataFrame(
        {
            "date": [date(2024, 1, 1), date(2024, 1, 2)],
            "value": [1.0, 2.0],
        }
    )
    csv_path = tmp_path / "fred_SER.csv"
    meta_path = tmp_path / "fred_SER_meta.json"

    save_cache(df, "SER", csv_path, meta_path)

    assert csv_path.exists()
    assert meta_path.exists()

    with meta_path.open() as f:
        meta = json.load(f)

    assert meta["series_id"] == "SER"
    assert meta["row_count"] == 2
    assert meta["max_observation_date"] == "2024-01-02"


def test_save_cache_rejects_empty_df(tmp_path):
    csv_path = tmp_path / "fred_SER.csv"
    meta_path = tmp_path / "fred_SER_meta.json"

    with pytest.raises(ValueError, match="Refusing to cache empty DataFrame"):
        save_cache(pd.DataFrame(columns=["date", "value"]), "SER", csv_path, meta_path)


def test_get_fred_series_df_uses_fresh_cache(monkeypatch, tmp_path):
    csv_path = tmp_path / "fred_SER.csv"
    meta_path = tmp_path / "fred_SER_meta.json"
    cached_df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
            "value": [1.0, 2.0],
        }
    )
    cached_df.to_csv(csv_path, index=False)

    meta = {
        "series_id": "SER",
        "pulled_at": datetime.now().isoformat(timespec="seconds"),
        "max_observation_date": "2024-01-02",
        "row_count": 2,
    }
    meta_path.write_text(json.dumps(meta))

    fetch_calls = {"count": 0}

    def fake_fetch(series_id, api_key):
        fetch_calls["count"] += 1
        return {}

    monkeypatch.setattr(fred_data_call, "fetch_fred_json", fake_fetch)

    result = get_fred_series_df("SER", cache_ttl_seconds=3600, cache_dir=tmp_path)

    assert_frame_equal(result, load_cache_df(csv_path))
    assert fetch_calls["count"] == 0


def test_get_fred_series_df_fetches_and_caches(monkeypatch, tmp_path):
    sample_json = {
        "observations": [
            {"date": "2024-01-01", "value": "1.5"},
            {"date": "2024-01-02", "value": "."},  # filtered out
            {"date": "2024-01-03", "value": "2.5"},
        ]
    }

    monkeypatch.setenv("API_KEY", "dummy-key")
    monkeypatch.setattr(
        fred_data_call, "fetch_fred_json", lambda series_id, api_key: sample_json
    )

    result = get_fred_series_df("SER", cache_ttl_seconds=1, cache_dir=tmp_path)

    expected = pd.DataFrame(
        {
            "date": [date(2024, 1, 1), date(2024, 1, 3)],
            "value": [1.5, 2.5],
        }
    )

    assert_frame_equal(result.reset_index(drop=True), expected)

    csv_path = tmp_path / "fred_SER.csv"
    meta_path = tmp_path / "fred_SER_meta.json"
    assert csv_path.exists()
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["series_id"] == "SER"
    assert meta["row_count"] == 2
    assert meta["max_observation_date"] == "2024-01-03"


def test_get_fred_series_df_falls_back_to_stale_cache(monkeypatch, tmp_path):
    csv_path = tmp_path / "fred_SER.csv"
    meta_path = tmp_path / "fred_SER_meta.json"

    cached_df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2023-12-31"), pd.Timestamp("2024-01-01")],
            "value": [1.0, 1.1],
        }
    )
    cached_df.to_csv(csv_path, index=False)

    stale_meta = {
        "series_id": "SER",
        "pulled_at": (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds"),
        "max_observation_date": "2024-01-01",
        "row_count": 2,
    }
    meta_path.write_text(json.dumps(stale_meta))

    monkeypatch.setenv("API_KEY", "dummy-key")

    def failing_fetch(series_id, api_key):
        raise RuntimeError("API unavailable")

    monkeypatch.setattr(fred_data_call, "fetch_fred_json", failing_fetch)

    with pytest.warns(UserWarning, match="Using stale cached data"):
        result = get_fred_series_df("SER", cache_ttl_seconds=1, cache_dir=tmp_path)

    assert_frame_equal(result.reset_index(drop=True), load_cache_df(csv_path))


def test_get_fred_series_df_raises_on_both_api_and_cache_failure(monkeypatch, tmp_path):
    csv_path = tmp_path / "fred_SER.csv"
    meta_path = tmp_path / "fred_SER_meta.json"
    meta_path.write_text(json.dumps({"pulled_at": datetime.now().isoformat(timespec="seconds")}))
    csv_path.write_text("bad csv content")

    monkeypatch.setenv("API_KEY", "dummy-key")

    def failing_fetch(series_id, api_key):
        raise RuntimeError("API unavailable")

    monkeypatch.setattr(fred_data_call, "fetch_fred_json", failing_fetch)

    with pytest.raises(RuntimeError, match="Cache is corrupted/unusable AND API request failed"):
        get_fred_series_df("SER", cache_ttl_seconds=1, cache_dir=tmp_path)
