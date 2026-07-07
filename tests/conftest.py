"""
Pytest fixtures shared across the data-pipeline test suite.

Both fixtures load the *already-built* canonical and borough-summary
parquets from `data/processed/`. They do NOT trigger a rebuild: the
`build_canonical.py` and `build_borough_summary.py` scripts already run
their own internal validation checks at build time (see those scripts), and
this test suite is the *external* invariant layer that runs after a
build has produced the artefacts.

If the artefacts are missing, the affected tests are skipped with a
clear message rather than failing -- a fresh checkout that has not yet
run the build scripts should still get a green pytest run on tests that
do not require the artefacts.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PATH = PROJECT_ROOT / "data" / "processed" / "lfb_canonical_2024_2026.parquet"
BOROUGH_SUMMARY_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_borough_summary_2024_2026.parquet"
)
MOBILISATIONS_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_mobilisations_2024_2026.parquet"
)


@pytest.fixture(scope="session")
def canonical() -> pd.DataFrame:
    if not CANONICAL_PATH.exists():
        pytest.skip(
            f"canonical parquet missing at {CANONICAL_PATH}; "
            "run `python src/data/build_canonical.py` first"
        )
    return pd.read_parquet(CANONICAL_PATH)


@pytest.fixture(scope="session")
def borough_summary() -> pd.DataFrame:
    if not BOROUGH_SUMMARY_PATH.exists():
        pytest.skip(
            f"borough-summary parquet missing at {BOROUGH_SUMMARY_PATH}; "
            "run `python src/data/build_borough_summary.py` first"
        )
    return pd.read_parquet(BOROUGH_SUMMARY_PATH)


@pytest.fixture(scope="session")
def mobilisations() -> pd.DataFrame:
    if not MOBILISATIONS_PATH.exists():
        pytest.skip(
            f"mobilisations parquet missing at {MOBILISATIONS_PATH}; "
            "run `python src/data/build_mobilisations.py` first"
        )
    return pd.read_parquet(MOBILISATIONS_PATH)
