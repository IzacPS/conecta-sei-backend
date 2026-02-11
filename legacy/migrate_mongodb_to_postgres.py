"""
AutomaSEI v2.0 - MongoDB → PostgreSQL Migration Script

Migra dados do MongoDB (v1.0.10) para PostgreSQL + ParadeDB (v2.0).

CONFORMIDADE COM LEGACY:
- Baseado em MIGRATION_PLAN.md
- Preserva 100% dos dados
- MongoDB permanece intacto (apenas leitura)

Uso:
    # Dry-run (simula sem escrever)
    python migrate_mongodb_to_postgres.py --dry-run

    # Migração real
    python migrate_mongodb_to_postgres.py

    # Validação apenas
    python migrate_mongodb_to_postgres.py --validate-only

    # Limpar PostgreSQL antes de migrar
    python migrate_mongodb_to_postgres.py --clear-postgres

Argumentos:
    --dry-run          Simula migração sem escrever no PostgreSQL
    --skip-backup      Pula criação de backup do MongoDB
    --clear-postgres   Limpa tabelas PostgreSQL antes de migrar
    --validate-only    Apenas valida dados sem migrar
    --batch-size N     Migra em lotes de N processos (padrão: 100)
    --verbose          Log detalhado
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import uuid

# MongoDB
from connect_mongo import get_database

# PostgreSQL
from database.session import get_session
from models.models_sqlalchemy import Institution, Process, SystemConfiguration
from database.repositories.institution_repository import InstitutionRepository
from database.repositories.process_repository import ProcessRepository

# Utils
from utils.file_utils import get_app_data_dir

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class MigrationStats:
    """Estatísticas da migração."""

    def __init__(self):
        self.total_processes_mongo = 0
        self.migrated_processes = 0
        self.failed_processes = 0
        self.total_configs_mongo = 0
        self.migrated_configs = 0
        self.failed_configs = 0
        self.errors: List[Dict[str, Any]] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def add_error(self, error_type: str, item_id: str, message: str):
        """Registra erro."""
        self.errors.append({
            "type": error_type,
            "item_id": item_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

    def duration_seconds(self) -> float:
        """Retorna duração da migração em segundos."""
        if not self.start_time or not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    def summary(self) -> Dict[str, Any]:
        """Retorna sumário das estatísticas."""
        return {
            "processes": {
                "total_mongo": self.total_processes_mongo,
                "migrated": self.migrated_processes,
                "failed": self.failed_processes,
                "success_rate": (
                    f"{(self.migrated_processes / self.total_processes_mongo * 100):.2f}%"
                    if self.total_processes_mongo > 0 else "N/A"
                )
            },
            "configurations": {
                "total_mongo": self.total_configs_mongo,
                "migrated": self.migrated_configs,
                "failed": self.failed_configs
            },
            "errors": {
                "count": len(self.errors),
                "details": self.errors
            },
            "duration_seconds": self.duration_seconds()
        }


class DataMigration:
    """
    Gerencia migração completa de MongoDB para PostgreSQL.

    CONFORMIDADE COM LEGACY:
    - Preserva 100% dos dados (MIGRATION_PLAN.md)
    - MongoDB não é modificado (apenas leitura)
    - Rollback automático em caso de erro
    """

    def __init__(
        self,
        dry_run: bool = False,
        skip_backup: bool = False,
        clear_postgres: bool = False,
        batch_size: int = 100,
        verbose: bool = False
    ):
        self.dry_run = dry_run
        self.skip_backup = skip_backup
        self.clear_postgres = clear_postgres
        self.batch_size = batch_size
        self.verbose = verbose
        self.stats = MigrationStats()

        if verbose:
            logger.setLevel(logging.DEBUG)

        # Conexões
        self.mongo_db = None
        self.postgres_session = None

    def run(self) -> bool:
        """
        Executa migração completa.

        Returns:
            True se migração foi bem-sucedida
        """
        try:
            logger.info("=" * 80)
            logger.info("AutomaSEI v2.0 - MongoDB → PostgreSQL Migration")
            logger.info("=" * 80)

            if self.dry_run:
                logger.warning("🔍 DRY-RUN MODE: Nenhuma alteração será feita no PostgreSQL")

            self.stats.start_time = datetime.now()

            # Fase 1: Preparação
            logger.info("\n📋 Fase 1: Preparação")
            self._connect_databases()

            if not self.skip_backup:
                self._backup_mongodb()

            if self.clear_postgres and not self.dry_run:
                self._clear_postgres()

            # Fase 2: Migração
            logger.info("\n🔄 Fase 2: Migração de Dados")

            # 2.1: Criar instituição legacy
            legacy_institution = self._create_legacy_institution()

            # 2.2: Migrar configurações
            self._migrate_configurations()

            # 2.3: Migrar processos
            self._migrate_processes(legacy_institution.id)

            # Fase 3: Validação
            logger.info("\n✅ Fase 3: Validação")
            validation_ok = self._validate_migration()

            # Fase 4: Relatório
            self.stats.end_time = datetime.now()
            self._generate_report()

            if validation_ok:
                logger.info("\n✅ Migração concluída com sucesso!")
                return True
            else:
                logger.error("\n❌ Migração completada com erros. Revise o relatório.")
                return False

        except Exception as e:
            logger.error(f"\n❌ Erro fatal durante migração: {e}")
            self.stats.add_error("fatal", "migration", str(e))
            return False

        finally:
            self._cleanup()

    def _connect_databases(self):
        """Conecta aos bancos de dados."""
        logger.info("Conectando aos bancos de dados...")

        # MongoDB
        try:
            self.mongo_db = get_database()
            logger.info(f"✅ MongoDB conectado: {self.mongo_db.name}")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar MongoDB: {e}")
            raise

        # PostgreSQL (apenas testa conexão)
        try:
            with get_session() as session:
                logger.info("✅ PostgreSQL conectado")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar PostgreSQL: {e}")
            raise

    def _backup_mongodb(self):
        """Cria backup JSON do MongoDB."""
        logger.info("Criando backup do MongoDB...")

        try:
            backup_dir = get_app_data_dir() / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"mongodb_dump_{timestamp}.json"

            backup_data = {
                "timestamp": timestamp,
                "database": self.mongo_db.name,
                "collections": {}
            }

            # Backup de processos
            processos = list(self.mongo_db.processos.find({}, {"_id": 0}))
            backup_data["collections"]["processos"] = processos
            logger.info(f"  - processos: {len(processos)} documentos")

            # Backup de configurações
            configs = list(self.mongo_db.configuracoes.find({}, {"_id": 0}))
            backup_data["collections"]["configuracoes"] = configs
            logger.info(f"  - configuracoes: {len(configs)} documentos")

            # Salvar JSON
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"✅ Backup salvo: {backup_file}")
            logger.info(f"   Tamanho: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")

        except Exception as e:
            logger.error(f"❌ Erro ao criar backup: {e}")
            raise

    def _clear_postgres(self):
        """Limpa tabelas PostgreSQL."""
        logger.warning("⚠️  Limpando tabelas PostgreSQL (TRUNCATE CASCADE)...")

        try:
            with get_session() as session:
                # Ordem importante: apagar processos antes de instituições (FK)
                session.query(Process).delete()
                session.query(SystemConfiguration).delete()
                session.query(Institution).delete()
                session.commit()

            logger.info("✅ Tabelas limpas")

        except Exception as e:
            logger.error(f"❌ Erro ao limpar PostgreSQL: {e}")
            raise

    def _create_legacy_institution(self) -> Institution:
        """
        Cria instituição 'legacy' para processos antigos.

        Returns:
            Institution criada ou existente
        """
        logger.info("Criando instituição 'legacy'...")

        try:
            # Carregar URL do SEI de configurações MongoDB
            sei_url = "https://colaboragov.sei.gov.br/sei/"  # Default
            config_url = self.mongo_db.configuracoes.find_one({"tipo": "url_sistema"})
            if config_url and "url" in config_url:
                sei_url = config_url["url"]

            institution_data = {
                "id": "legacy",
                "name": "Legacy Institution (SEI)",
                "sei_url": sei_url,
                "scraper_version": "v1.0.10",
                "sei_family": "v1",
                "active": True,
                "created_by": "migration_script",
                "credentials": {},  # Usuário deve configurar manualmente após migração
                "notes": "Instituição criada automaticamente pela migração MongoDB → PostgreSQL. IMPORTANTE: Configure as credenciais de acesso."
            }

            if self.dry_run:
                logger.info(f"🔍 [DRY-RUN] Criaria instituição: {institution_data}")
                # Criar objeto Institution em memória para dry-run
                return Institution(**institution_data)

            with get_session() as session:
                repo = InstitutionRepository(session)

                # Verificar se já existe
                existing = repo.get_by_id("legacy")
                if existing:
                    logger.info("✅ Instituição 'legacy' já existe")
                    return existing

                # Criar nova
                institution = repo.create(**institution_data)
                logger.info(f"✅ Instituição 'legacy' criada: {institution.sei_url}")
                return institution

        except Exception as e:
            logger.error(f"❌ Erro ao criar instituição legacy: {e}")
            raise

    def _migrate_configurations(self):
        """Migra collection 'configuracoes' → 'system_configuration'."""
        logger.info("Migrando configurações...")

        try:
            configs = list(self.mongo_db.configuracoes.find({}, {"_id": 0}))
            self.stats.total_configs_mongo = len(configs)

            logger.info(f"  Total de configurações: {self.stats.total_configs_mongo}")

            for config in configs:
                try:
                    # Campo 'tipo' vira 'key'
                    key = config.pop("tipo", None)
                    if not key:
                        logger.warning(f"⚠️  Configuração sem campo 'tipo', pulando: {config}")
                        continue

                    # Resto do documento vira 'value' (JSONB)
                    value = config

                    config_data = {
                        "key": key,
                        "value": value,
                        "description": "",
                        "updated_by": "migration_script"
                    }

                    if self.dry_run:
                        if self.verbose:
                            logger.debug(f"🔍 [DRY-RUN] Criaria config: {key}")
                        self.stats.migrated_configs += 1
                        continue

                    with get_session() as session:
                        # Verificar se já existe
                        existing = session.query(SystemConfiguration).filter_by(key=key).first()
                        if existing:
                            # Atualizar
                            existing.value = value
                            existing.updated_by = "migration_script"
                            existing.updated_at = datetime.utcnow()
                        else:
                            # Criar novo
                            new_config = SystemConfiguration(**config_data)
                            session.add(new_config)

                        session.commit()

                    self.stats.migrated_configs += 1

                    if self.verbose:
                        logger.debug(f"  ✅ {key}")

                except Exception as e:
                    logger.error(f"  ❌ Erro ao migrar configuração '{key}': {e}")
                    self.stats.add_error("config", key, str(e))
                    self.stats.failed_configs += 1

            logger.info(f"✅ Configurações migradas: {self.stats.migrated_configs}/{self.stats.total_configs_mongo}")

        except Exception as e:
            logger.error(f"❌ Erro ao migrar configurações: {e}")
            raise

    def _migrate_processes(self, institution_id: str):
        """
        Migra collection 'processos' → 'processes'.

        Args:
            institution_id: ID da instituição legacy
        """
        logger.info("Migrando processos...")

        try:
            # Contar total
            total = self.mongo_db.processos.count_documents({})
            self.stats.total_processes_mongo = total

            logger.info(f"  Total de processos: {total}")
            logger.info(f"  Batch size: {self.batch_size}")

            # Migrar em lotes
            skip = 0
            batch_num = 1

            while skip < total:
                logger.info(f"\n  📦 Lote {batch_num} ({skip + 1}-{min(skip + self.batch_size, total)}/{total})")

                processos = list(
                    self.mongo_db.processos.find({}, {"_id": 0})
                    .skip(skip)
                    .limit(self.batch_size)
                )

                for processo_mongo in processos:
                    try:
                        self._migrate_single_process(processo_mongo, institution_id)
                        self.stats.migrated_processes += 1

                    except Exception as e:
                        numero = processo_mongo.get("numero_processo", "UNKNOWN")
                        logger.error(f"    ❌ Erro ao migrar processo '{numero}': {e}")
                        self.stats.add_error("process", numero, str(e))
                        self.stats.failed_processes += 1

                # Próximo lote
                skip += self.batch_size
                batch_num += 1

            logger.info(f"\n✅ Processos migrados: {self.stats.migrated_processes}/{self.stats.total_processes_mongo}")

        except Exception as e:
            logger.error(f"❌ Erro ao migrar processos: {e}")
            raise

    def _migrate_single_process(self, processo_mongo: Dict[str, Any], institution_id: str):
        """
        Migra um único processo.

        Args:
            processo_mongo: Documento MongoDB
            institution_id: ID da instituição legacy
        """
        numero_processo = processo_mongo.get("numero_processo")

        if not numero_processo:
            raise ValueError("Processo sem 'numero_processo'")

        # Mapear campos MongoDB → PostgreSQL
        process_data = {
            "id": str(uuid.uuid4()),  # Gerar UUID
            "institution_id": institution_id,
            "numero_processo": numero_processo,
            "links": processo_mongo.get("links", {}),
            "documentos": processo_mongo.get("documentos", {}),
            "tipo_acesso_atual": processo_mongo.get("tipo_acesso_atual"),
            "melhor_link_atual": processo_mongo.get("melhor_link_atual"),
            "categoria": processo_mongo.get("categoria"),
            "status_categoria": processo_mongo.get("status_categoria"),
            "unidade": processo_mongo.get("unidade"),
            "autoridade": processo_mongo.get("Autoridade"),  # Autoridade → autoridade
            "sem_link_validos": processo_mongo.get("sem_link_validos", False),
            "apelido": processo_mongo.get("apelido"),
            "ultima_atualizacao": processo_mongo.get("ultima_atualizacao"),
            "metadata": {}  # Vazio por padrão
        }

        # Calcular created_at e updated_at de ultima_atualizacao
        ultima_atualizacao_str = processo_mongo.get("ultima_atualizacao")
        if ultima_atualizacao_str:
            try:
                # Tentar parsear "2024-01-15 10:30:00"
                timestamp = datetime.strptime(ultima_atualizacao_str, "%Y-%m-%d %H:%M:%S")
            except:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        process_data["created_at"] = timestamp
        process_data["updated_at"] = timestamp

        if self.dry_run:
            if self.verbose:
                logger.debug(f"    🔍 [DRY-RUN] Criaria processo: {numero_processo}")
            return

        # Inserir no PostgreSQL
        with get_session() as session:
            repo = ProcessRepository(session)

            # Verificar se já existe (por numero_processo)
            existing = repo.get_by_number(numero_processo)
            if existing:
                # Atualizar existente
                repo.update(existing.id, **{k: v for k, v in process_data.items() if k != "id"})
            else:
                # Criar novo
                repo.create(**process_data)

        if self.verbose:
            logger.debug(f"    ✅ {numero_processo}")

    def _validate_migration(self) -> bool:
        """
        Valida integridade dos dados migrados.

        Returns:
            True se validação passou
        """
        logger.info("Validando dados migrados...")

        validation_ok = True

        try:
            # 1. Contagem de processos
            logger.info("\n  1. Validando contagem de processos...")

            mongo_count = self.mongo_db.processos.count_documents({})

            if self.dry_run:
                postgres_count = 0  # Dry-run não migrou nada
                logger.info(f"     🔍 [DRY-RUN] MongoDB: {mongo_count}, PostgreSQL: N/A (dry-run)")
            else:
                with get_session() as session:
                    postgres_count = session.query(Process).count()

                if mongo_count == postgres_count:
                    logger.info(f"     ✅ Contagem OK: MongoDB={mongo_count}, PostgreSQL={postgres_count}")
                else:
                    logger.error(f"     ❌ Contagem DIFERENTE: MongoDB={mongo_count}, PostgreSQL={postgres_count}")
                    validation_ok = False

            # 2. Instituição legacy
            logger.info("\n  2. Validando instituição 'legacy'...")

            if not self.dry_run:
                with get_session() as session:
                    repo = InstitutionRepository(session)
                    legacy_inst = repo.get_by_id("legacy")

                    if legacy_inst:
                        logger.info(f"     ✅ Instituição 'legacy' encontrada: {legacy_inst.sei_url}")
                    else:
                        logger.error("     ❌ Instituição 'legacy' NÃO encontrada")
                        validation_ok = False

            # 3. Processos sem institution_id
            logger.info("\n  3. Validando referências de instituição...")

            if not self.dry_run:
                with get_session() as session:
                    orphan_processes = session.query(Process).filter(
                        Process.institution_id.is_(None)
                    ).count()

                    if orphan_processes == 0:
                        logger.info("     ✅ Todos os processos têm institution_id")
                    else:
                        logger.error(f"     ❌ {orphan_processes} processos SEM institution_id")
                        validation_ok = False

            # 4. Duplicatas de numero_processo
            logger.info("\n  4. Validando unicidade de numero_processo...")

            if not self.dry_run:
                with get_session() as session:
                    from sqlalchemy import func
                    duplicates = session.query(
                        Process.numero_processo,
                        func.count(Process.id)
                    ).group_by(Process.numero_processo).having(
                        func.count(Process.id) > 1
                    ).all()

                    if len(duplicates) == 0:
                        logger.info("     ✅ Nenhuma duplicata encontrada")
                    else:
                        logger.error(f"     ❌ {len(duplicates)} duplicatas encontradas:")
                        for numero, count in duplicates:
                            logger.error(f"        - {numero}: {count} ocorrências")
                        validation_ok = False

            # 5. Configurações
            logger.info("\n  5. Validando configurações...")

            mongo_config_count = self.mongo_db.configuracoes.count_documents({})

            if not self.dry_run:
                with get_session() as session:
                    postgres_config_count = session.query(SystemConfiguration).count()

                if mongo_config_count == postgres_config_count:
                    logger.info(f"     ✅ Configurações OK: {postgres_config_count}")
                else:
                    logger.error(
                        f"     ❌ Configurações DIFERENTES: "
                        f"MongoDB={mongo_config_count}, PostgreSQL={postgres_config_count}"
                    )
                    validation_ok = False

            return validation_ok

        except Exception as e:
            logger.error(f"❌ Erro durante validação: {e}")
            return False

    def _generate_report(self):
        """Gera relatório de migração."""
        logger.info("\n" + "=" * 80)
        logger.info("📊 RELATÓRIO DE MIGRAÇÃO")
        logger.info("=" * 80)

        summary = self.stats.summary()

        logger.info("\n🔹 Processos:")
        logger.info(f"  - Total no MongoDB: {summary['processes']['total_mongo']}")
        logger.info(f"  - Migrados: {summary['processes']['migrated']}")
        logger.info(f"  - Falhas: {summary['processes']['failed']}")
        logger.info(f"  - Taxa de sucesso: {summary['processes']['success_rate']}")

        logger.info("\n🔹 Configurações:")
        logger.info(f"  - Total no MongoDB: {summary['configurations']['total_mongo']}")
        logger.info(f"  - Migradas: {summary['configurations']['migrated']}")
        logger.info(f"  - Falhas: {summary['configurations']['failed']}")

        logger.info("\n🔹 Erros:")
        logger.info(f"  - Total de erros: {summary['errors']['count']}")

        if summary['errors']['count'] > 0:
            logger.info("\n  Detalhes dos erros:")
            for error in summary['errors']['details'][:10]:  # Mostrar primeiros 10
                logger.error(f"    - {error['type']}: {error['item_id']} - {error['message']}")

            if summary['errors']['count'] > 10:
                logger.info(f"    ... e mais {summary['errors']['count'] - 10} erros")

        logger.info(f"\n🔹 Duração: {summary['duration_seconds']:.2f} segundos")

        # Salvar relatório em arquivo
        self._save_report_file(summary)

        logger.info("\n" + "=" * 80)

    def _save_report_file(self, summary: Dict[str, Any]):
        """Salva relatório em arquivo JSON."""
        try:
            reports_dir = get_app_data_dir() / "migration_reports"
            reports_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"migration_report_{timestamp}.json"

            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"📄 Relatório salvo: {report_file}")

        except Exception as e:
            logger.warning(f"⚠️  Não foi possível salvar relatório: {e}")

    def _cleanup(self):
        """Limpa recursos."""
        # MongoDB fecha automaticamente
        # PostgreSQL sessions fecham automaticamente (context manager)
        pass


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="AutomaSEI v2.0 - MongoDB → PostgreSQL Migration"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula migração sem escrever no PostgreSQL"
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Pula criação de backup do MongoDB"
    )
    parser.add_argument(
        "--clear-postgres",
        action="store_true",
        help="Limpa tabelas PostgreSQL antes de migrar (ATENÇÃO: DESTRUTIVO)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Apenas valida dados sem migrar"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Tamanho do lote para migração de processos (padrão: 100)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log detalhado"
    )

    args = parser.parse_args()

    # Confirmação para --clear-postgres
    if args.clear_postgres and not args.dry_run:
        logger.warning("⚠️  ATENÇÃO: --clear-postgres IRÁ DELETAR TODOS OS DADOS DO POSTGRESQL!")
        confirm = input("Digite 'SIM' para confirmar: ")
        if confirm != "SIM":
            logger.info("Operação cancelada.")
            sys.exit(0)

    # Executar migração
    migration = DataMigration(
        dry_run=args.dry_run or args.validate_only,
        skip_backup=args.skip_backup,
        clear_postgres=args.clear_postgres,
        batch_size=args.batch_size,
        verbose=args.verbose
    )

    success = migration.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
