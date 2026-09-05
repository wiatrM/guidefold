#!/usr/bin/env python3
"""Paired exact-vector storage probe in bounded, session-local temporary tables."""
import argparse, hashlib, json, math, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".guidefold/checks/vector-storage-probe.json"
CMD = [
    "docker",
    "compose",
    "-p",
    "guidefold-search-gpu",
    "exec",
    "-T",
    "db",
    "psql",
    "-U",
    "postgres",
    "-d",
    "guidefold",
    "-XAtq",
    "-v",
    "ON_ERROR_STOP=1",
]


def run(script):
    p = subprocess.run(CMD, cwd=ROOT, input=script, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inline-target", type=int, choices=(2048, 6144), default=2048)
    args = parser.parse_args()
    out = (
        OUT
        if args.inline_target == 2048
        else OUT.with_name("vector-storage-target6144-probe.json")
    )
    if out.exists():
        raise SystemExit("Refusing to overwrite measurement")
    identity = json.loads(
        run(
            "SELECT json_build_object('snapshot',snapshot_id,'encoder',encoder_id) FROM gf.embedding_sets WHERE tenant='local' AND repo='skillret-service-bench' ORDER BY snapshot_id LIMIT 1;"
        )
    )
    assert re.fullmatch(
        r"repository:[a-f0-9]{64}", identity["snapshot"]
    ) and re.fullmatch(r"[a-f0-9]{64}", identity["encoder"])
    where = f"tenant='local' AND repo='skillret-service-bench' AND snapshot_id='{identity['snapshot']}' AND encoder_id='{identity['encoder']}'"
    script = f"""BEGIN;
SET LOCAL statement_timeout='20s';
SET LOCAL lock_timeout='1s';
CREATE TEMP TABLE probe_external (LIKE gf.embeddings INCLUDING ALL) ON COMMIT DROP;
CREATE TEMP TABLE probe_plain (LIKE gf.embeddings INCLUDING ALL) ON COMMIT DROP;
ALTER TABLE probe_plain ALTER COLUMN embedding SET STORAGE PLAIN;
ALTER TABLE probe_plain SET (toast_tuple_target={args.inline_target});
INSERT INTO probe_external SELECT * FROM gf.embeddings WHERE {where} LIMIT 6007;
DO $$ BEGIN IF (SELECT count(*) FROM probe_external)<>6006 THEN RAISE EXCEPTION 'unexpected_probe_count'; END IF; END $$;
INSERT INTO probe_plain SELECT * FROM probe_external;
ANALYZE probe_external;
ANALYZE probe_plain;
"""

    def query(table):
        return f"""WITH ranked AS (SELECT urn,row_number() OVER (ORDER BY embedding <=> (SELECT embedding FROM probe_external ORDER BY urn COLLATE "C" LIMIT 1),urn COLLATE "C") AS dense_rank FROM {table} WHERE {where}) SELECT urn,dense_rank FROM ranked WHERE dense_rank<=50 OR urn IN (SELECT urn FROM probe_external ORDER BY urn COLLATE "C" LIMIT 50) ORDER BY dense_rank"""

    for name in ("external", "plain"):
        table = "probe_" + name
        script += f"SELECT json_build_object('kind','ranks','layout','{name}','rows',json_agg(row_to_json(t))) FROM ({query(table)}) t;\n"
        script += f"SELECT json_build_object('kind','size','layout','{name}','heap_bytes',pg_relation_size(oid),'total_bytes',pg_total_relation_size(oid),'toast_bytes',pg_total_relation_size(reltoastrelid)) FROM pg_class WHERE oid='{table}'::regclass;\n"
    for i in range(30):
        order = ["external", "plain"] if i % 2 == 0 else ["plain", "external"]
        for name in order:
            script += f"SELECT json_build_object('kind','iteration','layout','{name}','iteration',{i});\nEXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) {query('probe_'+name)};\n"
    script += "COMMIT;\n"
    raw = run(script)
    decoder = json.JSONDecoder()
    records = []
    while raw.strip():
        raw = raw.lstrip()
        value, end = decoder.raw_decode(raw)
        records.append(value)
        raw = raw[end:]
    result = {
        "kind": "bounded_temp_vector_storage_probe",
        "quality_evaluated": False,
        "identity": identity,
        "inline_toast_target": args.inline_target,
        "rows_per_layout": 6006,
        "paired_iterations": 30,
        "original_table_modified": False,
        "original_statistics_modified": False,
        "tables_dropped_at_transaction_end": True,
        "resources_isolated": False,
        "arms": {k: {"execution_ms": [], "plans": []} for k in ("external", "plain")},
        "production_ready": False,
    }
    layout = None
    for record in records:
        if isinstance(record, list):
            plan = record[0]
            result["arms"][layout]["execution_ms"].append(plan["Execution Time"])
            result["arms"][layout]["plans"].append(plan)
            continue
        layout = record["layout"]
        arm = result["arms"][layout]
        if record["kind"] == "ranks":
            arm["ranked_sha256"] = hashlib.sha256(
                json.dumps(record["rows"], sort_keys=True).encode()
            ).hexdigest()
        if record["kind"] == "size":
            arm["size"] = {
                k: record[k] for k in ("heap_bytes", "total_bytes", "toast_bytes")
            }
    for arm in result["arms"].values():
        times = sorted(arm["execution_ms"])
        assert len(times) == 30
        arm["summary_ms"] = {
            f"p{p}": times[math.ceil(len(times) * p / 100) - 1] for p in (50, 95, 99)
        }
    result["exact_rank_parity"] = (
        result["arms"]["external"]["ranked_sha256"]
        == result["arms"]["plain"]["ranked_sha256"]
    )
    assert result["exact_rank_parity"]
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "exact_rank_parity": True,
                "arms": {
                    k: {"summary_ms": v["summary_ms"], "size": v["size"]}
                    for k, v in result["arms"].items()
                },
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
