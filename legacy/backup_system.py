import json
import datetime
from typing import Dict
from pathlib import Path
import os
import platform


class BackupManager:
    def __init__(
        self,
        backup_interval_hours: int = 6,
        max_backups: int = 5,
        app_name: str = "SEI_UNO_TRADE",
    ):
        self.backup_interval = backup_interval_hours * 3600
        self.max_backups = max_backups
        self.app_name = app_name
        self.backup_dir = self._get_backup_dir()
        self.backup_control = self.backup_dir / "backup_control.txt"
        self.initialize_backup_system()

    def _get_backup_dir(self) -> Path:
        system = platform.system()

        if system == "Windows":
            base_dir = Path(os.getenv("LOCALAPPDATA"))
        elif system == "Darwin":
            base_dir = Path.home() / "Library" / "Application Support"
        else:
            base_dir = Path.home() / ".local" / "share"

        return base_dir / self.app_name / "backups"

    def initialize_backup_system(self):
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        if not self.backup_control.exists():
            self._update_backup_timestamp(datetime.datetime.min)

    def _update_backup_timestamp(self, timestamp: datetime):
        self.backup_control.write_text(timestamp.datetime.strftime("%Y-%m-%d %H:%M:%S"))

    def _get_last_backup_time(self) -> datetime:
        try:
            timestamp_str = self.backup_control.read_text().strip()
            return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except (FileNotFoundError, ValueError):
            return datetime.datetime.min

    def _cleanup_old_backups(self):
        backup_files = sorted(self.backup_dir.glob("processos_atuais_*.json"))
        for old_backup in backup_files[: -self.max_backups]:
            try:
                old_backup.unlink()
            except Exception as e:
                print(f"Erro ao remover backup antigo {old_backup}: {e}")

    def save_process_data(self, processes: Dict) -> None:
        try:
            current_time = datetime.datetime.now()
            last_backup_time = self._get_last_backup_time()

            if (
                current_time - last_backup_time
            ).total_seconds() >= self.backup_interval:
                backup_file = (
                    self.backup_dir
                    / f"processos_atuais_{current_time.strftime('%Y%m%d_%H%M')}.json"
                )

                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(processes, f, ensure_ascii=False, indent=2)

                self._update_backup_timestamp(current_time)
                self._cleanup_old_backups()

        except Exception as e:
            print(f"Erro ao fazer backup dos dados: {e}")

    def get_backup_list(self) -> list:
        return sorted(self.backup_dir.glob("processos_atuais_*.json"), reverse=True)

    def restore_backup(self, backup_file: Path) -> Dict:
        try:
            if not backup_file.exists():
                return {}

            with open(backup_file, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception:
            return {}


backup_manager = BackupManager()


def save_process_data(processes: Dict) -> None:
    backup_manager.save_process_data(processes)
