"""Fifteen curated question/answer/context examples for the Phase 1 corpus."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.corpus import CORPUS


@dataclass(frozen=True)
class GoldenExample:
    """A retrieval-grounded regression example."""

    id: str
    query: str
    expected_answer: str
    expected_context: tuple[str, ...]


_CONTEXT = {document.metadata["id"]: document.page_content for document in CORPUS}

GOLDEN_DATASET: tuple[GoldenExample, ...] = (
    GoldenExample(
        "company-product",
        "What does Acme Orbit sell?",
        "Acme Orbit sells the OrbitNote, a cloud-connected notebook for field teams.",
        (_CONTEXT["company-overview"],),
    ),
    GoldenExample(
        "company-fictional",
        "Is Acme Orbit a real company in this dataset?",
        "Acme Orbit is a fictional company.",
        (_CONTEXT["company-overview"],),
    ),
    GoldenExample(
        "sync-methods",
        "How does OrbitNote sync handwritten notes?",
        "OrbitNote syncs handwritten notes over Wi-Fi and Bluetooth.",
        (_CONTEXT["orbitnote-sync"],),
    ),
    GoldenExample(
        "sync-storage",
        "Where are encrypted copies of notes stored?",
        "Encrypted copies are stored in the user's Orbit Vault.",
        (_CONTEXT["orbitnote-sync"],),
    ),
    GoldenExample(
        "battery-life",
        "How long does an OrbitNote battery last?",
        "OrbitNote battery lasts up to 14 days on a charge.",
        (_CONTEXT["orbitnote-battery"],),
    ),
    GoldenExample(
        "charge-time",
        "How long does it take to charge an OrbitNote from empty?",
        "Charging from empty takes about two hours with the included USB-C cable.",
        (_CONTEXT["orbitnote-battery"],),
    ),
    GoldenExample(
        "pro-storage",
        "How much storage does OrbitNote Pro include?",
        "The OrbitNote Pro includes 64 GB of storage.",
        (_CONTEXT["orbitnote-models"],),
    ),
    GoldenExample(
        "standard-storage",
        "How much storage does the standard OrbitNote include?",
        "The standard OrbitNote includes 16 GB of storage.",
        (_CONTEXT["orbitnote-models"],),
    ),
    GoldenExample(
        "vault-region",
        "Which region hosts Orbit Vault?",
        "Orbit Vault is hosted in the fictional Northstar region.",
        (_CONTEXT["orbit-vault-security"],),
    ),
    GoldenExample(
        "vault-encryption",
        "How are customer documents encrypted?",
        "Customer documents are encrypted in transit and at rest.",
        (_CONTEXT["orbit-vault-security"],),
    ),
    GoldenExample(
        "support-hours",
        "When does Acme Orbit support answer email requests?",
        "Support answers email requests Monday through Friday, 09:00 to 17:00 Northstar Time.",
        (_CONTEXT["support-hours"],),
    ),
    GoldenExample(
        "return-window",
        "What is the return window for a new OrbitNote?",
        "A new OrbitNote has a 30-day return window.",
        (_CONTEXT["returns"],),
    ),
    GoldenExample(
        "return-reset",
        "What must customers do before returning a device?",
        "Devices must be reset before they are returned.",
        (_CONTEXT["returns"],),
    ),
    GoldenExample(
        "team-price",
        "What is the Team plan price and what does it include?",
        "The Team plan costs $18 per active user each month and includes shared folders.",
        (_CONTEXT["pricing"],),
    ),
    GoldenExample(
        "export-formats",
        "Which file formats can OrbitNote export?",
        "OrbitNote exports pages as PDF, PNG, or plain text.",
        (_CONTEXT["exports"],),
    ),
)

assert len(GOLDEN_DATASET) == 15
