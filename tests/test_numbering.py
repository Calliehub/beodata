from text.numbering import FITT_BOUNDARIES


def test_fitt_coverage_complete() -> None:
    """All lines 1-3182 should be covered by fitt boundaries."""
    covered_lines: set[int] = set()
    for i, (start, end, name) in enumerate(FITT_BOUNDARIES):
        if i == 24:  # Skip non-existent fitt 24
            continue
        covered_lines.update(range(start, end + 1))

    expected_lines = set(range(1, 3183))
    missing = expected_lines - covered_lines
    assert not missing, f"Lines not covered by fitts: {sorted(missing)[:10]}..."
