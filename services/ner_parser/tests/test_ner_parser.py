from main import normalize, parse_batch, parse_descriptor


def test_normalize_strips_phone_and_state():
    assert normalize("NETFLIX.COM 866-579-7172 CA") == "netflix.com"


def test_parse_known_merchant():
    entity = parse_descriptor("NETFLIX.COM 866-579-7172 CA")
    assert entity is not None
    assert entity.merchant == "Netflix"
    assert entity.category == "Streaming"
    assert entity.confidence >= 0.5


def test_parse_processor_prefixed_descriptor():
    entity = parse_descriptor("SQ *PEAK FITNESS #0042 AUSTIN TX")
    assert entity is not None
    assert entity.merchant == "Peak Fitness Gym"


def test_apple_bill_maps_to_icloud():
    entity = parse_descriptor("APPLE.COM/BILL 866-712-7753")
    assert entity is not None
    assert entity.merchant == "iCloud+ 200GB"


def test_unknown_merchant_returns_none():
    assert parse_descriptor("CORNER DELI NYC") is None


def test_empty_descriptor_returns_none():
    assert parse_descriptor("   ") is None


def test_parse_batch_filters_unknowns():
    entities = parse_batch(["NETFLIX.COM CA", "CORNER DELI NYC", "DROPBOX* DROPBOX PLUS"])
    merchants = [e.merchant for e in entities]
    assert merchants == ["Netflix", "Dropbox Plus"]
