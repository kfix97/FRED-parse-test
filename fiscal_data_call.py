# Helpers for pulling Treasury Fiscal Data API debt_subject_to_limit series,
# validating the response, shaping it into a tidy DataFrame, and caching it.
from datetime import datetime
import json
import os
from pathlib import Path
from urllib.parse import urljoin
import warnings

import pandas as pd
import requests
from dotenv import load_dotenv


FISCAL_BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
DEBT_ENDPOINT = "/v1/accounting/dts/debt_subject_to_limit"


def get_fiscal_api_key(env_var="FISCAL_API_KEY"):
    """Read an optional Treasury API key from .env (not required for public access)."""
    load_dotenv()
    return os.getenv(env_var)


def fetch_debt_subject_to_limit(api_key=None, page_size=1000, max_pages=100):
    """
    Pull all pages from the debt_subject_to_limit endpoint.

    The Fiscal Data API paginates responses; follow links.next until exhausted.
    """
    headers = {}
    if api_key:
        headers["X-API-KEY"] = api_key

    base_url = f"{FISCAL_BASE_URL}{DEBT_ENDPOINT}"
    url = base_url
    params = {"page[size]": page_size}
    records = []
    page = 1

    while True:
        if params is not None:
            params["page[number]"] = page

        resp = requests.get(url, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

        data = payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError("Treasury response missing data array")

        records.extend(data)

        links = payload.get("links") or {}
        next_url = links.get("next")
        if not next_url:
            break

        page += 1
        if page > max_pages:
            raise RuntimeError("Pagination exceeded max_pages when fetching Treasury data")

        if next_url.startswith("&"):
            url = f"{base_url}?{next_url.lstrip('&')}"
        elif next_url.startswith("?"):
            url = f"{base_url}{next_url}"
        else:
            url = urljoin(base_url, next_url)
        params = None  # next_url already includes query params

    return records


def _to_number(value):
    """Coerce string or numeric inputs to float after trimming commas."""
    return float(str(value).replace(",", ""))


def _get_field(row: dict, aliases):
    """Return the first non-empty field from a list of possible aliases."""
    for key in aliases:
        val = row.get(key)
        if val not in (None, "", "null"):
            return val
    return None


def parse_debt_subject_to_limit(records):
    """Normalize Treasury debt rows to {date, debt_subject_to_limit, ...} dicts."""
    cleaned = []
    for row in records:
        raw_date = row.get("record_date")
        raw_debt = _get_field(
            row,
            [
                "debt_subject_to_limit",
                "debt_subject_to_limit_amt",
                "close_today_bal",  # present in table III-C
            ],
        )

        if not raw_date or raw_debt in (None, "", "null"):
            continue

        try:
            parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"Invalid record_date '{raw_date}'") from exc

        try:
            debt_value = _to_number(raw_debt)
        except (TypeError, ValueError):
            warnings.warn(f"Skipping row with non-numeric debt_subject_to_limit: {raw_debt}")
            continue

        record = {"date": parsed_date, "debt_subject_to_limit": debt_value}

        optional_fields = {
            "statutory_debt_limit": [
                "statutory_debt_limit",
                "statutory_debt_limit_amt",
            ],
            "total_public_debt_outstanding": [
                "total_public_debt_outstanding",
                "total_public_debt_outstanding_amt",
            ],
            "open_today_bal": ["open_today_bal"],
            "open_month_bal": ["open_month_bal"],
            "open_fiscal_year_bal": ["open_fiscal_year_bal"],
        }
        for normalized, aliases in optional_fields.items():
            raw_val = _get_field(row, aliases)
            if raw_val in (None, "", "null"):
                continue
            try:
                record[normalized] = _to_number(raw_val)
            except (TypeError, ValueError):
                continue

        cleaned.append(record)

    return cleaned


def load_cache_meta(meta_path: Path):
    if not meta_path.exists():
        return None
    with meta_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_cache_fresh(meta: dict, ttl_seconds: int) -> bool:
    pulled_at = meta.get("pulled_at")
    if not pulled_at:
        return False
    pulled_dt = datetime.fromisoformat(pulled_at)
    age_seconds = (datetime.now() - pulled_dt).total_seconds()
    return age_seconds <= ttl_seconds


