"""
Seed de dados para testar o fluxo scraper + pagamento.

Cria:
- Usuário admin: dev@automasei.local (role=admin) — usado como dev padrão sem header
- Usuário cliente: client@automasei.local (role=user) — testar como cliente com X-Dev-User-Email
- Instituição inativa "SEI Teste" vinculada ao cliente
- Uma PipelineRequest em status pending_scraper para o cliente

Uso (na raiz do projeto, com .env configurado):
    python scripts/seed-test-data.py

Requer: PostgreSQL rodando, migrations aplicadas (alembic upgrade head).
"""

import os
import sys

# Garante que .env seja carregado antes de importar app (session usa DATABASE_URL)
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.chdir(root)

from dotenv import load_dotenv
load_dotenv()

from app.database.session import get_session
from app.database.models.user import User
from app.database.models.institution import Institution
from app.database.models.pipeline_request import PipelineRequest


ADMIN_EMAIL = "dev@automasei.local"
ADMIN_UID = "dev-uid-001"
CLIENT_EMAIL = "client@automasei.local"
CLIENT_UID = "dev-client"
SEI_URL = "https://sei.exemplo.gov.br/sei"
INSTITUTION_NAME = "SEI Teste"


def main() -> None:
    with get_session() as session:
        # Admin (dev padrão no Swagger sem header)
        admin = session.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not admin:
            admin = User(
                firebase_uid=ADMIN_UID,
                email=ADMIN_EMAIL,
                display_name="Developer",
                role="admin",
                is_active=True,
            )
            session.add(admin)
            session.flush()
            print(f"  Criado admin: {ADMIN_EMAIL} (id={admin.id})")
        else:
            admin.role = "admin"
            print(f"  Admin já existe: {ADMIN_EMAIL} (id={admin.id})")

        # Cliente (impersonar com X-Dev-User-Email: client@automasei.local)
        client = session.query(User).filter(User.email == CLIENT_EMAIL).first()
        if not client:
            client = User(
                firebase_uid=CLIENT_UID,
                email=CLIENT_EMAIL,
                display_name="Cliente Teste",
                role="user",
                is_active=True,
            )
            session.add(client)
            session.flush()
            print(f"  Criado cliente: {CLIENT_EMAIL} (id={client.id})")
        else:
            print(f"  Cliente já existe: {CLIENT_EMAIL} (id={client.id})")

        # Instituição inativa (como no fluxo pending_scraper)
        inst = session.query(Institution).filter(
            Institution.sei_url == SEI_URL,
            Institution.name == INSTITUTION_NAME,
        ).first()
        if not inst:
            inst = Institution(
                user_id=client.id,
                name=INSTITUTION_NAME,
                sei_url=SEI_URL,
                is_active=False,
                extra_metadata={},
            )
            session.add(inst)
            session.flush()
            print(f"  Criada instituição: {INSTITUTION_NAME} (id={inst.id}, is_active=False)")
        else:
            print(f"  Instituição já existe: {INSTITUTION_NAME} (id={inst.id})")

        # PipelineRequest em pending_scraper para o cliente
        existing = session.query(PipelineRequest).filter(
            PipelineRequest.user_id == client.id,
            PipelineRequest.status == "pending_scraper",
            PipelineRequest.institution_id == inst.id,
        ).first()
        if not existing:
            pr = PipelineRequest(
                user_id=client.id,
                sei_url=SEI_URL,
                institution_name=INSTITUTION_NAME,
                detected_version="4.2.0",
                detected_family="v1",
                scraper_available=False,
                status="pending_scraper",
                institution_id=inst.id,
            )
            session.add(pr)
            session.flush()
            print(f"  Criada solicitação: pending_scraper (id={pr.id}) — use para orçamento/pagamento/entrega")
        else:
            print(f"  Solicitação pending_scraper já existe (id={existing.id})")

    print("\nSeed concluído. Para testar como cliente no Swagger, use header:")
    print("  X-Dev-User-Email: client@automasei.local")
    print("  (com AUTH_DEV_MODE=true)")


if __name__ == "__main__":
    main()
