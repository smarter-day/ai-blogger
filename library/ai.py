import os
import time
from pathlib import Path
from typing import BinaryIO, Optional, List, Any, Union

import openai
from openai.types.fine_tuning import FineTuningJob
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from .project import Project
from .utils import get_file_hash
from openai import OpenAIError, BadRequestError, APIError

# Status constants
FINE_TUNING_JOB_IN_SUCCEED_STATUS = ["succeeded"]
FINE_TUNING_JOB_IN_ERROR_STATUS = ["failed", "cancelled"]
FINE_TUNING_JOB_IN_PROGRESS_STATUS = [
    "validating_files",
    "queued",
    "running",
]


# Retry configuration using tenacity: 5 attempts, exponential backoff starting from 1s up to 10s.
# Define a custom retry function
def should_retry(exception):
    """Custom logic to determine if the exception should trigger a retry."""
    if isinstance(exception, BadRequestError):
        # Do not retry on bad request errors (400)
        return False
    elif isinstance(exception, APIError):
        if exception.code == 404:
            # Retry 5 times for 404 errors
            return stop_after_attempt(10)(exception)
        if exception.code == 500:
            # Retry up to 100 times for 500 errors
            return stop_after_attempt(100)(exception)
        if exception.code == 429:
            # Retry a lot of times for rate limiting errors
            return stop_after_attempt(1000)(exception)
    return False  # Default no retry


# Retry configuration with exponential backoff
retry_config = retry(
    retry=retry_if_exception(should_retry),
    wait=wait_exponential(multiplier=1, min=1, max=60)
)


@retry_config
def ask(client: openai.OpenAI, messages: List[Any], model_name: str) -> str:
    """Send a prompt to OpenAI and return the response."""
    response = client.chat.completions.create(
        messages=messages,
        model=model_name
    )
    return response.choices[0].message.content


@retry_config
def simple_ask(client: openai.OpenAI, model_name: str, prompt: str, **kwargs) -> str:
    if len(kwargs):
        prompt = prompt.format(**kwargs)
    return ask(
        client=client,
        messages=[{
            "role": "user",
            "content": prompt,
        }],
        model_name=model_name,
    )


@retry_config
def list_fine_tuning_jobs(project: Project):
    """Retrieve the list of fine-tuning jobs from OpenAI."""
    return project.get_openai_client().fine_tuning.jobs.list()


@retry_config
def handle_fine_tuning_status(project: Project, job_id: str, summary_jsonl_file: str, summary_hash: str) -> Union[
    bool, FineTuningJob]:
    """Check and wait for fine-tuning job to finish. Return True if succeeded."""

    job_info = get_fine_tune_job_info(job_id=job_id, project=project)

    if not job_info:
        return False

    project.get_db().update_fine_tune_job_info(
        file_path=str(summary_jsonl_file),
        file_hash=summary_hash,
        fine_tuning_job=job_info,
    )

    if job_info.status in FINE_TUNING_JOB_IN_SUCCEED_STATUS:
        return job_info

    if job_info.status in FINE_TUNING_JOB_IN_PROGRESS_STATUS:
        while job_info.status in FINE_TUNING_JOB_IN_PROGRESS_STATUS:
            print(f"Fine-tuning job {job_id}. Status: {job_info.status}. Waiting...")
            time.sleep(project.get_settings().fine_tuning_check_status_delay)
            job_info = get_fine_tune_job_info(job_id=job_id, project=project)
            project.get_db().update_fine_tune_job_info(
                file_path=str(summary_jsonl_file),
                file_hash=summary_hash,
                fine_tuning_job=job_info,
            )

        if job_info.status in FINE_TUNING_JOB_IN_SUCCEED_STATUS:
            project.get_db().update_fine_tune_job_info(
                file_path=str(summary_jsonl_file),
                file_hash=summary_hash,
                fine_tuning_job=job_info,
            )
            return job_info
    print(f"Fine-tuning job {job_id} failed or was cancelled.")
    return job_info


@retry_config
def get_fine_tune_job_info(job_id: str, project: Project) -> Optional[FineTuningJob]:
    """Retrieve fine-tuning job information from OpenAI."""
    return project.get_openai_client().fine_tuning.jobs.retrieve(fine_tuning_job_id=job_id)


@retry_config
def upload_file_to_openai(project: Project, file: BinaryIO) -> str:
    """Upload file to OpenAI."""
    response = project.get_openai_client().files.create(file=file, purpose='fine-tune')
    return response.id


@retry_config
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


@retry_config
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


@retry_config
def fine_tune(project: Project, model_name: str, file_id: str) -> Optional[FineTuningJob]:
    """Start a new fine-tuning job."""
    return project.get_openai_client().fine_tuning.jobs.create(
        model=model_name,
        training_file=file_id,
    )


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
