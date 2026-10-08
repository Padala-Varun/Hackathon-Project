"""Official JIRA ticket emails: body parsing, merging, cleaning and field extraction (no real .msg needed)."""
from app.ingest.extract import extract_learning, extract_root_cause
from app.ingest.msg_reader import is_junk, merge_tickets, parse_body, to_row

BODY = (
    "Issue created\n\n"
    "\tSummary:\t SCP disabled after upgrade\t \n"
    "Components:\t CMM-a2\t \n"
    "Created:\t 22.08.2026 12:45 AM\t \n"
    "Reporter:\t Jane Doe (Nokia) <https://jira.example/secure/ViewProfile.jspa?name=jd> \t \n"
    "Customers:\t SOME OPERATOR LTD\t \n"
    "Product Release:\t 26.7\t \n"
    "Technical solution provided:\t Use SFTP instead of legacy SCP.\n"
    "-----BEGIN OPENSSH PRIVATE KEY-----\nabc123\n-----END OPENSSH PRIVATE KEY-----\n"
    "Always make sure to update the transfer scripts before the upgrade.\t \n"
    "Description:\t The SCP command was disabled for security reasons in release 26.7.\n\n"
    "This message was sent by Atlassian Jira\n"
)


def test_parse_body_reads_multiline_fields_and_removes_secrets():
    f = parse_body(BODY)
    assert f["title"] == "SCP disabled after upgrade"
    assert f["product_release"] == "26.7" and f["components"] == "CMM-a2"
    assert "Use SFTP instead of legacy SCP." in f["technical_solution"]
    assert "Always make sure" in f["technical_solution"]
    assert "PRIVATE KEY-----" not in f["technical_solution"] and "[private key removed]" in f["technical_solution"]
    assert "https://" not in f["reporter"]
    assert "Atlassian" not in f["description"]


def test_to_row_structures_and_drops_personal_data():
    t = {"ticket_key": "PACOSDKB-1", **parse_body(BODY), "created": "2026-08-22", "vendor": "Nokia"}
    row = to_row(t)
    assert row["node_type"] == "CMM" and row["Components"] == "CMM-a2"  # product family + original variant
    assert row["outcome"] == "Resolved"
    assert not any(k in row for k in ("reporter", "customers", "case_id", "assignee", "project_manager"))
    assert "SOME OPERATOR" not in str(row) and "Jane Doe" not in str(row)


def test_open_tickets_and_test_tickets():
    open_row = to_row({"ticket_key": "X-2", "title": "IE not supported", "description": "Question", "technical_solution": "Not yet."})
    assert open_row["technical_solution"] == "" and open_row["outcome"].startswith("Open")
    assert is_junk({"title": "Testing email template-please ignore", "description": "", "technical_solution": "Test"})
    assert not is_junk({"title": "Real issue", "description": "A long enough description of a real problem", "technical_solution": "Fix"})


def test_merge_keeps_longest_values_and_first_title():
    merged = merge_tickets([
        {"ticket_key": "A-1", "title": "Clean title", "technical_solution": "short"},
        {"ticket_key": "A-1", "title": "FW: much longer forwarded subject line", "technical_solution": "a much longer fix text"},
    ])
    assert len(merged) == 1 and merged[0]["title"] == "Clean title"
    assert merged[0]["technical_solution"] == "a much longer fix text"


def test_extraction_uses_clear_signals_only():
    assert "was disabled" in extract_root_cause("The SCP command was disabled for security reasons.", "Use SFTP.")
    assert extract_root_cause("Something odd happens sometimes on the node.", "Restarted the pod.") == ""
    sections = "Root Cause:\nThe pod memory limit was configured to 71Gi.\n\nResolution:\nReduced it."
    assert extract_root_cause("", sections).startswith("The pod memory limit was configured to 71Gi")
    assert extract_learning("", "Don't change anything inside spinner.yaml after package generation.").startswith("Don't change")
    assert extract_learning("", "The 5G location changes do not trigger closure of a container.") == ""
