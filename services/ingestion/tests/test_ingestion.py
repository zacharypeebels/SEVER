from datetime import date

from main import Transaction, detect_recurring, sample_transactions


def test_sample_feed_has_noise_and_recurring():
    txns = sample_transactions(today=date(2026, 7, 6))
    assert len(txns) == 14  # 4 recurring x 3 months + 2 noise


def test_detect_recurring_finds_monthly_charges():
    txns = sample_transactions(today=date(2026, 7, 6))
    charges = detect_recurring(txns)
    merchants = {c.merchant for c in charges}
    assert merchants == {"Netflix", "Spotify Premium", "Peak Fitness Gym", "Adobe Creative Cloud"}
    assert all(c.cadence == "mo" for c in charges)


def test_one_off_purchases_not_flagged():
    txns = sample_transactions(today=date(2026, 7, 6))
    charges = detect_recurring(txns)
    merchants = {c.merchant for c in charges}
    assert "Corner Deli" not in merchants
    assert "Hardware Store" not in merchants


def test_min_occurrences_respected():
    txns = [
        Transaction("Gym", 30.0, date(2026, 6, 1), "1111"),
        Transaction("Gym", 30.0, date(2026, 7, 1), "1111"),
    ]
    assert detect_recurring(txns, min_occurrences=3) == []
    assert len(detect_recurring(txns, min_occurrences=2)) == 1
