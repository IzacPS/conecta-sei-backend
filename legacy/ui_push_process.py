import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import threading
import queue
import datetime
import re
from playwright.sync_api import Page
import json
import time
import signal
import sys
from pathlib import Path
import os
from email_api_ms import notify_process_update
from utils import get_app_data_dir

class PushProcessUI(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self.title("Monitor de Processo Único")
        self.geometry("800x600")

        try:
            import ctypes

            myappid = "br.gov.economia.sei.push_process"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Erro ao configurar AppUserModelID: {e}")

        try:
            self.iconbitmap("sei.ico")
        except:
            try:
                icon = ttk.PhotoImage(file="sei.png")
                self.iconphoto(True, icon)
            except Exception as e:
                print(f"Não foi possível carregar o ícone: {e}")

        self.is_monitoring = False
        self.log_queue = queue.Queue()
        self.process_number = None
        self.browser = None
        self.page = None
        self.playwright = None

        self.create_widgets()
        self.create_layout()
        self.monitor_log_queue()

        # Configurar protocolo de fechamento
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if self.is_monitoring:
            self.is_monitoring = False
            self.cleanup_resources()
        self.destroy()

    def create_widgets(self):
        self.config_frame = ttk.LabelFrame(self, text="Configurações", padding=10)

        self.url_frame = ttk.Frame(self.config_frame)
        ttk.Label(self.url_frame, text="URL do Processo:").pack(side=LEFT, padx=5)
        self.url_entry = ttk.Entry(self.url_frame, width=50)
        self.url_entry.pack(side=LEFT, padx=5, fill=X, expand=True)

        self.interval_frame = ttk.Frame(self.config_frame)
        ttk.Label(self.interval_frame, text="Intervalo de Verificação:").pack(
            side=LEFT, padx=5
        )

        self.interval_var = ttk.StringVar(value="30")
        self.interval_spin = ttk.Spinbox(
            self.interval_frame, from_=1, to=60, width=5, textvariable=self.interval_var
        )
        self.interval_spin.pack(side=LEFT, padx=5)
        ttk.Label(self.interval_frame, text="minutos").pack(side=LEFT)

        self.email_frame = ttk.Frame(self.config_frame)
        ttk.Label(self.email_frame, text="E-mail(s) para Notificação:").pack(
            side=LEFT, padx=5
        )
        self.email_entry = ttk.Entry(self.email_frame, width=50)
        self.email_entry.pack(side=LEFT, padx=5, fill=X, expand=True)

        self.control_button = ttk.Button(
            self.config_frame,
            text="Iniciar Monitoramento",
            command=self.toggle_monitoring,
            style="success.TButton",
            width=25,
        )

        self.log_frame = ttk.LabelFrame(self, text="Logs", padding=10)
        self.log_text = ttk.Text(self.log_frame, wrap=WORD, height=20, state=DISABLED)
        self.scrollbar = ttk.Scrollbar(
            self.log_frame, orient=VERTICAL, command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=self.scrollbar.set)

        self.clear_button = ttk.Button(
            self.log_frame,
            text="Limpar Logs",
            command=self.clear_logs,
            style="secondary.TButton",
            width=15,
        )

    def create_layout(self):
        self.config_frame.pack(fill=X, padx=10, pady=5)
        self.url_frame.pack(fill=X, pady=5)
        self.interval_frame.pack(fill=X, pady=5)
        self.control_button.pack(pady=10)

        self.log_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        self.clear_button.pack(pady=5)

    def init_browser(self):
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        return self.browser, self.page

    def login(self):
        from utils import login_to_sei
        login_to_sei(self.page)

    def get_process_number(self) -> str:
        process_info = self.page.query_selector(
            '//*[@id="tblCabecalho"]/tbody/tr[2]/td[2]'
        )
        if process_info:
            text = process_info.inner_text().strip()
            if text:
                return "".join(filter(str.isdigit, text))
        return None

    def get_document_numbers(self) -> list:
        self.page.wait_for_selector("#tblDocumentos", state="visible", timeout=30000)
        documents = []
        rows = self.page.query_selector_all("#tblDocumentos tr.infraTrClara")
        for row in rows:
            link = row.query_selector("td:nth-child(2) a")
            if link:
                doc_number = link.text_content().strip()
                if doc_number.isdigit():
                    documents.append(doc_number)
        return documents

    def load_document_data(self) -> dict:
        """Carrega dados de documentos salvos anteriormente"""
        try:
            app_data_dir = get_app_data_dir()
            json_path = app_data_dir / f"push_process_{self.process_number}.json"
            
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
            
        except Exception as e:
            self.log_queue.put(f"Erro ao carregar dados salvos: {str(e)}")
            return None

    def save_document_data(self, documents: list):
        """Salva dados de documentos no diretório de dados da aplicação"""
        try:
            app_data_dir = get_app_data_dir()
            json_path = app_data_dir / f"push_process_{self.process_number}.json"
            
            data = {
                "process_number": self.process_number,
                "documents": documents,
                "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                            
        except Exception as e:
            self.log_queue.put(f"Erro ao salvar dados: {str(e)}")

    def cleanup_resources(self):
        """Limpa recursos e remove arquivos temporários"""
        try:
            if self.browser:
                self.browser.close()
        except Exception as e:
            self.log_queue.put(f"Erro ao fechar browser: {str(e)}")
            
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            self.log_queue.put(f"Erro ao parar playwright: {str(e)}")

        # Remove arquivo temporário apenas se o monitoramento foi interrompido
        if self.process_number:
            try:
                app_data_dir = get_app_data_dir()
                json_path = app_data_dir / f"push_process_{self.process_number}.json"
                if json_path.exists():
                    json_path.unlink()
                    self.log_queue.put("Arquivo temporário removido")
            except Exception as e:
                self.log_queue.put(f"Erro ao remover arquivo temporário: {str(e)}")

    def run_monitoring(self):
        try:
            process_url = self.url_entry.get().strip()
            interval = int(self.interval_var.get())

            self.log_queue.put(f"Iniciando monitoramento...")
            self.log_queue.put(f"Intervalo: {interval} minutos")

            self.browser, self.page = self.init_browser()
            self.login()

            self.page.goto(process_url)
            self.process_number = self.get_process_number()

            if not self.process_number:
                raise Exception("Não foi possível determinar o número do processo")

            self.log_queue.put(f"Processo identificado: {self.process_number}")

            initial_documents = self.get_document_numbers()
            self.log_queue.put(f"Documentos encontrados: {len(initial_documents)}")
            
            saved_data = self.load_document_data()

            if not saved_data:
                self.log_queue.put("Primeira verificação. Salvando lista inicial de documentos...")
                self.save_document_data(initial_documents)
            else:
                self.log_queue.put("Dados existentes carregados.")

            while self.is_monitoring:
                try:
                    self.log_queue.put(f"Verificando novos documentos...")

                    self.page.reload()
                    current_documents = self.get_document_numbers()

                    saved_data = self.load_document_data()
                    if not saved_data:
                        self.log_queue.put("Dados salvos não encontrados, reinicializando...")
                        self.save_document_data(current_documents)
                        saved_documents = current_documents
                    else:
                        saved_documents = saved_data["documents"]

                    new_docs = [
                        doc for doc in current_documents if doc not in saved_documents
                    ]

                    if new_docs:
                        self.log_queue.put("NOVOS DOCUMENTOS ENCONTRADOS!")
                        self.log_queue.put("Números dos novos documentos:")
                        for doc in new_docs:
                            self.log_queue.put(f"- {doc}")
                        
                        # Notificar sobre novos documentos
                        try:
                            notify_process_update(
                                self.process_number,
                                f"Novos documentos encontrados: {', '.join(new_docs)}",
                            )
                        except Exception as e:
                            self.log_queue.put(f"Erro ao enviar notificação: {str(e)}")
                        
                        self.save_document_data(current_documents)
                        self.log_queue.put("Monitoramento concluído - novos documentos detectados!")
                        break
                    else:
                        self.log_queue.put("Nenhum documento novo encontrado.")

                    self.log_queue.put(f"Aguardando {interval} minutos até próxima verificação...")

                    for _ in range(interval * 60):
                        if not self.is_monitoring:
                            break
                        time.sleep(1)

                except Exception as e:
                    self.log_queue.put(f"Erro durante verificação: {str(e)}")
                    self.log_queue.put("Tentando novamente em 1 minuto...")
                    time.sleep(60)

                    try:
                        self.page.goto(process_url)
                    except:
                        self.login()
                        self.page.goto(process_url)

        except Exception as e:
            self.log_queue.put(f"Erro crítico: {str(e)}")

        finally:
            self.cleanup_resources()
            if self.is_monitoring:
                self.after(0, self.toggle_monitoring)

    def toggle_monitoring(self):
        if not self.is_monitoring:
            if not self.validate_input():
                return

            self.is_monitoring = True
            self.control_button.configure(
                text="Parar Monitoramento", style="danger.TButton"
            )
            self.url_entry.configure(state=DISABLED)
            self.interval_spin.configure(state=DISABLED)

            self.monitor_thread = threading.Thread(
                target=self.run_monitoring, daemon=True
            )
            self.monitor_thread.start()

        else:
            self.is_monitoring = False
            self.control_button.configure(
                text="Iniciar Monitoramento", style="success.TButton"
            )
            self.url_entry.configure(state=NORMAL)
            self.interval_spin.configure(state=NORMAL)
            self.log_queue.put("Monitoramento parado.")

    def validate_input(self) -> bool:
        url = self.url_entry.get().strip()
        if not url:
            Messagebox.show_error(
                "Campos Obrigatórios", "Por favor, insira a URL do processo."
            )
            return False

        try:
            interval = int(self.interval_var.get())
            if interval < 1:
                raise ValueError()
        except ValueError:
            Messagebox.show_error(
                "Intervalo Inválido",
                "O intervalo deve ser um número inteiro maior que zero.",
            )
            return False

        return True

    def monitor_log_queue(self):
        while True:
            try:
                message = self.log_queue.get_nowait()
                self.update_log(message)
            except queue.Empty:
                break

        self.after(100, self.monitor_log_queue)

    def update_log(self, message):
        self.log_text.configure(state=NORMAL)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.see(END)
        self.log_text.configure(state=DISABLED)

    def clear_logs(self):
        self.log_text.configure(state=NORMAL)
        self.log_text.delete(1.0, END)
        self.log_text.configure(state=DISABLED)


if __name__ == "__main__":
    app = PushProcessUI()
    app.mainloop()