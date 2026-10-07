"""Generate a synthetic LNI dataset shaped like the hackathon brief.

Output (under data/raw/):
  lni/lni_records.json      ~100 LNI records, including reworded duplicates of the same problem
  mops/*.md                 6 Method-of-Procedure documents
  logs/*.log                a few log / command-output snippets
  tests/test_incidents.json 20 new incidents with their known correct past match(es) + 2 out-of-scope

Everything here is invented. Usage:  python -m scripts.make_synthetic [--out ../data/raw]
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 7
START, END = date(2026, 3, 2), date(2026, 9, 28)

NODES = {
    "CMG": ("Nokia", ["CMG-03", "CMG-07", "CMG-09", "CMG-12", "CMG-15"]),
    "CMM": ("Nokia", ["CMM-01", "CMM-04", "CMM-06"]),
    "Edge Router": ("Cisco", ["ER-21", "ER-22", "ER-25", "ER-30"]),
    "Core Router": ("Juniper", ["CR-05", "CR-06"]),
    "OCP Cluster": ("Red Hat", ["OCP-02", "OCP-04", "OCP-05"]),
    "SBC": ("Ribbon", ["SBC-01", "SBC-02"]),
    "Firewall": ("Fortinet", ["FW-11", "FW-12"]),
    "HSS": ("Nokia", ["HSS-02", "HSS-03"]),
    "SEG": ("Nokia", ["SEG-03", "SEG-04"]),
    "LB": ("F5", ["LB-01", "LB-02"]),
    "eNodeB": ("Nokia", ["ENB-4411", "ENB-4415", "ENB-5120"]),
    "NetAct": ("Nokia", ["NETACT-01"]),
}

# Each family = one underlying problem. Variants pick different phrasings -> reworded duplicates.
FAMILIES: list[dict] = [
    {
        "key": "cmg_mtu_bfd", "node_type": "CMG", "nodes": ["CMG-07", "CMG-03"], "count": 2,
        "change_type": "Software upgrade", "mop_id": "MOP-UPG-04", "mop_step": "7", "release": ["24.3", "24.3"],
        "severity": "High", "outcome": ["Rollback", "Service degraded"],
        "title": [
            "{node} SW upgrade to 24.3: throughput drop and BFD flaps after re-enabling sessions",
            "Post-upgrade instability on packet core gateway {node} - BGP peers bouncing, large packets dropped",
        ],
        "description": [
            "Planned upgrade of {node} to release 24.3 following MOP-UPG-04. Upgrade itself completed; issues started at step 7 when sessions were re-enabled.",
            "Release activation on {node} per MOP-UPG-04. After reboot and session re-enable the gateway became unstable and the change was escalated.",
        ],
        "symptoms": [
            "After activating release 24.3 and re-enabling sessions, GTP-U throughput dropped about 40% and BFD sessions to the PE routers went down repeatedly.",
            "Once traffic was restored the BGP neighbours kept going up and down every few minutes and subscribers reported slow data; large packets were being fragmented.",
        ],
        "error_signature": ["%BFD-5-SESSION_DOWN; ICMP fragmentation needed", "BFD state DOWN (detect time expired); GTP-U packet too big"],
        "commands": [
            "show bfd session; show interface ethernet-1/1 detail; show router bgp summary",
            "show interface mtu; show bfd session detail; ping -s 8900 -M do <peer>",
        ],
        "root_cause": [
            "The software upgrade reset interface MTU from 9000 (jumbo) to the vendor default 1500 and BFD timers from 300ms x3 back to the default 1000ms x3; the custom values were not part of the post-upgrade config template.",
            "Upgrade to 24.3 re-applied factory defaults on the uplink interfaces: MTU fell back to 1500 and the BFD transmit/receive interval reverted to default, so peers timed out and jumbo GTP-U packets were fragmented.",
        ],
        "resolution": [
            "Re-applied MTU 9000 on all uplink interfaces and restored BFD interval 300ms multiplier 3, then re-enabled the BGP sessions. Pinned both values in the post-upgrade config template.",
            "Restored jumbo MTU and the custom BFD timers from the pre-upgrade backup, bounced the BFD sessions and confirmed stable BGP for 30 minutes.",
        ],
        "learning": [
            "Verify interface MTU and BFD timers against the pre-check snapshot before re-enabling sessions after a CMG upgrade; upgrades can silently revert them to defaults.",
            "Add MTU and BFD timer checks to the MOP-UPG-04 post-checks and keep both values in the post-upgrade config template.",
        ],
    },
    {
        "key": "cmg_gtp_echo", "node_type": "CMG", "nodes": ["CMG-09", "CMG-15", "CMG-03"], "count": 3,
        "change_type": "Software upgrade", "mop_id": "MOP-UPG-04", "mop_step": "8", "release": ["24.7"],
        "severity": "Medium", "outcome": ["Resolved"],
        "title": [
            "False GTP path failure alarms after {node} upgrade to 24.7",
            "{node}: GTP-C echo timeouts towards peers following release activation",
            "Path management alarms flooding NetAct after gateway SW update on {node}",
        ],
        "description": [
            "Upgrade of {node} to 24.7 using MOP-UPG-04. Post-checks showed a large number of new alarms.",
            "Release 24.7 activated on {node}. NOC raised a ticket for alarm flood during post-checks.",
            "Gateway software update on {node}; alarms appeared right after the reboot step.",
        ],
        "symptoms": [
            "Dozens of 'GTP path failure' alarms raised towards eNodeB peers although traffic was normal.",
            "Echo request timeouts reported for many GTP-C peers right after the new release was activated; KPIs looked fine.",
            "NetAct flooded with path-down alarms from the gateway; no real subscriber impact observed.",
        ],
        "error_signature": ["ALM-GTP-PATH-FAILURE; echo response timeout", "GTP echo timeout (N3 retries exceeded)", "path management alarm: peer unreachable"],
        "commands": ["show gtp path-management; show alarms active", "show gtp peer statistics"],
        "root_cause": [
            "Release 24.7 changed the default GTP echo interval from 60s to 20s with N3=2, which was too aggressive for peers behind a slow transport.",
            "Default GTP path management timers changed in the new release; the old customised echo interval was not migrated.",
            "New SW release introduced stricter GTP echo defaults; peers with high latency missed responses.",
        ],
        "resolution": [
            "Set GTP echo interval back to 60s and N3 requests to 5; alarms cleared within 10 minutes.",
            "Re-applied the customised path-management profile (echo 60s, N3=5) and cleared the stale alarms in NetAct.",
        ],
        "learning": [
            "Compare GTP path-management timers before and after a CMG upgrade; release 24.7 changed the defaults.",
            "Include GTP echo timer settings in the CMG pre-check snapshot.",
        ],
    },
    {
        "key": "cmg_charging_gy", "node_type": "CMG", "nodes": ["CMG-12", "CMG-03", "CMG-07"], "count": 3,
        "change_type": "Charging configuration change", "mop_id": "", "mop_step": "", "release": ["24.3"],
        "severity": "High", "outcome": ["Service degraded", "Resolved", "Service degraded"],
        "title": [
            "Subscribers getting free data after Gy peer change on {node}",
            "{node}: credit-control requests timing out after OCS peer reconfiguration",
            "Revenue leakage on {node}: online charging bypassed following Diameter peer update",
        ],
        "description": [
            "Change to point {node} Gy interface to the new OCS cluster.",
            "OCS migration: Diameter peer configuration updated on {node}.",
            "Reconfiguration of Diameter realm routing for online charging on {node}.",
        ],
        "symptoms": [
            "After changing the OCS Diameter peer, CCR-I requests timed out and the gateway applied failure handling CONTINUE, so data was not charged.",
            "Gy CCR timeouts spiked to 30%; sessions were allowed without quota.",
            "Charging team saw a drop in charged volume after the peer update; Diameter Tx timer expiries on the gateway.",
        ],
        "error_signature": ["DIAMETER_UNABLE_TO_DELIVER (3002); Tx timer expired", "CCR-I timeout; CCFH=CONTINUE", "Diameter peer state OKAY but no CCA received"],
        "commands": ["show diameter peer; show diameter realm-routing", "show charging gy statistics"],
        "root_cause": [
            "The new OCS peer was configured with a wrong Destination-Realm, so requests were routed to an unreachable host and failure handling defaulted to CONTINUE.",
            "Diameter realm routing entry still pointed to the old OCS; the Tx timer expired and CCFH CONTINUE let sessions through uncharged.",
            "Typo in the destination realm during the peer update made credit-control requests undeliverable.",
        ],
        "resolution": [
            "Corrected the Destination-Realm and the realm routing table; CCR/CCA success rate back to 99.9%.",
            "Fixed realm routing and temporarily set CCFH to TERMINATE for new sessions until charging was confirmed.",
        ],
        "learning": [
            "Before changing Diameter/Gy peers, send a test CCR to the new peer and check realm routing; monitor charged volume right after the change.",
            "Verify credit-control success rate for 15 minutes after any charging configuration change.",
        ],
    },
    {
        "key": "cmg_backup_missing", "node_type": "CMG", "nodes": ["CMG-12", "CMG-09"], "count": 2,
        "change_type": "Software upgrade", "mop_id": "MOP-UPG-04", "mop_step": "2", "release": ["24.3", "24.7"],
        "severity": "High", "outcome": ["Outage", "Rollback"],
        "title": [
            "Rollback of {node} upgrade took 4 hours - no exported configuration backup",
            "{node} upgrade fallback delayed: config backup missing on backup server",
        ],
        "description": [
            "Upgrade of {node} failed at activation and rollback was required.",
            "Software upgrade on {node} had to be reverted; restoring the old configuration took far longer than planned.",
        ],
        "symptoms": [
            "Rollback could not restore the running configuration because the export was never copied off the node; config had to be rebuilt by hand.",
            "Fallback to the previous release worked but the custom configuration was lost; the backup file was not on the backup server.",
        ],
        "error_signature": ["file not found: backup/cfg-latest.tgz", "restore failed: no backup available"],
        "commands": ["admin save; file copy cf3:/config.cfg backup-server:", "file dir backup/"],
        "root_cause": [
            "MOP step 2 (export configuration backup) was skipped because the backup server transfer failed silently and nobody checked it.",
            "The configuration backup was saved locally on the node only; the local disk was reformatted during the failed upgrade.",
        ],
        "resolution": [
            "Rebuilt the configuration from the last change records and golden template; service restored after 4 hours.",
            "Recovered config from the peer node and the change history, then reverted the release.",
        ],
        "learning": [
            "Confirm the configuration backup exists on the backup server (checksum) before starting any CMG upgrade.",
            "Never keep the only backup on the node being upgraded; verify the off-box copy as a go/no-go check.",
        ],
    },
    {
        "key": "cmg_drain_overload", "node_type": "CMG", "nodes": ["CMG-15", "CMG-07", "CMG-03"], "count": 3,
        "change_type": "Software upgrade", "mop_id": "MOP-UPG-04", "mop_step": "4", "release": ["24.7"],
        "severity": "High", "outcome": ["Service degraded", "Rollback", "Service degraded"],
        "title": [
            "Mate gateway overloaded while draining {node} for upgrade",
            "Session drops on mate CMG during traffic drain of {node}",
            "{node} upgrade: traffic drain caused CPU overload on the pair gateway",
        ],
        "description": [
            "Traffic drain step of MOP-UPG-04 executed on {node} at 22:00.",
            "Upgrade window for {node}; user-plane traffic moved to the mate gateway before activation.",
            "Drain of {node} started earlier than planned due to window constraints.",
        ],
        "symptoms": [
            "When user-plane traffic was drained to the mate gateway its CPU went above 95% and new PDN sessions were rejected.",
            "During the drain the pair gateway started dropping sessions and attach success fell.",
            "Mate CMG overload alarms and session setup failures during the drain step.",
        ],
        "error_signature": ["ALM-CPU-OVERLOAD; session create rejected", "PDN connectivity reject cause #26 insufficient resources", "overload control active"],
        "commands": ["show system cpu; show session statistics", "show redundancy status"],
        "root_cause": [
            "The drain was executed at 22:00 while traffic was still near busy-hour level; the mate gateway did not have capacity for both loads.",
            "Capacity check of the mate gateway was not done; combined sessions exceeded its licensed and CPU capacity.",
            "Drain started before the traffic dip; mate node already at 60% load.",
        ],
        "resolution": [
            "Stopped the drain, rebalanced traffic back and rescheduled the upgrade after 01:00.",
            "Paused the change, waited for low traffic and drained in two batches.",
        ],
        "learning": [
            "Check mate gateway load and capacity (below 45%) before draining a CMG; drain only after the nightly traffic dip.",
            "Drain user-plane traffic in batches and watch mate CPU between batches.",
        ],
    },
    {
        "key": "netact_stale_alarms", "node_type": "CMM", "nodes": ["CMM-04", "CMM-01", "CMM-06"], "count": 3,
        "change_type": "Software upgrade", "mop_id": "MOP-UPG-02", "mop_step": "7", "release": ["26.7"],
        "severity": "Medium", "outcome": ["Resolved"],
        "title": [
            "Alarms out of sync between {node} (26.7) and NetAct",
            "NetAct showing cleared alarms of {node} as still active",
            "Stale alarm entries for {node} remain in NetAct after upgrade",
        ],
        "description": [
            "After upgrading {node} to 26.7 the alarm lists on the node and in NetAct differ.",
            "Post-upgrade alarm sync check failed for {node}.",
            "NOC reported ghost alarms for {node} in NetAct after the maintenance window.",
        ],
        "symptoms": [
            "NetAct keeps showing alarms that are no longer active on the CMM; they cannot be acknowledged or deleted.",
            "Historical alarms reappear in NetAct after every resync even though the mobility manager cleared them.",
            "Operators see ghost alarms for the CMM in NetAct; alarm lists on node and OSS do not match.",
        ],
        "error_signature": ["stale alarm returned by SNMP get; alarm resync mismatch", "NetAct alarm upload contains cancelled alarms", "SNMP alarm table not refreshed"],
        "commands": ["ps -o pid,stat,cmd -p $(pgrep -f snmpservice.py); kubectl get pods -n alms", "snmpwalk alarm table; check NetAct maintenance mode"],
        "root_cause": [
            "The SNMP agent process on the alarm management pod kept a stale cached alarm table after the upgrade, and NetAct was still in maintenance mode so updates were not processed.",
            "Alarm cache in the snmpagent service was not refreshed after the release activation; resync uploaded historical entries.",
            "NetAct maintenance mode was left enabled after the window and the SNMP agent served outdated alarm entries.",
        ],
        "resolution": [
            "Removed maintenance mode in NetAct, backed up /var/log on the alarm pod, restarted the snmpagent process and waited about 2 minutes; stale alarms disappeared after resync.",
            "Restarted the SNMP agent service on the alarm management pod during a maintenance window and triggered a manual alarm resync from NetAct.",
        ],
        "learning": [
            "After CMM upgrades, remove NetAct maintenance mode and compare node vs NetAct alarm lists before closing the change.",
            "Restarting the snmpagent process clears stale alarms; do it in a maintenance window and back up logs first.",
        ],
    },
    {
        "key": "rtr_bgp_timers", "node_type": "Edge Router", "nodes": ["ER-21", "ER-22", "ER-25"], "count": 3,
        "change_type": "Vendor patch (SMU)", "mop_id": "MOP-RTR-07", "mop_step": "6", "release": ["7.11.1"],
        "severity": "High", "outcome": ["Service degraded", "Resolved", "Service degraded"],
        "title": [
            "BGP session flapping on edge router {node} after vendor patch",
            "{node}: eBGP neighbours dropping every few minutes post patch",
            "Peering instability with transit provider after SMU install on {node}",
        ],
        "description": [
            "Vendor patch installed on {node} to fix a security advisory.",
            "SMU installation on {node} following MOP-RTR-07.",
            "Patch window for {node}; router reloaded as part of the SMU install.",
        ],
        "symptoms": [
            "eBGP sessions to the transit provider flapped every 3-4 minutes after the patch; routes withdrawn and re-advertised.",
            "Neighbours kept resetting with hold timer expired after the SMU was applied.",
            "Customer traffic rerouted repeatedly; BGP adjacency changes logged continuously.",
        ],
        "error_signature": ["%BGP-5-ADJCHANGE: neighbor Down - hold time expired", "%BGP-3-NOTIFICATION: hold time expired", "BGP neighbor reset (hold timer expired)"],
        "commands": ["show bgp neighbor | include hold time; show running-config router bgp", "show bgp summary; show logging | include ADJCHANGE"],
        "root_cause": [
            "The vendor patch reverted the custom BGP keepalive/hold timers (10/30) to defaults (60/180) on our side while the peer kept aggressive timers, causing hold-timer expiry under load.",
            "Custom BGP timers lived only in a config section that the patch overwrote; the defaults came back.",
            "SMU install restarted the BGP process with default timers while the peer expected 10/30.",
        ],
        "resolution": [
            "Re-applied keepalive 10 / hold 30 via automation and soft-reset the sessions; peering stable.",
            "Restored the BGP timer configuration from backup and added it to the golden config enforced by automation.",
        ],
        "learning": [
            "Record BGP timers before patching edge routers and verify them after the reload, before declaring the change complete.",
            "Keep BGP timers in the golden config so automation re-applies them after vendor patches.",
        ],
    },
    {
        "key": "rtr_firmware_mtu", "node_type": "Edge Router", "nodes": ["ER-30", "ER-21", "ER-25"], "count": 3,
        "change_type": "Firmware upgrade", "mop_id": "MOP-RTR-07", "mop_step": "5", "release": ["7.11.1"],
        "severity": "High", "outcome": ["Service degraded", "Resolved", "Rollback"],
        "title": [
            "BGP flapping on edge router {node} after firmware push - MTU mismatch",
            "{node} firmware 7.11 reset interface MTU, peering unstable",
            "Edge router {node} lost jumbo MTU after firmware upgrade",
        ],
        "description": [
            "Firmware upgrade of {node} to 7.11.1 using MOP-RTR-07.",
            "Firmware push to {node}; router reloaded and interfaces came back up.",
            "Planned firmware upgrade on {node} during the night window.",
        ],
        "symptoms": [
            "After the firmware push BGP sessions came up but dropped when full table updates were exchanged; pings with large packets failed.",
            "Sessions stuck or flapping during route exchange; small pings ok, large packets dropped.",
            "Peering flaps and OSPF adjacency stuck in EXSTART after the reload.",
        ],
        "error_signature": ["%BGP-5-ADJCHANGE neighbor Down; MTU mismatch", "OSPF neighbor stuck in EXSTART/EXCHANGE", "fragmentation needed and DF set"],
        "commands": ["show interface | include MTU; ping <peer> size 9000 df-bit", "show ospf neighbor; show bgp summary"],
        "root_cause": [
            "Firmware 7.11 reset interface MTU to the vendor default (1514) while the peer used 9216, so large BGP updates were dropped.",
            "MTU mismatch introduced by the firmware default reset on the edge router.",
            "Firmware reload wiped the interface MTU overrides; MTU on both ends no longer matched.",
        ],
        "resolution": [
            "Pinned MTU 9216 in the post-upgrade config template and re-applied it; sessions stable.",
            "Re-configured the interface MTU to match the peer and cleared the BGP sessions.",
        ],
        "learning": [
            "Verify interface MTU on both ends after any router firmware upgrade before re-enabling peering.",
            "Pin MTU in the post-upgrade template so firmware defaults cannot override it.",
        ],
    },
    {
        "key": "rtr_static_route", "node_type": "Core Router", "nodes": ["CR-05", "CR-06", "CR-05"], "count": 3,
        "change_type": "Planned reload", "mop_id": "MOP-RTR-07", "mop_step": "7", "release": ["23.4R2"],
        "severity": "High", "outcome": ["Outage", "Outage", "Resolved"],
        "title": [
            "OAM network unreachable after core router {node} reload",
            "{node} lost static routes after reboot",
            "Management access lost to sites after {node} restart",
        ],
        "description": [
            "Planned reload of {node} to clear a memory leak.",
            "Router {node} rebooted as part of a line card replacement.",
            "Restart of {node} for software maintenance.",
        ],
        "symptoms": [
            "After the planned reload NetAct lost connectivity to 40 sites; OAM subnets unreachable.",
            "Static routes configured last month disappeared after reboot; management traffic blackholed.",
            "SSH to downstream nodes failed after the router restart; routing table missing static entries.",
        ],
        "error_signature": ["route not found; destination unreachable", "no route to host (OAM subnet)", "NetAct: node connection lost"],
        "commands": ["show route static; show configuration | compare rollback 1", "show route 10.0.0.0/8"],
        "root_cause": [
            "Static routes were added in an earlier change only to the running configuration and never committed/saved, so the reload removed them.",
            "The previous engineer did not save the configuration, so the reboot dropped the unsaved static routes.",
            "Running vs startup configuration drift: unsaved routes were lost on restart.",
        ],
        "resolution": [
            "Re-added the static routes from the change record and saved the configuration; reachability restored.",
            "Restored routes from backup, committed the config and added a running/startup diff check to the MOP.",
        ],
        "learning": [
            "Before any reload, diff running vs startup configuration and save pending changes.",
            "Always save/commit configuration at the end of each change; check config drift before reboots.",
        ],
    },
    {
        "key": "ocp_drain_pdb", "node_type": "OCP Cluster", "nodes": ["OCP-02", "OCP-04", "OCP-05"], "count": 3,
        "change_type": "Node patching", "mop_id": "MOP-OCP-03", "mop_step": "3", "release": ["4.16"],
        "severity": "Medium", "outcome": ["Rollback", "Rollback", "Resolved"],
        "title": [
            "Worker node drain stuck during {node} patching",
            "{node} maintenance overran: drain blocked by PodDisruptionBudget",
            "Cluster patching on {node} exceeded maintenance window - pods could not be evicted",
        ],
        "description": [
            "Monthly OS patching of worker nodes on {node} following MOP-OCP-03.",
            "Patch rollout for {node} worker pool.",
            "Kernel patch on {node}; each worker drained and rebooted in turn.",
        ],
        "symptoms": [
            "oc adm drain hung for 45 minutes on worker-3; eviction kept failing.",
            "Drain command retried evictions endlessly and the patch window was exceeded.",
            "Node stayed SchedulingDisabled with pods not evicted; change rolled back at end of window.",
        ],
        "error_signature": ["Cannot evict pod as it would violate the pod's disruption budget", "error when evicting pods: PodDisruptionBudget", "eviction retry loop: too many requests (429)"],
        "commands": ["oc adm drain worker-3 --ignore-daemonsets --delete-emptydir-data; oc get pdb -A", "oc get pdb -A; oc describe pdb"],
        "root_cause": [
            "An application PodDisruptionBudget had minAvailable equal to its replica count (2/2), so no pod could ever be evicted.",
            "The PDB allowed zero disruptions for the CNF pods, so the drain could not proceed.",
            "PodDisruptionBudget misconfigured (maxUnavailable 0) blocked eviction.",
        ],
        "resolution": [
            "Temporarily scaled the deployment to 3 replicas so the PDB allowed one disruption, then drained and patched the node.",
            "Coordinated with the app team to relax the PDB during the window; the drain completed.",
        ],
        "learning": [
            "Check all PodDisruptionBudgets for zero allowed disruptions before draining OCP nodes.",
            "Run 'oc get pdb -A' as a pre-check and agree a plan with app owners if ALLOWED DISRUPTIONS is 0.",
        ],
    },
    {
        "key": "ocp_configmap_crashloop", "node_type": "OCP Cluster", "nodes": ["OCP-04", "OCP-02", "OCP-05"], "count": 3,
        "change_type": "CNF image upgrade", "mop_id": "", "mop_step": "", "release": ["4.16"],
        "severity": "High", "outcome": ["Service degraded", "Rollback", "Service degraded"],
        "title": [
            "CNF pods in CrashLoopBackOff after image upgrade on {node}",
            "Application pods failing to start after container image update on {node}",
            "Upgrade of CNF on {node} left pods crash looping",
        ],
        "description": [
            "Rolling update of the policy CNF to a new image version on {node}.",
            "Container image bump for the charging CNF on {node}.",
            "CNF minor release deployed via pipeline on {node}.",
        ],
        "symptoms": [
            "New pods failed readiness and restarted continuously; old replicas were already terminated, causing capacity loss.",
            "Pods crash on start with a config error; rollout stuck at 50%.",
            "Rolling update produced CrashLoopBackOff on every new pod.",
        ],
        "error_signature": ["CrashLoopBackOff; KeyError: 'diameter.peer.timeout'", "Back-off restarting failed container", "config validation failed: missing key"],
        "commands": ["oc get pods -n cnf; oc logs <pod> --previous; oc get configmap -o yaml", "oc rollout status deployment/<name>; oc describe pod"],
        "root_cause": [
            "The new image version required a new configmap key that was not added before the rollout.",
            "The configmap was not updated to the new schema expected by the upgraded image.",
            "A mandatory configuration parameter for the new release was missing from the configmap.",
        ],
        "resolution": [
            "Added the missing key to the configmap and restarted the rollout; pods became ready.",
            "Rolled back to the previous image, updated the configmap, then re-ran the upgrade.",
        ],
        "learning": [
            "Diff the configmap against the new release's required parameters before rolling out a new image.",
            "Use maxUnavailable 0 / surge rollouts so capacity is kept if new pods fail.",
        ],
    },
    {
        "key": "sbc_cert_chain", "node_type": "SBC", "nodes": ["SBC-01", "SBC-02", "SBC-01"], "count": 3,
        "change_type": "Certificate renewal", "mop_id": "MOP-CRT-01", "mop_step": "3", "release": ["12.1"],
        "severity": "High", "outcome": ["Outage", "Service degraded", "Outage"],
        "title": [
            "SIP TLS handshake failures after certificate renewal on {node}",
            "{node}: interconnect calls failing after cert update",
            "VoLTE interconnect down after TLS certificate replacement on {node}",
        ],
        "description": [
            "Annual TLS certificate renewal on {node} using MOP-CRT-01.",
            "Replacement of the expiring interconnect certificate on {node}.",
            "Certificate rotation on {node} ahead of expiry.",
        ],
        "symptoms": [
            "After installing the renewed certificate the interconnect partner rejected TLS connections; calls to that partner failed.",
            "SIP over TLS trunks went down right after the certificate swap.",
            "Peer reports 'unknown CA' and drops the TLS session.",
        ],
        "error_signature": ["TLS alert: unknown_ca", "SSL handshake failed: certificate verify failed", "SIP trunk state OOS (TLS)"],
        "commands": ["openssl s_client -connect <peer>:5061 -showcerts", "show tls profile; show sip trunk status"],
        "root_cause": [
            "The new certificate was installed without the intermediate CA certificate, so peers could not build the trust chain.",
            "Incomplete certificate chain uploaded; the intermediate CA was missing.",
            "The renewed certificate was issued by a new intermediate CA that was not included in the bundle.",
        ],
        "resolution": [
            "Uploaded the full chain (leaf + intermediate) and restarted the TLS profile; trunks recovered.",
            "Re-imported the certificate bundle with the intermediate CA and verified with openssl s_client.",
        ],
        "learning": [
            "Validate the full certificate chain with 'openssl s_client -showcerts' against a peer before cut-over.",
            "Always install the leaf and intermediate certificates together during renewal.",
        ],
    },
    {
        "key": "fw_sctp_block", "node_type": "Firewall", "nodes": ["FW-11", "FW-12", "FW-11"], "count": 3,
        "change_type": "Firewall policy change", "mop_id": "MOP-FW-05", "mop_step": "3", "release": ["7.4"],
        "severity": "High", "outcome": ["Outage", "Outage", "Rollback"],
        "title": [
            "eNodeBs lost S1 connection after firewall rule cleanup on {node}",
            "{node} policy change dropped SCTP traffic to CMM",
            "Mass S1 setup failures following firewall change on {node}",
        ],
        "description": [
            "Rule-base cleanup on {node} to remove unused rules.",
            "Firewall policy consolidation on {node} following MOP-FW-05.",
            "Quarterly firewall hygiene change on {node}.",
        ],
        "symptoms": [
            "Hundreds of eNodeBs reported S1 link down; attach failures spiked.",
            "SCTP associations from RAN to the mobility manager dropped right after the policy push.",
            "S1-MME associations failing; RAN alarms 'S1 link failure' across a region.",
        ],
        "error_signature": ["SCTP ABORT; S1 link failure alarm", "S1 SETUP FAILURE; SCTP INIT no response", "deny log: proto 132 dport 36412"],
        "commands": ["diagnose sniffer packet any 'port 36412'; show firewall policy", "show log traffic deny"],
        "root_cause": [
            "Firewall rule cleanup removed the rule permitting SCTP (protocol 132) port 36412; only TCP/UDP were kept.",
            "Rule consolidation treated the SCTP rule as unused because hit counters had been reset, and deleted it.",
            "SCTP was not covered by the new 'any service' object, which only included TCP/UDP.",
        ],
        "resolution": [
            "Restored the SCTP 36412 rule from the policy backup; associations re-established within 5 minutes.",
            "Re-added an explicit SCTP permit and verified S1 associations recovered.",
        ],
        "learning": [
            "Before firewall cleanups, check rules carrying SCTP/Diameter (36412, 3868) and verify associations immediately after the push.",
            "Never rely on hit counters alone to delete rules; confirm with traffic owners.",
        ],
    },
    {
        "key": "cmm_disk_full", "node_type": "CMM", "nodes": ["CMM-01", "CMM-06", "CMM-04"], "count": 3,
        "change_type": "Software upgrade", "mop_id": "MOP-UPG-02", "mop_step": "3", "release": ["26.7"],
        "severity": "Medium", "outcome": ["Rollback", "Rollback", "Resolved"],
        "title": [
            "{node} upgrade aborted: no space left on device",
            "Upgrade of mobility manager {node} failed at image copy step",
            "{node} release activation stopped due to full log partition",
        ],
        "description": [
            "Upgrade of {node} to 26.7 per MOP-UPG-02.",
            "Release upgrade on {node}; image transfer started on schedule.",
            "Planned upgrade window for {node}.",
        ],
        "symptoms": [
            "Package transfer failed midway and the upgrade framework aborted the procedure.",
            "Upgrade precheck passed but image extraction failed with disk errors.",
            "Release activation stopped; node remained on the old release and the window was lost.",
        ],
        "error_signature": ["No space left on device (/var/log)", "write error: ENOSPC", "upgrade aborted: insufficient disk space"],
        "commands": ["df -h /var/log; du -sh /var/log/*", "df -h; find /var/log -size +500M"],
        "root_cause": [
            "The /var/log partition was 97% full due to debug logging left enabled from a previous troubleshooting session.",
            "Old core dumps and debug logs filled the log partition used as the upgrade staging area.",
            "A debug trace left on after a past case filled the disk.",
        ],
        "resolution": [
            "Archived and removed old logs and core files, disabled debug logging and re-ran the upgrade in the next window.",
            "Cleaned /var/log and added a disk-space check to the precheck script.",
        ],
        "learning": [
            "Check free disk space on /var/log (need more than 30% free) before starting a CMM upgrade; disable leftover debug logging.",
            "Add 'df -h' to the upgrade pre-checks and abort early if staging space is low.",
        ],
    },
    {
        "key": "cmm_license", "node_type": "CMM", "nodes": ["CMM-04", "CMM-01", "CMM-06"], "count": 3,
        "change_type": "Hardware migration", "mop_id": "MOP-UPG-02", "mop_step": "8", "release": ["26.7"],
        "severity": "High", "outcome": ["Service degraded", "Service degraded", "Resolved"],
        "title": [
            "Attach rejects at busy hour after {node} migration",
            "Mobility manager {node} capacity capped after hardware migration",
            "Subscribers rejected: license limit reached on new {node}",
        ],
        "description": [
            "Migration of {node} to new hardware.",
            "Hardware refresh of {node}; configuration restored on the new platform.",
            "Lift-and-shift of {node} onto the new cloud infrastructure.",
        ],
        "symptoms": [
            "At 19:00 attach success rate dropped to 80% with rejects although load was normal.",
            "Registered subscribers flat-lined at exactly 500k and new attaches were rejected.",
            "Capacity alarm 'license limit reached' during peak hour.",
        ],
        "error_signature": ["EMM cause #22 congestion; license capacity exceeded", "ALM-LICENSE-LIMIT", "attach reject: capacity license"],
        "commands": ["show license capacity; show subscriber count", "show alarms active | include LICENSE"],
        "root_cause": [
            "The capacity license was not transferred to the new hardware; the node ran with the default trial capacity.",
            "License file bound to the old node ID; the new node fell back to base capacity.",
            "The migration procedure omitted the license re-installation step.",
        ],
        "resolution": [
            "Installed the correct capacity license for the new node ID; rejects stopped immediately.",
            "Obtained a re-hosted license and installed it; verified the capacity counters.",
        ],
        "learning": [
            "After any migration, verify installed license capacity matches the old node before the traffic swing.",
            "Include a license capacity check in the post-migration checklist.",
        ],
    },
    {
        "key": "cmm_dns_diameter", "node_type": "CMM", "nodes": ["CMM-06", "CMM-04", "CMM-01"], "count": 3,
        "change_type": "DNS resolver change", "mop_id": "", "mop_step": "", "release": ["26.7"],
        "severity": "High", "outcome": ["Outage", "Service degraded", "Resolved"],
        "title": [
            "Authentication failures after DNS resolver change on {node}",
            "S6a peers down on {node} following DNS server migration",
            "Diameter peer to HSS not resolving after resolver update on {node}",
        ],
        "description": [
            "Migration of {node} to the new DNS resolver pair.",
            "DNS server change for the core network; {node} reconfigured.",
            "Resolver update on {node} as part of the DNS consolidation project.",
        ],
        "symptoms": [
            "S6a Diameter peers went down; attaches failed with authentication errors.",
            "The mobility manager could not reconnect to the HSS after a planned peer restart.",
            "Subscriber registration failures increasing; Diameter connections closed.",
        ],
        "error_signature": ["Diameter peer DOWN: DNS resolution failed", "NXDOMAIN for hss01.epc.example", "S6a AIR timeout"],
        "commands": ["nslookup hss01.epc.example <new-resolver>; show diameter peers", "dig +short hss01.epc.example"],
        "root_cause": [
            "The new DNS resolvers lacked the internal EPC zone, so the HSS peer FQDN no longer resolved when connections were re-established.",
            "The resolver migration missed the private 3GPP zone, so peer FQDN lookups failed.",
            "The DNS forwarder for the EPC domain was not configured on the new resolvers.",
        ],
        "resolution": [
            "Added the EPC zone forwarder on the new resolvers and restarted the Diameter peers.",
            "Temporarily configured static host entries for the HSS peers, then fixed the DNS zone.",
        ],
        "learning": [
            "Before switching DNS resolvers, resolve every Diameter peer FQDN from the node against the new servers.",
            "Keep a list of critical FQDNs (HSS, PCRF, OCS) and test them as a pre-check.",
        ],
    },
    {
        "key": "ntp_after_replacement", "node_type": "HSS", "nodes": ["HSS-02", "HSS-03", "HSS-02"], "count": 3,
        "change_type": "Hardware replacement", "mop_id": "", "mop_step": "", "release": ["22.1"],
        "severity": "Medium", "outcome": ["Service degraded", "Resolved", "Resolved"],
        "title": [
            "Clock drift on {node} after board replacement",
            "Wrong timestamps after hardware swap on {node}",
            "Time not synchronised on replaced unit of {node}",
        ],
        "description": [
            "Faulty board replaced on {node}.",
            "Hardware swap on {node} after a disk failure.",
            "Field replacement of a blade in {node}.",
        ],
        "symptoms": [
            "Logs and alarms on the replaced unit were 7 minutes behind; authentication vectors were rejected intermittently.",
            "Records from the node carried timestamps in the future and mediation rejected batches.",
            "Certificate validation errors and log correlation issues after the hardware replacement.",
        ],
        "error_signature": ["NTP unsynchronised; stratum 16", "clock offset > 300s", "certificate not yet valid"],
        "commands": ["chronyc tracking; chronyc sources", "timedatectl status"],
        "root_cause": [
            "The replacement hardware came with factory settings; NTP servers were not configured as part of the replacement procedure.",
            "NTP configuration was not restored after the board swap.",
            "The replacement procedure missed the time-sync configuration.",
        ],
        "resolution": [
            "Configured NTP servers and forced a time sync; rejects stopped.",
            "Restored the NTP config from backup and re-sent the affected records to mediation.",
        ],
        "learning": [
            "After any hardware replacement, verify NTP sync status (stratum, offset) before returning the node to service.",
            "Add a time-sync check to replacement procedures.",
        ],
    },
    {
        "key": "snmp_creds_reset", "node_type": "CMG", "nodes": ["CMG-15", "CMG-09", "CMG-03"], "count": 3,
        "change_type": "Software upgrade", "mop_id": "MOP-UPG-04", "mop_step": "9", "release": ["24.7"],
        "severity": "Medium", "outcome": ["Resolved"],
        "title": [
            "{node} shown as unreachable in NetAct after upgrade",
            "NetAct lost management of {node} post SW update",
            "No alarms or PM data from {node} after release activation",
        ],
        "description": [
            "Upgrade of {node} to 24.7 completed; OSS integration check failed.",
            "Release activation on {node}; NOC noticed missing alarms next morning.",
            "Software update of {node}; PM reports empty after the change.",
        ],
        "symptoms": [
            "NetAct reported the node as disconnected; no alarms or PM counters received since the upgrade.",
            "Alarm upload failed and PM files were missing for 6 hours after the change.",
            "OSS showed the node unmanaged; the NOC was blind to node alarms.",
        ],
        "error_signature": ["SNMPv3 authentication failure (usmStatsWrongDigests)", "NetAct: node connection lost", "PM file transfer failed: permission denied"],
        "commands": ["show snmp usm users; show snmp statistics", "snmpget -v3 -u netact <node> sysUpTime.0"],
        "root_cause": [
            "The upgrade reset the SNMPv3 user credentials to defaults, so NetAct authentication failed.",
            "The SNMP USM user was recreated with a default auth key during the upgrade.",
            "Release activation replaced the SNMP config; the OSS credentials were no longer valid.",
        ],
        "resolution": [
            "Re-created the SNMPv3 user with the agreed credentials and re-integrated the node in NetAct.",
            "Restored the SNMP config from backup and triggered a NetAct alarm resync.",
        ],
        "learning": [
            "After upgrades, confirm the node is managed in NetAct (alarms and PM flowing) before closing the change.",
            "Back up SNMP/OSS integration settings before upgrades.",
        ],
    },
    {
        "key": "vrrp_garp", "node_type": "Core Router", "nodes": ["CR-06", "CR-05", "CR-06"], "count": 3,
        "change_type": "Failover test", "mop_id": "", "mop_step": "", "release": ["23.4R2"],
        "severity": "Medium", "outcome": ["Service degraded", "Resolved", "Service degraded"],
        "title": [
            "Traffic blackholed after VRRP failover test on {node}",
            "Hosts unreachable after gateway switchover on {node}",
            "Partial outage after router redundancy failover on {node}",
        ],
        "description": [
            "Planned VRRP failover test on {node}.",
            "Redundancy test: mastership moved from {node} to its pair.",
            "Annual resilience test of the {node} gateway pair.",
        ],
        "symptoms": [
            "After the planned failover some servers lost connectivity for 20 minutes.",
            "Only part of the hosts recovered after mastership moved to the backup router.",
            "Stale gateway MAC on downstream switches; traffic dropped.",
        ],
        "error_signature": ["VRRP state change Master->Backup; ARP entry stale", "gratuitous ARP not received", "MAC move not learned"],
        "commands": ["show vrrp detail; show arp", "clear arp-cache"],
        "root_cause": [
            "The new master did not send gratuitous ARP because 'garp on failover' was disabled; downstream devices kept the old MAC.",
            "Gratuitous ARP was disabled on the VRRP group, so ARP caches stayed stale.",
            "The virtual MAC was not used; failover changed the gateway MAC without GARP.",
        ],
        "resolution": [
            "Cleared ARP on the downstream switches and enabled gratuitous ARP on failover; retest successful.",
            "Enabled VRRP virtual MAC/GARP and repeated the failover test in the next window.",
        ],
        "learning": [
            "Check VRRP gratuitous ARP / virtual MAC settings before failover tests.",
            "Have 'clear arp' commands ready as part of the failover rollback plan.",
        ],
    },
    {
        "key": "qos_not_reapplied", "node_type": "Edge Router", "nodes": ["ER-22", "ER-25", "ER-30"], "count": 3,
        "change_type": "Interface migration", "mop_id": "", "mop_step": "", "release": ["7.11.1"],
        "severity": "Medium", "outcome": ["Service degraded", "Resolved", "Service degraded"],
        "title": [
            "VoLTE voice quality degraded after interface reconfiguration on {node}",
            "Jitter on voice traffic after link migration on {node}",
            "QoS policy missing on new uplink of {node}",
        ],
        "description": [
            "Uplink of {node} moved to a new 100G port.",
            "Link migration on {node} to new line card.",
            "Subinterface re-creation on {node} during port consolidation.",
        ],
        "symptoms": [
            "MOS dropped and VoLTE customers reported choppy audio after the uplink move.",
            "Voice packets queued as best effort; jitter above 60ms at busy hour.",
            "QCI-1 traffic not prioritised on the new interface.",
        ],
        "error_signature": ["service-policy not attached", "EF queue drops (no policy)", "VoLTE MOS < 3.5"],
        "commands": ["show policy-map interface <if>; show running-config interface <if>", "show qos interface"],
        "root_cause": [
            "The service-policy was not re-attached when the subinterface was recreated on the new port.",
            "The QoS policy is bound to the interface, so moving the link removed it.",
            "The interface migration procedure did not include re-applying QoS.",
        ],
        "resolution": [
            "Attached the QoS service-policy to the new interface; jitter normalised.",
            "Re-applied the QoS policy and verified DSCP EF queueing.",
        ],
        "learning": [
            "When moving or recreating interfaces, re-attach QoS policies and verify with 'show policy-map interface'.",
            "Compare interface config (QoS, MTU, ACL) before and after a link migration.",
        ],
    },
    {
        "key": "ipsec_rekey", "node_type": "SEG", "nodes": ["SEG-03", "SEG-04", "SEG-03"], "count": 3,
        "change_type": "Software upgrade", "mop_id": "", "mop_step": "", "release": ["21.8"],
        "severity": "High", "outcome": ["Service degraded", "Service degraded", "Resolved"],
        "title": [
            "IPsec tunnels to eNodeBs dropping every hour after {node} upgrade",
            "Security gateway {node} tunnels flapping at rekey",
            "Periodic RAN backhaul outages after SecGW software update on {node}",
        ],
        "description": [
            "Software upgrade of security gateway {node}.",
            "SecGW {node} updated to the latest maintenance release.",
            "Upgrade of {node} to fix a crypto vulnerability.",
        ],
        "symptoms": [
            "Tunnels went down at each rekey interval (60 min), causing short S1 outages.",
            "Periodic disconnects of sites every hour exactly.",
            "IKE SA renegotiation failures logged regularly.",
        ],
        "error_signature": ["IKEv2 CHILD_SA rekey failed: NO_PROPOSAL_CHOSEN", "IPsec SA lifetime mismatch", "tunnel down: rekey timeout"],
        "commands": ["show crypto ikev2 sa; show crypto ipsec sa", "show crypto profile"],
        "root_cause": [
            "The upgrade changed the default Child SA lifetime and PFS group; eNodeBs proposed the old values so rekey failed.",
            "IKE proposal defaults changed in the new software (PFS group 14 vs 2).",
            "The crypto profile reverted to the new defaults after the upgrade.",
        ],
        "resolution": [
            "Re-configured the crypto profile with the previous lifetime and PFS group; tunnels stable.",
            "Aligned the IKE/IPsec proposals with the RAN configuration.",
        ],
        "learning": [
            "Snapshot IKE/IPsec proposals before SecGW upgrades and compare after.",
            "Watch the first rekey cycle after the change before closing it.",
        ],
    },
    {
        "key": "vlan_mismatch", "node_type": "Edge Router", "nodes": ["ER-30", "ER-25", "ER-22"], "count": 3,
        "change_type": "New transport link", "mop_id": "", "mop_step": "", "release": ["7.11.1"],
        "severity": "Low", "outcome": ["Resolved"],
        "title": [
            "New backhaul link on {node} carrying no traffic after commissioning",
            "VLAN mismatch on new transport link at {node}",
            "Link up but no traffic after transport integration on {node}",
        ],
        "description": [
            "Commissioning of a new backhaul link on {node}.",
            "Transport integration for new site cluster on {node}.",
            "New leased line connected to {node}.",
        ],
        "symptoms": [
            "Interface up/up but no ARP resolution or traffic across the new link.",
            "Pings across the new link fail although the optics are fine.",
            "Site integration delayed: the transport link passes no packets.",
        ],
        "error_signature": ["ARP incomplete", "input packets dropped: unknown VLAN", "no traffic counters increment"],
        "commands": ["show interface <if>.210; show arp", "monitor interface traffic"],
        "root_cause": [
            "The subinterface was configured with VLAN 210 while the transport provider delivered VLAN 201.",
            "VLAN ID typo in the design sheet.",
            "dot1q tag mismatch between the router and the transport provider.",
        ],
        "resolution": [
            "Corrected the dot1q tag to match the provider; traffic flowed.",
            "Aligned the VLAN ID with the transport team and updated the design record.",
        ],
        "learning": [
            "Confirm VLAN IDs with the transport provider in writing before commissioning.",
            "Use packet capture / counters to check tagging when a new link passes no traffic.",
        ],
    },
    {
        "key": "lb_healthcheck", "node_type": "LB", "nodes": ["LB-01", "LB-02", "LB-01"], "count": 3,
        "change_type": "Application upgrade", "mop_id": "", "mop_step": "", "release": ["17.1"],
        "severity": "High", "outcome": ["Outage", "Outage", "Resolved"],
        "title": [
            "Self-care portal down after backend upgrade - all pool members down on {node}",
            "{node} marked every backend unhealthy after app release",
            "Load balancer {node} health monitor failing after application update",
        ],
        "description": [
            "Release of the self-care portal backend behind {node}.",
            "Application update for the customer portal; traffic via {node}.",
            "New version of the API gateway deployed behind {node}.",
        ],
        "symptoms": [
            "Users received HTTP 503 from the portal right after the app release.",
            "All pool members went red on the load balancer although the apps were running.",
            "Health monitor returned 404; the pool was empty.",
        ],
        "error_signature": ["HTTP 503 Service Unavailable; pool has no available members", "monitor /health returned 404", "all members down"],
        "commands": ["show ltm pool members; show ltm monitor http", "curl -I http://<member>/health"],
        "root_cause": [
            "The application release moved the health endpoint from /health to /actuator/health; the LB monitor still polled the old path.",
            "The health check URL changed in the new app version.",
            "The monitor path was not updated together with the release.",
        ],
        "resolution": [
            "Updated the LB monitor path; pool members came back up.",
            "Temporarily kept the old /health path via app config, then updated the monitor.",
        ],
        "learning": [
            "Before app upgrades behind a load balancer, confirm the health-check endpoint is unchanged or update the monitor.",
            "Test the health endpoint on the new version before switching traffic.",
        ],
    },
    {
        "key": "hss_replication_lag", "node_type": "HSS", "nodes": ["HSS-03", "HSS-02", "HSS-03"], "count": 3,
        "change_type": "Database switchover", "mop_id": "", "mop_step": "", "release": ["22.1"],
        "severity": "High", "outcome": ["Service degraded", "Service degraded", "Resolved"],
        "title": [
            "Authentication failures for new subscribers after {node} DB switchover",
            "{node}: recently provisioned SIMs rejected after site switchover",
            "Subscriber data missing on standby after {node} database failover",
        ],
        "description": [
            "Planned database switchover of {node} to the secondary site.",
            "Geo-redundancy switchover test on {node}.",
            "Active/standby swap of the subscriber database on {node}.",
        ],
        "symptoms": [
            "Subscribers provisioned in the last hour could not register; older subscribers were fine.",
            "Newly activated SIM cards rejected with unknown subscriber after the switchover.",
            "Provisioning team reported recent changes missing on the new active site.",
        ],
        "error_signature": ["DIAMETER_ERROR_USER_UNKNOWN (5001)", "replication lag 3600s", "subscriber not found"],
        "commands": ["show db replication status", "check replication lag on standby"],
        "root_cause": [
            "Replication to the standby site lagged by about an hour, and the switchover was executed without checking the lag.",
            "The standby database was behind the active; recent provisioning had not replicated yet.",
            "Switchover done while replication was degraded after a link flap.",
        ],
        "resolution": [
            "Switched back, waited for replication to catch up, then repeated the switchover.",
            "Re-provisioned the affected subscribers and resynchronised the databases.",
        ],
        "learning": [
            "Check database replication lag is near zero before any HSS switchover.",
            "Add a replication status go/no-go check to the switchover procedure.",
        ],
    },
    {
        "key": "ran_pci_conflict", "node_type": "eNodeB", "nodes": ["ENB-4411", "ENB-5120", "ENB-4415"], "count": 3,
        "change_type": "Site integration", "mop_id": "", "mop_step": "", "release": ["24R1"],
        "severity": "Medium", "outcome": ["Service degraded", "Resolved", "Service degraded"],
        "title": [
            "Dropped calls in cluster after new site {node} integration",
            "Handover failures near new eNodeB {node}",
            "{node} integration caused call drops on neighbour cells",
        ],
        "description": [
            "Integration of new site {node}.",
            "New eNodeB {node} brought on air.",
            "Capacity site {node} integrated into the cluster.",
        ],
        "symptoms": [
            "Call drop rate doubled in neighbouring cells after the new site went on air.",
            "Handover failures and RRC re-establishments increased around the new site.",
            "Customers near the new site experienced dropped calls while moving.",
        ],
        "error_signature": ["PCI confusion; handover failure", "RRC re-establishment rate high", "X2 handover preparation failure"],
        "commands": ["check PCI plan; neighbour relation table", "KPI: HO success rate per cell"],
        "root_cause": [
            "The new site was planned with a PCI already used by a neighbour cell (PCI confusion).",
            "PCI conflict between the new cell and an existing neighbour.",
            "The PCI plan was not refreshed before integration; duplicate PCI in the neighbourhood.",
        ],
        "resolution": [
            "Changed the PCI of the new cell and refreshed neighbour relations; KPIs recovered.",
            "Re-planned the PCI with the SON tool and re-integrated the site.",
        ],
        "learning": [
            "Run a PCI conflict/confusion check against neighbours before site integration.",
            "Monitor handover KPIs for 24 hours after integrating a new site.",
        ],
    },
    {
        "key": "netact_mediation", "node_type": "NetAct", "nodes": ["NETACT-01", "NETACT-01", "NETACT-01"], "count": 3,
        "change_type": "Node upgrade (OSS adaptation)", "mop_id": "", "mop_step": "", "release": ["24"],
        "severity": "Low", "outcome": ["Resolved"],
        "title": [
            "PM counters missing in NetAct after node release upgrade",
            "Performance reports empty for upgraded nodes",
            "KPI dashboards blank after network element upgrade",
        ],
        "description": [
            "Network elements upgraded to a new release; NetAct adaptation not updated.",
            "Post-upgrade PM data validation failed.",
            "Reporting team raised missing KPI data after the upgrade weekend.",
        ],
        "symptoms": [
            "PM files arrive but counters are not loaded; reports show gaps.",
            "KPI dashboards show no data for nodes upgraded over the weekend.",
            "Mediation rejects measurement files from upgraded nodes.",
        ],
        "error_signature": ["unknown measurement type; adaptation not found", "PM file rejected: schema mismatch", "no adaptation for release"],
        "commands": ["check NetAct adaptation version for NE release", "PM loader logs"],
        "root_cause": [
            "The NetAct adaptation for the new node release was not installed before the node upgrade.",
            "Mediation adaptation version mismatch with the upgraded node release.",
            "OSS adaptation update was not scheduled together with the node upgrade.",
        ],
        "resolution": [
            "Installed the matching NetAct adaptation and reloaded the PM files.",
            "Deployed the adaptation package and re-processed the rejected files.",
        ],
        "learning": [
            "Install the matching NetAct adaptation before upgrading network elements to a new release.",
            "Include OSS adaptation readiness in the upgrade go/no-go checklist.",
        ],
    },
]

ROUTINE = [
    ("CMG", "Software upgrade", "MOP-UPG-04", "Routine upgrade of {node} to 24.7 completed", "Upgrade executed per MOP-UPG-04; all post-checks passed."),
    ("CMG", "Configuration change", "", "APN profile update on {node}", "New APN added and tested; no impact."),
    ("CMM", "Software upgrade", "MOP-UPG-02", "{node} upgraded to 26.7 without issues", "Upgrade per MOP-UPG-02; alarm sync verified in NetAct."),
    ("CMM", "Configuration change", "", "TAC list update on {node}", "Tracking area list updated; attach success unchanged."),
    ("Edge Router", "Firmware upgrade", "MOP-RTR-07", "Firmware upgrade on {node} completed", "Firmware 7.11.1 installed; MTU and BGP timers verified after reload."),
    ("Edge Router", "Configuration change", "", "Prefix-list update on {node}", "Customer prefix added; BGP advertisement verified."),
    ("Core Router", "Software upgrade", "MOP-RTR-07", "Junos upgrade on {node}", "Upgrade completed; routes and protocols verified."),
    ("OCP Cluster", "Node patching", "MOP-OCP-03", "Worker patching on {node} completed", "All workers drained and patched within the window."),
    ("OCP Cluster", "Cluster upgrade", "", "Minor version update of {node}", "Cluster updated to 4.16.x; operators healthy."),
    ("SBC", "Certificate renewal", "MOP-CRT-01", "Certificate renewed on {node}", "Full chain installed and validated with peers."),
    ("Firewall", "Firewall policy change", "MOP-FW-05", "New partner VPN rule on {node}", "Rule added; traffic verified."),
    ("HSS", "Configuration change", "", "Roaming partner profile on {node}", "Profile added; test subscribers registered."),
    ("SEG", "Configuration change", "", "New eNodeB tunnels on {node}", "Tunnels established for 12 new sites."),
    ("LB", "Application upgrade", "", "Portal release behind {node}", "Health monitor checked before switch; release successful."),
    ("eNodeB", "Site integration", "", "Integration of {node}", "Site integrated; KPIs within target after 24h."),
    ("CMG", "Hardware replacement", "", "Line card replacement on {node}", "Card replaced; interfaces and MTU verified."),
    ("CMM", "Hardware migration", "MOP-UPG-02", "Migration of {node} to new platform", "Licenses transferred and verified before traffic swing."),
    ("Edge Router", "Interface migration", "", "Uplink moved to new port on {node}", "QoS and MTU re-applied and verified."),
    ("NetAct", "Node upgrade (OSS adaptation)", "", "Adaptation package installed for CMG 24.7", "Adaptation installed ahead of node upgrades."),
    ("Core Router", "Failover test", "", "VRRP failover test on {node}", "Failover and failback successful within 3s."),
    ("CMG", "Software upgrade", "MOP-UPG-04", "{node} upgraded to 24.3", "Pre-check snapshot compared after upgrade; no deviations."),
    ("Firewall", "Firewall policy change", "MOP-FW-05", "Rule cleanup on {node}", "SCTP/Diameter rules verified untouched; cleanup done."),
]

MOPS = {
    "MOP-UPG-04": ("Software upgrade on packet core gateway (CMG)", "CMG", "Nokia", [
        "Confirm maintenance window approval and notify the NOC and the mate-site team.",
        "Export the configuration backup to the backup server and verify the checksum.",
        "Run pre-checks: capture 'show router bgp summary', 'show bfd session', interface MTU, GTP path-management timers and active session counts.",
        "Drain user-plane traffic to the mate gateway (check mate load first).",
        "Load the new software package and activate the target release.",
        "Reboot the gateway and wait for all cards and pods to come up.",
        "Re-enable BGP/BFD sessions and restore traffic.",
        "Post-checks: compare session counts, BGP/BFD state, interface MTU and GTP timers with the pre-check snapshot.",
        "Confirm alarms and PM data are flowing to NetAct, monitor KPIs for 30 minutes and close the change.",
    ]),
    "MOP-UPG-02": ("Software upgrade on mobility manager (CMM)", "CMM", "Nokia", [
        "Confirm maintenance window and put the node in NetAct maintenance mode.",
        "Take a configuration and database backup.",
        "Check free disk space on /var/log and the staging partition.",
        "Transfer and verify the release package.",
        "Upgrade the pods/VMs to the target release.",
        "Verify S1/N2 associations and attach success rate.",
        "Remove NetAct maintenance mode and verify alarm synchronisation between node and NetAct.",
        "Verify license capacity and subscriber counters.",
        "Monitor KPIs for 30 minutes and close the change.",
    ]),
    "MOP-RTR-07": ("Firmware / software upgrade on edge and core routers", "Edge Router", "Cisco", [
        "Back up the running and startup configuration off-box.",
        "Diff running vs startup configuration and save pending changes.",
        "Record BGP neighbour timers, interface MTU and QoS policies.",
        "Install the firmware / SMU package.",
        "Reload the router and verify interfaces and MTU on both ends.",
        "Verify BGP sessions, timers and received prefixes.",
        "Verify static routes and OAM reachability.",
        "Close the change after 30 minutes of stable routing.",
    ]),
    "MOP-OCP-03": ("Worker node patching on OpenShift (OCP)", "OCP Cluster", "Red Hat", [
        "Check cluster health and operator status.",
        "List PodDisruptionBudgets and confirm each allows at least one disruption.",
        "Cordon and drain the worker node.",
        "Apply the OS patch.",
        "Reboot the node and wait for Ready state.",
        "Uncordon the node and verify pods rescheduled.",
        "Repeat for the next worker; close the change.",
    ]),
    "MOP-CRT-01": ("TLS certificate renewal on SBC", "SBC", "Ribbon", [
        "Check current certificate expiry and peer trust requirements.",
        "Generate the CSR and obtain the signed certificate.",
        "Install the leaf and intermediate certificates (full chain).",
        "Restart the TLS profile in a low-traffic period.",
        "Verify the TLS handshake with each interconnect peer using openssl s_client.",
        "Monitor SIP trunk status and close the change.",
    ]),
    "MOP-FW-05": ("Firewall policy change", "Firewall", "Fortinet", [
        "Back up the current policy.",
        "Review the rule changes with traffic owners (SCTP 36412, Diameter 3868).",
        "Apply the policy change.",
        "Verify S1/SCTP and Diameter associations and deny logs.",
        "Roll back immediately if associations drop.",
    ]),
}

LOGS = {
    "bfd_flap_cmg.log": ("cmg_mtu_bfd", "CMG-07", """2026-04-18 02:41:07 CMG-07 %BFD-5-SESSION_DOWN: BFD session to 10.20.1.1 down (detect time expired)
