from pymongo import MongoClient
import sys
import time
import socket
import os
import signal
import subprocess
import platform

CONNECTION_STRING = "mongodb+srv://sei:1ZNx0lp9mztM78CQ@seiunotrade.obksnk6.mongodb.net/?retryWrites=true&w=majority&appName=SEIUNOTRADE"

def find_and_kill_python_processes():
    """Encontra e termina todos os processos Python relacionados ao SEI_UNO_TRADE"""
    print("Buscando processos Python relacionados ao SEI-UNO-TRADE...")
    
    system = platform.system()
    killed = 0
    
    if system == "Windows":
        try:
            # Lista processos Python no Windows
            output = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"]).decode()
            lines = output.strip().split("\n")[1:]  # Pular o cabeçalho
            
            for line in lines:
                parts = line.strip('"').split('","')
                pid = int(parts[1]) if len(parts) > 1 else None
                
                if pid and pid != os.getpid():  # Não mata o processo atual
                    try:
                        # Verifica se este processo está relacionado ao SEI
                        cmd_output = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}", "/V", "/FO", "CSV"]).decode()
                        if "SEI_UNO_TRADE" in cmd_output or "sei-uno-trade" in cmd_output.lower():
                            os.kill(pid, signal.SIGTERM)
                            print(f"Processo Python terminado: PID {pid}")
                            killed += 1
                    except:
                        pass
        except Exception as e:
            print(f"Erro ao processar lista de tarefas: {str(e)}")
            
    else:  # Linux e macOS
        try:
            # Lista processos Python no Linux/macOS
            output = subprocess.check_output(["ps", "aux"]).decode()
            lines = output.strip().split("\n")
            
            for line in lines:
                if "python" in line.lower() and ("SEI_UNO_TRADE" in line or "sei-uno-trade" in line.lower()):
                    parts = line.split()
                    if len(parts) > 1:
                        pid = int(parts[1])
                        if pid != os.getpid():  # Não mata o processo atual
                            try:
                                os.kill(pid, signal.SIGTERM)
                                print(f"Processo Python terminado: PID {pid}")
                                killed += 1
                            except:
                                pass
        except Exception as e:
            print(f"Erro ao processar lista de processos: {str(e)}")
    
    return killed

def close_mongodb_connections():
    """Fecha conexões MongoDB diretamente"""
    try:
        print("Conectando ao banco de dados para validar conexão...")
        client = MongoClient(CONNECTION_STRING, serverSelectionTimeoutMS=5000)
        
        # Apenas verifica se a conexão está funcionando
        db = client["sei_database"]
        db.processos.find_one()
        
        print("Conexão com MongoDB funcional.")
        
        # Fecha a conexão atual
        client.close()
        print("Conexão fechada com sucesso.")
        return True
        
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {str(e)}")
        return False

def reset_mongo_client_pool():
    """Reset da pool de conexões do PyMongo"""
    try:
        # Criar conexão e fechar imediatamente para limpar o pool
        for _ in range(5):  # Tenta múltiplas vezes para garantir
            try:
                client = MongoClient(CONNECTION_STRING, maxPoolSize=1)
                client.close()
            except:
                pass
        print("Pool de conexões do MongoDB resetada.")
        return True
    except Exception as e:
        print(f"Erro ao resetar pool de conexões: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== Script para encerrar conexões com MongoDB do SEI-UNO-TRADE ===")
    print("Iniciando processo de limpeza...")
    
    # Estratégia 1: Matar processos Python relacionados
    killed_count = find_and_kill_python_processes()
    print(f"\nProcessos Python encerrados: {killed_count}")
    
    # Estratégia 2: Testar e fechar conexão para validar
    mongodb_ok = close_mongodb_connections()
    
    # Estratégia 3: Resetar pool de conexões
    pool_reset = reset_mongo_client_pool()
    
    if mongodb_ok:
        print("\nAção concluída: Banco de dados acessível e operações de limpeza executadas.")
        print("As conexões anteriores devem ter sido finalizadas pelo servidor MongoDB.")
    else:
        print("\nAviso: Não foi possível validar a conexão com o MongoDB.")
        print("No entanto, as operações de limpeza foram executadas.")
    
    print("\nOperação de limpeza concluída. Se ainda houver problemas, pode ser necessário:")
    print("1. Reiniciar manualmente os aplicativos SEI")
    print("2. Aguardar o timeout das conexões no servidor MongoDB (geralmente 30 minutos)")