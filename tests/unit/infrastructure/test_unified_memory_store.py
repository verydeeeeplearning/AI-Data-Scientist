"""UnifiedMemoryStore tests — TDD RED phase.

Tests SQLite + FTS5 based memory: store, search, type filtering,
confidence decay, duplicate detection, and CRUD operations.
"""

import time

from ds_agent.domain.entities.memory import MemoryEntry, MemoryType

# ---------------------------------------------------------------------------
# Domain entity tests
# ---------------------------------------------------------------------------


class TestMemoryEntry:
    def test_default_id_generated(self):
        e = MemoryEntry(key="test", content="hello")
        assert len(e.id) == 12

    def test_effective_confidence_no_decay(self):
        e = MemoryEntry(confidence=1.0, updated_at=time.time())
        assert e.effective_confidence > 0.99

    def test_effective_confidence_with_decay(self):
        six_months_ago = time.time() - (6 * 30 * 24 * 3600)
        e = MemoryEntry(confidence=1.0, updated_at=six_months_ago)
        expected = 1.0 * (0.95**6)
        assert abs(e.effective_confidence - expected) < 0.01

    def test_is_stale(self):
        # 24 months ago — confidence should be very low
        old_time = time.time() - (24 * 30 * 24 * 3600)
        e = MemoryEntry(confidence=1.0, updated_at=old_time)
        assert e.is_stale is True

    def test_not_stale_recent(self):
        e = MemoryEntry(confidence=1.0, updated_at=time.time())
        assert e.is_stale is False

    def test_memory_type_values(self):
        assert MemoryType.SESSION == "session"
        assert MemoryType.PROJECT == "project"
        assert MemoryType.DOMAIN == "domain"
        assert MemoryType.GLOBAL == "global"


# ---------------------------------------------------------------------------
# UnifiedMemoryStore tests
# ---------------------------------------------------------------------------


