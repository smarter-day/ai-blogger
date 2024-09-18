import os.path
import time
from pathlib import Path
from typing import BinaryIO, Optional, List, Any, Union

import openai
from openai.types.fine_tuning import FineTuningJob

from .project import Project
from .utils import get_file_hash

# Status constants
FINE_TUNING_JOB_IN_SUCCEED_STATUS = ["succeeded"]
FINE_TUNING_JOB_IN_ERROR_STATUS = ["failed", "cancelled"]
FINE_TUNING_JOB_IN_PROGRESS_STATUS = [
    "validating_files",
    "queued",
    "running",
]


def ask(client: openai.OpenAI, messages: List[Any], model_name: str) -> str:
    """Send a prompt to OpenAI and return the response."""
    response = client.chat.completions.create(
        messages=messages,
        model=model_name
    )
    return response.choices[0].message.content


def simple_ask(client: openai.OpenAI, model_name: str, prompt: str, **kwargs) -> str:
    return ask(
        client=client,
        messages=[{
            "role": "user",
            "content": prompt.format(**kwargs),
        }],
        model_name=model_name,
    )


def list_fine_tuning_jobs(project: Project):
    """
    Retrieve the list of fine-tuning jobs from OpenAI.
    """
    try:
        return project.get_openai_client().fine_tuning.jobs.list()
    except Exception as e:
        print(f"Error while listing fine-tuning jobs: {str(e)}")
        return None


def handle_fine_tuning_status(project: Project, job_id: str, summary_jsonl_file: str, summary_hash: str) -> Union[bool, FineTuningJob]:
    """Check and wait for fine-tuning job to finish. Return True if succeeded."""
    job_info = get_fine_tune_job_info(job_id=job_id, project=project)
    if not job_info:
        return False

    if job_info.status in FINE_TUNING_JOB_IN_SUCCEED_STATUS:
        project.get_db().update_fine_tune_job_info(
            file_path=str(summary_jsonl_file),
            file_hash=summary_hash,
            fine_tuning_job=job_info,
        )
        return job_info

    if job_info.status in FINE_TUNING_JOB_IN_PROGRESS_STATUS:
        while job_info.status in FINE_TUNING_JOB_IN_PROGRESS_STATUS:
            print(f"Fine-tuning job {job_id}. Status: {job_info.status}. Waiting...")
            project.get_db().update_fine_tune_job_info(
                file_path=str(summary_jsonl_file),
                file_hash=summary_hash,
                fine_tuning_job=job_info,
            )
            time.sleep(project.get_settings().fine_tuning_check_status_delay)
            job_info = get_fine_tune_job_info(job_id=job_id, project=project)

        if job_info.status in FINE_TUNING_JOB_IN_SUCCEED_STATUS:
            project.get_db().update_fine_tune_job_info(
                file_path=str(summary_jsonl_file),
                file_hash=summary_hash,
                fine_tuning_job=job_info,
            )
            return job_info
    print(f"Fine-tuning job {job_id} failed or was cancelled.")
    return job_info


def get_fine_tune_job_info(job_id: str, project: Project) -> Optional[FineTuningJob]:
    """Retrieve fine-tuning job information from OpenAI."""
    try:
        return project.get_openai_client().fine_tuning.jobs.retrieve(fine_tuning_job_id=job_id)
    except Exception as e:
        print(f"Failed to retrieve fine-tuning job info: {str(e)}")
        return None


def upload_file_to_openai(project: Project, file: BinaryIO) -> str:
    """Upload file to OpenAI."""
    response = project.get_openai_client().files.create(file=file, purpose='fine-tune')
    return response.id


def upload_training_file(project: Project, file_path: Path) -> Optional[str]:
    """Upload the training file to OpenAI if it hasn't been uploaded already."""
    try:
        with open(file_path, "rb") as file:
            file_hash = get_file_hash(file_path)
            file_id = upload_file_to_openai(project, file)
            print(f"File uploaded successfully: {file_id}")
            return file_id
    except Exception as e:
        print(f"Failed to upload training file: {str(e)}")
        raise


def wait_for_available_fine_tuning_slot(project: Project):
    """Wait for an available fine-tuning slot."""
    while True:
        try:
            fine_tuning_jobs = list_fine_tuning_jobs(project=project)
            running_jobs = [job for job in fine_tuning_jobs.data if job.status in FINE_TUNING_JOB_IN_PROGRESS_STATUS]
            if len(running_jobs) < project.get_settings().fine_tuning_max_concurrent_jobs:
                print(f"Available fine-tuning slot found. Active jobs: {len(running_jobs)}")
                return
            else:
                print(f"Waiting for available fine-tuning slot. Active jobs: {len(running_jobs)}")
                time.sleep(project.get_settings().fine_tuning_check_status_delay)
        except Exception as e:
            print(f"Error while checking fine-tuning jobs: {str(e)}")
            time.sleep(project.get_settings().fine_tuning_check_status_delay)


def fine_tune(project: Project, model_name: str, file_id: str) -> Optional[FineTuningJob]:
    """Start a new fine-tuning job."""
    try:
        return project.get_openai_client().fine_tuning.jobs.create(
            model=model_name,
            training_file=file_id,
        )
    except Exception as e:
        print(f"Error while fine-tuning model: {str(e)}")
        return None


def combine_fine_tuning_files(project, combined_file_name: str = 'summary.jsonl') -> Path:
    """Combine multiple fine-tuning files into one."""
    tuning_files = project.get_tuning_files()
    combined_data = []

    for file_path in tuning_files:
        if str(file_path).endswith(os.path.sep + combined_file_name):
            continue
        combined_data.extend(Path(file_path).read_text().splitlines())

    summary_file = project.get_tuning_directory() / combined_file_name

    if os.path.exists(summary_file):
        os.remove(summary_file)

    if not summary_file.parent.exists():
        summary_file.parent.mkdir(parents=True)

    summary_file.write_text('\n'.join(combined_data))
    return summary_file
