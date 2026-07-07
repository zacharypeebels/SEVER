from datetime import date

from main import fetch_recurring_charges, stream_to_charge


def test_monthly_stream_maps_to_mo():
    c = stream_to_charge("Netflix", 15.49, "MONTHLY", date(2026, 7, 1), 6)
    assert c.cadence == "mo"
    assert c.amount == 15.49
    assert c.occurrences == 6


def test_annual_stream_maps_to_yr():
    c = stream_to_charge("Calm", 69.99, "ANNUALLY", date(2026, 3, 15), 2)
    assert c.cadence == "yr"


def test_semi_annual_treated_as_yearly():
    assert stream_to_charge("X", 10.0, "SEMI_ANNUALLY", date(2026, 1, 1), 2).cadence == "yr"


def test_unknown_frequency_defaults_to_monthly():
    assert stream_to_charge("X", 10.0, "UNKNOWN", date(2026, 1, 1), 3).cadence == "mo"


def test_negative_amounts_normalized():
    assert stream_to_charge("X", -12.5, "MONTHLY", date(2026, 1, 1), 3).amount == 12.5


def test_sandbox_mode_uses_local_detection(monkeypatch):
    monkeypatch.setenv("SEVER_INGEST_MODE", "sandbox")
    charges = fetch_recurring_charges()
    assert {c.merchant for c in charges} == {
        "Netflix", "Spotify Premium", "Peak Fitness Gym", "Adobe Creative Cloud"
    }
