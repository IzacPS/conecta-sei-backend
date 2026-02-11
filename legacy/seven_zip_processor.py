from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import subprocess
import os
import re
from dataclasses import dataclass

@dataclass
class SplitFilesGroup:
    base_name: str
    all_parts: List[Path]
    main_part: Path

class SevenZipSplitProcessor:
    def __init__(self, log_function=print):
        self.log = log_function
        self.split_groups: List[SplitFilesGroup] = []
        
    def _normalize_split_name(self, filename: str) -> str:
        base = re.sub(r'\.zip$', '', filename)
        base = re.sub(r'\.\d{3}$', '', base)
        return base
        
    def _find_split_files(self, directory: Path) -> List[Path]:
        split_files = []
        for file in directory.rglob("*"):
            if not file.is_file():
                continue
            if not ("SDCOMdividido" in file.name and re.search(r'\.\d{3}($|\.)', file.name)):
                continue
            split_files.append(file)
        return split_files
        
    def _group_related_files(self, files: List[Path]) -> List[SplitFilesGroup]:
        groups_dict: Dict[str, List[Path]] = {}
        
        for file in files:
            base_name = self._normalize_split_name(file.name)
            if base_name not in groups_dict:
                groups_dict[base_name] = []
            groups_dict[base_name].append(file)
        
        groups = []
        for base_name, file_list in groups_dict.items():
            main_part = next(
                (f for f in file_list if f.name.endswith('.001')),
                next((f for f in file_list if '.001.' in f.name), None)
            )
            
            if main_part:
                groups.append(SplitFilesGroup(
                    base_name=base_name,
                    all_parts=sorted(file_list, key=lambda x: x.name),
                    main_part=main_part
                ))
        
        return groups
            
    def _extract_split_file(self, group: SplitFilesGroup, output_dir: Path) -> bool:
        try:
           
            exe_path = Path(__file__).parent / "7za.exe"
            if not exe_path.exists():
                exe_path = Path(os.getcwd()) / "7za.exe"
                if not exe_path.exists():
                    raise FileNotFoundError("7za.exe não encontrado")
            
            output_dir.mkdir(exist_ok=True)
            
            main_file = str(group.main_part)
            if main_file.endswith('.zip'):
                main_file_base = main_file[:-4]
                for part in group.all_parts:
                    if part.suffix == '.zip':
                        part_no_zip = part.with_suffix('')
                        if not part_no_zip.exists():
                            os.rename(part, part_no_zip)
            else:
                main_file_base = main_file
            
            cmd = [
                str(exe_path),
                "x",
                main_file_base,
                f"-o{output_dir}",
                "-y"
            ]
                        
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                self.log(f"Saída do 7zip: {process.stdout}")
                self.log(f"Erro do 7zip: {process.stderr}")
                return False
                                
            return True
            
        except Exception as e:
            self.log(f"Erro ao extrair arquivo splitado: {str(e)}")
            return False
        
    def process_files(self, user_files_path: Path, sei_files_path: Path) -> bool:
        try:
            self.log("\nIniciando processamento de arquivos quebrados...")
            
            user_splits = self._find_split_files(user_files_path)
            sei_splits = self._find_split_files(sei_files_path)
            
            self.log(f"\nEncontrados {len(user_splits)} arquivos quebrados do usuário")
            self.log(f"Encontrados {len(sei_splits)} arquivos quebrados do SEI")
            
            user_groups = self._group_related_files(user_splits)
            sei_groups = self._group_related_files(sei_splits)
                        
            success = True
            for group in user_groups:
                output_dir = user_files_path / "extracted"
                if not self._extract_split_file(group, output_dir):
                    success = False
                self.split_groups.append(group)
            
            for group in sei_groups:
                output_dir = sei_files_path / "extracted"
                if not self._extract_split_file(group, output_dir):
                    success = False
                self.split_groups.append(group)
            
            self.log(f"\nTotal de grupos processados: {len(self.split_groups)}")
            return success
            
        except Exception as e:
            self.log(f"Erro no processamento de arquivos splitados: {str(e)}")
            return False
            
    def should_ignore_file(self, file_path: Path) -> bool:
        if not self.split_groups:
            return False
            
        for group in self.split_groups:
            if file_path in group.all_parts:
                return True
                
        return False