2026-04-18 02:41:09 CMG-07 %BGP-5-ADJCHANGE: neighbor 10.20.1.1 Down - BFD adjacency down
2026-04-18 02:41:31 CMG-07 %BFD-5-SESSION_UP: BFD session to 10.20.1.1 up
2026-04-18 02:43:52 CMG-07 %BFD-5-SESSION_DOWN: BFD session to 10.20.1.1 down (detect time expired)
# show bfd session
Peer 10.20.1.1  State Down  Tx 1000ms  Rx 1000ms  Mult 3
# show interface ethernet-1/1 | include MTU
MTU 1500
"""),
    "stale_alarms_cmm.log": ("netact_stale_alarms", "CMM-04", """# ps -o pid,stat,cmd -p $(pgrep -f snmpservice.py)
PID     STAT CMD
3674453 Sl   python3 /opt/app/lib/snmpagent/snmpservice.py
# NetAct alarm resync result
uploaded 42 alarms, 17 not present on node (cancelled), maintenance mode = ON
"""),
    "bgp_holdtime_er.log": ("rtr_bgp_timers", "ER-21", """RP/0/RSP0/CPU0:ER-21 %BGP-5-ADJCHANGE : neighbor 198.51.100.1 Down - BGP Notification sent, hold time expired
RP/0/RSP0/CPU0:ER-21 %BGP-5-ADJCHANGE : neighbor 198.51.100.1 Up
# show bgp neighbor 198.51.100.1 | include hold time
Hold time is 180, keepalive interval is 60 seconds
Configured hold time: 180, keepalive: 60
"""),
    "drain_pdb_ocp.log": ("ocp_drain_pdb", "OCP-02", """$ oc adm drain worker-3 --ignore-daemonsets --delete-emptydir-data
