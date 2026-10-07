# Evaluation report

Dataset: 98 LNI records, 6 MOPs, 4 logs. Test set: 20 incidents with a known correct past match + 2 out-of-scope.

Models: embeddings `BAAI/bge-small-en-v1.5`, reranker `Xenova/ms-marco-MiniLM-L-6-v2`, vector store `chroma`, confidence threshold 50%.

## Retrieval ablation

| Pipeline | Hit@1 | Hit@3 | MRR | Latency |
|---|---|---|---|---|
| BM25 keyword only | 95% | 100% | 0.97 | 0.03s |
| Dense semantic only | 100% | 100% | 1.00 | 0.04s |
| Hybrid (RRF) | 100% | 100% | 1.00 | 0.08s |
| Hybrid + rerank | 100% | 100% | 1.00 | 1.10s |
| Hybrid + rerank + fingerprint | 100% | 100% | 1.00 | 0.96s |
| Full pipeline with bge-reranker-base | 100% | 100% | 1.00 | 8.33s |

## Agent (end to end, LLM off)

- Correct past match ranked first: **100%**, in top 3: **100%**
- Out-of-scope incidents answered with "No verified match found": **100%**
- Recommendation statements citing a retrieved record: **100%**
- Average time per agent run: 2.91s

| Test | Mode | Incident / planned LNI | Top match | Result |
|---|---|---|---|---|
| T01 | pre_change | Software upgrade on packet core gateway CMG-12 using MOP-UPG-04 | LNI-1079 (97%) | HIT@1 |
| T02 | incident | After the gateway release update the uplink BGP peers keep bouncing an | LNI-1079 (93%) | HIT@1 |
| T03 | incident | Lots of GTP path down alarms on the packet gateway after the new relea | LNI-1004 (73%) | HIT@1 |
| T04 | incident | Online charging not applied - sessions continue without quota since th | LNI-1073 (74%) | HIT@1 |
| T05 | incident | NetAct still lists alarms that the CMM already cleared and we cannot d | LNI-1043 (96%) | HIT@1 |
| T06 | incident | eBGP to transit keeps dropping with hold time expired since we patched | LNI-1014 (92%) | HIT@1 |
| T07 | incident | BGP session flapping on edge router after firmware push; big pings fai | LNI-1033 (98%) | HIT@1 |
| T08 | incident | Lost OAM reachability to many sites after reloading the core router | LNI-1083 (94%) | HIT@1 |
| T09 | incident | oc adm drain hangs - cannot evict pod because of the disruption budget | LNI-1070 (95%) | HIT@1 |
| T10 | incident | Pods restart continuously after deploying the new container version, l | LNI-1012 (89%) | HIT@1 |
| T11 | incident | Interconnect partner rejects our TLS since the SBC certificate was ren | LNI-1060 (97%) | HIT@1 |
| T12 | incident | eNodeBs dropping S1 right after the firewall policy cleanup | LNI-1064 (96%) | HIT@1 |
| T13 | incident | CMM upgrade failed with ENOSPC while extracting the image | LNI-1054 (98%) | HIT@1 |
| T14 | incident | Attach rejected at peak on the newly migrated mobility manager, subscr | LNI-1046 (87%) | HIT@1 |
| T15 | incident | HSS Diameter peer will not come up after we changed DNS servers, looku | LNI-1050 (82%) | HIT@1 |
| T16 | incident | Node clock is minutes off after replacing the board and records are re | LNI-1048 (75%) | HIT@1 |
| T17 | incident | NetAct shows the gateway as disconnected since the upgrade - SNMP auth | LNI-1027 (92%) | HIT@1 |
| T18 | incident | IPsec tunnels to sites go down every 60 minutes since the security gat | LNI-1053 (85%) | HIT@1 |
| T19 | incident | Portal returns 503 after the app release; every pool member is down on | LNI-1076 (89%) | HIT@1 |
| T20 | incident | Voice quality is bad after moving the uplink to a new port - QoS looks | LNI-1010 (70%) | HIT@1 |
| T21 | incident | Office printer on floor 3 does not print double-sided | LNI-1050 (14%) | correctly refused |
| T22 | incident | Kafka consumer lag growing on the analytics data lake | LNI-1044 (20%) | correctly refused |
