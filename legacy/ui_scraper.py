import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import datetime
import threading
import queue
from ttkbootstrap.dialogs import Messagebox
import time
import get_process_update as gpu
import get_process_links_status as gpls
import get_process_docs_update as gpdu
import get_docs_download as gdd
from logger_system import setup_logging
import json

class ScraperUI(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        
        self.title("Extrator de Dados do SEI")
        self.geometry("800x500")
        self.resizable(True, True)

        try:
            self.iconbitmap("sei.ico")
        except:
            try:
                icon = ttk.PhotoImage(file="sei.png")
                self.iconphoto(True, icon)
            except Exception as e:
                print(f"Não foi possível carregar o ícone: {e}")

        self.is_running = False
        self.log_queue = queue.Queue()
        self.logger = setup_logging(self.log_queue)
        self.current_thread = None
        self.event_stop = threading.Event()

        self.create_widgets()
        self.create_layout()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.monitor_log_queue()

    def create_widgets(self):
        self.config_frame = ttk.LabelFrame(self, text="Temporizador", padding=10)
        
        self.schedule_type = ttk.StringVar(value="interval")
        
        schedule_type_frame = ttk.Frame(self.config_frame)
        schedule_type_frame.pack(fill=X, pady=5)
        
        ttk.Radiobutton(
            schedule_type_frame,
            text="Por Intervalo",
            variable=self.schedule_type,
            value="interval",
            command=self.toggle_schedule_type
        ).pack(side=LEFT, padx=10)
        
        ttk.Radiobutton(
            schedule_type_frame,
            text="Horário Específico",
            variable=self.schedule_type,
            value="specific_time",
            command=self.toggle_schedule_type
        ).pack(side=LEFT, padx=10)
        
        self.interval_frame = ttk.LabelFrame(self.config_frame, text="Configurar Intervalo", padding=5)
        self.interval_frame.pack(fill=X, pady=5)
        
        ttk.Label(self.interval_frame, text="Intervalo de Verificação (min. 10 minutos):").pack(anchor=W, padx=5)
        
        time_frame = ttk.Frame(self.interval_frame)
        time_frame.pack(fill=X, pady=5)
        
        self.hours_var = ttk.StringVar(value="0")
        self.hours_spin = ttk.Spinbox(
            time_frame,
            from_=0,
            to=23,
            width=5,
            textvariable=self.hours_var
        )
        self.hours_spin.pack(side=LEFT, padx=5)
        ttk.Label(time_frame, text="h").pack(side=LEFT)
        
        self.minutes_var = ttk.StringVar(value="30")
        self.minutes_spin = ttk.Spinbox(
            time_frame,
            from_=1,
            to=59,
            width=5,
            textvariable=self.minutes_var
        )
        self.minutes_spin.pack(side=LEFT, padx=5)
        ttk.Label(time_frame, text="m").pack(side=LEFT)
        
        self.specific_time_frame = ttk.LabelFrame(self.config_frame, text="Horário Específico", padding=5)
        
        ttk.Label(self.specific_time_frame, text="Executar todos os dias às:").pack(anchor=W, padx=5)
        
        time_entry_frame = ttk.Frame(self.specific_time_frame)
        time_entry_frame.pack(fill=X, pady=5)
        
        self.hour_specific = ttk.StringVar(value="00")
        self.minute_specific = ttk.StringVar(value="00")
        
        self.hour_specific_spin = ttk.Spinbox(
            time_entry_frame,
            from_=0,
            to=23,
            width=5,
            textvariable=self.hour_specific,
            format="%02.0f"
        )
        self.hour_specific_spin.pack(side=LEFT, padx=5)
        
        ttk.Label(time_entry_frame, text=":").pack(side=LEFT)
        
        self.minute_specific_spin = ttk.Spinbox(
            time_entry_frame,
            from_=0,
            to=59,
            width=5,
            textvariable=self.minute_specific,
            format="%02.0f"
        )
        self.minute_specific_spin.pack(side=LEFT, padx=5)
        
        self.actions_frame = ttk.LabelFrame(self, text="Ações Individuais", padding=10)
        
        self.update_processes_btn = ttk.Button(
            self.actions_frame,
            text="Atualizar Lista de Processos",
            command=lambda: self.run_specific_action("processes"),
            width=30
        )
        
        self.update_links_btn = ttk.Button(
            self.actions_frame,
            text="Atualizar Links dos Processos",
            command=lambda: self.run_specific_action("links"),
            width=30
        )
        
        self.update_docs_btn = ttk.Button(
            self.actions_frame,
            text="Verificar Novos Documentos",
            command=lambda: self.run_specific_action("docs"),
            width=30
        )
        
        self.download_docs_btn = ttk.Button(
            self.actions_frame,
            text="Baixar Documentos Novos",
            command=lambda: self.run_specific_action("download"),
            width=30
        )
        
        self.cycle_frame = ttk.LabelFrame(self, text="Ciclo Completo", padding=10)
        
        self.single_cycle_btn = ttk.Button(
            self.cycle_frame,
            text="Executar Ciclo Único",
            command=lambda: self.run_specific_action("full_cycle"),
            style="info.TButton",
            width=25
        )
        
        self.start_button = ttk.Button(
            self.cycle_frame,
            text="Iniciar Ciclo",
            command=self.toggle_scraper,
            style="success.TButton",
            width=35
        )
        
        self.log_frame = ttk.LabelFrame(self, text="Logs", padding=10)
        self.log_text = ttk.Text(self.log_frame, wrap=WORD, height=20, state=DISABLED)
        self.scrollbar = ttk.Scrollbar(self.log_frame, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.scrollbar.set)
        
        self.clear_button = ttk.Button(
            self.log_frame,
            text="Limpar Logs",
            command=self.clear_logs,
            style="secondary.TButton",
            width=15
        )
        
        self.toggle_schedule_type()

    def create_layout(self):
        self.config_frame.pack(fill=X, padx=10, pady=5)
        
        self.actions_frame.pack(fill=X, padx=10, pady=5)
        for btn in [
            self.update_processes_btn,
            self.update_links_btn,
            self.update_docs_btn,
            self.download_docs_btn
        ]:
            btn.pack(pady=5)
        
        self.cycle_frame.pack(fill=X, padx=10, pady=5)
        self.single_cycle_btn.pack(pady=5, padx=5)
        ttk.Separator(self.cycle_frame, orient=HORIZONTAL).pack(fill=X, pady=5, padx=5)
        self.start_button.pack(pady=5, padx=5)
        
        self.log_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        self.clear_button.pack(pady=5)

    def toggle_schedule_type(self):
        schedule_type = self.schedule_type.get()
        
        if schedule_type == "interval":
            self.interval_frame.pack(fill=X, pady=5)
            self.specific_time_frame.pack_forget()
        else:
            self.interval_frame.pack_forget()
            self.specific_time_frame.pack(fill=X, pady=5)
            
        self.update_controls_state()

    def update_controls_state(self):
        if self.is_running:
            state = DISABLED
        else:
            state = NORMAL
            
        if self.schedule_type.get() == "interval":
            self.hours_spin.configure(state=state)
            self.minutes_spin.configure(state=state)
            self.hour_specific_spin.configure(state=DISABLED)
            self.minute_specific_spin.configure(state=DISABLED)
        else:
            self.hours_spin.configure(state=DISABLED)
            self.minutes_spin.configure(state=DISABLED)
            self.hour_specific_spin.configure(state=state)
            self.minute_specific_spin.configure(state=state)

    def run_scheduled_cycles(self):
        while self.is_running and not self.event_stop.is_set():
            if self.schedule_type.get() == "specific_time":
                now = datetime.datetime.now()
                hour = int(self.hour_specific.get())
                minute = int(self.minute_specific.get())
                
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                if target_time <= now:
                    target_time = target_time.replace(day=now.day + 1)
                
                wait_time = (target_time - now).total_seconds()
                self.log_queue.put(f"Aguardando até {target_time.strftime('%H:%M')} para próxima execução...")
            else:
                interval = (int(self.hours_var.get()) * 3600) + (int(self.minutes_var.get()) * 60)
                wait_time = max(600, interval)
                self.log_queue.put(f"Aguardando {interval // 60} minutos até o próximo ciclo...")

            for _ in range(int(wait_time)):
                if self.event_stop.is_set():
                    break
                time.sleep(1)

            if self.event_stop.is_set():
                break

            self.run_full_cycle()

    def toggle_scraper(self):
        if not self.is_running:
            if not self.validate_schedule():
                return
                
            self.is_running = True
            self.event_stop.clear()
            self.start_button.configure(text="Parar Ciclo", style="danger.TButton")
            self.toggle_buttons(False)
            self.update_controls_state()
            
            self.current_thread = threading.Thread(target=self.run_scheduled_cycles, daemon=True)
            self.current_thread.start()
        else:
            self.is_running = False
            self.event_stop.set()
            self.start_button.configure(text="Iniciar Ciclo", style="success.TButton")
            self.toggle_buttons(True)
            self.update_controls_state()

    def validate_schedule(self):
        if self.schedule_type.get() == "interval":
            try:
                hours = int(self.hours_var.get())
                minutes = int(self.minutes_var.get())
                total_minutes = (hours * 60) + minutes
                
                if total_minutes < 10:
                    Messagebox.show_error(
                        "Erro de Validação",
                        "O intervalo mínimo é de 10 minutos."
                    )
                    return False
            except ValueError:
                Messagebox.show_error(
                    "Erro de Validação",
                    "Por favor, insira valores válidos para horas e minutos."
                )
                return False
        else:
            try:
                hour = int(self.hour_specific.get())
                minute = int(self.minute_specific.get())
                
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    Messagebox.show_error(
                        "Erro de Validação",
                        "Por favor, insira um horário válido (HH:MM)."
                    )
                    return False
            except ValueError:
                Messagebox.show_error(
                    "Erro de Validação",
                    "Por favor, insira um horário válido."
                )
                return False
                
        return True

    def run_specific_action(self, action_type):
        def run_action():
            try:
                action_messages = {
                    "processes": "Iniciando busca por novos processos no SEI...",
                    "links": "Verificando links de acesso dos processos...",
                    "docs": "Buscando novos documentos nos processos...",
                    "download": "Iniciando download dos documentos novos...",
                    "full_cycle": "Iniciando ciclo completo de verificação..."
                }

                self.log_queue.put(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {action_messages.get(action_type)}")
                
                if action_type == "processes":
                    processes = gpu.update_processos()
                    self.log_queue.put(f"Busca concluída! {len(processes) if processes else 0} processos totais.")
                
                elif action_type == "links":
                    gpls.update_documentos_processos()
                    self.log_queue.put("Verificação de links concluída com sucesso!")
                
                elif action_type == "docs":
                    gpdu.update_process_documents()
                    self.log_queue.put("Busca por novos documentos finalizada!")
                
                elif action_type == "download":
                    gdd.download_new_documents()
                    self.log_queue.put("Download de documentos concluído com sucesso!")
                
                elif action_type == "full_cycle":
                    self.run_full_cycle()
                
                completion_messages = {
                    "processes": "Lista de processos atualizada com sucesso!",
                    "links": "Links de acesso verificados e atualizados!",
                    "docs": "Verificação de documentos concluída!",
                    "download": "Documentos baixados e organizados!",
                    "full_cycle": "Ciclo completo finalizado!"
                }
                
                self.log_queue.put(completion_messages.get(action_type, "Ação concluída com sucesso!"))
            
            except Exception as e:
                error_messages = {
                    "processes": "Erro ao buscar processos",
                    "links": "Erro ao verificar links",
                    "docs": "Erro ao buscar documentos",
                    "download": "Erro ao baixar documentos",
                    "full_cycle": "Erro durante o ciclo"
                }
                self.log_queue.put(f"{error_messages.get(action_type, 'Erro')}: {str(e)}")
            
            finally:
                self.after(0, lambda: self.toggle_buttons(True))

        self.toggle_buttons(False)
        self.current_thread = threading.Thread(target=run_action, daemon=True)
        self.current_thread.start()


    def run_full_cycle(self):
        try:
            self.log_queue.put("\nIniciando ciclo completo de verificação...")
            
            # Atualiza processos
            processes = gpu.update_processos()
            self.log_queue.put(f"1. Busca por processos concluída! Encontrados: {len(processes) if processes else 0}")
            
            if self.event_stop.is_set():
                return
            
            # Atualiza links
            gpls.update_documentos_processos()
            self.log_queue.put("2. Links de acesso verificados e atualizados!")
            
            if self.event_stop.is_set():
                return
            
            # Atualiza documentos
            gpdu.update_process_documents()
            self.log_queue.put("3. Busca por novos documentos finalizada!")
            
            if self.event_stop.is_set():
                return
            
            # Baixa documentos
            gdd.download_new_documents()
            self.log_queue.put("4. Download e organização dos documentos concluídos!")
            
            self.log_queue.put("Ciclo completo finalizado com sucesso!")
        
        except Exception as e:
            self.log_queue.put(f"Erro durante o ciclo de verificação: {str(e)}")


    def toggle_buttons(self, state):
        state_value = NORMAL if state else DISABLED
        buttons = [
            self.update_processes_btn,
            self.update_links_btn,
            self.update_docs_btn,
            self.download_docs_btn,
            self.single_cycle_btn
        ]
        
        for button in buttons:
            button.configure(state=state_value)
        
        if not self.is_running:
            self.start_button.configure(state=state_value)

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
        if self.is_running:
            if not Messagebox.okcancel(
                "Confirmar Saída",
                "O scraper está em execução. Deseja realmente sair?"
            ):
                return
            
            # Para o ciclo e aguarda a thread terminar
            self.is_running = False
            self.event_stop.set()
            if self.current_thread and self.current_thread.is_alive():
                self.current_thread.join(timeout=1.0)
        
        self.destroy()