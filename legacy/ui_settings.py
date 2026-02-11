import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
import threading
import datetime
from connect_mongo import get_database
from utils import load_credentials, save_credentials, get_app_data_dir


class SettingsUI(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self.title("Configurações")
        self.geometry("450x600")
        self.resizable(True, True)

        try:
            import ctypes
            myappid = "br.gov.economia.sei.settings"
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

        self.test_in_progress = False
        self.notification_emails = []
        self.db = get_database()
        self.config_collection = self.db.configuracoes
        self.create_widgets()
        self.load_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        main_container = ttk.Frame(self)
        main_container.pack(fill=BOTH, expand=True, padx=20, pady=10)

        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=BOTH, expand=True, pady=10)

        self.create_credentials_tab()
        self.create_notifications_tab()
        self.create_action_frame(main_container)

    def create_credentials_tab(self):
        cred_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(cred_frame, text="Credenciais")

        title = ttk.Label(
            cred_frame,
            text="Configurações de Acesso ao SEI",
            font=("Segoe UI", 12, "bold"),
            bootstyle="info",
        )
        title.pack(fill=X, pady=(0, 20))

        # Status das credenciais
        self.status_frame = ttk.LabelFrame(cred_frame, text="Status", padding=10)
        self.status_frame.pack(fill=X, pady=10)
        
        self.status_label = ttk.Label(
            self.status_frame,
            text="Carregando...",
            font=("Segoe UI", 10),
        )
        self.status_label.pack()

        url_frame = ttk.LabelFrame(cred_frame, text="URL do Sistema", padding=10)
        url_frame.pack(fill=X, pady=10)

        self.url_entry = ttk.Entry(url_frame, width=50)
        self.url_entry.pack(fill=X, padx=5)
        ttk.Label(
            url_frame,
            text="Utilize o endereço para usuários externos do SEI",
            font=("Segoe UI", 9),
        ).pack(pady=(5, 0))

        creds_frame = ttk.LabelFrame(
            cred_frame, text="Credenciais de Acesso", padding=10
        )
        creds_frame.pack(fill=X, pady=10)

        email_frame = ttk.Frame(creds_frame)
        email_frame.pack(fill=X, pady=5)
        ttk.Label(email_frame, text="Email:", width=15).pack(side=LEFT)
        self.email_entry = ttk.Entry(email_frame)
        self.email_entry.pack(side=LEFT, fill=X, expand=True)

        pass_frame = ttk.Frame(creds_frame)
        pass_frame.pack(fill=X, pady=5)
        ttk.Label(pass_frame, text="Senha:", width=15).pack(side=LEFT)
        self.password_entry = ttk.Entry(pass_frame, show="●")
        self.password_entry.pack(side=LEFT, fill=X, expand=True)

        self.test_button = ttk.Button(
            cred_frame,
            text="Testar Conexão",
            command=self.test_connection,
            style="info.TButton",
            width=20,
        )
        self.test_button.pack(pady=20)

    def create_notifications_tab(self):
        notif_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(notif_frame, text="Notificações")

        title = ttk.Label(
            notif_frame,
            text="Configurações de Notificações",
            font=("Segoe UI", 12, "bold"),
            bootstyle="info",
        )
        title.pack(fill=X, pady=(0, 20))

        email_frame = ttk.LabelFrame(
            notif_frame, text="Emails para Notificação", padding=10
        )
        email_frame.pack(fill=X, pady=10)

        input_frame = ttk.Frame(email_frame)
        input_frame.pack(fill=X, pady=5)

        self.email_input = ttk.Entry(input_frame)
        self.email_input.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))

        add_btn = ttk.Button(
            input_frame,
            text="Adicionar",
            command=self.add_email,
            style="info.TButton",
            width=15,
        )
        add_btn.pack(side=RIGHT)

        self.email_list = ttk.Treeview(
            email_frame, columns=("email",), show="headings", height=6
        )
        self.email_list.heading("email", text="Email")
        self.email_list.pack(fill=X, pady=5)

        remove_btn = ttk.Button(
            email_frame,
            text="Remover Selecionado",
            command=self.remove_email,
            style="danger.TButton",
            width=20,
        )
        remove_btn.pack(pady=5)

    def create_action_frame(self, parent):
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=X, pady=10)

        self.save_btn = ttk.Button(
            action_frame,
            text="Salvar Configurações",
            command=self.save_settings,
            style="success.TButton",
            width=25,
        )
        self.save_btn.pack(side=LEFT, padx=5)

        self.cancel_btn = ttk.Button(
            action_frame,
            text="Cancelar",
            command=self.on_closing,
            style="danger.TButton",
            width=15,
        )
        self.cancel_btn.pack(side=LEFT, padx=5)

    def update_status_display(self, credentials: dict):
        """Atualiza a exibição do status das credenciais"""
        source = credentials.get("source", "unknown")
        has_complete = all(credentials.get(field, "").strip() 
                          for field in ["site_url", "email", "senha"])
        
        if has_complete:
            if source == "mongodb":
                status_text = "✅ Credenciais válidas (MongoDB - autoritativo)"
                status_style = "success"
            elif source == "local_file":
                status_text = "⚠️ Credenciais válidas (arquivo local - backup)"
                status_style = "warning"
            else:
                status_text = "✅ Credenciais válidas"
                status_style = "success"
        else:
            status_text = "❌ Credenciais incompletas ou não configuradas"
            status_style = "danger"
        
        self.status_label.configure(text=status_text, bootstyle=status_style)

    def update_mongodb_settings(self, key, value, is_email=False):
        try:
            update_data = {
                "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            if is_email:
                update_data["emails"] = value
            else:
                update_data["valor"] = value

            self.config_collection.update_one(
                {"tipo": key}, {"$set": update_data}, upsert=True
            )
        except Exception as e:
            print(f"Erro ao atualizar configuração {key}: {e}")

    def add_email(self):
        email = self.email_input.get().strip()
        if not email:
            return

        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            Messagebox.show_error(
                "Email Inválido", "Por favor, insira um email válido."
            )
            return

        if email not in self.notification_emails:
            self.notification_emails.append(email)
            self.email_list.insert("", END, values=(email,))
            self.email_input.delete(0, END)
            self.update_mongodb_settings(
                "email_notifications", self.notification_emails, is_email=True
            )

    def remove_email(self):
        selected = self.email_list.selection()
        if not selected:
            return

        for item in selected:
            email = self.email_list.item(item)["values"][0]
            self.notification_emails.remove(email)
            self.email_list.delete(item)

            self.update_mongodb_settings(
                "email_notifications", self.notification_emails, is_email=True
            )

    def load_settings(self):
        try:
            default_url = "https://colaboragov.sei.gov.br/sei/controlador_externo.php?acao=usuario_externo_logar&id_orgao_acesso_externo=0"

            # Carregar emails de notificação
            email_config = self.config_collection.find_one({"tipo": "email_notifications"})
            if email_config and "emails" in email_config:
                self.notification_emails = email_config["emails"]
                for email in self.notification_emails:
                    self.email_list.insert("", END, values=(email,))

            # Carregar credenciais usando o sistema autoritativo
            credentials = load_credentials()
            
            # Atualizar status
            self.update_status_display(credentials)
            
            # Preencher campos
            self.url_entry.delete(0, END)
            self.url_entry.insert(0, credentials.get("site_url", default_url))
            
            self.email_entry.delete(0, END)
            self.email_entry.insert(0, credentials.get("email", ""))
            
            self.password_entry.delete(0, END)
            self.password_entry.insert(0, credentials.get("senha", ""))

        except Exception as e:
            Messagebox.show_error(
                "Erro de Configuração", f"Erro ao carregar configurações: {str(e)}"
            )

    def validate_settings(self):
        url = self.url_entry.get().strip()
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()

        if not all([url, email, password]):
            Messagebox.show_error(
                "Campos Obrigatórios", "Todos os campos são obrigatórios."
            )
            return False

        email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_pattern, email):
            Messagebox.show_error(
                "Email Inválido", "Por favor, insira um email válido."
            )
            return False

        return True

    def save_settings(self):
        if not self.validate_settings():
            return

        try:
            url = self.url_entry.get().strip()
            email = self.email_entry.get().strip()
            password = self.password_entry.get().strip()

            # Usar o sistema autoritativo do MongoDB
            credentials = {
                "site_url": url,
                "email": email,
                "senha": password
            }
            
            success = save_credentials(credentials)
            
            if success:
                # Atualizar status
                credentials["source"] = "mongodb"  # Forçar source para exibição
                self.update_status_display(credentials)
                
                Messagebox.show_info(
                    "Configurações Salvas",
                    "Suas credenciais foram salvas com sucesso no MongoDB e sincronizadas para arquivo local!",
                )
            else:
                Messagebox.show_error(
                    "Erro ao Salvar",
                    "Não foi possível salvar as credenciais. Verifique a conexão com o MongoDB."
                )

        except Exception as e:
            Messagebox.show_error(
                "Erro ao Salvar", f"Não foi possível salvar as configurações: {str(e)}"
            )

    def test_connection(self):
        if self.test_in_progress:
            return

        if not self.validate_test_fields():
            return

        self.test_in_progress = True
        self.test_button.configure(state="disabled", text="Testando conexão...")

        thread = threading.Thread(target=self._run_connection_test, daemon=True)
        thread.start()

    def validate_test_fields(self):
        url = self.url_entry.get().strip()
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()

        if not all([url, email, password]):
            Messagebox.show_error(
                "Campos Incompletos",
                "Por favor, preencha URL, email e senha para testar a conexão.",
            )
            return False
        return True

    def _run_connection_test(self):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                page.goto(self.url_entry.get().strip())
                page.fill("#txtEmail", self.email_entry.get().strip())
                page.fill("#pwdSenha", self.password_entry.get().strip())
                page.click("#sbmLogin")

                page.wait_for_selector(
                    "#divInfraBarraSistema", state="visible", timeout=30000
                )
                browser.close()
                self.after(0, lambda: self.show_test_success())

        except Exception as e:
            self.after(0, lambda: self.show_test_error(str(e)))
        finally:
            self.after(0, self.reset_test_button)

    def show_test_success(self):
        Messagebox.show_info("Conexão estabelecida com sucesso!", "Teste de Conexão")

    def show_test_error(self, error_msg: str):
        Messagebox.show_error(
            "Não foi possível conectar ao SEI", f"Erro de Conexão: {error_msg}"
        )

    def reset_test_button(self):
        self.test_button.configure(state="normal", text="Testar Conexão")
        self.test_in_progress = False

    def on_closing(self):
        self.destroy()