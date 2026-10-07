from pathlib import Path

from app.agent.fingerprint import Fingerprinter
from app.agent.guardrails import id_pattern, verify_citations
from app.ingest.chunker import record_chunks
from app.ingest.structure import FieldMapper, parse_mop, to_record
from app.rag.tokenizer import tokenize

FIELD_MAP = Path(__file__).resolve().parents[1] / "field_map.yaml"


def test_tokenizer_keeps_telecom_identifiers():
    toks = tokenize("BGP flapping on CMG-12 after MOP-UPG-04 step 7, release 7.11.1: %BGP-5-ADJCHANGE")
    for t in ["cmg-12", "mop-upg-04", "7.11.1", "%bgp-5-adjchange", "flap", "bgp"]:
        assert t in toks
    assert "on" not in toks and "after" not in toks


def test_fingerprint_extracts_node_mop_release():
    fp = Fingerprinter().extract("Software upgrade on packet core gateway CMG-12 using MOP-UPG-04 to release 24.3")
    assert fp.nodes == ["CMG-12"]  # UPG-04 inside the MOP id is not a node
    assert fp.mop_ids == ["MOP-UPG-04"]
    assert "24.3" in fp.releases
    assert "CMG" in fp.node_types
    assert "upgrade" in fp.change_types


def test_fingerprint_errors_and_commands():
    fp = Fingerprinter().extract("%BGP-5-ADJCHANGE neighbor down, hold time expired\nshow bgp summary")
    assert "%BGP-5-ADJCHANGE" in fp.error_signatures
    assert "hold time expired" in fp.error_signatures
    assert "show bgp summary" in fp.commands


def test_field_mapper_handles_unknown_column_names():
    rec = to_record({"Ticket ID": "CHG-77", "Summary": "Peering down", "RCA": "MTU mismatch",
                     "Technical Solution Provided": "Set MTU 9216", "Node Name": "er-21", "Customer Region": "North"},
                    FieldMapper(FIELD_MAP), 1)
    assert rec.id == "CHG-77" and rec.title == "Peering down"
    assert rec.root_cause == "MTU mismatch" and rec.resolution == "Set MTU 9216"
    assert rec.node == "ER-21" and rec.node_type == "Edge Router"
    assert rec.extra == {"Customer Region": "North"}


def test_parse_mop_steps():
    mop = parse_mop("x.md", "# MOP-UPG-04: CMG upgrade\nNode type: CMG\n\n1. Backup config.\n2) Check MTU\n   and BFD timers.\n")
    assert mop.mop_id == "MOP-UPG-04" and mop.node_type == "CMG"
    assert [s.no for s in mop.steps] == [1, 2]
    assert mop.steps[1].text == "Check MTU and BFD timers."


def test_chunk_by_field_skips_empty_fields():
    rec = to_record({"id": "LNI-1", "title": "t", "symptoms": "s", "root_cause": "rc"}, FieldMapper(FIELD_MAP), 1)
    fields = {c.field for c in record_chunks(rec)}
    assert fields == {"symptom", "root_cause"}  # no description/MOP -> no "change" chunk


def test_citation_validator():
    allowed = {"LNI-1001", "LNI-1002", "MOP-UPG-04"}
    text = ("- MTU reverted after upgrade [LNI-1001]\n- Unsupported claim\n- Invented record [LNI-9999]\n"
            "- Mixed [LNI-1002, LNI-4242]\n- Follow MOP-UPG-04 step 8\n")
    kept, dropped = verify_citations(text, allowed, id_pattern(["LNI-1001"]))
    assert kept == ["- MTU reverted after upgrade [LNI-1001]", "- Follow MOP-UPG-04 step 8"]
    assert len(dropped) == 3


def test_customer_and_personal_fields_are_never_ingested():
    rec = to_record({"Summary": "Package verify failed", "Customers": "SOME OPERATOR LTD", "Case ID": "05960701",
                     "Reporter": "Jane Doe", "Description": "Contact jane.doe@example.com for logs", "RCA Category": "Upgrade"},
                    FieldMapper(FIELD_MAP), 1)
    dumped = rec.model_dump_json()
    assert "SOME OPERATOR" not in dumped and "05960701" not in dumped and "Jane Doe" not in dumped
    assert "jane.doe@example.com" not in dumped and "[email]" in rec.description
    assert rec.extra == {"RCA Category": "Upgrade"}
