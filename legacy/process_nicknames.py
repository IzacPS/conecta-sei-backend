from typing import Dict, Optional
from connect_mongo import get_database


def set_process_nickname(process_number: str, nickname: str) -> bool:
    try:
        db = get_database()
        collection = db.processos

        processo = collection.find_one({"numero_processo": process_number})
        if not processo:
            print(f"Processo {process_number} não encontrado.")
            return False

        existing_nickname = collection.find_one({"apelido": nickname})
        if existing_nickname and existing_nickname["numero_processo"] != process_number:
            print(
                f"Aviso: O apelido '{nickname}' já estava associado ao processo {existing_nickname['numero_processo']}"
            )

        collection.update_one(
            {"numero_processo": process_number}, {"$set": {"apelido": nickname}}
        )

        print(f"Apelido '{nickname}' definido para o processo {process_number}")
        return True

    except Exception as e:
        print(f"Erro ao definir apelido: {str(e)}")
        return False


def get_process_by_nickname(nickname: str) -> Optional[str]:
    try:
        db = get_database()
        collection = db.processos

        processo = collection.find_one({"apelido": nickname})
        if processo:
            return processo["numero_processo"]

        print(f"Nenhum processo encontrado com o apelido '{nickname}'")
        return None

    except Exception as e:
        print(f"Erro ao buscar processo por apelido: {str(e)}")
        return None


def list_process_nicknames() -> Dict[str, str]:
    try:
        db = get_database()
        collection = db.processos

        processos = collection.find({"apelido": {"$exists": True}})
        return {
            processo["apelido"]: processo["numero_processo"] for processo in processos
        }

    except Exception as e:
        print(f"Erro ao listar apelidos: {str(e)}")
        return {}


def remove_process_nickname(process_number: str) -> bool:
    try:
        db = get_database()
        collection = db.processos

        processo = collection.find_one({"numero_processo": process_number})
        if not processo:
            print(f"Processo {process_number} não encontrado.")
            return False

        if "apelido" in processo:
            collection.update_one(
                {"numero_processo": process_number}, {"$unset": {"apelido": ""}}
            )
            print(f"Apelido removido do processo {process_number}")
            return True
        else:
            print(f"Processo {process_number} não possui apelido.")
            return False

    except Exception as e:
        print(f"Erro ao remover apelido: {str(e)}")
        return False


if __name__ == "__main__":
    pass
