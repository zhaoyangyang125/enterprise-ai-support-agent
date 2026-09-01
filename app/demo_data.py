from app.schemas.rag import IndexedChunk


DEMO_DOCUMENT_CHUNKS = [
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