evicting pod cnf/policy-engine-7d9f
error when evicting pods/"policy-engine-7d9f" -n "cnf" (will retry after 5s): Cannot evict pod as it would violate the pod's disruption budget.
$ oc get pdb -n cnf
NAME            MIN AVAILABLE   ALLOWED DISRUPTIONS
policy-engine   2               0
"""),
}

# 20 new incidents / planned LNIs, worded differently from the records, with the family that is the known answer.
TESTS = [
    ("pre_change", "Software upgrade on packet core gateway CMG-12 using MOP-UPG-04", "cmg_mtu_bfd"),
    ("incident", "After the gateway release update the uplink BGP peers keep bouncing and big packets are dropped", "cmg_mtu_bfd"),
    ("incident", "Lots of GTP path down alarms on the packet gateway after the new release but subscribers seem fine", "cmg_gtp_echo"),
    ("incident", "Online charging not applied - sessions continue without quota since the OCS peer was changed", "cmg_charging_gy"),
    ("incident", "NetAct still lists alarms that the CMM already cleared and we cannot delete them", "netact_stale_alarms"),
    ("incident", "eBGP to transit keeps dropping with hold time expired since we patched the router", "rtr_bgp_timers"),
    ("incident", "BGP session flapping on edge router after firmware push; big pings fail, small ones work", "rtr_firmware_mtu"),
    ("incident", "Lost OAM reachability to many sites after reloading the core router", "rtr_static_route"),
    ("incident", "oc adm drain hangs - cannot evict pod because of the disruption budget", "ocp_drain_pdb"),
    ("incident", "Pods restart continuously after deploying the new container version, logs show a missing config key", "ocp_configmap_crashloop"),
    ("incident", "Interconnect partner rejects our TLS since the SBC certificate was renewed - unknown CA", "sbc_cert_chain"),
    ("incident", "eNodeBs dropping S1 right after the firewall policy cleanup", "fw_sctp_block"),
    ("incident", "CMM upgrade failed with ENOSPC while extracting the image", "cmm_disk_full"),
    ("incident", "Attach rejected at peak on the newly migrated mobility manager, subscriber count capped", "cmm_license"),
    ("incident", "HSS Diameter peer will not come up after we changed DNS servers, lookups return NXDOMAIN", "cmm_dns_diameter"),
    ("incident", "Node clock is minutes off after replacing the board and records are rejected downstream", "ntp_after_replacement"),
    ("incident", "NetAct shows the gateway as disconnected since the upgrade - SNMP authentication failures", "snmp_creds_reset"),
    ("incident", "IPsec tunnels to sites go down every 60 minutes since the security gateway update", "ipsec_rekey"),
    ("incident", "Portal returns 503 after the app release; every pool member is down on the load balancer", "lb_healthcheck"),
    ("incident", "Voice quality is bad after moving the uplink to a new port - QoS looks missing", "qos_not_reapplied"),
    ("incident", "Office printer on floor 3 does not print double-sided", None),
    ("incident", "Kafka consumer lag growing on the analytics data lake", None),
]


def pick(seq, i):
    return seq[i % len(seq)]


def rand_date(rng: random.Random) -> date:
    return START + timedelta(days=rng.randint(0, (END - START).days))


def build(out: Path) -> None:
    rng = random.Random(SEED)
    rows: list[tuple[str | None, dict]] = []

    for fam in FAMILIES:
        nt = fam["node_type"]
        vendor = NODES[nt][0]
        for i in range(fam["count"]):
            node = pick(fam["nodes"], i)
            fill = lambda key: pick(fam[key], i).format(node=node)
            rows.append((fam["key"], {
                "date": "",  # set below
                "title": fill("title"),
                "change_type": fam["change_type"],
                "vendor": vendor,
                "node": node,
                "node_type": nt,
                "release": pick(fam["release"], i),
                "mop_id": fam["mop_id"],
                "mop_step": fam["mop_step"],
                "description": fill("description"),
                "symptoms": fill("symptoms"),
                "error_signature": fill("error_signature"),
                "commands": fill("commands"),
                "root_cause": fill("root_cause"),
                "resolution": fill("resolution"),
                "learning": fill("learning"),
                "outcome": pick(fam["outcome"], i),
                "severity": fam["severity"],
                "verified": True,
            }))

    for nt, change_type, mop_id, title, notes in ROUTINE:
        vendor, nodes = NODES[nt]
        node = rng.choice(nodes)
        rows.append((None, {
            "date": "", "title": title.format(node=node), "change_type": change_type, "vendor": vendor,
            "node": node, "node_type": nt, "release": "", "mop_id": mop_id, "mop_step": "",
            "description": notes, "symptoms": "", "error_signature": "", "commands": "",
            "root_cause": "", "resolution": "", "learning": notes,
            "outcome": "Success", "severity": "Low", "verified": True,
        }))

    for _, rec in rows:
        rec["date"] = rand_date(rng).isoformat()
    rows.sort(key=lambda r: r[1]["date"])
    family_ids: dict[str, list[str]] = {}
    records = []
    for n, (key, rec) in enumerate(rows, start=1001):
        rec = {"lni_id": f"LNI-{n}", **rec}
        records.append(rec)
        if key:
            family_ids.setdefault(key, []).append(rec["lni_id"])

    (out / "lni").mkdir(parents=True, exist_ok=True)
    (out / "mops").mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    (out / "tests").mkdir(parents=True, exist_ok=True)
    (out / "lni" / "lni_records.json").write_text(json.dumps(records, indent=2), encoding="utf-8")

    for mop_id, (title, nt, vendor, steps) in MOPS.items():
        body = [f"# {mop_id}: {title}", "", f"Node type: {nt}", f"Vendor: {vendor}", "", "## Steps", ""]
        body += [f"{i}. {s}" for i, s in enumerate(steps, start=1)]
        (out / "mops" / f"{mop_id}.md").write_text("\n".join(body) + "\n", encoding="utf-8")

    for name, (key, node, text) in LOGS.items():
        header = f"# node: {node}\n# related: {family_ids[key][0]}\n"
        (out / "logs" / name).write_text(header + text, encoding="utf-8")

    tests = []
    for i, (mode, text, key) in enumerate(TESTS, start=1):
        tests.append({
            "test_id": f"T{i:02d}", "mode": mode, "query": text,
            "expected": family_ids.get(key, []) if key else [],
        })
    (out / "tests" / "test_incidents.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} LNI records, {len(MOPS)} MOPs, {len(LOGS)} logs, {len(tests)} test incidents to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[2] / "data" / "raw")
    build(ap.parse_args().out)
