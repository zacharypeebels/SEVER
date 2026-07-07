from datetime import date, timedelta

from main import RecurringCharge, charges_to_items


def _charge(merchant="NETFLIX.COM CA", amount=15.49):
    return RecurringCharge(
        merchant=merchant,
        amount=amount,
        cadence="mo",
        occurrences=3,
        last_seen=date.today() - timedelta(days=5),
    )


def test_items_use_ner_canonical_names():
    charges = [_charge()]
    ner = [{"raw": "NETFLIX.COM CA", "merchant": "Netflix", "category": "Streaming", "confidence": 0.9}]
    items = charges_to_items(charges, ner)
    assert items[0]["merchant"] == "Netflix"
    assert items[0]["category"] == "Streaming"
    assert items[0]["lastUsed"] == 5


def test_items_fall_back_to_raw_descriptor():
    items = charges_to_items([_charge(merchant="MYSTERY GYM LLC")], None)
    assert items[0]["merchant"] == "MYSTERY GYM LLC"
    assert items[0]["category"] == "Uncategorized"


def test_unmatched_ner_result_ignored():
    charges = [_charge(merchant="CORNER DELI")]
    ner = [{"raw": "CORNER DELI", "merchant": None, "category": None, "confidence": 0.0}]
    items = charges_to_items(charges, ner)
    assert items[0]["merchant"] == "CORNER DELI"
