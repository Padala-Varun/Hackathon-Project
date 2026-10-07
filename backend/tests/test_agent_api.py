from app.schemas import RecommendRequest

SCENARIO = "Software upgrade on packet core gateway CMG-12 using MOP-UPG-04"


def mtu_bfd_ids(kb):
    return {r.id for r in kb.records.values() if "MTU" in r.root_cause and "BFD" in r.root_cause}


def test_required_endpoints_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/ingest", "/match", "/recommend", "/feedback", "/tickets", "/nodes/{node}/history", "/mock/webhook"]:
        assert p in paths


def test_ingest_counts(kb):
    s = kb.stats()
    assert s["records"] >= 90 and s["mops"] == 6 and s["logs"] == 4 and s["chunks"] > 300
    assert len(kb.tests) == 22


def test_match_returns_ranked_matches_with_confidence(client):
    r = client.post("/match", json={"text": "eBGP to transit drops with hold time expired after router patch"}).json()
    assert r["matches"] and 0 <= r["matches"][0]["confidence"] <= 100
    assert r["matches"][0]["reasons"] and r["matches"][0]["evidence"]


def test_pre_change_asks_for_missing_release(agent):
    rec = agent.run_sync(RecommendRequest(mode="pre_change", text=SCENARIO, use_llm=False, notify=False))
    assert rec.status == "needs_clarification" and rec.clarification.field == "release"
    assert "24.3" in rec.clarification.options


def test_pre_change_sample_scenario_cites_mtu_bfd_records(agent, kb):
    rec = agent.run_sync(RecommendRequest(mode="pre_change", text=SCENARIO, release="24.3", use_llm=False, notify=False))
    assert rec.status == "ok" and rec.risk.level == "High"
    cited = {c for i in rec.items + rec.prechecks + [w for s in rec.mop_steps for w in s.warnings] for c in i.citations}
    assert mtu_bfd_ids(kb) <= cited  # both MTU/BFD past LNIs are cited
    step7 = next(s for s in rec.mop_steps if s.no == 7)
    assert {c for w in step7.warnings for c in w.citations} & mtu_bfd_ids(kb)
    retrieved = {i for m in rec.matches for i in m.all_ids} | {c for s in rec.mop_steps for w in s.warnings for c in w.citations}
    assert cited <= retrieved  # every claim traces back to a retrieved record
    assert [e.type for e in rec.trace][:3] == ["fingerprint", "plan", "tool_call"]


def test_out_of_scope_is_refused(agent):
    rec = agent.run_sync(RecommendRequest(mode="incident", text="Office printer does not print double-sided",
                                          skip_clarification=True, use_llm=False))
    assert rec.status == "no_match" and rec.summary.startswith("No verified match found")
    assert not rec.items
    assert any(e.type == "requery" for e in rec.trace)


def test_llm_output_is_citation_checked(agent, kb, monkeypatch):
    good = sorted(mtu_bfd_ids(kb))[0]

    class FakeLLM:
        def available(self):
            return True

        def stream(self, messages):
            yield f"- MTU and BFD timers reverted to defaults after the upgrade [{good}]\n"
            yield "- Reboot the router twice to be safe\n"
            yield "- Seen before in [LNI-9999]\n"

    monkeypatch.setattr(agent, "llm", FakeLLM())
    rec = agent.run_sync(RecommendRequest(mode="pre_change", text=SCENARIO, release="24.3", notify=False))
    assert rec.llm_used and rec.summary == f"- MTU and BFD timers reverted to defaults after the upgrade [{good}]"
    assert len(rec.dropped_claims) == 2


def test_agent_cannot_call_side_effect_tools(agent):
    import pytest

    with pytest.raises(PermissionError):
        agent.tools.call("write_learning", feedback={})


def test_feedback_writes_back_and_is_searchable(client, kb):
    before = kb.stats()["learnings"]
    r = client.post("/feedback", json={
        "incident_text": "CMG-12 GTP-U throughput collapsed after 24.7 activation; uplink MTU back to 1500",
        "verified_by": "eng-test", "matched_ids": [sorted(mtu_bfd_ids(kb))[0]],
        "verified_root_cause": "Release 24.7 reset uplink MTU to 1500", "verified_fix": "Re-applied MTU 9000",
        "learning": "Check MTU after each CMG upgrade", "ticket_id": "INC-5002"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["record"]["source"] == "learning" and body["ticket"]["status"] == "Resolved"
    assert kb.stats()["learnings"] == before + 1
    found = client.post("/match", json={"text": "GTP-U throughput collapsed after activation, uplink MTU 1500"}).json()
    assert body["record"]["id"] in [m["record_id"] for m in found["matches"]]


def test_feedback_requires_a_human(client):
    r = client.post("/feedback", json={"incident_text": "x", "verified_by": " ", "verified_fix": "y"})
    assert r.status_code == 422


def test_stream_emits_sse_events(client):
    with client.stream("POST", "/recommend/stream", json={"mode": "incident", "text": "pods CrashLoopBackOff after "
                       "image upgrade, missing configmap key", "use_llm": False}) as r:
        body = "".join(r.iter_text())
    assert "event: plan" in body and "event: final" in body


def test_trends_find_recurring_problems(client):
    t = client.get("/trends").json()
    assert t["problem_records"] > 50 and "CMG" in t["by_node_type"]
    assert all(c["count"] >= 2 for c in t["recurring"])