def load_debt_cache_df(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["date"])
    if df.empty:
        raise ValueError("Cache DF is empty")
    if "date" not in df.columns or "debt_subject_to_limit" not in df.columns:
        raise ValueError("Cache DF missing required columns")
    if df["date"].isna().any() or df["debt_subject_to_limit"].isna().any():
        raise ValueError("Cache DF contains missing date/debt_subject_to_limit")
    df = df.sort_values("date").reset_index(drop=True)
    return df


def save_debt_cache(df: pd.DataFrame, csv_path: Path, meta_path: Path):
    if df.empty:
        raise ValueError("Refusing to cache empty DataFrame")
    if "date" not in df.columns or "debt_subject_to_limit" not in df.columns:
        raise ValueError("Refusing to cache DF missing required columns")
    if df["date"].isna().any() or df["debt_subject_to_limit"].isna().any():
        raise ValueError("Refusing to cache DF with missing date/debt_subject_to_limit")

    max_dt = pd.to_datetime(df["date"]).max()
    if pd.isna(max_dt):
        raise ValueError("Refusing to cache DF with invalid max date")

    meta = {
        "dataset": "debt_subject_to_limit",
        "pulled_at": datetime.now().isoformat(timespec="seconds"),
        "max_record_date": max_dt.date().isoformat(),
        "row_count": int(len(df)),
    }

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_csv = csv_path.with_suffix(".csv.tmp")
    tmp_meta = meta_path.with_suffix(".json.tmp")

    df.to_csv(tmp_csv, index=False)
    with tmp_meta.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    tmp_csv.replace(csv_path)
    tmp_meta.replace(meta_path)


def get_debt_subject_to_limit_df(cache_ttl_seconds=86400, cache_dir="cache", page_size=1000):
    cache_dir_path = Path(cache_dir)
    csv_path = cache_dir_path / "treasury_debt_subject_to_limit.csv"
    meta_path = cache_dir_path / "treasury_debt_subject_to_limit_meta.json"

    meta = load_cache_meta(meta_path)
    if meta and csv_path.exists() and is_cache_fresh(meta, cache_ttl_seconds):
        return load_debt_cache_df(csv_path)

    try:
        api_key = get_fiscal_api_key()
        raw_records = fetch_debt_subject_to_limit(api_key=api_key, page_size=page_size)
        if not isinstance(raw_records, list) or len(raw_records) == 0:
            raise RuntimeError("No Treasury records returned")

        cleaned = parse_debt_subject_to_limit(raw_records)
        if len(cleaned) == 0:
            sample = raw_records[:2]
            raise RuntimeError(
                "All Treasury records were filtered out during parsing. "
                f"Sample payload: {sample}"
            )

        df = pd.DataFrame(cleaned)
        if df.duplicated(subset="date").any():
            agg_map = {"debt_subject_to_limit": "sum"}
            if "statutory_debt_limit" in df.columns:
                agg_map["statutory_debt_limit"] = "max"
            if "total_public_debt_outstanding" in df.columns:
                agg_map["total_public_debt_outstanding"] = "max"
            for col in ("open_today_bal", "open_month_bal", "open_fiscal_year_bal"):
                if col in df.columns:
                    agg_map[col] = "max"
            df = df.groupby("date", as_index=False).agg(agg_map)

        df = df.sort_values("date").reset_index(drop=True)

        save_debt_cache(df, csv_path, meta_path)
        return df

    except Exception as api_err:
        try:
            if csv_path.exists() and meta:
                df = load_debt_cache_df(csv_path)
                warnings.warn(
                    f"Using stale Treasury cached data. "
                    f"Pulled at {meta.get('pulled_at')}, "
                    f"max record date {meta.get('max_record_date')}. "
                    f"API error: {api_err}"
                )
                return df
        except Exception as cache_err:
            raise RuntimeError(
                "Treasury cache is corrupted/unusable AND API request failed. "
                f"API error: {api_err}. Cache error: {cache_err}."
            ) from api_err

        raise


if __name__ == "__main__":
    df = get_debt_subject_to_limit_df()
    print(df.head())
