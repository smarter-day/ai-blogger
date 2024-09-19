import atexit
from pathlib import Path
from typing import Tuple, Any

from openai.types.fine_tuning import FineTuningJob
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

Base = declarative_base()


class FineTuningModel(Base):
    __tablename__ = 'fine_tuning'

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String, nullable=True, unique=True)
    file_hash = Column(String, nullable=True, default='')
    openai_tuning_job_id = Column(String, nullable=True, default='')
    openai_tuning_job_status = Column(String, nullable=True, default='')
    openai_tuning_job_model = Column(String, nullable=True, default='')


class DatabaseManager:
    def __init__(self, db_file: Path):
        self.db_path = db_file
        self.engine = create_engine(f'sqlite:///{self.db_path}', echo=False)
        self.Session = sessionmaker(bind=self.engine)
        atexit.register(self.close)
        self.session = self.Session()
        Base.metadata.create_all(self.engine)

    def get_fine_tune_job_info(self, file_path: str) -> Tuple[Any, Any]:
        """Returns fine-tuning job info and file hash for a given file path."""
        fine_tune_entry = self.session.query(FineTuningModel).filter_by(file_path=file_path).first()
        if fine_tune_entry:
            return fine_tune_entry, str(fine_tune_entry.file_hash)
        else:
            return None, None

    def update_fine_tune_job_info(self, file_path: str, file_hash: str, fine_tuning_job: FineTuningJob):
        """Update existing entry with new OpenAI tuning job info or create a new one."""
        fine_tune_entry = self.session.query(FineTuningModel).filter_by(file_path=file_path).first()

        if fine_tune_entry:
            print(f"DB: Updating fine-tuning job info for {file_path}")
            # Update the existing entry
            fine_tune_entry.file_hash = file_hash
            fine_tune_entry.openai_tuning_job_id = fine_tuning_job.id
            fine_tune_entry.openai_tuning_job_status = fine_tuning_job.status
            fine_tune_entry.openai_tuning_job_model = fine_tuning_job.fine_tuned_model
            flag_modified(fine_tune_entry, "file_hash")  # Explicitly flag the field as modified
            self.session.merge(fine_tune_entry)  # Ensure merge operation is performed
        else:
            print(f"DB: Creating fine-tuning job info for {file_path}")
            # Create a new entry
            fine_tune_entry = FineTuningModel(
                file_path=file_path,
                file_hash=file_hash,
                openai_tuning_job_id=fine_tuning_job.id,
                openai_tuning_job_status=fine_tuning_job.status,
                openai_tuning_job_model=fine_tuning_job.fine_tuned_model
            )
            self.session.add(fine_tune_entry)

        self.session.commit()

    def close(self):
        self.session.close()
