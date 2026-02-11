from utils import load_process_data, save_process_data
from logger_system import UILogger
import datetime
import re
from typing import Dict, Tuple, Optional
from documento_historico import salvar_historico_documento
from connect_mongo import get_database

def parse_date(date_str: str) -> Optional[datetime.datetime]:
    """
    Tenta analisar uma string de data em vários formatos possíveis.
    Retorna None se não conseguir converter.
    """
    formats = [
        "%Y-%m-%d %H:%M:%S",  # 2025-01-21 07:14:50
        "%d/%m/%Y",           # 22/03/2024
        "%d/%m/%Y %H:%M:%S",  # 22/03/2024 07:14:50
        "%Y-%m-%d"            # 2025-01-21
    ]
    
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    
    return None

def analisa_documento(doc_info: Dict, doc_number: str, processo_number: str) -> Tuple[bool, str]:
    """
    Analisa um documento para determinar se ele deve ser redefinido.
    Retorna uma tupla (deve_redefinir, motivo).
    """
    current_date = datetime.datetime.now()
    motivo = ""
    
    # Verificar se tem status 'baixado' primeiro
    if doc_info.get("status") != "baixado":
        return False, ""
    
    # Extrair e validar datas
    ult_verif_str = doc_info.get("ultima_verificacao", "")
    prim_visual_str = doc_info.get("primeira_visualizacao", "")
    data_doc_str = doc_info.get("data", "")
    
    ult_verif = parse_date(ult_verif_str) if ult_verif_str else None
    prim_visual = parse_date(prim_visual_str) if prim_visual_str else None
    data_doc = parse_date(data_doc_str) if data_doc_str else None
    
    # Verificar datas futuras
    if ult_verif and ult_verif > current_date:
        return True, f"Data de última verificação futura: {ult_verif_str}"
    
    if prim_visual and prim_visual > current_date:
        return True, f"Data de primeira visualização futura: {prim_visual_str}"
    
    # Verificar se a primeira visualização é anterior à data do documento
    if prim_visual and data_doc and prim_visual.date() < data_doc.date():
        return True, f"Data de visualização ({prim_visual_str}) anterior à data do documento ({data_doc_str})"
    
    # Verificar se há registro de download no histórico
    try:
        db = get_database()
        historico_col = db.documentos_historico
        
        # Buscar registros de download bem-sucedidos
        registro = historico_col.find_one({
            "processo_numero": processo_number,
            "documento_numero": doc_number,
            "resultado": "sucesso"
        })
        
        if not registro:
            return True, "Documento marcado como baixado, mas sem registro de download no histórico"
    except Exception as e:
        # Se falhar ao verificar histórico, logar mas não resetar 
        # apenas por esse motivo
        pass
    
    return False, motivo

def fix_document_status():
    """
    Corrige os documentos incorretamente marcados como 'baixado' sem terem sido
    efetivamente baixados e enviados ao SharePoint.
    """
    logger = UILogger()
    logger.log("Iniciando correção dos status de documentos...")
    
    # Carrega todos os processos
    processes = load_process_data()
    if not processes:
        logger.log("Nenhum processo encontrado na base de dados.")
        return

    # Estatísticas para relatório
    total_processes = len(processes)
    changed_docs_count = 0
    affected_processes = 0
    
    # Processar cada processo
    for i, (process_number, process_data) in enumerate(processes.items(), 1):
        logger.log(f"Verificando processo {process_number} ({i}/{total_processes})")
        
        # Verificar se o processo tem documentos
        if not process_data.get("documentos"):
            continue
            
        process_modified = False
        novos_docs = []
        
        # Para cada documento do processo
        for doc_number, doc_info in list(process_data["documentos"].items()):
            # Analisar o documento
            should_reset, motivo = analisa_documento(doc_info, doc_number, process_number)
            
            # Resetar status se necessário
            if should_reset:
                old_status = doc_info["status"]
                doc_info["status"] = "nao_baixado"
                process_modified = True
                changed_docs_count += 1
                novos_docs.append(doc_number)
                
                logger.log(
                    f"  - Documento {doc_number} (tipo: {doc_info.get('tipo', 'N/A')}) " +
                    f"com data {doc_info.get('data', 'N/A')} alterado de " +
                    f"'{old_status}' para 'nao_baixado'. Motivo: {motivo}"
                )
                
                # Registrar mudança no histórico
                try:
                    registro_historico = {
                        "processo_numero": process_number,
                        "documento_numero": doc_number,
                        "tipo_documento": doc_info.get("tipo", "Desconhecido"),
                        "timestamp_inicio": datetime.datetime.now(),
                        "timestamp_fim": datetime.datetime.now(),
                        "tipo_operacao": "correcao_status",
                        "resultado": "sucesso",
                        "detalhes": f"Status alterado de {old_status} para nao_baixado. Motivo: {motivo}",
                        "apelido_processo": process_data.get("apelido", "")
                    }
                    salvar_historico_documento(registro_historico)
                except Exception:
                    pass
        
        # Atualizar a lista de novos documentos
        if process_modified:
            affected_processes += 1
            
            if novos_docs:
                process_data["novos_documentos"] = novos_docs
                logger.log(f"  - Adicionados {len(novos_docs)} documentos à lista de novos documentos")
            elif "novos_documentos" in process_data:
                process_data.pop("novos_documentos", None)
    
    # Salvar as alterações de volta na base de dados
    if changed_docs_count > 0:
        save_process_data(processes)
        logger.log(
            f"\nOperação concluída. {changed_docs_count} documentos corrigidos " +
            f"em {affected_processes} processos."
        )
    else:
        logger.log("Nenhum documento encontrado para ser corrigido.")

if __name__ == "__main__":
    fix_document_status()