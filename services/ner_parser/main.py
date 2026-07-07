"""SEVER NER Parser — extracts merchant/subscription entities from raw
transaction descriptors.

Beta implementation: rule-based normalization + known-merchant matching.
Card-network descriptors are noisy ("NETFLIX.COM 866-579-7172 CA");
this strips the noise and maps to canonical merchants with categories.
A statistical NER model can replace `parse_descriptor` later without
changing the interface.
"""

import re
from dataclasses import dataclass
from typing import Optional

KNOWN_MERCHANTS = {
    "netflix": ("Netflix", "Streaming"),
    "spotify": ("Spotify Premium", "Streaming"),
    "icloud": ("iCloud+ 200GB", "Storage"),
    "apple.com/bill": ("iCloud+ 200GB", "Storage"),
    "adobe": ("Adobe Creative Cloud", "Software"),
    "duolingo": ("Duolingo Super", "Education"),
    "dashpass": ("DashPass", "Delivery"),
    "doordash dashpass": ("DashPass", "Delivery"),
    "calm": ("Calm", "Wellness"),
    "nyt": ("NYT Digital", "News"),
    "nytimes": ("NYT Digital", "News"),
    "dropbox": ("Dropbox Plus", "Storage"),
    "peak fitness": ("Peak Fitness Gym", "Health"),
}

_NOISE_PATTERNS = [
    re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b"),          # phone numbers
    re.compile(r"\b(POS|ACH|TST\*|SQ \*|PAYPAL \*)\b", re.I),  # processor prefixes
    re.compile(r"\b[A-Z]{2}\s*$"),                        # trailing state code
    re.compile(r"#\d+"),                                  # store numbers
    re.compile(r"\s{2,}"),                                # collapse whitespace
]


@dataclass(frozen=True)
class MerchantEntity:
    raw: str
    merchant: str
    category: str
    confidence: float


def normalize(descriptor: str) -> str:
    text = descriptor.strip()
    for pattern in _NOISE_PATTERNS:
        text = pattern.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def parse_descriptor(descriptor: str) -> Optional[MerchantEntity]:
    """Map a raw card descriptor to a canonical merchant, or None if unknown."""
    normalized = normalize(descriptor)
    if not normalized:
        return None

    for key, (merchant, category) in KNOWN_MERCHANTS.items():
        if key in normalized:
            # Confidence scales with how much of the descriptor the match explains.
            confidence = round(min(1.0, len(key) / max(1, len(normalized))), 2)
            return MerchantEntity(
                raw=descriptor,
                merchant=merchant,
                category=category,
                confidence=max(0.5, confidence),
            )
    return None


def parse_batch(descriptors: list[str]) -> list[MerchantEntity]:
    entities = []
    for d in descriptors:
        entity = parse_descriptor(d)
        if entity is not None:
            entities.append(entity)
    return entities


def main() -> None:
    samples = [
        "NETFLIX.COM 866-579-7172 CA",
        "SQ *PEAK FITNESS #0042 AUSTIN TX",
        "APPLE.COM/BILL 866-712-7753",
        "CORNER DELI NYC",
    ]
    for entity in parse_batch(samples):
        print(f"{entity.raw!r} -> {entity.merchant} ({entity.category}, {entity.confidence})")


if __name__ == "__main__":
    main()
