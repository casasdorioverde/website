from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .emailer import send_report_email
from .models import PropertyReport
from .providers.http_json import HttpJsonAirbnbProvider
from .report import build_dataframe, to_csv, to_html, to_json
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

    airbnb_provider = HttpJsonAirbnbProvider(config.airbnb_provider)

    for competitor in config.competitors:
        if competitor.booking_url:
            logger.info("Scraping Booking.com listing for %s", competitor.name)
            reports.append(scrape_booking_listing(competitor, config.search))

        if competitor.airbnb_listing_id:
            logger.info("Fetching Airbnb data for %s", competitor.name)
            airbnb_report = airbnb_provider.fetch(competitor.airbnb_listing_id)
            airbnb_report.name = competitor.name
            airbnb_report.rooms = airbnb_report.rooms or competitor.rooms
            airbnb_report.has_pool = (
                airbnb_report.has_pool
                if airbnb_report.has_pool is not None
                else competitor.has_pool
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
    args = parser.parse_args(argv)

    config = load_config(args.config)
    reports = collect_reports(config)
    df = build_dataframe(reports)

    csv_body = to_csv(df)
    html_body = to_html(df)

    if args.output_csv:
        with open(args.output_csv, "w") as f:
            f.write(csv_body)
        logger.info("Wrote CSV report to %s", args.output_csv)

    if args.output_json:
        with open(args.output_json, "w") as f:
            f.write(to_json(df))
        logger.info("Wrote JSON report to %s", args.output_json)

    if args.dry_run:
        print(df.to_string(index=False))
        return 0

    send_report_email(config.email, html_body, csv_body)
    logger.info("Report emailed to %s", ", ".join(config.email.to))
    return 0


if __name__ == "__main__":
    sys.exit(main())
