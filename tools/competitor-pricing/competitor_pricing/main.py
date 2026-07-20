from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import CompetitorConfig, load_config
from .emailer import send_report_email
from .history import (
    build_history_map,
    load_history_files,
    previous_snapshot,
    write_history_file,
)
from .models import PropertyReport
from .providers.http_json import HttpJsonAirbnbProvider
from .report import build_dataframe, compute_alerts, to_csv, to_html, to_json
from .scrapers.booking import scrape_booking_listing

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def collect_reports(config) -> list[PropertyReport]:
    reports: list[PropertyReport] = [
        PropertyReport(
            name=config.us.name,
            source="us",
            price_per_night=config.us.price_per_night,
            currency=config.us.currency,
            rooms=config.us.rooms,
            has_pool=config.us.has_pool,
            occupancy_signal="n/a",
        )
    ]

    # Our own Booking.com listing, scraped like a competitor so the report
    # shows the price guests actually see (parity check vs config price).
    scrape_targets: list[CompetitorConfig] = []
    if config.us.booking_url:
        scrape_targets.append(
            CompetitorConfig(
                name=f"{config.us.name} (Booking.com)",
                booking_url=config.us.booking_url,
                rooms=config.us.rooms,
                has_pool=config.us.has_pool,
            )
        )
    scrape_targets.extend(config.competitors)

    airbnb_provider = HttpJsonAirbnbProvider(config.airbnb_provider)

    for target in scrape_targets:
        if target.booking_url:
            for window in config.search.windows:
                logger.info(
                    "Scraping Booking.com listing for %s [%s]", target.name, window.label
                )
                reports.append(
                    scrape_booking_listing(target, window, config.search.adults)
                )

        if target.airbnb_listing_id:
            # Provider data (occupancy estimates etc.) is not tied to a
            # specific date window, so this yields one window-less row.
            logger.info("Fetching Airbnb data for %s", target.name)
            airbnb_report = airbnb_provider.fetch(target.airbnb_listing_id)
            airbnb_report.name = target.name
            airbnb_report.region = target.region
            airbnb_report.rooms = airbnb_report.rooms or target.rooms
            airbnb_report.has_pool = (
                airbnb_report.has_pool
                if airbnb_report.has_pool is not None
                else target.has_pool
            )
            reports.append(airbnb_report)

    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare B&B competitor pricing")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report to stdout instead of emailing it",
    )
    parser.add_argument(
        "--output-csv",
        help="Optionally also write the CSV report to this local path",
    )
    parser.add_argument(
        "--output-json",
        help="Optionally also write a JSON report (for the dashboard) to this local path",
    )
    parser.add_argument(
        "--history-dir",
        help="Directory of dated JSON snapshots; enables week-over-week deltas, "
        "sparklines and change alerts",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)

    prev = {}
    history_map = {}
    if args.history_dir:
        files = load_history_files(Path(args.history_dir))
        prev = previous_snapshot(files)
        history_map = build_history_map(files)
        logger.info(
            "Loaded %d history run(s); previous snapshot has %d rows",
            len(files),
            len(prev),
        )

    reports = collect_reports(config)
    df = build_dataframe(reports, prev)
    alerts = compute_alerts(df, prev, config.us.price_per_night)
    for a in alerts:
        logger.info("ALERT [%s] %s", a["kind"], a["text"])

    csv_body = to_csv(df)
    html_body = to_html(df)
    json_body = to_json(
        df, alerts, history_map, windows=[w.label for w in config.search.windows]
    )

    if args.history_dir:
        path = write_history_file(Path(args.history_dir), json_body)
        logger.info("Wrote history snapshot to %s", path)

    if args.output_csv:
        with open(args.output_csv, "w") as f:
            f.write(csv_body)
        logger.info("Wrote CSV report to %s", args.output_csv)

    if args.output_json:
        with open(args.output_json, "w") as f:
            f.write(json_body)
        logger.info("Wrote JSON report to %s", args.output_json)

    if args.dry_run:
        print(df.to_string(index=False))
        if alerts:
            print("\nAlerts:")
            for a in alerts:
                print(f"  - {a['text']}")
        return 0

    if config.email.mode == "changes_only" and not alerts:
        logger.info("email.mode=changes_only and no alerts this run; not emailing")
        return 0

    send_report_email(config.email, html_body, csv_body, alerts)
    logger.info("Report emailed to %s", ", ".join(config.email.to))
    return 0


if __name__ == "__main__":
    sys.exit(main())
