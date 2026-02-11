import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import json
import sys
import os
from pathlib import Path
from typing import Optional
from ttkbootstrap.tooltip import ToolTip
from ttkbootstrap.dialogs import Messagebox
import requests
from ui_scraper import ScraperUI
from ui_file_comparator import FileComparatorUI
from ui_process_manager import ProcessManagerUI
from ui_settings import SettingsUI
from ui_push_process import PushProcessUI
import threading

class Config:
    APP_NAME = "AutomaSEI"
    APP_ID = "unotrade.automa.sei"
    CREDENTIALS_FILE = "credenciais.json"
    APP_VERSION = "1.0.10"

    WINDOW_SIZE = "400x540"
    PADDING = 15

    STYLES = {
        "TITLE_FONT": ("Segoe UI", 18, "bold"),
        "SUBTITLE_FONT": ("Segoe UI", 12),
        "VERSION_FONT": ("Segoe UI", 9),
    }

    MODULES = {
        "scraper": {
            "title": "Extrator de Dados",
            "description": "Monitora e baixa novos processos automaticamente",
            "style": "primary",
        },
        "push_process": {
            "title": "Monitor de Processo",
            "description": "Monitora um processo específico em tempo real",
            "style": "info",
        },
        "file_comparator": {
            "title": "Comparador de Arquivos",
            "description": "Compare arquivos locais com documentos do SEI",
            "style": "success",
        },
        "process_manager": {
            "title": "Gerenciador de Processos",
            "description": "Gerencie processos, categorias, links e apelidos",
            "style": "warning",
        },
        "settings": {
            "title": "Configurações",
            "description": "Configure suas credenciais e preferências",
            "style": "secondary",
        },
    }



class MainState:
    def __init__(self):
        self.version = None
        self.settings_loaded = False


class MainApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="superhero")
        self.state = MainState()
        self.title(Config.APP_NAME)
        self.geometry(Config.WINDOW_SIZE)
        self.resizable(False, False)

        self.center_window()

        self.windows = {
            "scraper": None,
            "file_comparator": None,
            "process_manager": None,
            "settings": None,
            "push_process": None,
        }

        self.setup_app_id()
        self.setup_icon()
        self.create_widgets()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def center_window(self):
        window_width, window_height = map(int, Config.WINDOW_SIZE.split("x"))
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        position_x = (screen_width // 2) - (window_width // 2)
        position_y = (screen_height // 2) - (window_height // 2)

        self.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

    def setup_app_id(self):
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(Config.APP_ID)
        except Exception as e:
            print(f"Erro ao configurar AppUserModelID: {e}")

    def setup_icon(self):
        try:
            if hasattr(sys, "_MEIPASS"):
                icon_path = os.path.join(sys._MEIPASS, "sei.ico")
            else:
                icon_path = os.path.join(os.path.dirname(__file__), "sei.ico")

            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            else:
                raise FileNotFoundError(f"Ícone não encontrado: {icon_path}")

        except Exception as e:
            print(f"Erro ao carregar o ícone bitmap: {e}")
            try:
                fallback_icon = os.path.join(os.path.dirname(__file__), "sei.png")
                if os.path.exists(fallback_icon):
                    icon = ttk.PhotoImage(file=fallback_icon)
                    self.iconphoto(True, icon)
                else:
                    raise FileNotFoundError(
                        f"Ícone PNG alternativo não encontrado: {fallback_icon}"
                    )
            except Exception as e:
                print(f"Erro ao carregar o ícone de fallback: {e}")

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=Config.PADDING)
        main_frame.pack(fill=BOTH, expand=True)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 15))

        title_label = ttk.Label(
            header_frame, text=Config.APP_NAME, font=Config.STYLES["TITLE_FONT"]
        )
        title_label.pack()

        modules_frame = ttk.Frame(main_frame)
        modules_frame.pack(fill=BOTH, expand=True)

        for module_key, module_info in Config.MODULES.items():
            self.create_module_button(modules_frame, module_key, module_info)

        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(fill=X, pady=(5, 0))

        buttons_frame = ttk.Frame(footer_frame)
        buttons_frame.pack(anchor=CENTER, pady=5)

        close_btn = ttk.Button(
            buttons_frame,
            text="✕ Sair",
            command=self.close_application,
            bootstyle="danger",
            width=12,
        )
        close_btn.pack(side=LEFT, padx=2)
        ToolTip(close_btn, text="Fechar o aplicativo")

        self.state.version = self.get_version()
        version_label = ttk.Label(
            footer_frame,
            text=f"v{self.state.version}",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        )
        version_label.pack(pady=(0, 5))
        ToolTip(version_label, text=f"SEI Automação v{self.state.version}")

        ttk.Separator(footer_frame, bootstyle="secondary").pack(fill=X)

    def create_module_button(self, parent, module_key, module_info):
        frame = ttk.Frame(parent)
        frame.pack(fill=X, pady=3)

        button_text = f"{module_info['title']}"

        button = ttk.Button(
            frame,
            text=button_text,
            command=lambda: self.handle_module_click(module_key),
            width=35,
            style=f"{module_info['style']}.TButton",
        )
        button.pack(pady=(0, 2))

        # Descrição do módulo
        desc_label = ttk.Label(
            frame,
            text=module_info["description"],
            wraplength=350,
            justify=CENTER,
            font=("Segoe UI", 10),
        )
        desc_label.pack()

        ToolTip(button, text=module_info["description"])

        ttk.Separator(frame, bootstyle="secondary").pack(fill=X, pady=(3, 0))

    def handle_module_click(self, module_key):
        module_functions = {
            "scraper": self.open_scraper,
            "push_process": self.open_push_process,
            "file_comparator": self.open_file_comparator,
            "process_manager": self.open_process_manager,
            "settings": self.open_settings,
        }

        if module_key in module_functions:
            module_functions[module_key]()

    def open_window(self, window_key: str, window_class) -> Optional[ttk.Toplevel]:
        """Abre uma janela"""
        try:
            if (
                self.windows[window_key] is None
                or not self.windows[window_key].winfo_exists()
            ):
                self.windows[window_key] = window_class(self)
                return self.windows[window_key]
            else:
                self.windows[window_key].focus_force()
                return None
        except Exception as e:
            Messagebox.show_error("Erro", f"Não foi possível abrir a janela: {str(e)}")
            return None

    def open_scraper(self):
        self.open_window("scraper", ScraperUI)

    def open_push_process(self):
        self.open_window("push_process", PushProcessUI)

    def open_file_comparator(self):
        self.open_window("file_comparator", FileComparatorUI)

    def open_process_manager(self):
        self.open_window("process_manager", ProcessManagerUI)

    def open_settings(self):
        self.open_window("settings", SettingsUI)

    def destroy_all_windows(self):
        """Destrói todas as janelas ativas"""
        for window_key, window in self.windows.items():
            if window is not None and window.winfo_exists():
                try:
                    window.destroy()
                except Exception as e:
                    print(f"Erro ao fechar janela {window_key}: {e}")
                self.windows[window_key] = None

    def on_closing(self):
        """Fecha todas as janelas e a aplicação"""
        try:
            self.quit()
            self.destroy()
        finally:
            sys.exit()

    def close_application(self):
        try:
            self.quit()
            self.destroy()
        finally:
            sys.exit()

    @staticmethod
    def get_version():
        return Config.APP_VERSION

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()