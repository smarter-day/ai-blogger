import os
from pathlib import Path
from typing import List

from openai import OpenAI

from library.database import DatabaseManager
from library.env import get_api_key
from library.settings import Settings


class Project:

    def __init__(self, project_id: str):
        self.openai_client = None
        self.settings = Settings(project_id)
        self.ensure_directories_exist()

    def ensure_directories_exist(self):
        """
        Ensure that the necessary directories for the project exist.
        """
        os.makedirs(self.settings.results_dir, exist_ok=True)
        os.makedirs(self.settings.prompts_dir, exist_ok=True)
        os.makedirs(self.settings.tuning_dir, exist_ok=True)

    def get_tuning_files(self) -> List[Path]:
        """Retrieve all tuning files (JSONL) from the project directory."""
        return list(self.settings.tuning_dir.glob("*.jsonl"))

    def get_tuning_directory(self) -> Path:
        """
        Get the directory path where tuning files are stored.
        :return: Path to the tuning directory.
        """
        return self.settings.tuning_dir

    def get_openai_client(self) -> OpenAI:
        if not self.openai_client:
            self.openai_client = OpenAI(api_key=get_api_key())
        return self.openai_client

    def get_settings(self) -> Settings:
        return self.settings

    def get_db(self) -> DatabaseManager:
        return DatabaseManager(self.settings.db_file.__str__())
