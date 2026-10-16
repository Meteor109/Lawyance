from __future__ import annotations

import json
import gzip
import hashlib
from pathlib import Path
import pytest
from RAG.common_law import singapore

from RAG.common_law.singapore import (
    ensure_singapore_law_database_ready,
    exact_search,
    fuzzy_search,
    link_search,
    reset_engine,
    semantic_search,
)


TITLE = "Central Provident Fund (Amendment) Act 2026"


@pytest.fixture(autouse=True)
def isolated_seed(monkeypatch, tmp_path):
    monkeypatch.setattr(singapore, "DATA_PATH", Path("RAG/common_law/data/SG/official_seed.json"))
    monkeypatch.setattr(singapore, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(singapore, "DB_PATH", tmp_path / "cache/singapore_law.db")
    monkeypatch.setattr(singapore, "MANIFEST_PATH", tmp_path / "cache/singapore_manifest.json")
    reset_engine()
    yield
    reset_engine()


def decode(value: str) -> dict:
    assert isinstance(value, str)
    return json.loads(value)


def test_seed_contract_and_provenance() -> None:
    seed_path = Path("RAG/common_law/data/SG/official_seed.json")
    records = json.loads(seed_path.read_text(encoding="utf-8"))
    assert len(records) == 10
    assert len({item["rule_id"] for item in records}) == 10
    for item in records:
        for key in ("law_name", "article_number", "content", "url"):
            assert item[key]
        assert item["language"] == "en"
        assert item["country"] == "SG"
        assert item["jurisdiction"] == "Singapore"
        assert item["legal_system"] == "common"
        assert item["status"] == "unknown"
        assert len(item["source_sha256"]) == 64
        assert len(item["source_text_sha256"]) == 64
        assert item["translation_notice"]


def test_readiness_is_deterministic() -> None:
    first = ensure_singapore_law_database_ready(force_rebuild=True)
    second = ensure_singapore_law_database_ready()
    assert first["mode"] == "full"
    assert second["mode"] == "unchanged"
    assert first["content_sha256"] == second["content_sha256"]
    assert first["schema_version"] == "1.1.0"
    assert first["record_count"] == 10


def test_exact_search_normalizes_section_notation() -> None:
    reset_engine()
    result = decode(exact_search(TITLE, "第1条"))
    assert result["success"] is True
    assert result["data"]["rule_id"] == "SG-EGAZETTE-2026-ACT14-SEC1"
    assert result["data"]["url"].startswith("https://assets.egazette.gov.sg/")


def test_exact_search_miss_uses_exact_envelope() -> None:
    result = decode(exact_search(TITLE, "section 999"))
    assert result["success"] is False
    assert result["data"] is None
    assert isinstance(result["search_time"], float)


def test_fuzzy_and_semantic_envelopes() -> None:
    fuzzy = decode(fuzzy_search("中央公积金 投资", limit=200))
    assert fuzzy["success"] is True
    assert 1 <= fuzzy["returned_count"] <= 20
    assert fuzzy["total_count"] >= fuzzy["returned_count"]
    assert any(item["law_name"] == TITLE for item in fuzzy["data"])

    semantic = decode(semantic_search("energy conservation", limit=2))
    assert semantic["success"] is True
    assert semantic["returned_count"] <= 2


def test_link_search_returns_compatible_references_and_data() -> None:
    result = decode(link_search(f"Use {TITLE}, s. 2"))
    assert result["success"] is True
    assert result["text"]
    assert len(result["references"]) == 1
    assert len(result["data"]) == 1
    reference = result["references"][0]
    assert set(("title", "article_number", "url", "content")) <= set(reference)
    assert reference["article_number"] == "section 2"
    assert result["data"][0]["rule_id"] == "SG-EGAZETTE-2026-ACT14-SEC2"


def test_gzip_shards_stream_and_invalidate_cache(monkeypatch, tmp_path):
    seed = json.loads(singapore.DATA_PATH.read_text(encoding="utf-8"))
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for number, record in enumerate(seed[:2], 1):
        with gzip.open(corpus / f"part-{number:03d}.jsonl.gz", "wt", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
    monkeypatch.setattr(singapore, "DATA_PATH", corpus)
    first = ensure_singapore_law_database_ready()
    assert first["record_count"] == 2
    assert ensure_singapore_law_database_ready()["mode"] == "unchanged"
    with gzip.open(corpus / "part-003.jsonl.gz", "wt", encoding="utf-8") as stream:
        stream.write(json.dumps(seed[2]) + "\n")
    changed = ensure_singapore_law_database_ready()
    assert changed["mode"] == "full"
    assert changed["record_count"] == 3
    assert changed["content_sha256"] != first["content_sha256"]


def test_plain_jsonl_and_invalid_shard(monkeypatch, tmp_path):
    record = json.loads(singapore.DATA_PATH.read_text(encoding="utf-8"))[0]
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps(record) + "\n\n", encoding="utf-8")
    monkeypatch.setattr(singapore, "DATA_PATH", source)
    assert ensure_singapore_law_database_ready()["record_count"] == 1
    source.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        ensure_singapore_law_database_ready()


def test_delivery_manifest_rejects_missing_or_changed_shards(monkeypatch, tmp_path):
    record = json.loads(singapore.DATA_PATH.read_text(encoding="utf-8"))[0]
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    shard = corpus / "part-001.jsonl.gz"
    with gzip.open(shard, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")
    manifest = {"record_count": 1, "shards": [{"file": shard.name, "sha256": hashlib.sha256(shard.read_bytes()).hexdigest()}]}
    (corpus / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(singapore, "DATA_PATH", corpus)
    assert ensure_singapore_law_database_ready()["record_count"] == 1
    shard.write_bytes(shard.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        ensure_singapore_law_database_ready()
    shard.rename(corpus / "part-002.jsonl.gz")
    with pytest.raises(ValueError, match="shard list"):
        ensure_singapore_law_database_ready()
