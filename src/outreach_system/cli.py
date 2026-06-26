from __future__ import annotations

import argparse
import logging
import sys

from outreach_system.config import get_settings
from outreach_system.exceptions import ConfigurationError, OutreachError
from outreach_system.main import run_pipeline

logger = logging.getLogger(__name__)

EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 2
EXIT_CRITICAL_FAILURE = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the outreach pipeline.")
    parser.add_argument("--run-now", action="store_true", help="Run the pipeline immediately.")
    parser.add_argument(
        "--max-emails",
        type=int,
        default=100,
        help="Maximum emails to send in this execution.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = get_settings()
        summary = run_pipeline(max_emails=args.max_emails, settings=settings)
    except ConfigurationError:
        logger.exception("Configuration error.")
        return EXIT_CRITICAL_FAILURE
    except OutreachError:
        logger.exception("Critical application failure.")
        return EXIT_CRITICAL_FAILURE
    except Exception:
        logger.exception("Unhandled critical failure.")
        return EXIT_CRITICAL_FAILURE

    return EXIT_PARTIAL_FAILURE if summary.partially_failed else EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
