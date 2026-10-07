"""Shared telecom vocabulary: node-type keywords, error/command patterns and query-expansion synonyms."""
import re

# Longest phrases first when matching. Values are canonical node types used in the dataset.
NODE_TYPE_KEYWORDS: dict[str, list[str]] = {
    "CMG": ["packet core gateway", "cloud mobile gateway", "packet gateway", "user plane", "pgw", "sgw", "upf", "cmg"],
    "CMM": ["mobility manager", "cloud mobility manager", "mme", "amf", "cmm"],
    "Edge Router": ["edge router", "pe router", "transit router"],
    "Core Router": ["core router", "p router", "junos"],
    "OCP Cluster": ["openshift", "ocp", "kubernetes", "worker node", "oc adm"],
    "SBC": ["session border controller", "sbc", "sip trunk", "interconnect"],
    "Firewall": ["firewall", "fw policy", "rule cleanup"],
    "HSS": ["hss", "udm", "subscriber database"],
    "SEG": ["security gateway", "secgw", "ipsec gateway"],
    "LB": ["load balancer", "pool member", "f5"],
    "eNodeB": ["enodeb", "gnodeb", "new site", "cell"],
    "NetAct": ["netact", "oss", "pm counters"],
}

# Node-name prefixes -> node type (used when a record has a node but no node type).
NODE_PREFIX_TYPES: dict[str, str] = {
    "CMG": "CMG", "CMM": "CMM", "ER": "Edge Router", "PE": "Edge Router", "CR": "Core Router",
    "OCP": "OCP Cluster", "SBC": "SBC", "FW": "Firewall", "HSS": "HSS", "SEG": "SEG", "LB": "LB",
    "ENB": "eNodeB", "GNB": "eNodeB", "NETACT": "NetAct",
}

CHANGE_TYPE_KEYWORDS: dict[str, list[str]] = {
    "upgrade": ["upgrade", "release activation", "software update", "sw update", "new release"],
    "patch": ["patch", "smu", "hotfix"],
    "firmware": ["firmware"],
    "migration": ["migration", "migrate", "lift-and-shift"],
    "replacement": ["replacement", "replace", "swap"],
    "certificate": ["certificate", "cert renewal", "tls cert"],
    "firewall change": ["firewall", "policy change", "rule"],
    "failover": ["failover", "switchover"],
    "reload": ["reload", "reboot", "restart"],
    "configuration change": ["config change", "configuration change", "reconfigur"],
    "integration": ["integration", "commissioning"],
}
RELEASE_CHANGES = {"upgrade", "patch", "firmware"}

# Query expansion for the agent's re-query step (term -> extra words).
SYNONYMS: dict[str, list[str]] = {
    "flap": ["up/down", "bouncing", "unstable", "dropping", "adjchange"],
    "bouncing": ["flapping", "up/down"],
    "mtu": ["jumbo frames", "fragmentation", "packet too big"],
    "bfd": ["bidirectional forwarding detection", "bfd session down", "detect time"],
    "upgrade": ["software update", "release activation", "firmware", "patch"],
    "patch": ["smu", "upgrade"],
    "timer": ["keepalive", "hold time", "interval", "defaults"],
    "alarm": ["alarms", "fault", "netact"],
    "certificate": ["cert", "tls", "ssl", "chain"],
    "drain": ["evict", "cordon", "disruption budget"],
    "disk": ["space", "enospc", "partition", "/var/log"],
    "license": ["capacity", "limit"],
    "dns": ["resolver", "fqdn", "nxdomain"],
    "clock": ["ntp", "time sync", "drift", "timestamp"],
    "charging": ["gy", "ocs", "credit control", "ccr", "quota"],
    "s1": ["sctp", "36412", "enodeb"],
    "voice": ["volte", "jitter", "mos", "qos"],
    "ipsec": ["ike", "rekey", "tunnel"],
    "vlan": ["dot1q", "tag"],
    "503": ["pool members down", "health check", "monitor"],
    "revert": ["reset to default", "defaults", "factory default", "overwritten"],
    "default": ["reverted", "reset", "factory"],
    "reachability": ["unreachable", "static route", "oam"],
}

GENERAL_PRECHECKS = [
    "Take and verify an off-box configuration backup.",
    "Capture a pre-check snapshot (interfaces, MTU, routing/BFD timers, sessions, alarms) to compare after the change.",
    "Agree rollback criteria and confirm the maintenance window with the NOC.",
]

ERROR_PATTERNS = [
    re.compile(r"%[A-Z0-9_]+-\d-[A-Z0-9_]+"),  # syslog mnemonics: %BGP-5-ADJCHANGE
    re.compile(r"\b(?:ALM|ERR|ERROR)-[A-Z0-9-]{3,}\b"),
    re.compile(r"\bDIAMETER_[A-Z_]+\b"),
    re.compile(r"\b(?:HTTP\s)?5\d\d\b(?=\s|$|[;,.])"),
    re.compile(r"\bcause\s*#\d+\b", re.I),
]
ERROR_PHRASES = [
    "hold time expired", "detect time expired", "no space left on device", "enospc", "crashloopbackoff",
    "nxdomain", "unknown_ca", "unknown ca", "certificate verify failed", "no_proposal_chosen", "packet too big",
    "fragmentation needed", "disruption budget", "permission denied", "authentication failure", "license limit",
    "connection lost", "session down", "path failure", "timeout", "unreachable", "stale alarm",
]
COMMAND_PREFIXES = (
    "show ", "display ", "oc ", "kubectl ", "ping ", "traceroute ", "ps ", "pgrep ", "systemctl ", "grep ",
    "cat ", "clear ", "openssl ", "df ", "du ", "nslookup ", "dig ", "snmpget ", "snmpwalk ", "chronyc ", "curl ",
)
