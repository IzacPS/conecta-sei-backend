from pathlib import Path
import hashlib
import zipfile
import re
from typing import Dict, List, Set, Optional, Tuple
import datetime
import os
import tempfile
import shutil
from pathlib import Path


class FileProcessor:
    def __init__(self, log_function=print):
        self.log = log_function
        self._hash_cache = {}
        self.temp_extractions = []
        self.temp_base_dir = None

    def copy_to_temp(self, source_dir: Path) -> Path:
        temp_base_dir = self.create_temp_directory("user_files")
        self.temp_base_dir = temp_base_dir
        
        user_files_temp = temp_base_dir / "user_files"
        user_files_temp.mkdir(exist_ok=True)
        
        for file_path in source_dir.rglob("*"):
            if not file_path.is_file():
                continue
                
            relative_path = file_path.relative_to(source_dir)
            temp_file_path = user_files_temp / relative_path
            temp_file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, temp_file_path)
            
        return user_files_temp

    def create_temp_directory(self, base_name: str) -> Path:
        base_path = Path(os.getenv("LOCALAPPDATA")) / "SEI_UNO_TRADE"
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        temp_dir = base_path / f"{base_name}_{current_time}"
        
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True)
        
        return temp_dir

    def cleanup_temp_files(self):
        if self.temp_base_dir and self.temp_base_dir.exists():
            shutil.rmtree(self.temp_base_dir, ignore_errors=True)
        
        for temp_dir in self.temp_extractions:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        self.temp_extractions.clear()
        self._hash_cache.clear()
        self.temp_base_dir = None

    def get_file_hash(self, file_path: Path) -> str:
        if str(file_path) in self._hash_cache:
            return self._hash_cache[str(file_path)]
        
        hash_func = hashlib.sha256()
        with file_path.open("rb") as f:
            while chunk := f.read(8192):
                hash_func.update(chunk)
        
        file_hash = hash_func.hexdigest()
        self._hash_cache[str(file_path)] = file_hash
        return file_hash

    def verify_document_type(self, file_path: Path, expected_type: str) -> Dict:
        filename = file_path.name.upper()
        vr_patterns = [r"\bVR\b", r"\bRESTRITO\b", r"\bRESTRICTED\b", r"\bREST\b"]
        vc_patterns = [r"\bVC\b", r"\bCONFIDENCIAL\b", r"\bCONFIDENTIAL\b", r"\bCONF\b"]
        
        detected_type = "UNKNOWN"
        if any(re.search(pattern, filename) for pattern in vr_patterns):
            detected_type = "VR"
        elif any(re.search(pattern, filename) for pattern in vc_patterns):
            detected_type = "VC"

        return {
            "filename": file_path.name,
            "expected_type": expected_type,
            "detected_type": detected_type,
            "matches": expected_type == detected_type,
            "should_be_marked": expected_type != "UNKNOWN" and detected_type == "UNKNOWN",
            "wrong_type": detected_type != "UNKNOWN" and detected_type != expected_type,
            "missing_type": detected_type == "UNKNOWN",
        }

    def extract_zip_recursive(self, zip_path: Path, extract_to: Path) -> List[Path]:
        extracted_files = []
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_to)
            
            for file_name in zip_ref.namelist():
                file_path = extract_to / file_name
                if file_path.suffix.lower() == ".zip":
                    nested_files = self.extract_zip_recursive(file_path, file_path.parent)
                    extracted_files.extend(nested_files)
                else:
                    extracted_files.append(file_path)
                    
        return extracted_files

    def process_directory(self, directory_path: Path, split_processor=None, process_zip: bool = True, origin: str = "user") -> Dict[str, Dict]:
        files_data = {}
        
        for file_path in directory_path.rglob("*"):
            if not file_path.is_file():
                continue
                
            if split_processor and split_processor.should_ignore_file(file_path):
                continue
                
            is_split_part = "SDCOMdividido" in file_path.name and re.search(r'\.\d{3}($|\.)', file_path.name)
            
            if process_zip and file_path.suffix.lower() == ".zip" and not is_split_part:
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(directory_path)
                        
                    for extracted_file in directory_path.rglob("*"):
                        if not extracted_file.is_file() or extracted_file == file_path:
                            continue
                            
                        file_hash = self.get_file_hash(extracted_file)
                        files_data[file_hash] = {
                            "file_path": file_path,
                            "extracted_name": extracted_file.name,
                            "is_zipped": True,
                            "status": "pending",
                            "origin": origin
                        }
                        
                except Exception as e:
                    self.log(f"Erro ao processar ZIP {file_path.name}: {str(e)}")
                    continue
            else:
                file_hash = self.get_file_hash(file_path)
                files_data[file_hash] = {
                    "file_path": file_path,
                    "is_zipped": False,
                    "status": "pending",
                    "origin": origin
                }
        
        return files_data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_temp_files()
