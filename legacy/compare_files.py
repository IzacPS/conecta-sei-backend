import threading
import queue
import datetime
import json
import os
import re
import zipfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Set, Union
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
from file_processor import FileProcessor
from seven_zip_processor import SevenZipSplitProcessor
from utils import get_app_data_dir

class FileComparator:
    def __init__(self, process_url: str, user_files_path: str, doc_type: str, log_function=print):
        self.process_url = process_url
        self.user_files_path = Path(user_files_path)
        self.doc_type = doc_type
        self.log = log_function
        self.browser = None
        self.page = None
        self.playwright = None
        self.temp_dir = None
        self.process_number = None
        self.file_processor = FileProcessor(log_function)
        
        self.user_files_data = {}
        self.sei_files_data = {}
        
        self.validation_results = {
            "matched_files": {},
            "unmatched_user_files": {},
            "unexpected_sei_files": {},
            "type_mismatches": {},
        }
        
        self._validate_inputs()

    def _validate_inputs(self):
        if self.doc_type not in ["VC", "VR"]:
            raise ValueError("Document type must be 'VC' or 'VR'")
        if not self.user_files_path.exists():
            raise FileNotFoundError(f"User files path does not exist: {self.user_files_path}")

    def process_user_files(self):
        self.log("\nETAPA 1: Processando arquivos do usuário")
        
        user_files_temp = self.file_processor.copy_to_temp(self.user_files_path)
        
        split_processor = SevenZipSplitProcessor(self.log)
        
        if not split_processor.process_files(user_files_temp, user_files_temp):
            raise Exception("Falha no processamento 7zip dos arquivos do usuário")
            
        self.user_files_data = self.file_processor.process_directory(
            user_files_temp,
            split_processor=split_processor,
            origin="user"
        )
        
        self.log(f"Total de arquivos do usuário processados: {len(self.user_files_data)}")
        return user_files_temp

    def init_browser(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        self.page.set_default_timeout(30000)

    def login(self):
        from utils import login_to_sei
        try:
            login_to_sei(self.page)
        except Exception as e:
            self.log_queue.put(f"Erro de login: {str(e)}")
            raise

    def extract_process_number(self):
        process_text = self.page.locator('//*[@id="tblCabecalho"]/tbody/tr[2]/td[2]').inner_text().strip()
        self.process_number = re.sub("[^0-9]", "", process_text)
        return self.process_number

    def find_latest_receipt(self) -> Optional[str]:
        self.log("\nBuscando o recibo eletrônico mais recente...")
        receipts = self.page.query_selector_all('tr.infraTrClara td:text-is("Recibo Eletrônico de Protocolo ")')
        
        if not receipts:
            self.log("Nenhum recibo eletrônico encontrado")
            return None
            
        latest_receipt_row = receipts[-1].query_selector("xpath=..")
        if not latest_receipt_row:
            return None
            
        receipt_link = latest_receipt_row.query_selector("td:nth-child(2) a")
        if not receipt_link:
            return None
            
        self.log(f"Abrindo recibo número: {receipt_link.text_content().strip()}")
        
        with self.page.context.expect_page() as new_page_info:
            receipt_link.click(modifiers=["Control"])
        receipt_page = new_page_info.value
        receipt_page.wait_for_load_state("networkidle")
        
        content = receipt_page.content()
        receipt_page.close()
        return content

    def extract_document_numbers(self, html_content: str) -> Set[str]:
        soup = BeautifulSoup(html_content, "html.parser")
        document_numbers = {td.get_text(strip=True) for td in soup.find_all("td") 
                          if re.match(r"^\d{8}$", td.get_text(strip=True))}
        
        if document_numbers:
            self.log(f"\nEncontrados no recibo {len(document_numbers)} números de documento:")
            for doc in sorted(document_numbers):
                self.log(f"- {doc}")
                
        return document_numbers

    def download_sei_files(self, doc_numbers: Set[str], target_dir: Path) -> Dict[str, List[Path]]:
        downloaded_files = {}
        self.log(f"\nIniciando download de {len(doc_numbers)} documentos do recibo...")
        
        self.page.wait_for_selector("tr.infraTrClara", state="visible")
        
        for doc_num in sorted(doc_numbers):
            self.log(f"\nBaixando documento {doc_num}")
            try:
                doc_link = self.page.locator(f'tr.infraTrClara td:nth-child(2) a:text("{doc_num}")').first
                if not doc_link:
                    continue

                with self.page.expect_download() as download_info:
                    self.page.keyboard.down("Alt")
                    doc_link.click()
                    self.page.keyboard.up("Alt")
                    
                download = download_info.value
                file_path = target_dir / download.suggested_filename
                download.save_as(file_path)
                downloaded_files[doc_num] = [file_path]
                
                self.log(f"✓ Documento {doc_num} baixado com sucesso")
                
            except Exception as e:
                self.log(f"Erro ao baixar documento {doc_num}: {str(e)}")
                continue
                
            self.page.wait_for_timeout(1000)
            
        return downloaded_files

    def process_sei_files(self, downloaded_files: Dict[str, List[Path]], sei_files_temp: Path):
        self.log("\nETAPA 2: Processando arquivos do SEI")
        
        split_processor = SevenZipSplitProcessor(self.log)
        
        if not split_processor.process_files(sei_files_temp, sei_files_temp):
            raise Exception("Falha no processamento 7zip dos arquivos do SEI")
            
        self.sei_files_data = {}
        
        for doc_num, file_paths in downloaded_files.items():
            for file_path in file_paths:
                dir_to_process = file_path.parent
                if file_path.suffix.lower() == ".zip":
                    dir_to_process = sei_files_temp / f"extract_{doc_num}"
                    dir_to_process.mkdir(exist_ok=True)
                    self.file_processor.extract_zip_recursive(file_path, dir_to_process)
                
                processed_files = self.file_processor.process_directory(
                    dir_to_process,
                    split_processor=split_processor,
                    origin="sei"
                )
                
                for file_hash, file_data in processed_files.items():
                    file_data["doc_number"] = doc_num
                    self.sei_files_data[file_hash] = file_data
        
        self.log(f"Total de arquivos do SEI processados: {len(self.sei_files_data)}")

    def compare_files(self):
        self.log("\nETAPA 3: Comparando arquivos")
        
        for file_hash, user_file in self.user_files_data.items():
            if file_hash in self.sei_files_data:
                sei_file = self.sei_files_data[file_hash]
                user_file["status"] = "matched"
                
                self.validation_results["matched_files"][file_hash] = {
                    "user_file": user_file["file_path"],
                    "sei_file": sei_file["file_path"],
                    "doc_num": sei_file["doc_number"]
                }
            else:
                self.validation_results["unmatched_user_files"][file_hash] = user_file
        
        for file_hash, sei_file in self.sei_files_data.items():
            if file_hash not in self.user_files_data:
                type_validation = self.file_processor.verify_document_type(
                    sei_file["file_path"], 
                    self.doc_type
                )
                
                if not type_validation["matches"]:
                    self.validation_results["type_mismatches"][sei_file["doc_number"]] = type_validation
                
                self.validation_results["unexpected_sei_files"][file_hash] = {
                    "sei_file": sei_file["file_path"],
                    "doc_num": sei_file["doc_number"],
                    "type_validation": type_validation
                }
                
        self.generate_validation_report()

    def generate_validation_report(self):
        self.log("\nRelatório de Validação de Arquivos")
        self.log("=" * 50)
        
        matched_count = len(self.validation_results["matched_files"])
        
        unmatched_files = {
            k: v for k, v in self.validation_results["unmatched_user_files"].items() 
            if "SDCOMdividido" not in v["file_path"].name and (
                not v.get("extracted_name") or "SDCOMdividido" not in v["extracted_name"]
            )
        }
        unmatched_count = len(unmatched_files)
        
        unexpected_count = len(self.validation_results["unexpected_sei_files"])
        type_mismatch_count = len(self.validation_results["type_mismatches"])
        
        self.log(f"\nResumo de Contagem:")
        self.log(f"Total de documentos verificados: {matched_count + unmatched_count}")
        self.log(f"Documentos encontrados no SEI: {matched_count}")
        self.log(f"Documentos não encontrados no SEI: {unmatched_count}")
        self.log(f"Documentos extras no SEI: {unexpected_count}")
        self.log(f"Documentos com tipo incorreto: {type_mismatch_count}")
        
        if self.validation_results["matched_files"]:
            self.log("\n1. Arquivos com Correspondência")
            self.log("-" * 30)
            for i, (_, data) in enumerate(self.validation_results["matched_files"].items(), 1):
                self.log(f"\n{i}. Documento SEI: {data['doc_num']}")
                self.log(f"   Arquivo do usuário: {data['user_file'].name}")
                self.log(f"   Arquivo no SEI: {data['sei_file'].name}")
        
        if unmatched_files:
            self.log("\n2. Arquivos da Fonte da Verdade Não Encontrados no SEI")
            self.log("-" * 30)
            for i, (_, data) in enumerate(unmatched_files.items(), 1):
                if data["is_zipped"]:
                    self.log(f"\n{i}. Arquivo não encontrado: {data['extracted_name']}")
                    self.log(f"   Contido no ZIP: {data['file_path'].name}")
                else:
                    self.log(f"\n{i}. Arquivo não encontrado: {data['file_path'].name}")
        
        if self.validation_results["unexpected_sei_files"]:
            self.log("\n3. Arquivos no SEI Não Presentes na Fonte da Verdade")
            self.log("-" * 30)
            for i, (_, data) in enumerate(self.validation_results["unexpected_sei_files"].items(), 1):
                self.log(f"\n{i}. Documento SEI: {data['doc_num']}")
                self.log(f"   Arquivo: {data['sei_file'].name}")
                
                if "type_validation" in data:
                    type_info = data["type_validation"]
                    if type_info["missing_type"]:
                        self.log(f"   ATENÇÃO: Arquivo sem marcação de tipo - deveria ser {type_info['expected_type']}")
                    elif type_info["wrong_type"]:
                        self.log(f"   ATENÇÃO: Tipo incorreto - marcado como {type_info['detected_type']}, deveria ser {type_info['expected_type']}")
        
        if self.validation_results["type_mismatches"]:
            self.log("\n4. Resumo das Divergências de Tipo")
            self.log("-" * 30)
            
            missing_type = [(doc_num, info) for doc_num, info in self.validation_results["type_mismatches"].items() if info["missing_type"]]
            wrong_type = [(doc_num, info) for doc_num, info in self.validation_results["type_mismatches"].items() if info["wrong_type"]]
            
            if missing_type:
                self.log("\nDocumentos sem marcação de tipo adequada:")
                for doc_num, info in missing_type:
                    self.log(f"- Documento {doc_num} ({info['filename']})")
                    self.log(f"  Deveria estar marcado como: {info['expected_type']}")
                    
            if wrong_type:
                self.log("\nDocumentos com tipo incorreto:")
                for doc_num, info in wrong_type:
                    self.log(f"- Documento {doc_num} ({info['filename']})")
                    self.log(f"  Marcado como: {info['detected_type']}")
                    self.log(f"  Deveria ser: {info['expected_type']}")

    def cleanup(self):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self.file_processor.cleanup_temp_files()
        
    def compare(self):
        try:
            self.temp_dir = self.file_processor.create_temp_directory(f"compare_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
            self.file_processor.temp_base_dir = self.temp_dir
            
            user_files_temp = self.process_user_files()
            
            self.init_browser()
            self.login()
            self.page.goto(self.process_url)
            self.page.wait_for_load_state("networkidle")
            
            self.extract_process_number()
            receipt_content = self.find_latest_receipt()
            if not receipt_content:
                raise Exception("Recibo eletrônico não encontrado")
                
            doc_numbers = self.extract_document_numbers(receipt_content)
            if not doc_numbers:
                raise Exception("Documentos não encontrados no recibo")
            
            sei_files_temp = self.temp_dir / "sei_files"
            sei_files_temp.mkdir(exist_ok=True)
            
            downloaded_files = self.download_sei_files(doc_numbers, sei_files_temp)
            self.process_sei_files(downloaded_files, sei_files_temp)
            
            self.compare_files()
            
        except Exception as e:
            self.log(f"Erro durante a comparação: {str(e)}")
            raise
            
        finally:
            self.cleanup()

def compare_files(process_url: str, user_files_path: str, doc_type: str, log_function=print):
    comparator = FileComparator(process_url, user_files_path, doc_type, log_function)
    comparator.compare()