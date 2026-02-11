"""
Migração MongoDB (v1) → PostgreSQL (v2) — compatível com o schema atual da API v2.

Migra:
- configuracoes → system_configuration (key, value JSONB)
- processos → processes (com instituição "Legacy (MongoDB)")
- Cria instituição Legacy com sei_url vinda do Mongo (url_sistema)

Uso (na raiz do projeto):
  python scripts/migrate-mongo-to-postgres.py --dry-run   # simula
  python scripts/migrate-mongo-to-postgres.py             # migra
  python scripts/migrate-mongo-to-postgres.py --clear-postgres  # limpa Postgres e migra

Requer: MongoDB acessível (MONGO_URI em .env; connect_mongo foi movido para legacy/), .env com DATABASE_URL.
"""

import argparse
import json
import logging
import os
import sys
import ast
import re
from datetime import datetime
from pathlib import Path

# Raiz do projeto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv()

# MongoDB
try:
    import pymongo
except Exception as e:
    raise SystemExit(
        "pymongo não está instalado. Instale com: pip install pymongo"
    ) from e

# PostgreSQL (app v2)
from app.database.session import get_session
from app.database.models.institution import Institution
from app.database.models.institution_credential import InstitutionCredential
from app.database.models.process import Process
from app.database.models.document_history import DocumentHistory
from app.database.models.system_configuration import SystemConfiguration
from app.database.models.user import User
from app.utils.encryption import encrypt_value


def get_app_data_dir() -> Path:
    base = Path(os.getenv("LOCALAPPDATA", os.path.expanduser("~"))) / "SEI_UNO_TRADE"
    base.mkdir(parents=True, exist_ok=True)
    return base


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

LEGACY_CONNECT = ROOT / "legacy" / "connect_mongo.py"


def _extract_legacy_connection_string() -> str:
    """Best-effort: extract CONNECTION_STRING from legacy/connect_mongo.py without importing it."""
    try:
        if not LEGACY_CONNECT.exists():
            return ""
        tree = ast.parse(LEGACY_CONNECT.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "CONNECTION_STRING":
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            return node.value.value
    except Exception:
        return ""
    return ""


def get_database():
    """Return MongoDB database handle (prefers env MONGO_URI)."""
    mongo_uri = (os.getenv("MONGO_URI") or "").strip() or _extract_legacy_connection_string()
    if not mongo_uri:
        raise SystemExit(
            "MONGO_URI não definido e não foi possível extrair do legacy/connect_mongo.py. "
            "Defina MONGO_URI no .env."
        )
    db_name = (os.getenv("MONGO_DB_NAME") or "sei_database").strip() or "sei_database"
    client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=8000)
    # fail fast if unreachable
    client.admin.command("ping")
    return client[db_name]


