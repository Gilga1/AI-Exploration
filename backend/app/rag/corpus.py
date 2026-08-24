"""Small fixed Acme Orbit corpus used for offline Phase 1 evaluation."""

from app.rag.vectorstore import RagDocument


CORPUS: tuple[RagDocument, ...] = (
    RagDocument(
        "Acme Orbit is a fictional company that sells the OrbitNote, a cloud-connected "
        "notebook for field teams.",
        {"id": "company-overview", "title": "Company overview"},
    ),
    RagDocument(
        "OrbitNote syncs handwritten notes over Wi-Fi and Bluetooth. It stores encrypted "
        "copies in the user's Orbit Vault.",
        {"id": "orbitnote-sync", "title": "OrbitNote sync"},
    ),
    RagDocument(
        "OrbitNote battery lasts up to 14 days on a charge. Charging from empty takes "
        "about two hours with the included USB-C cable.",
        {"id": "orbitnote-battery", "title": "Battery and charging"},
    ),
    RagDocument(
        "The OrbitNote Pro includes 64 GB of storage and a replaceable stylus tip. The "
        "standard OrbitNote includes 16 GB of storage.",
        {"id": "orbitnote-models", "title": "OrbitNote models"},
    ),
    RagDocument(
        "Orbit Vault is hosted in the fictional Northstar region. Customer documents are "
        "encrypted in transit and at rest.",
        {"id": "orbit-vault-security", "title": "Orbit Vault security"},
    ),
    RagDocument(
        "Acme Orbit's support team answers email requests Monday through Friday, 09:00 to "
        "17:00 Northstar Time. The support address is help@acmeorbit.example.",
        {"id": "support-hours", "title": "Support"},
    ),
    RagDocument(
        "A new OrbitNote has a 30-day return window. Devices must be reset before they are "
        "returned.",
        {"id": "returns", "title": "Returns"},
    ),
    RagDocument(
        "The Team plan costs $18 per active user each month and includes shared folders. "
        "The Starter plan costs $9 per active user each month.",
        {"id": "pricing", "title": "Plans and pricing"},
    ),
    RagDocument(
        "OrbitNote exports pages as PDF, PNG, or plain text. It does not export directly "
        "to Microsoft Word files.",
        {"id": "exports", "title": "Export formats"},
    ),
)
