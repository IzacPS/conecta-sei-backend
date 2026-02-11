import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import json
import datetime
from utils import load_process_data, save_process_data
from logger_system import UILogger
from ttkbootstrap.tooltip import ToolTip
import sys
import os
import pyperclip
from ttkbootstrap import Progressbar
from ui_add_process import AddProcessUI

class ProcessManagerUI(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self.title("Gerenciador de Processos do SEI")
        self.geometry("1200x900")
        self.setup_icon()
        self.after(100, self.load_processes)

        try:
            import ctypes

            myappid = "br.gov.economia.sei.process_manager"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Erro ao configurar AppUserModelID: {str(e)}")

        # Variáveis de controle para filtros
        self.filter_vars = {
            "pendentes": ttk.BooleanVar(value=False),
            "integral": ttk.BooleanVar(value=False),
            "parcial": ttk.BooleanVar(value=False),
            "confidencial": ttk.BooleanVar(value=False),
            "restrito": ttk.BooleanVar(value=False),
        }

        self.processes = {}
        self.create_widgets()
        self.load_processes()
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

    def on_closing(self):
        """Handler para fechamento da janela"""
        self.destroy()

    def create_widgets(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=5)

        self.list_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.list_tab, text="📋 Listagem")
        self.create_list_tab()

        self.stats_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_tab, text="📊 Estatísticas")
        self.create_stats_tab()

    def create_list_tab(self):
        filter_frame = ttk.LabelFrame(
            self.list_tab, text="🔍 Filtros", padding=10, bootstyle="info"
        )
        filter_frame.pack(fill=X, padx=5, pady=5)

        buttons_frame = ttk.Frame(self.list_tab)
        buttons_frame.pack(fill=X, pady=(0, 5))

        add_process_btn = ttk.Button(
            buttons_frame,
            text="➕ Adicionar Processo",
            command=self.open_add_process,
            bootstyle="success",
            width=20
        )
        add_process_btn.pack(side=LEFT, padx=5)

        status_frame = ttk.Frame(filter_frame)
        status_frame.pack(fill=X, pady=5)

        filters = [
            ("Pendentes", "pendentes", "Mostrar processos pendentes de categorização"),
            ("Acesso Integral", "integral", "Mostrar processos com acesso integral"),
            ("Acesso Parcial", "parcial", "Mostrar processos com acesso parcial"),
            ("Confidencial", "confidencial", "Mostrar processos confidenciais"),
            ("Restrito", "restrito", "Mostrar processos restritos"),
        ]

        for text, var, tooltip in filters:
            cb = ttk.Checkbutton(
                status_frame,
                text=text,
                variable=self.filter_vars[var],
                command=self.apply_filters,
                bootstyle="round-toggle",
            )
            cb.pack(side=LEFT, padx=10)
            ToolTip(cb, text=tooltip)

        # Frame de busca com estilo moderno
        search_frame = ttk.Frame(filter_frame)
        search_frame.pack(fill=X, pady=5)

        ttk.Label(search_frame, text="Buscar:").pack(side=LEFT, padx=5)
        self.search_entry = ttk.Entry(search_frame, bootstyle="primary")
        self.search_entry.pack(side=LEFT, fill=X, expand=True, padx=5)
        self.search_entry.bind("<KeyRelease>", self.apply_filters)
        ToolTip(self.search_entry, text="Busque por número do processo ou apelido")

        list_frame = ttk.Frame(self.list_tab)
        list_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

        self.create_treeview(list_frame)
        self.create_edit_frame(self.list_tab)

    def create_treeview(self, parent):
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=BOTH, expand=True)

        columns = (
            "Processo",
            "Apelido",
            "Tipo de Acesso",
            "Autoridade",
            "Categoria",
            "Status",
            "Última Verificação",
        )

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            bootstyle="info",
        )

        widths = {
            "Processo": 200,
            "Apelido": 200,
            "Tipo de Acesso": 100,
            "Autoridade": 30,
            "Categoria": 100,
            "Status": 100,
            "Última Verificação": 150,
        }

        for col, width in widths.items():
            self.tree.heading(col, text=col, anchor="center")
            self.tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
            bootstyle="primary-round",
        )
        hsb = ttk.Scrollbar(
            tree_frame,
            orient="horizontal",
            command=self.tree.xview,
            bootstyle="primary-round",
        )

        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def create_edit_frame(self, parent):
        edit_frame = ttk.LabelFrame(
            parent, text="Editar Processo", padding=10, bootstyle="info"
        )
        edit_frame.pack(fill=X, padx=5, pady=5)

        info_frame = ttk.Frame(edit_frame)
        info_frame.pack(fill=X, pady=5)

        self.process_label = ttk.Label(
            info_frame,
            text="📄 Nenhum processo selecionado",
            font=("Segoe UI", 10, "bold"),
        )
        self.process_label.pack(side=LEFT)

        self.access_label = ttk.Label(info_frame, text="", font=("Segoe UI", 10))
        self.access_label.pack(side=RIGHT)

        copy_button = ttk.Button(
            info_frame,
            text="Copiar",
            command=self.copy_process_number,
            bootstyle="primary",
        )
        copy_button.pack(side=LEFT, padx=10)

        form_frame = ttk.Frame(edit_frame)
        form_frame.pack(fill=X, pady=5)

        nickname_frame = ttk.Frame(form_frame)
        nickname_frame.pack(fill=X, pady=2)
        ttk.Label(nickname_frame, text="Apelido:").pack(side=LEFT, padx=5)
        self.nickname_entry = ttk.Entry(nickname_frame, width=40, bootstyle="primary")
        self.nickname_entry.pack(side=LEFT, padx=5)

        category_frame = ttk.Frame(form_frame)
        category_frame.pack(fill=X, pady=2)
        ttk.Label(category_frame, text="Categoria:").pack(side=LEFT, padx=5)

        self.category_var = ttk.StringVar()
        categories = [("Restrito", "restrito"), ("Confidencial", "confidencial")]

        for text, value in categories:
            rb = ttk.Radiobutton(
                category_frame,
                text=text,
                value=value,
                variable=self.category_var,
                bootstyle="primary-toolbutton",
            )
            rb.pack(side=LEFT, padx=5)

        # Frame de botões
        button_frame = ttk.Frame(edit_frame)
        button_frame.pack(fill=X, pady=5)

        self.save_button = ttk.Button(
            button_frame,
            text="💾 Salvar Alterações",
            command=self.save_changes,
            bootstyle="success",
            width=20,
        )
        self.save_button.pack(side=LEFT, padx=5)

        self.toggle_edit_controls(False)

    def create_stats_tab(self):
        stats_frame = ttk.Frame(self.stats_tab, padding=10)
        stats_frame.pack(fill=BOTH, expand=True)

        general_frame = ttk.LabelFrame(
            stats_frame, text="📊 Estatísticas Gerais", padding=10, bootstyle="info"
        )
        general_frame.pack(fill=X, pady=5)

        self.stats_labels = {
            "total": ttk.Label(general_frame, text="Total de Processos: 0"),
            "integral": ttk.Label(general_frame, text="Acesso Integral: 0"),
            "parcial": ttk.Label(general_frame, text="Acesso Parcial: 0"),
            "pendentes": ttk.Label(general_frame, text="Pendentes de Categorização: 0"),
            "confidencial": ttk.Label(general_frame, text="Confidenciais: 0"),
            "restrito": ttk.Label(general_frame, text="Restritos: 0"),
        }

        for label in self.stats_labels.values():
            label.pack(anchor=W, pady=2)

        update_btn = ttk.Button(
            general_frame,
            text="🔄 Atualizar Estatísticas",
            command=self.update_statistics,
            bootstyle="info",
            width=20,
        )
        update_btn.pack(pady=10)
        ToolTip(update_btn, text="Atualizar todas as estatísticas")

    def load_processes(self):
        """Carrega processos do JSON e atualiza a interface"""
        try:
            # Verifica se o widget tree já existe antes de tentar atualizar
            if not hasattr(self, 'tree') or not self.tree.winfo_exists():
                return
                
            self.processes = load_process_data()
            if self.processes:
                self.update_treeview()
                self.update_statistics()
        except Exception as e:
            print(f"Erro ao carregar processos: {e}")

    def copy_process_number(self):
        process_number = self.process_label.cget("text").replace("Processo: ", "")
        pyperclip.copy(process_number)

    def open_add_process(self):
        add_window = AddProcessUI(self)
        add_window.transient(self)
        add_window.focus_set()
        add_window.wait_window()
        self.load_processes()

    def update_treeview(self):
        """Atualiza a Treeview com os processos filtrados"""
        try:
            # Verifica se o widget tree já existe antes de tentar atualizar
            if not hasattr(self, 'tree') or not self.tree.winfo_exists():
                return

            # Limpa a árvore
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Obtém o termo de pesquisa
            search_term = self.search_entry.get().strip().lower()

            # Insere os processos filtrados na árvore
            for process_number, data in self.processes.items():
                if self.should_display_process(process_number, data, search_term):
                    self.tree.insert(
                        "",
                        "end",
                        values=(
                            process_number,
                            data.get("apelido", ""),
                            data.get("tipo_acesso_atual", "N/A"),
                            data.get("Autoridade", "N/A"),
                            data.get("categoria", "pendente"),
                            data.get("status_categoria", "pendente"),
                            data.get(
                                "ultima_verificacao",
                                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            ),
                        ),
                    )
        except Exception as e:
            print(f"Erro ao atualizar treeview: {e}")

    def should_display_process(
        self, process_number: str, data: dict, search_term: str
    ) -> bool:
        """Determina se um processo deve ser exibido com base nos filtros"""

        if search_term:
            if not (
                search_term in process_number.lower()
                or search_term in str(data.get("apelido", "")).lower()
            ):
                return False

        if (
            self.filter_vars["pendentes"].get()
            and data.get("status_categoria") != "pendente"
        ):
            return False
        if (
            self.filter_vars["integral"].get()
            and data.get("tipo_acesso_atual") != "integral"
        ):
            return False
        if (
            self.filter_vars["parcial"].get()
            and data.get("tipo_acesso_atual") != "parcial"
        ):
            return False
        if (
            self.filter_vars["confidencial"].get()
            and data.get("categoria") != "confidencial"
        ):
            return False
        if self.filter_vars["restrito"].get() and data.get("categoria") != "restrito":
            return False

        return True

    def apply_filters(self, event=None):
        """Aplica filtros à listagem"""
        self.update_treeview()

    def update_statistics(self):
        stats = {
            "total": len(self.processes),
            "integral": sum(
                1
                for p in self.processes.values()
                if p.get("tipo_acesso_atual") == "integral"
            ),
            "parcial": sum(
                1
                for p in self.processes.values()
                if p.get("tipo_acesso_atual") == "parcial"
            ),
            "pendentes": sum(
                1
                for p in self.processes.values()
                if p.get("status_categoria") == "pendente"
            ),
            "confidencial": sum(
                1
                for p in self.processes.values()
                if p.get("categoria") == "confidencial"
            ),
            "restrito": sum(
                1
                for p in self.processes.values()
                if p.get("categoria") == "restrito"
                or (
                    p.get("tipo_acesso_atual") == "integral"
                    and p.get("categoria") != "confidencial"
                )
            ),
        }

        self.stats_labels["total"].configure(
            text=f"Total de Processos: {stats['total']}"
        )
        self.stats_labels["integral"].configure(
            text=f"Acesso Integral: {stats['integral']}"
        )
        self.stats_labels["parcial"].configure(
            text=f"Acesso Parcial: {stats['parcial']}"
        )
        self.stats_labels["pendentes"].configure(
            text=f"Pendentes de Categorização: {stats['pendentes']}"
        )
        self.stats_labels["confidencial"].configure(
            text=f"Confidenciais: {stats['confidencial']}"
        )
        self.stats_labels["restrito"].configure(text=f"Restritos: {stats['restrito']}")

    def toggle_edit_controls(self, state: bool):
        """Habilita/desabilita controles de edição"""
        state_value = "normal" if state else "disabled"
        self.nickname_entry.configure(state=state_value)
        self.save_button.configure(state=state_value)

        for child in self.tree.winfo_children():
            if isinstance(child, ttk.Radiobutton):
                child.configure(state=state_value)

    def on_select(self, event):
        """Manipula seleção na treeview"""
        selected_items = self.tree.selection()
        if not selected_items:
            self.toggle_edit_controls(False)
            self.process_label.configure(text="Nenhum processo selecionado")
            self.access_label.configure(text="")
            return

        item = selected_items[0]
        values = self.tree.item(item)["values"]
        process_number = values[0]
        process_data = self.processes.get(process_number, {})

        self.process_label.configure(text=f"Processo: {process_number}")
        self.access_label.configure(
            text=f"Acesso: {process_data.get('tipo_acesso_atual', 'N/A')}"
        )

        self.nickname_entry.delete(0, END)
        self.nickname_entry.insert(0, process_data.get("apelido", ""))

        self.category_var.set(process_data.get("categoria", "normal"))

        self.toggle_edit_controls(True)

    def save_changes(self):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        try:
            item = selected_items[0]
            process_number = self.tree.item(item)["values"][0]

            new_nickname = self.nickname_entry.get().strip()
            new_category = self.category_var.get()

            if not new_category:
                Messagebox.show_error(
                    "Erro", "Por favor, selecione uma categoria para o processo."
                )
                return

            if process_number not in self.processes:
                self.processes[process_number] = {}

            process_data = self.processes[process_number]
            old_category = process_data.get("categoria")

            process_data["apelido"] = new_nickname
            process_data["categoria"] = new_category
            process_data["status_categoria"] = "categorizado"
            process_data["ultima_atualizacao"] = datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            if old_category != new_category:
                if "historico_categoria" not in process_data:
                    process_data["historico_categoria"] = []

                process_data["historico_categoria"].append(
                    {
                        "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "categoria_anterior": old_category,
                        "categoria_nova": new_category,
                    }
                )

                logger = UILogger()
                logger.log(
                    f"[PROCESSO {process_number}] Categoria alterada de {old_category or 'pendente'} para {new_category}"
                )

            save_process_data(self.processes)

            self.update_treeview()
            self.update_statistics()

            Messagebox.show_info("Sucesso", "Alterações salvas com sucesso!")

        except Exception as e:
            Messagebox.show_error("Erro", f"Erro ao salvar alterações: {str(e)}")