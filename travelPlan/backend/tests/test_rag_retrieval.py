from app.tools.rag_tools import POIRetriever


def test_rag_retrieval_matches_preference_tags() -> None:
    retriever = POIRetriever()
    results = retriever.search(["museum", "art"], top_k=6)
    assert results
    assert any(
        "museum" in str(item.get("category", "")).lower()
        or "museum" in [str(tag).lower() for tag in item.get("tags", [])]
        for item in results
    )
