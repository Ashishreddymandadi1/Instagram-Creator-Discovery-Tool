"""Synthetic fixtures must be clearly labelled and never leak into live output."""
from tests.fixtures.synthetic_creators import SYNTHETIC_CREATORS, SYNTHETIC_DEMO_DATA


def test_fixtures_are_flagged():
    assert SYNTHETIC_DEMO_DATA is True
    for c in SYNTHETIC_CREATORS:
        assert "SYNTHETIC" in c["display_name"].upper()
        for ev in c["evidence"]:
            assert ev["synthetic"] is True
            assert "SYNTHETIC" in (ev["snippet"] or "").upper()


def test_no_live_code_imports_synthetic_fixtures():
    import pathlib

    app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = [
        p for p in app_dir.rglob("*.py")
        if "synthetic_creators" in p.read_text(encoding="utf-8")
        or "tests.fixtures" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
