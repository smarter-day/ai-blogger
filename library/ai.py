import json
import os
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, BinaryIO, List, Optional, Union

import openai
import requests
import typer
from openai import APIError, BadRequestError
from openai.types.fine_tuning import FineTuningJob
from tenacity import (retry, retry_if_exception, stop_after_attempt,
                      wait_exponential)

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


class HumanizerProvider(ABC):
    """Interface all humanizers must follow."""

    name: str = "humanizer"

    @abstractmethod
    def humanize(self, text: str) -> str:
        """Return a humanized version of text or raise on failure."""
        raise NotImplementedError


class RephrasyHumanizer(HumanizerProvider):
    def __init__(
        self,
        api_key: str,
        api_url: str,
        model: str = "undetectable",
        language: str = "",
        words: bool = False,
        costs: bool = False,
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model or "undetectable"
        self.language = language or ""
        self.words = bool(words)
        self.costs = bool(costs)
        self.timeout = timeout
        self.name = "rephrasy.ai"

    def humanize(self, text: str) -> str:
        if not self.api_key:
            raise ValueError("REPHRASY_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model": self.model,
        }

        if self.language:
            payload["language"] = self.language
        if self.words:
            payload["words"] = True
        if self.costs:
            payload["costs"] = True

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        # Try common keys the service might return
        for key in ("output", "result", "text", "rephrased_text"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value

        raise ValueError("Rephrasy.ai response did not include output text")


class UndetectableHumanizer(HumanizerProvider):
    def __init__(
        self,
        api_key: str,
        submit_url: str = "https://humanize.undetectable.ai/submit",
        document_url: str = "https://humanize.undetectable.ai/document",
        attempts: int = 6,
        poll_delay: int = 2,
    ):
        self.api_key = api_key
        self.submit_url = submit_url
        self.document_url = document_url
        self.attempts = attempts
        self.poll_delay = poll_delay
        self.name = "undetectable.ai"

    def humanize(self, text: str) -> str:
        if not self.api_key:
            raise ValueError("HUMANIZE_API_TOKEN is not configured")

        headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "content": text,
            "readability": "High School",
            "purpose": "General Writing",
            "strength": "More Human",
            "model": "v11",
        }

        submit_res = requests.post(
            self.submit_url,
            headers=headers,
            json=payload,
            timeout=30,
        )
        if not submit_res.ok:
            raise ValueError(
                f"Submit request failed (HTTP {submit_res.status_code}): "
                f"{json.dumps(submit_res.json())}"
            )

        submit_data = submit_res.json()
        if "error" in submit_data:
            raise ValueError(f"Humanization error: {json.dumps(submit_data)}")

        doc_id = submit_data.get("id")
        if not doc_id:
            raise ValueError("No 'id' returned in submit response.")

        for attempt in range(self.attempts):
            doc_res = requests.post(
                self.document_url,
                headers=headers,
                json={"id": doc_id},
                timeout=30,
            )
            if doc_res.ok:
                doc_data = doc_res.json()
                if "error" in doc_data:
                    raise ValueError(f"Retrieval error: {doc_data['error']}")

                output_text = doc_data.get("output")
                if output_text:
                    return output_text
            else:
                typer.echo(
                    f"Attempt {attempt + 1} retrieve failed "
                    f"(HTTP {doc_res.status_code}): {json.dumps(doc_res.json())}"
                )
            time.sleep(self.poll_delay)

        raise TimeoutError("Undetectable.ai did not return output after polling.")


def _resolve_humanizer(settings) -> Optional[HumanizerProvider]:
    """Choose a humanizer provider based on env-backed settings."""
    provider = (settings.humanize_provider or "rephrasy").lower()

    def _to_bool(val) -> bool:
        return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}

    # Preferred provider
    if provider == "rephrasy":
        if settings.rephrasy_api_key:
            return RephrasyHumanizer(
                api_key=settings.rephrasy_api_key,
                api_url=settings.rephrasy_api_url,
                model=settings.rephrasy_model,
                language=settings.rephrasy_language,
                words=_to_bool(settings.rephrasy_words),
                costs=_to_bool(settings.rephrasy_costs),
            )
        typer.echo(
            "Warning: REPHRASY_API_KEY is missing; falling back to Undetectable.ai "
            "if configured."
        )
        if settings.humanize_api_token:
            return UndetectableHumanizer(api_key=settings.humanize_api_token)
        return None

    if provider in {"undetectable", "undetectable.ai", "humanize"}:
        if settings.humanize_api_token:
            return UndetectableHumanizer(api_key=settings.humanize_api_token)
        typer.echo(
            "Warning: HUMANIZE_API_TOKEN is missing; cannot use Undetectable.ai."
        )
        return None

    # Unknown provider: try reasonable fallbacks
    typer.echo(
        f"Warning: Unknown humanizer provider '{provider}'. "
        "Defaulting to rephrasy.ai if configured."
    )
    if settings.rephrasy_api_key:
        return RephrasyHumanizer(
            api_key=settings.rephrasy_api_key,
            api_url=settings.rephrasy_api_url,
        )
    if settings.humanize_api_token:
        return UndetectableHumanizer(api_key=settings.humanize_api_token)
    return None


def humanize(project, humanized_output_file: Path, generated_post: str):
    """
    Strip metadata from generated_post, delegate humanization to the configured
    provider, and write the output.
    """

    # 1) Remove everything before the first '#' and everything after '---'
    text_to_process = generated_post

    header_split = re.split(r"(?m)^#+", text_to_process, maxsplit=1)
    if len(header_split) == 2:
        processed_text = "#" + header_split[1]
    else:
        processed_text = text_to_process

    processed_text = re.split(r"(?m)^---\s*$", processed_text, maxsplit=1)[0].strip()

    if len(processed_text) < 50:
        typer.echo(
            "Warning: Post is too short for the humanizer API (must be >= 50 chars)."
        )
        humanized_output_file.write_text(processed_text)
        typer.echo(f"(Fallback) Short blog post written to: {humanized_output_file}")
        return

    settings = project.get_settings()
    provider = _resolve_humanizer(settings)

    if not provider:
        typer.echo("No humanizer provider configured; writing original content.")
        humanized_output_file.write_text(processed_text)
        return

    try:
        humanized_text = provider.humanize(processed_text)
    except Exception as exc:
        typer.echo(f"Humanization via {provider.name} failed: {exc}")
        humanized_text = processed_text

    humanized_output_file.write_text(humanized_text)
    typer.echo(f"Humanized blog post written to: {humanized_output_file}")