class TestUnifiedMemoryStoreBasic:
    """Test 0-3.1: Store and retrieve memory entries."""

    def test_store_and_get(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test_memory.db"))
        entry = MemoryEntry(
            type=MemoryType.DOMAIN,
            key="churn_definition",
            content="Customer churn is defined as no purchase in 90 days",
            tags=["churn", "definition"],
        )
        entry_id = store.store(entry)
        assert entry_id == entry.id

        retrieved = store.get(entry_id)
        assert retrieved is not None
        assert retrieved.key == "churn_definition"
        assert retrieved.content == "Customer churn is defined as no purchase in 90 days"
        assert retrieved.type == MemoryType.DOMAIN

    def test_store_returns_id(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        entry = MemoryEntry(key="test", content="test content")
        entry_id = store.store(entry)
        assert isinstance(entry_id, str)
        assert len(entry_id) > 0


class TestUnifiedMemoryStoreSearch:
    """Test 0-3.2 + 0-3.6: Keyword and FTS5 full-text search."""

    def test_keyword_search(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        store.store(MemoryEntry(key="churn_def", content="Churn is 90 day inactivity"))
        store.store(MemoryEntry(key="revenue", content="Revenue = price * quantity"))
        store.store(MemoryEntry(key="ltv", content="LTV prediction model"))

        results = store.search("churn")
        assert len(results) >= 1
        assert any("churn" in r.content.lower() or "churn" in r.key.lower() for r in results)

    def test_search_returns_relevant(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        store.store(MemoryEntry(key="a", content="Machine learning classification"))
        store.store(MemoryEntry(key="b", content="Regression analysis for pricing"))

        results = store.search("classification")
        assert len(results) >= 1
        assert results[0].key == "a"

    def test_search_empty_query_returns_all(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        store.store(MemoryEntry(key="a", content="First"))
        store.store(MemoryEntry(key="b", content="Second"))

        results = store.search("*")
        assert len(results) >= 2

    def test_search_no_results(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        store.store(MemoryEntry(key="a", content="Python programming"))

        results = store.search("quantum_computing_xyz")
        assert len(results) == 0


class TestUnifiedMemoryStoreTypeFilter:
    """Test 0-3.3: Type-based filtering."""

    def test_filter_by_type(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        store.store(MemoryEntry(type=MemoryType.SESSION, key="s1", content="Session data"))
        store.store(MemoryEntry(type=MemoryType.PROJECT, key="p1", content="Project data"))
        store.store(MemoryEntry(type=MemoryType.DOMAIN, key="d1", content="Domain data"))
        store.store(MemoryEntry(type=MemoryType.GLOBAL, key="g1", content="Global data"))

        session_results = store.search("data", memory_type=MemoryType.SESSION)
        assert all(r.type == MemoryType.SESSION for r in session_results)

        domain_results = store.search("data", memory_type=MemoryType.DOMAIN)
        assert all(r.type == MemoryType.DOMAIN for r in domain_results)

    def test_list_by_type(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        store.store(MemoryEntry(type=MemoryType.DOMAIN, key="d1", content="Domain 1"))
        store.store(MemoryEntry(type=MemoryType.DOMAIN, key="d2", content="Domain 2"))
        store.store(MemoryEntry(type=MemoryType.PROJECT, key="p1", content="Project 1"))

        domain_entries = store.list_by_type(MemoryType.DOMAIN)
        assert len(domain_entries) == 2
        assert all(e.type == MemoryType.DOMAIN for e in domain_entries)


class TestUnifiedMemoryStoreConfidenceDecay:
    """Test 0-3.4: Confidence decay applied during search."""

    def test_old_entries_have_lower_confidence(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))

        # Recent entry
        recent = MemoryEntry(key="recent", content="Recent knowledge about data")
        store.store(recent)

        # Old entry (6 months ago)
        old = MemoryEntry(
            key="old",
            content="Old knowledge about data",
            updated_at=time.time() - (6 * 30 * 24 * 3600),
            created_at=time.time() - (6 * 30 * 24 * 3600),
        )
        store.store(old)

        results = store.search("knowledge")
        if len(results) >= 2:
            # Recent should have higher effective confidence
            recent_r = next((r for r in results if r.key == "recent"), None)
            old_r = next((r for r in results if r.key == "old"), None)
            if recent_r and old_r:
                assert recent_r.effective_confidence > old_r.effective_confidence


class TestUnifiedMemoryStoreDuplicateDetection:
    """Test 0-3.5: Duplicate key+type upserts instead of creating new."""

    def test_upsert_on_same_key_and_type(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))

        # First store
        store.store(MemoryEntry(type=MemoryType.DOMAIN, key="churn_def", content="Old definition"))

        # Store again with same key+type — should update, not duplicate
        store.store(
            MemoryEntry(type=MemoryType.DOMAIN, key="churn_def", content="Updated definition")
        )

        results = store.list_by_type(MemoryType.DOMAIN)
        churn_entries = [r for r in results if r.key == "churn_def"]
        assert len(churn_entries) == 1
        assert churn_entries[0].content == "Updated definition"


class TestUnifiedMemoryStoreCRUD:
    """Test 0-3.7: Update and delete operations."""

    def test_update_content(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        entry = MemoryEntry(key="test", content="original")
        entry_id = store.store(entry)

        updated = store.update(entry_id, content="modified")
        assert updated is True

        retrieved = store.get(entry_id)
        assert retrieved is not None
        assert retrieved.content == "modified"

    def test_update_tags(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        entry = MemoryEntry(key="test", content="content", tags=["old"])
        entry_id = store.store(entry)

        store.update(entry_id, tags=["new", "updated"])
        retrieved = store.get(entry_id)
        assert retrieved is not None
        assert "new" in retrieved.tags

    def test_delete(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        entry = MemoryEntry(key="test", content="to delete")
        entry_id = store.store(entry)

        deleted = store.delete(entry_id)
        assert deleted is True

        retrieved = store.get(entry_id)
        assert retrieved is None

    def test_delete_nonexistent(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        assert store.delete("nonexistent") is False

    def test_update_nonexistent(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        assert store.update("nonexistent", content="new") is False

    def test_get_nonexistent(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "test.db"))
        assert store.get("nonexistent") is None


class TestSessionScopedSearch:
    """Session-scoped search for memories stored under MemoryType.SESSION."""

    def _store_sessions(self, tmp_path):
        from ds_agent.memory.unified_store import UnifiedMemoryStore

        store = UnifiedMemoryStore(db_path=str(tmp_path / "sess.db"))
        store.store(
            MemoryEntry(
                type=MemoryType.SESSION,
                key="plan-a",
                content="churn modeling retrospective",
                source_session_id="sess-alpha",
            )
        )
        store.store(
            MemoryEntry(
                type=MemoryType.SESSION,
                key="plan-b",
                content="revenue forecasting retrospective",
                source_session_id="sess-beta",
            )
        )
        store.store(
            MemoryEntry(
                type=MemoryType.PROJECT,
                key="project-note",
                content="churn modeling long-term decision",
            )
        )
        return store

    def test_search_sessions_returns_only_session_type(self, tmp_path):
        store = self._store_sessions(tmp_path)
        results = store.search_sessions(query="churn")
        assert len(results) == 1
        assert results[0].type == MemoryType.SESSION
        assert results[0].source_session_id == "sess-alpha"

    def test_search_sessions_filters_by_session_id(self, tmp_path):
        store = self._store_sessions(tmp_path)
        results = store.search_sessions(query="retrospective", session_id="sess-beta")
        assert len(results) == 1
        assert results[0].source_session_id == "sess-beta"

    def test_search_sessions_lists_all_with_wildcard(self, tmp_path):
        store = self._store_sessions(tmp_path)
        results = store.search_sessions(query="*")
        assert {e.source_session_id for e in results} == {"sess-alpha", "sess-beta"}
