import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tooltip import ToolTip
from tkinter import filedialog
import threading
import queue
import datetime
import compare_files
import os
import sys
from pathlib import Path

class FileComparatorUI(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self.title("Comparador de Arquivos do SEI")
        self.geometry("900x600")
        self.setup_icon()
        
        try:
            import ctypes
            myappid = 'br.gov.economia.sei.comparator'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Erro ao configurar AppUserModelID: {e}")
        
        self.selected_folder = None
        self.log_queue = queue.Queue()
        self.comparison_in_progress = False
        self.comparison_thread = None
        self.doc_type = ttk.StringVar(value="VC")
        
        self.create_widgets()
        self.monitor_log_queue()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_icon(self):
        try:
            if hasattr(sys, "_MEIPASS"):
                icon_path = os.path.join(sys._MEIPASS, "img", "sei.ico")
            else:
                icon_path = "sei.ico"

            self.iconbitmap(icon_path)
        except Exception as e:
            try:
                icon = ttk.PhotoImage(file="sei.png")
                self.iconphoto(True, icon)
            except Exception as e:
                print(f"Não foi possível carregar o ícone: {e}")

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=True)
        
        config_frame = ttk.LabelFrame(main_frame, text="Configurações", padding=10, bootstyle="info")
        config_frame.pack(fill=X, pady=(0, 5))
        
        folder_frame = ttk.Frame(config_frame)
        folder_frame.pack(fill=X, pady=5)
        
        ttk.Label(folder_frame, text="Pasta Local:").pack(side=LEFT, padx=5)
        self.folder_label = ttk.Label(folder_frame, text="Nenhuma pasta selecionada", bootstyle="secondary")
        self.folder_label.pack(side=LEFT, padx=5)
        
        self.select_folder_btn = ttk.Button(
            folder_frame,
            text="Selecionar",
            command=self.select_folder,
            bootstyle="info",
            width=15
        )
        self.select_folder_btn.pack(side=LEFT, padx=5)
        
        url_frame = ttk.Frame(config_frame)
        url_frame.pack(fill=X, pady=5)
        
        ttk.Label(url_frame, text="URL do Processo:").pack(side=LEFT, padx=5)
        self.url_entry = ttk.Entry(url_frame)
        self.url_entry.pack(side=LEFT, padx=5, fill=X, expand=True)

        action_frame = ttk.Frame(config_frame)
        action_frame.pack(fill=X, pady=5)
        
        type_frame = ttk.LabelFrame(action_frame, text="Tipo de Documento", padding=5)
        type_frame.pack(side=LEFT, fill=X, expand=True)
        
        self.vc_radio = ttk.Radiobutton(
            type_frame,
            text="Versão Confidencial (VC)",
            variable=self.doc_type,
            value="VC",
            bootstyle="primary-toolbutton"
        )
        self.vc_radio.pack(side=LEFT, padx=20)
        
        self.vr_radio = ttk.Radiobutton(
            type_frame,
            text="Versão Restrita (VR)",
            variable=self.doc_type,
            value="VR",
            bootstyle="primary-toolbutton"
        )
        self.vr_radio.pack(side=LEFT, padx=20)
        
        button_frame = ttk.Frame(action_frame)
        button_frame.pack(side=RIGHT, padx=5)
        
        self.compare_btn = ttk.Button(
            button_frame,
            text="🔄 Iniciar Comparação",
            command=self.start_comparison,
            bootstyle="success",
            width=20
        )
        self.compare_btn.pack(side=LEFT, padx=5)
        
        self.cancel_btn = ttk.Button(
            button_frame,
            text="❌ Cancelar",
            command=self.cancel_comparison,
            bootstyle="danger",
            width=15,
            state=DISABLED
        )
        self.cancel_btn.pack(side=LEFT, padx=5)

        # Frame de logs
        log_frame = ttk.LabelFrame(main_frame, text="Logs", padding=10)
        log_frame.pack(fill=BOTH, expand=True)
        
        self.log_text = ttk.Text(
            log_frame,
            wrap=WORD,
            state=DISABLED,
            font=("Consolas", 9)
        )
        
        log_scroll = ttk.Scrollbar(log_frame, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        log_scroll.pack(side=RIGHT, fill=Y)
        
        clear_btn = ttk.Button(
            log_frame,
            text="🧹 Limpar Logs",
            command=self.clear_logs,
            bootstyle="secondary",
            width=15
        )
        clear_btn.pack(side=BOTTOM, pady=(5, 0))
    
    def select_folder(self):
        folder_path = filedialog.askdirectory(title="Selecione a pasta com os arquivos para comparação")
        if folder_path:
            self.selected_folder = folder_path
            self.folder_label.configure(text=str(Path(folder_path).name), bootstyle="primary")
    
    def start_comparison(self):
        if not self.validate_inputs():
            return
            
        self.comparison_in_progress = True
        self.toggle_controls(False)
        self.clear_logs()
        
        self.comparison_thread = threading.Thread(target=self.run_comparison, daemon=True)
        self.comparison_thread.start()
    
    def cancel_comparison(self):
        if self.comparison_in_progress:
            self.comparison_in_progress = False
            self.log_queue.put("Cancelando comparação...")
    
    def validate_inputs(self) -> bool:
        if not self.selected_folder:
            Messagebox.show_error("Erro de Validação", "Por favor, selecione uma pasta local.")
            return False
            
        if not self.url_entry.get().strip():
            Messagebox.show_error("Erro de Validação", "Por favor, insira a URL do processo.")
            return False
        
        return True
    
    def run_comparison(self):
        try:
            self.log_queue.put(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando comparação...")
            
            def log_to_queue(message):
                self.log_queue.put(message)
                if not self.comparison_in_progress:
                    raise Exception("Comparação cancelada pelo usuário")
            
            compare_files.compare_files(
                process_url=self.url_entry.get().strip(),
                user_files_path=self.selected_folder,
                doc_type=self.doc_type.get(),
                log_function=log_to_queue
            )
            
        except Exception as e:
            if str(e) != "Comparação cancelada pelo usuário":
                self.log_queue.put(f"Erro durante a comparação: {str(e)}")
        finally:
            self.comparison_in_progress = False
            self.after(0, lambda: self.toggle_controls(True))
    
    def toggle_controls(self, enabled: bool):
        state = NORMAL if enabled else DISABLED
        self.select_folder_btn.configure(state=state)
        self.url_entry.configure(state=state)
        self.compare_btn.configure(state=state)
        self.cancel_btn.configure(state=not state)
        self.vc_radio.configure(state=state)
        self.vr_radio.configure(state=state)
    
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
        self.log_text.insert(END, f"{message}\n")
        self.log_text.see(END)
        self.log_text.configure(state=DISABLED)
    
    def clear_logs(self):
        self.log_text.configure(state=NORMAL)
        self.log_text.delete(1.0, END)
        self.log_text.configure(state=DISABLED)
    
    def on_closing(self):
        if self.comparison_in_progress:
            if not Messagebox.okcancel(
                "Confirmar Saída",
                "Uma comparação está em andamento. Deseja realmente sair?"
            ):
                return
            
            self.comparison_in_progress = False
            if self.comparison_thread and self.comparison_thread.is_alive():
                self.comparison_thread.join(timeout=1.0)
        
        self.destroy()