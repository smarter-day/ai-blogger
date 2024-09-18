import atexit
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

from openai.types.fine_tuning import FineTuningJob


class DatabaseManager:
    def __init__(self, db_file: Path):
        atexit.register(self.close)
        self.db_path = db_file
        self.conn = sqlite3.connect(self.db_path)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fine_tuning (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                openai_tuning_job_id TEXT NULL,
                openai_tuning_job_status TEXT NULL,
                openai_tuning_job_model TEXT NULL
            )
        ''')
        self.conn.commit()

    def get_fine_tune_job_info(self, file_path: str) -> Tuple[Optional[FineTuningJob], Optional[str]]:
        """Returns fine-tuning job info and file hash for a given file path."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM fine_tuning WHERE file_path=?', (file_path,))
        result = cursor.fetchone()
        if result:
            return FineTuningJob(
                id=result[2],
                status=result[3],
                fine_tuned_model=result[4]
            ), result[1]
        else:
            return None, None

    def update_fine_tune_job_info(self, file_path: str, file_hash: str, fine_tuning_job: FineTuningJob):
        """Update existing entry with new openai tuning job info."""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE fine_tuning SET '
                       'file_hash=?, '
                       'openai_tuning_job_id = ?, '
                       'openai_tuning_job_status = ?, '
                       'openai_tuning_job_model = ? '
                       'WHERE file_path=?',
                       (
                           file_hash,
                           fine_tuning_job.id,
                           fine_tuning_job.status,
                           fine_tuning_job.fine_tuned_model,
                           file_path,
                       ))
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
