"""
Inspect MongoDB used by legacy app.

Goals:
- List collection names and counts
- Sample 1 document per collection (print only keys, not sensitive values)
- Help identify which collection stores the "legacy user" record

Connection priority:
1) MONGO_URI env var
2) Extract CONNECTION_STRING from legacy/connect_mongo.py (fallback)
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any

import pymongo


ROOT = Path(__file__).resolve().parent.parent
LEGACY_CONNECT = ROOT / "legacy" / "connect_mongo.py"


SENSITIVE_KEY_RE = re.compile(
    r"(senha|password|secret|token|key|private|connection|uri)",
    re.IGNORECASE,
)


def _extract_legacy_connection_string() -> str:
    if not LEGACY_CONNECT.exists():
        return ""
    tree = ast.parse(LEGACY_CONNECT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "CONNECTION_STRING":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    return ""


def _safe_preview(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted preview of a Mongo document."""
    out: dict[str, Any] = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if SENSITIVE_KEY_RE.search(k):
            out[k] = "***redacted***"
            continue
        # Keep small scalar previews, else just describe type.
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v if not (isinstance(v, str) and len(v) > 120) else (v[:117] + "...")
        elif isinstance(v, dict):
            out[k] = {"__type__": "dict", "keys": list(v.keys())[:25]}
        elif isinstance(v, list):
            out[k] = {"__type__": "list", "len": len(v)}
        else:
            out[k] = {"__type__": type(v).__name__}
    return out


def main() -> None:
    mongo_uri = (os.getenv("MONGO_URI") or "").strip()
    if not mongo_uri:
        mongo_uri = _extract_legacy_connection_string()

    if not mongo_uri:
        raise SystemExit("No MONGO_URI configured and legacy/connect_mongo.py not found.")

    db_name = (os.getenv("MONGO_DB_NAME") or "sei_database").strip() or "sei_database"

    client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=8000)
    # Force a ping to fail fast if unreachable.
    client.admin.command("ping")

    db = client[db_name]
    names = sorted(db.list_collection_names())

    print(f"MongoDB OK. db={db_name}. collections={len(names)}")
    for name in names:
        col = db[name]
        try:
            count = col.count_documents({})
        except Exception:
            count = -1
        sample = col.find_one({})
        keys = list(sample.keys()) if isinstance(sample, dict) else []
        print(f"- {name}: count={count}, keys={keys[:40]}")

        if isinstance(sample, dict):
            preview = _safe_preview(sample)
            # Special-case: show likely 'email' field if present (non-sensitive)
            if "email" in sample and not SENSITIVE_KEY_RE.search("email"):
                preview["email"] = sample.get("email")
            print(f"  preview={preview}")

    # ── Safe highlights for migration ──
    if "configuracoes" in names:
        cfg = db["configuracoes"]
        tipos = sorted({d.get("tipo") for d in cfg.find({}, {"_id": 0, "tipo": 1}) if d.get("tipo")})
        print("\nconfiguracoes.tipos=", tipos)

        url_doc = cfg.find_one({"tipo": "url_sistema"}, {"_id": 0, "tipo": 1, "valor": 1, "url": 1})
        if isinstance(url_doc, dict):
            url = url_doc.get("url") or url_doc.get("valor") or ""
            print("url_sistema.url=", url)

        cred_doc = cfg.find_one(
            {"tipo": "credenciais_acesso"},
            {"_id": 0, "tipo": 1, "email": 1, "user": 1, "usuario": 1},
        )
        if isinstance(cred_doc, dict):
            legacy_email = cred_doc.get("email") or cred_doc.get("user") or cred_doc.get("usuario") or ""
            print("credenciais_acesso.login_identifier=", legacy_email)


if __name__ == "__main__":
    main()