def parse_ultima_atualizacao(s: str | None):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def run_migration(
    dry_run: bool = False,
    skip_backup: bool = False,
    clear_postgres: bool = False,
    batch_size: int = 100,
    verbose: bool = False,
) -> bool:
    stats = {
        "processes_mongo": 0,
        "processes_migrated": 0,
        "processes_failed": 0,
        "configs_mongo": 0,
        "configs_migrated": 0,
        "configs_failed": 0,
        "errors": [],
        "start": None,
        "end": None,
    }
    stats["start"] = datetime.now()

    try:
        mongo_db = get_database()
        logger.info("MongoDB conectado: %s", mongo_db.name)

        with get_session() as _session:
            pass  # test connection
        logger.info("PostgreSQL conectado")

        # Backup Mongo (opcional)
        if not skip_backup and not dry_run:
            backup_dir = get_app_data_dir() / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"mongodb_dump_{ts}.json"
            data = {
                "timestamp": ts,
                "database": mongo_db.name,
                "collections": {
                    "processos": list(mongo_db.processos.find({}, {"_id": 0})),
                    "configuracoes": list(mongo_db.configuracoes.find({}, {"_id": 0})),
                },
            }
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.info("Backup Mongo salvo: %s", backup_file)

        # Limpar Postgres (opcional)
        if clear_postgres and not dry_run:
            logger.warning("Limpando tabelas PostgreSQL...")
            with get_session() as session:
                session.query(DocumentHistory).delete(synchronize_session=False)
                session.query(InstitutionCredential).delete(synchronize_session=False)
                session.query(Process).delete(synchronize_session=False)
                session.query(SystemConfiguration).delete(synchronize_session=False)
                legacy_inst = session.query(Institution).filter(Institution.name == "Legacy (MongoDB)").first()
                if legacy_inst:
                    session.delete(legacy_inst)
                session.commit()
            logger.info("Tabelas limpas.")

        # ── Configs principais do legacy ───────────────────────────────
        config_url = mongo_db.configuracoes.find_one({"tipo": "url_sistema"}, {"_id": 0})
        sei_url = (
            (config_url.get("url") if isinstance(config_url, dict) else None)
            or (config_url.get("valor") if isinstance(config_url, dict) else None)
            or "https://colaboragov.sei.gov.br/sei/"
        )

        config_creds = mongo_db.configuracoes.find_one({"tipo": "credenciais_acesso"}, {"_id": 0})
        legacy_login = ""
        legacy_password = ""
        if isinstance(config_creds, dict):
            legacy_login = (
                config_creds.get("email")
                or config_creds.get("user")
                or config_creds.get("usuario")
                or ""
            )
            legacy_password = config_creds.get("senha") or ""

        # 1) Usuário v2 do legacy (para multi-tenant)
        legacy_user_email = legacy_login.strip().lower() if legacy_login else "legacy@conectasei.local"
        uid_slug = re.sub(r"[^a-z0-9_-]+", "-", legacy_user_email)[:110].strip("-")
        legacy_firebase_uid = f"legacy-{uid_slug}" if uid_slug else "legacy-user"

        with get_session() as session:
            legacy_user = session.query(User).filter(User.email == legacy_user_email).first()
            if not legacy_user:
                if dry_run:
                    logger.info("[DRY-RUN] Criaria usuário legacy: %s", legacy_user_email)
                    legacy_user_id = 1  # fictício
                else:
                    legacy_user = User(
                        firebase_uid=legacy_firebase_uid,
                        email=legacy_user_email,
                        display_name="Legacy User",
                        role="admin",
                        is_active=True,
                    )
                    session.add(legacy_user)
                    session.flush()
                    legacy_user_id = legacy_user.id
                    logger.info("Usuário legacy criado: email=%s id=%s", legacy_user_email, legacy_user_id)
            else:
                legacy_user_id = legacy_user.id
                logger.info("Usuário legacy já existe: email=%s id=%s", legacy_user_email, legacy_user_id)

        # 2) Instituição Legacy vinculada ao usuário v2
        with get_session() as session:
            legacy = session.query(Institution).filter(Institution.name == "Legacy (MongoDB)").first()
            if not legacy:
                if dry_run:
                    logger.info("[DRY-RUN] Criaria instituição Legacy (MongoDB)")
                    legacy_id = 1  # fictício para dry-run
                else:
                    legacy = Institution(
                        name="Legacy (MongoDB)",
                        sei_url=sei_url,
                        is_active=True,
                        user_id=legacy_user_id,
                        extra_metadata={"migrated_from": "mongodb"},
                    )
                    session.add(legacy)
                    session.flush()
                    legacy_id = legacy.id
                    logger.info("Instituição Legacy criada: id=%s", legacy_id)
            else:
                legacy_id = legacy.id
                if not dry_run and legacy.user_id != legacy_user_id:
                    legacy.user_id = legacy_user_id
                    session.commit()
                logger.info("Instituição Legacy já existe: id=%s", legacy_id)

        # 2.5) institution_credentials (senha SEI encriptada)
        if legacy_login and legacy_password and not dry_run:
            with get_session() as session:
                existing_cred = session.query(InstitutionCredential).filter(
                    InstitutionCredential.institution_id == legacy_id,
                    InstitutionCredential.credential_type == "login",
                    InstitutionCredential.user_id == legacy_login,
                    InstitutionCredential.active.is_(True),
                ).first()
                if not existing_cred:
                    session.add(
                        InstitutionCredential(
                            institution_id=legacy_id,
                            credential_type="login",
                            user_id=legacy_login,
                            secret_encrypted=encrypt_value(legacy_password),
                            active=True,
                        )
                    )
                    session.commit()
                    logger.info("InstitutionCredential criado (institution_id=%s)", legacy_id)

        # 2) Configurações
        configs = list(mongo_db.configuracoes.find({}, {"_id": 0}))
        stats["configs_mongo"] = len(configs)
        for config in configs:
            key = config.pop("tipo", None)
            if not key:
                continue
            value = config
            if key == "url_sistema":
                # Legacy stores URL in "valor" (sometimes "url")
                url = ""
                if isinstance(value, dict):
                    url = value.get("url") or value.get("valor") or ""
                value = {"url": url}
            if dry_run:
                stats["configs_migrated"] += 1
                continue
            try:
                with get_session() as session:
                    existing = session.query(SystemConfiguration).filter(SystemConfiguration.key == key).first()
                    if existing:
                        existing.value = value
                        existing.updated_by = "migration_script"
                    else:
                        session.add(SystemConfiguration(
                            key=key,
                            value=value,
                            description="",
                            updated_by="migration_script",
                        ))
                    session.commit()
                stats["configs_migrated"] += 1
            except Exception as e:
                stats["configs_failed"] += 1
                stats["errors"].append({"type": "config", "key": key, "message": str(e)})
        logger.info("Configurações: %s/%s migradas", stats["configs_migrated"], stats["configs_mongo"])

        # 3) Processos
        total = mongo_db.processos.count_documents({})
        stats["processes_mongo"] = total
        skip = 0
        while skip < total:
            batch = list(mongo_db.processos.find({}, {"_id": 0}).skip(skip).limit(batch_size))
            for doc in batch:
                numero = doc.get("numero_processo")
                if not numero:
                    stats["processes_failed"] += 1
                    continue
                try:
                    last_checked = parse_ultima_atualizacao(doc.get("ultima_atualizacao"))
                    if dry_run:
                        stats["processes_migrated"] += 1
                        continue
                    with get_session() as session:
                        existing = session.query(Process).filter(Process.process_number == numero).first()
                        payload = {
                            "institution_id": legacy_id,
                            "process_number": numero,
                            "links": doc.get("links") or {},
                            "best_current_link": doc.get("melhor_link_atual"),
                            "access_type": doc.get("tipo_acesso_atual"),
                            "category": doc.get("categoria"),
                            "category_status": doc.get("status_categoria"),
                            "unit": doc.get("unidade"),
                            "authority": doc.get("Autoridade"),
                            "no_valid_links": bool(doc.get("sem_link_validos", False)),
                            "nickname": doc.get("apelido"),
                            "documents_data": doc.get("documentos") or {},
                            "last_checked_at": last_checked,
                            "extra_metadata": {
                                "ultima_verificacao": doc.get("ultima_verificacao"),
                                "recibos_processados": doc.get("recibos_processados") or {},
                                "migrated_from": "mongodb",
                            },
                        }
                        if existing:
                            for k, v in payload.items():
                                setattr(existing, k, v)
                        else:
                            session.add(Process(**payload))
                        session.commit()
                    stats["processes_migrated"] += 1
                except Exception as e:
                    stats["processes_failed"] += 1
                    stats["errors"].append({"type": "process", "id": numero, "message": str(e)})
                    if verbose:
                        logger.exception("Processo %s", numero)
            skip += batch_size
            logger.info("Processos: %s/%s", min(skip, total), total)

        # 4) documentos_historico → document_history (best-effort)
        if not dry_run and "documentos_historico" in mongo_db.list_collection_names():
            try:
                total_hist = mongo_db.documentos_historico.count_documents({})
            except Exception:
                total_hist = 0

            if total_hist:
                # Build mapping for process number → id
                with get_session() as session:
                    proc_rows = session.query(Process.id, Process.process_number).filter(
                        Process.institution_id == legacy_id
                    ).all()
                proc_map = {n: pid for (pid, n) in proc_rows}

                def _json_safe(v):
                    if isinstance(v, datetime):
                        return v.isoformat()
                    return v

                migrated_hist = 0
                failed_hist = 0
                batch_docs = []
                cursor = mongo_db.documentos_historico.find({}, {"_id": 0})
                for h in cursor:
                    pnum = h.get("processo_numero") or ""
                    pid = proc_map.get(pnum)
                    if not pid:
                        failed_hist += 1
                        continue

                    dnum = str(h.get("documento_numero") or "").strip()
                    if not dnum:
                        failed_hist += 1
                        continue

                    ts = h.get("timestamp_gravacao") or h.get("timestamp_fim") or h.get("timestamp_inicio") or datetime.utcnow()
                    if not isinstance(ts, datetime):
                        ts = datetime.utcnow()

                    legacy_extra = {k: _json_safe(v) for k, v in h.items()}
                    batch_docs.append(DocumentHistory(
                        process_id=pid,
                        document_number=dnum,
                        action=str(h.get("tipo_operacao") or "legacy"),
                        old_status=None,
                        new_status=None,
                        file_path=None,
                        file_size=None,
                        performed_by="migration_script",
                        timestamp=ts,
                        extra_metadata={
                            "legacy": {
                                k: v for k, v in legacy_extra.items()
                                if k not in {"processo_numero", "documento_numero"}
                            }
                        },
                    ))

                    if len(batch_docs) >= 500:
                        with get_session() as session:
                            session.add_all(batch_docs)
                            session.commit()
                        migrated_hist += len(batch_docs)
                        batch_docs = []
                        logger.info("DocumentHistory: %s/%s", migrated_hist, total_hist)

                if batch_docs:
                    with get_session() as session:
                        session.add_all(batch_docs)
                        session.commit()
                    migrated_hist += len(batch_docs)

                logger.info("DocumentHistory migrado: %s (falhas: %s)", migrated_hist, failed_hist)

        stats["end"] = datetime.now()
        duration = (stats["end"] - stats["start"]).total_seconds()
        logger.info("Migração concluída. Processos: %s migrados, %s falhas. Configs: %s. Duração: %.1fs",
                    stats["processes_migrated"], stats["processes_failed"], stats["configs_migrated"], duration)
        logger.info("Para testar no Swagger (AUTH_DEV_MODE=true): X-Dev-User-Email: %s", legacy_user_email)
        if stats["errors"]:
            for err in stats["errors"][:10]:
                logger.error("  %s: %s - %s", err["type"], err.get("id", err.get("key")), err["message"])
        return stats["processes_failed"] == 0 and stats["configs_failed"] == 0

    except Exception as e:
        logger.exception("Erro fatal: %s", e)
        return False


def main():
    ap = argparse.ArgumentParser(description="MongoDB → PostgreSQL (schema v2)")
    ap.add_argument("--dry-run", action="store_true", help="Simular sem escrever no Postgres")
    ap.add_argument("--skip-backup", action="store_true", help="Não criar backup do Mongo")
    ap.add_argument("--clear-postgres", action="store_true", help="Limpar processos/configs/legacy antes de migrar")
    ap.add_argument("--batch-size", type=int, default=100, help="Tamanho do lote de processos")
    ap.add_argument("--verbose", action="store_true", help="Log detalhado")
    args = ap.parse_args()

    if args.clear_postgres and not args.dry_run:
        r = input("Digite 'SIM' para confirmar limpeza do Postgres: ")
        if r != "SIM":
            sys.exit(0)

    ok = run_migration(
        dry_run=args.dry_run,
        skip_backup=args.skip_backup,
        clear_postgres=args.clear_postgres,
        batch_size=args.batch_size,
        verbose=args.verbose,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
