import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import threading
import queue
import datetime
import re
import json
from pathlib import Path
import os
from utils import load_process_data, save_process_data, create_process_entry, notify_process_update

class AddProcessUI(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self.title("Adicionar Processo Manualmente")
        self.geometry("600x500")
        self.resizable(True, True)

        try:
            import ctypes
            myappid = "br.gov.economia.sei.add_process"
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

        self.log_queue = queue.Queue()
        self.processes_data = load_process_data() or {}
        
        self.create_widgets()
        self.monitor_log_queue()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def check_process_manual(self):
        """Verifica manualmente se o processo existe quando o botão é clicado"""
        process_number = self.process_entry.get().strip()
        
        if not process_number:
            self.log_queue.put("Digite um número de processo para verificar")
            return
            
        existing_key, process_data = self.find_process_by_number(process_number)
        
        if existing_key:
            self.log_queue.put(f"Processo {process_number} já existe na base de dados")
            
            if process_data.get("apelido"):
                self.nickname_entry.delete(0, END)
                self.nickname_entry.insert(0, process_data["apelido"])
                
            if process_data.get("unidade"):
                self.unit_entry.delete(0, END)
                self.unit_entry.insert(0, process_data["unidade"])
                
            self.access_type.set(process_data.get("tipo_acesso_atual", "parcial"))
            self.category_var.set(process_data.get("categoria", "restrito"))
            self.status_var.set(process_data.get("status_categoria", "pendente"))
            
            if process_data.get("melhor_link_atual"):
                self.link_entry.delete(0, END)
                self.link_entry.insert(0, process_data["melhor_link_atual"])
                
            # Atualiza o campo para mostrar a formatação correta
            if existing_key != process_number:
                self.process_entry.delete(0, END)
                self.process_entry.insert(0, existing_key)
                
            # Habilita o botão de exclusão
            self.delete_btn.configure(state=NORMAL)
        else:
            digits_only = self.normalize_process_number_for_comparison(process_number)
            if len(digits_only) >= 10:
                self.log_queue.put(f"Processo {process_number} não encontrado - será criado um novo registro")
                # Desabilita o botão de exclusão pois o processo não existe
                self.delete_btn.configure(state=DISABLED)
            else:
                self.log_queue.put("Número de processo inválido - formato incorreto")
                # Desabilita o botão de exclusão
                self.delete_btn.configure(state=DISABLED)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        form_frame = ttk.LabelFrame(main_frame, text="Dados do Processo", padding=10)
        form_frame.pack(fill=X, pady=5)

        # Número do Processo
        process_frame = ttk.Frame(form_frame)
        process_frame.pack(fill=X, pady=5)
        
        ## Correção: Definir width diretamente em Label, não em Pack
        label = ttk.Label(process_frame, text="Processo:", width=15)
        label.pack(side=LEFT, padx=5)
        
        self.process_entry = ttk.Entry(process_frame)
        self.process_entry.pack(side=LEFT, fill=X, expand=True, padx=5)
        check_btn = ttk.Button(
            process_frame, 
            text="Verificar",
            command=self.check_process_manual,
            bootstyle="info",
            width=10
        )
        check_btn.pack(side=RIGHT, padx=5)

        # Apelido
        nickname_frame = ttk.Frame(form_frame)
        nickname_frame.pack(fill=X, pady=5)
        
        label = ttk.Label(nickname_frame, text="Apelido:", width=15)
        label.pack(side=LEFT, padx=5)
        
        self.nickname_entry = ttk.Entry(nickname_frame)
        self.nickname_entry.pack(side=LEFT, fill=X, expand=True, padx=5)

        # Link do Processo
        link_frame = ttk.Frame(form_frame)
        link_frame.pack(fill=X, pady=5)
        
        label = ttk.Label(link_frame, text="Link:", width=15)
        label.pack(side=LEFT, padx=5)
        
        self.link_entry = ttk.Entry(link_frame)
        self.link_entry.pack(side=LEFT, fill=X, expand=True, padx=5)

        # Unidade
        unit_frame = ttk.Frame(form_frame)
        unit_frame.pack(fill=X, pady=5)
        
        label = ttk.Label(unit_frame, text="Unidade:", width=15)
        label.pack(side=LEFT, padx=5)
        
        self.unit_entry = ttk.Entry(unit_frame)
        self.unit_entry.pack(side=LEFT, fill=X, expand=True, padx=5)

        # Tipo de Acesso
        access_frame = ttk.Frame(form_frame)
        access_frame.pack(fill=X, pady=5)
        
        label = ttk.Label(access_frame, text="Tipo de Acesso:", width=15)
        label.pack(side=LEFT, padx=5)
        
        self.access_type = ttk.StringVar(value="parcial")
        ttk.Radiobutton(
            access_frame, 
            text="Parcial", 
            variable=self.access_type, 
            value="parcial",
            bootstyle="primary-toolbutton"
        ).pack(side=LEFT, padx=5)
        
        ttk.Radiobutton(
            access_frame, 
            text="Integral", 
            variable=self.access_type, 
            value="integral",
            bootstyle="primary-toolbutton"
        ).pack(side=LEFT, padx=5)

        # Categoria
        category_frame = ttk.Frame(form_frame)
        category_frame.pack(fill=X, pady=5)
        
        label = ttk.Label(category_frame, text="Categoria:", width=15)
        label.pack(side=LEFT, padx=5)
        
        self.category_var = ttk.StringVar(value="restrito")
        ttk.Radiobutton(
            category_frame, 
            text="Restrito", 
            variable=self.category_var, 
            value="restrito",
            bootstyle="primary-toolbutton"
        ).pack(side=LEFT, padx=5)
        
        ttk.Radiobutton(
            category_frame, 
            text="Confidencial", 
            variable=self.category_var, 
            value="confidencial",
            bootstyle="primary-toolbutton"
        ).pack(side=LEFT, padx=5)

        # Status da Categoria
        status_frame = ttk.Frame(form_frame)
        status_frame.pack(fill=X, pady=5)
        
        label = ttk.Label(status_frame, text="Status:", width=15)
        label.pack(side=LEFT, padx=5)
        
        self.status_var = ttk.StringVar(value="categorizado")
        ttk.Radiobutton(
            status_frame, 
            text="Categorizado", 
            variable=self.status_var, 
            value="categorizado",
            bootstyle="primary-toolbutton"
        ).pack(side=LEFT, padx=5)
        
        ttk.Radiobutton(
            status_frame, 
            text="Pendente", 
            variable=self.status_var, 
            value="pendente",
            bootstyle="primary-toolbutton"
        ).pack(side=LEFT, padx=5)

        # Botões de ação
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=X, pady=10)

        self.save_btn = ttk.Button(
            action_frame,
            text="Salvar Processo",
            command=self.save_process,
            bootstyle="success",
            width=20
        )
        self.save_btn.pack(side=LEFT, padx=5)

        self.delete_btn = ttk.Button(
            action_frame,
            text="Excluir Processo",
            command=self.delete_process,
            bootstyle="danger",
            width=20,
            state=DISABLED
        )
        self.delete_btn.pack(side=LEFT, padx=5)

        self.clear_btn = ttk.Button(
            action_frame,
            text="Limpar Campos",
            command=self.clear_fields,
            bootstyle="secondary",
            width=15
        )
        self.clear_btn.pack(side=LEFT, padx=5)

        self.cancel_btn = ttk.Button(
            action_frame,
            text="Cancelar",
            command=self.on_closing,
            bootstyle="danger",
            width=15
        )
        self.cancel_btn.pack(side=LEFT, padx=5)

        log_frame = ttk.LabelFrame(main_frame, text="Status", padding=10)
        log_frame.pack(fill=BOTH, expand=True, pady=5)
        
        self.log_text = ttk.Text(log_frame, wrap=WORD, height=10, state=DISABLED)
        self.scrollbar = ttk.Scrollbar(log_frame, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.scrollbar.set)
        
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)

    def check_process_exists(self, event=None):
        process_number = self.process_entry.get().strip()
        
        # Não fazer nada se o campo estiver vazio
        if not process_number:
            return
        
        existing_key, process_data = self.find_process_by_number(process_number)
        
        if existing_key:
            self.log_queue.put(f"Processo {process_number} já existe na base de dados")
            
            if process_data.get("apelido"):
                self.nickname_entry.delete(0, END)
                self.nickname_entry.insert(0, process_data["apelido"])
                
            if process_data.get("unidade"):
                self.unit_entry.delete(0, END)
                self.unit_entry.insert(0, process_data["unidade"])
                
            self.access_type.set(process_data.get("tipo_acesso_atual", "parcial"))
            self.category_var.set(process_data.get("categoria", "restrito"))
            self.status_var.set(process_data.get("status_categoria", "pendente"))
            
            if process_data.get("melhor_link_atual"):
                self.link_entry.delete(0, END)
                self.link_entry.insert(0, process_data["melhor_link_atual"])
                
            # Atualiza o campo para mostrar a formatação correta
            if existing_key != process_number:
                self.process_entry.delete(0, END)
                self.process_entry.insert(0, existing_key)
        else:
            # Verificar se tem pelo menos 10 dígitos numéricos
            digits_only = self.normalize_process_number_for_comparison(process_number)
            if len(digits_only) >= 10:
                self.log_queue.put(f"Processo {process_number} não encontrado - será criado um novo registro")


    def normalize_process_number_for_comparison(self, process_number):
        """Remove caracteres não numéricos do número do processo apenas para comparação"""
        return re.sub(r'\D', '', process_number)


    def find_process_by_number(self, process_number):
        """Procura um processo pelo número, mesmo que a formatação seja diferente"""
        # Tenta localizar o processo exatamente como foi digitado
        if process_number in self.processes_data:
            return process_number, self.processes_data[process_number]
        
        # Se não encontrar, normaliza e compara apenas os dígitos
        normalized = self.normalize_process_number_for_comparison(process_number)
        
        for proc_num, proc_data in self.processes_data.items():
            if self.normalize_process_number_for_comparison(proc_num) == normalized:
                return proc_num, proc_data
        
        return None, None

    def delete_process(self):
        process_number = self.process_entry.get().strip()
        
        if not process_number:
            Messagebox.show_error("Erro", "Nenhum processo selecionado para exclusão.")
            return
        
        existing_key, _ = self.find_process_by_number(process_number)
        
        if not existing_key:
            Messagebox.show_error("Erro", "Processo não encontrado no banco de dados.")
            return
        
        if not Messagebox.yesno(
            "Confirmar Exclusão", 
            f"Tem certeza que deseja excluir o processo {existing_key}?\n\nEssa ação não pode ser desfeita."
        ):
            return
        
        try:
            if existing_key in self.processes_data:
                del self.processes_data[existing_key]
                
                save_process_data(self.processes_data)
                
                self.log_queue.put(f"Processo {existing_key} excluído com sucesso")
                notify_process_update(f"Processo excluído manualmente", existing_key)
                
                self.clear_fields()
                
                Messagebox.show_info(
                    "Sucesso",
                    f"Processo {existing_key} foi excluído com sucesso!"
                )
            else:
                Messagebox.show_error("Erro", "Processo não encontrado no banco de dados.")
        except Exception as e:
            error_msg = str(e)
            self.log_queue.put(f"Erro ao excluir processo: {error_msg}")
            Messagebox.show_error(
                "Erro",
                f"Não foi possível excluir o processo: {error_msg}"
            )


    def validate_process_number(self, process_number):
        if not process_number:
            return False, "Número do processo é obrigatório."
        
        digits_only = self.normalize_process_number_for_comparison(process_number)
        if len(digits_only) < 10:
            return False, "Número do processo deve ter pelo menos 10 dígitos."
        
        sei_pattern = r'^\d{1,6}\.\d{6}\/\d{4}-\d{2}$'
        if not re.match(sei_pattern, process_number) and len(digits_only) < 20:
            return False, "Formato do processo parece incorreto. Use: NNNNN.NNNNNN/AAAA-DD"
                
        return True, ""

    def validate_link(self, link):
        if not link:
            return False, "Link do processo é obrigatório."
            
        # Verificação simples para garantir que é um link do SEI
        if "sei" not in link.lower():
            return False, "O link deve ser um endereço válido do SEI."
            
        return True, ""

    def validate_fields(self):
        process_number = self.process_entry.get().strip()
        link = self.link_entry.get().strip()
        
        valid_process, process_msg = self.validate_process_number(process_number)
        if not valid_process:
            Messagebox.show_error("Validação", process_msg)
            return False
            
        valid_link, link_msg = self.validate_link(link)
        if not valid_link:
            Messagebox.show_error("Validação", link_msg)
            return False
            
        return True

    def save_process(self):
        if not self.validate_fields():
            return
                
        process_number = self.process_entry.get().strip()
        nickname = self.nickname_entry.get().strip()
        raw_link = self.link_entry.get().strip()
        link = self.normalize_link(raw_link)
        unit = self.unit_entry.get().strip()
        access_type = self.access_type.get()
        category = self.category_var.get()
        status = self.status_var.get()
        
        try:
            existing_key, existing_data = self.find_process_by_number(process_number)
            
            if existing_key:
                process_data = existing_data
                actual_key = existing_key
                
                old_access = process_data.get("tipo_acesso_atual")
                old_category = process_data.get("categoria")
                
                process_data["apelido"] = nickname
                process_data["unidade"] = unit
                process_data["tipo_acesso_atual"] = access_type
                process_data["categoria"] = category
                process_data["status_categoria"] = status
                
                # Atualiza o link se não existir ou for diferente
                if link:
                    # Se não tiver links, inicializa o dicionário
                    if "links" not in process_data:
                        process_data["links"] = {}
                    
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Adiciona o novo link se não existir
                    if link not in process_data["links"]:
                        process_data["links"][link] = {
                            "status": "Ativo",
                            "tipo_acesso": access_type,
                            "ultima_verificacao": current_time,
                            "historico": []
                        }
                    
                    # Define como o melhor link atual
                    process_data["melhor_link_atual"] = link
                
                # Registra mudanças importantes
                if old_access != access_type:
                    self.log_queue.put(f"Tipo de acesso alterado de {old_access} para {access_type}")
                    
                if old_category != category:
                    self.log_queue.put(f"Categoria alterada de {old_category or 'não definida'} para {category}")
                    
                self.log_queue.put(f"Processo {actual_key} atualizado com sucesso")
                notify_process_update(f"Processo atualizado manualmente", actual_key)
                
            else:
                # Cria um novo processo
                process_data = create_process_entry(process_number)
                actual_key = process_number  # A chave é o número formatado
                
                # Configura os dados básicos
                process_data["apelido"] = nickname
                process_data["unidade"] = unit
                process_data["tipo_acesso_atual"] = access_type
                process_data["categoria"] = category
                process_data["status_categoria"] = status
                process_data["sem_link_validos"] = False
                
                # Adiciona o link
                if link:
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    process_data["links"][link] = {
                        "status": "Ativo",
                        "tipo_acesso": access_type,
                        "ultima_verificacao": current_time,
                        "historico": []
                    }
                    process_data["melhor_link_atual"] = link
                
                self.processes_data[actual_key] = process_data
                self.log_queue.put(f"Novo processo {actual_key} criado com sucesso")
                notify_process_update(f"Novo processo adicionado manualmente", actual_key)
            
            # Salva os dados atualizados
            save_process_data(self.processes_data)
            
            # Mensagem de sucesso
            Messagebox.show_info(
                "Sucesso",
                f"Processo {actual_key} salvo com sucesso!",
            )
            
            # Limpa os campos
            if Messagebox.okcancel("Continuar", "Deseja adicionar outro processo?"):
                self.clear_fields()
            else:
                self.destroy()
                
        except Exception as e:
            error_msg = str(e)
            self.log_queue.put(f"Erro ao salvar processo: {error_msg}")
            Messagebox.show_error(
                "Erro",
                f"Não foi possível salvar o processo: {error_msg}"
            )

    def clear_fields(self):
        self.process_entry.delete(0, END)
        self.nickname_entry.delete(0, END)
        self.link_entry.delete(0, END)
        self.unit_entry.delete(0, END)
        self.access_type.set("parcial")
        self.category_var.set("restrito")
        self.status_var.set("categorizado")
        self.process_entry.focus_set()
        
        # Desabilita o botão de exclusão
        self.delete_btn.configure(state=DISABLED)

    def on_closing(self):
        self.destroy()
        
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

    def normalize_link(self, full_url: str) -> str:
        if not full_url:
            return ""
            
        # Se o link já parece ser relativo, retorna como está
        if not (full_url.startswith("http://") or full_url.startswith("https://")):
            return full_url
        
        try:
            # Tenta extrair a parte após "/sei/"
            if "/sei/" in full_url:
                return full_url.split("/sei/")[1]
            # Caso alternativo, tenta pegar apenas o caminho + query string
            import re
            match = re.search(r'(processo[^?]*\?.+)$', full_url)
            if match:
                return match.group(1)
            return full_url
        except Exception:
            # Em caso de erro, retorna o link original
            return full_url
