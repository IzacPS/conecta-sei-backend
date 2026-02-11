from typing import Dict, Optional
import datetime
from connect_mongo import get_database
from logger_system import UILogger

def salvar_historico_documento(registro: Dict):
    """
    Salva um registro de operação de documento (download/upload) no histórico.
    
    O registro deve conter:
    - processo_numero: número do processo
    - documento_numero: número do documento
    - tipo_operacao: "download", "upload" ou "completo"
    - timestamp_inicio: quando a operação começou
    - timestamp_fim: quando a operação terminou (opcional)
    - resultado: "sucesso", "falha", "pendente"
    - erro: mensagem de erro em caso de falha (opcional)
    - detalhes: informações adicionais (opcional)
    """
    try:
        db = get_database()
        col_historico = db.documentos_historico
        
        # Garantir que o registro tenha os campos necessários
        if not all(k in registro for k in ["processo_numero", "documento_numero", "tipo_operacao", "timestamp_inicio", "resultado"]):
            logger = UILogger()
            logger.log(f"Registro de histórico incompleto: faltam campos obrigatórios")
            return
        
        # Assegurar que timestamp_fim existe
        if "timestamp_fim" not in registro:
            registro["timestamp_fim"] = datetime.datetime.now()
            
        # Calcular duração
        if "duracao_ms" not in registro:
            try:
                duracao = (registro["timestamp_fim"] - registro["timestamp_inicio"]).total_seconds() * 1000
                registro["duracao_ms"] = duracao
            except:
                registro["duracao_ms"] = 0
                
        # Adicionar timestamp de gravação no banco
        registro["timestamp_gravacao"] = datetime.datetime.now()
        
        # Inserir no MongoDB
        col_historico.insert_one(registro)
        
        logger = UILogger()
        logger.log(f"Registro de histórico salvo para o documento {registro['documento_numero']}")
        
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao salvar histórico do documento: {str(e)}")


def criar_indices_historico():
    """
    Cria índices na coleção de histórico para otimizar consultas.
    """
    try:
        db = get_database()
        col_historico = db.documentos_historico
        
        # Índices para pesquisas comuns
        col_historico.create_index("processo_numero")
        col_historico.create_index("documento_numero")
        col_historico.create_index("resultado")
        col_historico.create_index("timestamp_inicio")
        col_historico.create_index([("processo_numero", 1), ("documento_numero", 1)])
        
        logger = UILogger()
        logger.log("Índices criados na coleção de histórico de documentos")
        
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao criar índices na coleção de histórico: {str(e)}")


def obter_estatisticas_historico():
    """
    Retorna estatísticas sobre as operações de documentos.
    """
    try:
        db = get_database()
        col_historico = db.documentos_historico
        
        # Total de operações
        total = col_historico.count_documents({})
        
        # Por resultado
        sucessos = col_historico.count_documents({"resultado": "sucesso"})
        falhas = col_historico.count_documents({"resultado": "falha"})
        pendentes = col_historico.count_documents({"resultado": "pendente"})
        
        # Por tipo de operação
        downloads = col_historico.count_documents({"tipo_operacao": "download"})
        uploads = col_historico.count_documents({"tipo_operacao": "upload"})
        completos = col_historico.count_documents({"tipo_operacao": "completo"})
        
        # Tempos médios
        pipeline_tempos = [
            {"$match": {"resultado": "sucesso"}},
            {"$group": {
                "_id": "$tipo_operacao",
                "duracao_media": {"$avg": "$duracao_ms"},
                "contagem": {"$sum": 1}
            }}
        ]
        
        tempos_medios = {}
        for resultado in col_historico.aggregate(pipeline_tempos):
            tempos_medios[resultado["_id"]] = {
                "duracao_media_ms": resultado["duracao_media"],
                "contagem": resultado["contagem"]
            }
        
        return {
            "total_operacoes": total,
            "resultados": {
                "sucessos": sucessos,
                "falhas": falhas,
                "pendentes": pendentes
            },
            "por_tipo": {
                "downloads": downloads,
                "uploads": uploads,
                "completos": completos
            },
            "tempos_medios": tempos_medios,
            "timestamp_consulta": datetime.datetime.now()
        }
        
    except Exception as e:
        logger = UILogger()
        logger.log(f"Erro ao obter estatísticas de histórico: {str(e)}")
        return {}
