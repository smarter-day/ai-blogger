import json
import os
import re
import time
from pathlib import Path
from typing import BinaryIO, Optional, List, Any, Union

import openai
import requests
import typer
from openai import BadRequestError, APIError
from openai.types.fine_tuning import FineTuningJob
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

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


def humanize(project, humanized_output_file: Path, generated_post: str):
    """
    Takes a text 'generated_post', strips away everything before the first '#'
    and everything after '---', then submits that cleaned text to Undetectable.ai
    to be humanized. The final output is saved to <filename>.humanized.md.
    """

    # 1) Remove everything before the first '#' and everything after '---'
    text_to_process = generated_post

    # Part (a): Keep everything from the first header onwards
    header_split = re.split(r"(?m)^#+", text_to_process, maxsplit=1)
    if len(header_split) == 2:
        # Re-attach the first '#' to preserve the heading
        processed_text = "#" + header_split[1]
    else:
        # No header found—keep entire text
        processed_text = text_to_process

    # Part (b): remove from '---' onward
    processed_text = re.split(r"(?m)^---\s*$", processed_text, maxsplit=1)[0].strip()

    # If the text is too short, the Humanize API may reject it.
    if len(processed_text) < 50:
        typer.echo("Warning: Post is too short for the Humanize API (must be >= 50 chars).")
        # Write the stripped text as the "humanized" version (fallback)
        humanized_output_file.write_text(processed_text)
        typer.echo(f"(Fallback) Short blog post written to: {humanized_output_file}")
        return

    # 2) Submit the text to Undetectable.ai’s Humanize endpoint
    humanize_token = project.get_settings().humanize_api_token
    if not humanize_token:
        typer.echo("Warning: No HUMANIZE_API_TOKEN set in settings. Skipping humanization.")
        humanized_output_file.write_text(processed_text)
        return

    submit_url = "https://humanize.undetectable.ai/submit"
    document_url = "https://humanize.undetectable.ai/document"
    headers = {
        "apikey": humanize_token,
        "Content-Type": "application/json"
    }

    # Prepare the payload according to the doc examples
    payload = {
        "content": processed_text,
        "readability": "High School",
        "purpose": "General Writing",
        "strength": "More Human",
        "model": "v11",
    }

    try:
        # Step A: Submit the document
        submit_res = requests.post(submit_url, headers=headers, json=payload, timeout=30)
        if not submit_res.ok:
            # If the request fails, store the processed_text as fallback
            typer.echo(f"Humanization submit request failed (HTTP {submit_res.status_code}). Error: {json.dumps(submit_res.json())}")
            return

        submit_data = submit_res.json()
        if "error" in submit_data:
            # e.g. {"error": "Insufficient credits"}
            typer.echo(f"Humanization error:  Error: {json.dumps(submit_res.json())}")
            return

        # We expect e.g. {"status": "Document submitted successfully", "id": "..."}
        doc_id = submit_data.get("id")
        if not doc_id:
            typer.echo("No 'id' returned in submit response.")
            return

        # Step B: Retrieve the document until it's processed (basic polling)
        # You may need to adjust attempts or delay to suit typical processing time.
        humanized_text = processed_text  # fallback if retrieval fails
        for attempt in range(6):  # try up to 6 times
            doc_res = requests.post(document_url, headers=headers, json={"id": doc_id}, timeout=30)
            if doc_res.ok:
                doc_data = doc_res.json()
                if "error" in doc_data:
                    # e.g. {"error": "Insufficient credits"} or other
                    typer.echo(f"Humanization retrieval error: {doc_data['error']}")
                    break

                output_text = doc_data.get("output")
                # If 'output' is returned, we have the final text
                if output_text:
                    humanized_text = output_text
                    break
            else:
                # If we got a 4xx/5xx, break or keep polling as needed
                typer.echo(
                    f"Attempt {attempt + 1} to retrieve doc failed (HTTP {doc_res.status_code}). Error: {json.dumps(doc_res.json())}.")
                # doc_res.json() might have an error message
            time.sleep(2)  # wait a bit before next attempt

        # 3) Save the final text as `.humanized.md`
        humanized_output_file.write_text(humanized_text)
        typer.echo(f"Humanized blog post written to: {humanized_output_file}")

    except requests.RequestException as e:
        typer.echo(f"Humanization request error: {e}")
        raise e
