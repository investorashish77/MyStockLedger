import argparse
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

BSE_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
OUTPUT_DIR = Path("announcements")
DEFAULT_COLUMNS = [
    "SCRIP_CD", "SLONGNAME", "HEADLINE", "CATEGORYNAME", "SUBCATNAME",
    "NEWS_DT", "ATTACHMENTNAME", "NSURL", "NEWSID"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Referer": "https://www.bseindia.com/",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch BSE announcements by day into local CSV repository")
    parser.add_argument("--from-date", default="20260101", help="Start date (YYYYMMDD)")
    parser.add_argument("--to-date", default=datetime.now().strftime("%Y%m%d"), help="End date (YYYYMMDD)")
    parser.add_argument("--max-retries", type=int, default=4, help="Retries per page request")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds")
    parser.add_argument("--delay-min", type=float, default=0.5, help="Min delay between page calls")
    parser.add_argument("--delay-max", type=float, default=1.5, help="Max delay between page calls")
    parser.add_argument("--force", action="store_true", help="Re-fetch dates even if daily CSV already exists")
    return parser.parse_args()


def fetch_with_retry(url, headers, payload, timeout, max_retries):
    attempt = 0
    while True:
        try:
            response = requests.get(url, headers=headers, params=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            attempt += 1
            if attempt > max_retries:
                raise RuntimeError(
                    f"Failed after {max_retries} retries for date={payload['strPrevDate']} page={payload['pageno']}: {exc}"
                ) from exc
            wait_seconds = min(2 ** attempt, 20)
            print(
                f"    Retry {attempt}/{max_retries} for date={payload['strPrevDate']} page={payload['pageno']} "
                f"after error: {exc}. Waiting {wait_seconds}s..."
            )
            time.sleep(wait_seconds)


def fetch_one_day(date_str, timeout, max_retries, delay_min, delay_max):
    payload = {
        "pageno": 1,
        "strCat": "-1",
        "strPrevDate": date_str,
        "strScrip": "",
        "strSearch": "P",
        "strToDate": date_str,
        "strType": "C",
        "subcategory": "",
    }

    rows = []
    while True:
        print(f"  Page {payload['pageno']}")
        json_data = fetch_with_retry(BSE_API_URL, HEADERS, payload, timeout, max_retries)
        table_rows = json_data.get("Table", [])
        if not table_rows:
            break
        rows.extend(table_rows)
        payload["pageno"] += 1
        time.sleep(random.uniform(delay_min, delay_max))
    return rows


def write_daily_csv(output_path: Path, rows):
    if rows:
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(columns=DEFAULT_COLUMNS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)


def main():
    args = parse_args()
    start_date = datetime.strptime(args.from_date, "%Y%m%d")
    end_date = datetime.strptime(args.to_date, "%Y%m%d")
    if start_date > end_date:
        raise ValueError("from-date cannot be after to-date")

    current_date = start_date
    success_days = 0
    skipped_days = 0
    failed_days = 0
    total_rows = 0

    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        daily_csv = OUTPUT_DIR / f"bse_announcements_{date_str}.csv"

        if daily_csv.exists() and not args.force:
            print(f"Skipping {date_str}: file already exists ({daily_csv})")
            skipped_days += 1
            current_date += timedelta(days=1)
            continue

        print(f"\nFetching data for {date_str}")
        try:
            rows = fetch_one_day(
                date_str=date_str,
                timeout=args.timeout,
                max_retries=args.max_retries,
                delay_min=args.delay_min,
                delay_max=args.delay_max
            )
            write_daily_csv(daily_csv, rows)
            print(f"Saved {len(rows)} row(s) -> {daily_csv}")
            success_days += 1
            total_rows += len(rows)
        except Exception as exc:
            failed_days += 1
            print(f"Failed for {date_str}: {exc}")

        current_date += timedelta(days=1)

    print(
        f"\nDone. success_days={success_days}, skipped_days={skipped_days}, "
        f"failed_days={failed_days}, total_rows={total_rows}"
    )


if __name__ == "__main__":
    main()
