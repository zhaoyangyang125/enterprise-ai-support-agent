"""Reviewed public-only fictional allowlist. Never import private demo documents here."""
from app.schemas.rag import IndexedChunk

PUBLIC_DOCUMENT_CHUNKS = [
    IndexedChunk(
        chunk_id="TRAVEL-POLICY-V1-P3",
        document_id="TRAVEL_POLICY",
        document_version_id="TRAVEL_POLICY-V1",
        content="国内出張の宿泊費上限は1泊10,000円です。",
        source_name="TravelPolicy_v1.pdf",
        page=3,
        section="2.1 国内出張",
    )
]

# Every business row is approved here, including tables that must remain empty.
PUBLIC_DATABASE_ROWS = {
    "users": [{"user_id": "U001"}],
    "leave_balances": [{"balance_id": 1, "user_id": "U001", "remaining_days": 8.0,
                        "updated_at": "2026-01-01 00:00:00.000000"}],
    "documents": [{"document_id": "TRAVEL_POLICY", "title": "架空の国内出張規定"}],
    "document_versions": [{"document_version_id": "TRAVEL_POLICY-V1",
                           "document_id": "TRAVEL_POLICY", "version_label": "v1",
                           "status": "active", "effective_from": None, "effective_to": None}],
    "document_permissions": [{"permission_id": 1, "document_id": "TRAVEL_POLICY",
                              "subject_type": "role", "subject_id": "EMPLOYEE", "action": "read"}],
    "leave_requests": [],
    "pending_leave_actions": [],
}
