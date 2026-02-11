from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING, TEXT
import logging
from typing import Dict, List, Optional

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mongo-indexes")

CONNECTION_STRING = "mongodb+srv://sei:1ZNx0lp9mztM78CQ@seiunotrade.obksnk6.mongodb.net/?retryWrites=true&w=majority&appName=SEIUNOTRADE"

def get_database(db_name="sei_database"):
    try:
        client = MongoClient(CONNECTION_STRING)
        db = client[db_name]
        return db, client
    except Exception as e:
        logger.error(f"Erro ao conectar ao MongoDB: {str(e)}")
        raise

def create_indexes():
    db, client = get_database()
    try:
        # Índices para a coleção 'processos'
        process_indexes = [
            IndexModel([("numero_processo", ASCENDING)], unique=True, name="idx_numero_processo"),
            IndexModel([("apelido", ASCENDING)], sparse=True, name="idx_apelido"),
            IndexModel([("categoria", ASCENDING)], name="idx_categoria"),
            IndexModel([("status_categoria", ASCENDING)], name="idx_status_categoria"),
            IndexModel([("tipo_acesso_atual", ASCENDING)], name="idx_tipo_acesso"),
            IndexModel([("sem_link_validos", ASCENDING)], name="idx_sem_links"),
            IndexModel([("ultima_atualizacao", DESCENDING)], name="idx_ultima_atualizacao"),
            IndexModel([("ultima_verificacao", DESCENDING)], name="idx_ultima_verificacao"),
        ]
        
        # Criar índices na coleção de processos
        result = db.processos.create_indexes(process_indexes)
        logger.info(f"Índices criados na coleção 'processos': {result}")
        
        # Índices para a coleção 'documentos_historico'
        doc_hist_indexes = [
            IndexModel([("processo_numero", ASCENDING)], name="idx_hist_processo"),
            IndexModel([("documento_numero", ASCENDING)], name="idx_hist_documento"),
            IndexModel([("resultado", ASCENDING)], name="idx_hist_resultado"),
            IndexModel([("timestamp_inicio", DESCENDING)], name="idx_hist_timestamp"),
            IndexModel([("tipo_operacao", ASCENDING)], name="idx_hist_tipo_operacao"),
            IndexModel([("processo_numero", ASCENDING), ("documento_numero", ASCENDING)], name="idx_processo_documento")
        ]
        
        # Criar índices na coleção de histórico de documentos
        result = db.documentos_historico.create_indexes(doc_hist_indexes)
        logger.info(f"Índices criados na coleção 'documentos_historico': {result}")
        
        # Índices para a coleção 'configuracoes'
        config_indexes = [
            IndexModel([("tipo", ASCENDING)], unique=True, name="idx_config_tipo")
        ]
        
        # Criar índices na coleção de configurações
        result = db.configuracoes.create_indexes(config_indexes)
        logger.info(f"Índices criados na coleção 'configuracoes': {result}")
        
        logger.info("Criação de índices concluída com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro ao criar índices: {str(e)}")
    finally:
        client.close()

def list_existing_indexes():
    db, client = get_database()
    try:
        collections = ["processos", "documentos_historico", "configuracoes"]
        
        for collection_name in collections:
            collection = db[collection_name]
            indexes = list(collection.list_indexes())
            
            logger.info(f"\nÍndices na coleção '{collection_name}':")
            for index in indexes:
                logger.info(f"  - {index['name']}: {index['key']}")
    
    except Exception as e:
        logger.error(f"Erro ao listar índices: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    logger.info("Iniciando criação de índices...")
    create_indexes()
    logger.info("\nListando índices existentes:")
    list_existing_indexes()