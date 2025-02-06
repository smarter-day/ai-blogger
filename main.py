import time
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from library import ai, env
from library.project import Project
from library.utils import get_file_hash

app = typer.Typer()
load_dotenv()


def do_fine_tuning(
    project: Project,
    summary_jsonl_file: Path,
    summary_hash: str,
) -> Optional[str]:
    file_id = ai.upload_training_file(project=project, file_path=summary_jsonl_file)
    if not file_id:
        typer.echo(f"Failed to upload file: {summary_jsonl_file}")
        raise typer.Exit(code=1)

    ai.wait_for_available_fine_tuning_slot(project=project)
    fine_tune_job = ai.fine_tune(
        project=project,
        file_id=file_id,
        model_name=project.get_settings().gpt_model,
    )

    typer.echo(
        f"Fine-tuning started for {summary_jsonl_file}. "
        f"Model: {project.get_settings().gpt_model}. "
        f"Job ID: {fine_tune_job.id}"
    )

    project.get_db().update_fine_tune_job_info(
        file_path=str(summary_jsonl_file),
        file_hash=summary_hash,
        fine_tuning_job=fine_tune_job,
    )

    time.sleep(project.get_settings().fine_tuning_check_status_delay)
    fine_tune_job = ai.handle_fine_tuning_status(
        project=project,
        job_id=fine_tune_job.id,
        summary_jsonl_file=str(summary_jsonl_file),
        summary_hash=summary_hash,
    )
    if fine_tune_job and fine_tune_job.fine_tuned_model:
        typer.echo(f"Fine-tuning completed. Model: {fine_tune_job.fine_tuned_model}")
    else:
        typer.echo(f"Fine-tuning failed for {summary_jsonl_file}. Error: {fine_tune_job.error}")
        raise typer.Exit(code=1)

    project.get_db().update_fine_tune_job_info(
        file_path=str(summary_jsonl_file),
        file_hash=summary_hash,
        fine_tuning_job=fine_tune_job,
    )
    return fine_tune_job.fine_tuned_model


@app.command()
def tune(project_id: str = typer.Argument(..., help="Project identifier")):
    """
    Execute fine-tuning process.
    """
    project = Project(project_id)
    summary_jsonl_file: Path = project.get_settings().summary_jsonl_file
    summary_hash = get_file_hash(summary_jsonl_file)

    # Check for previous job info from DB
    fine_tune_job_info, entry_hash = project.get_db().get_fine_tune_job_info(
        file_path=str(summary_jsonl_file)
    )
    fine_tune_model = None

    if entry_hash != summary_hash or not fine_tune_job_info:
        fine_tune_model = do_fine_tuning(project, summary_jsonl_file, summary_hash)
    else:
        typer.echo(f"No changes detected in {summary_jsonl_file}.")
        fine_tune_model = fine_tune_job_info.openai_tuning_job_model
        if not fine_tune_model:
            fine_tune_model = do_fine_tuning(project, summary_jsonl_file, summary_hash)

    if not fine_tune_model:
        typer.echo("Failed to fine-tune the model")
        raise typer.Exit(code=1)
    typer.echo(f"Fine-tuning job model: {fine_tune_model}")


@app.command()
def run(
    project_id: str = typer.Argument(..., help="Project identifier"),
    disable_fine_tuning: bool = typer.Option(
        True, "--disable-fine-tuning", help="Disable fine-tuning step"
    ),
):
    """
    Run project to generate articles.
    """
    project = Project(project_id)
    project.ensure_directories_exist()
    ai.combine_fine_tuning_files(project=project)

    if not disable_fine_tuning:
        summary_jsonl_file: Path = project.get_settings().summary_jsonl_file
        summary_hash = get_file_hash(summary_jsonl_file)
        fine_tune_job_info, entry_hash = project.get_db().get_fine_tune_job_info(
            file_path=str(summary_jsonl_file)
        )
        fine_tune_model = None

        if entry_hash != summary_hash or not fine_tune_job_info:
            fine_tune_model = do_fine_tuning(project, summary_jsonl_file, summary_hash)
        else:
            typer.echo(f"No changes detected in {summary_jsonl_file}.")
            fine_tune_model = fine_tune_job_info.openai_tuning_job_model
            if not fine_tune_model:
                fine_tune_model = do_fine_tuning(project, summary_jsonl_file, summary_hash)

        if not fine_tune_model:
            typer.echo("Failed to fine-tune the model")
            raise typer.Exit(code=1)
        typer.echo(f"Fine-tuning job model: {fine_tune_model}")

    article_prompt = project.get_settings().blog_prompt_filename.read_text()
    titles = project.get_settings().titles_file.read_text().splitlines()
    total_articles = project.get_settings().total_articles_per_title

    for title in titles:
        for i in range(1, total_articles + 1):
            for language_code, target_language in env.get_languages().items():
                results_dir = project.get_settings().results_dir / title
                results_dir.mkdir(parents=True, exist_ok=True)
                results_file = results_dir / f"result_{i}.{language_code}.md"
                if results_file.exists():
                    continue
                typer.echo(
                    f"Generating article {i}/{total_articles} for '{title}' in {target_language}..."
                )
                translated_article = ai.simple_ask(
                    client=project.get_openai_client(),
                    model_name=project.get_settings().gpt_model,
                    prompt=article_prompt,
                    article_title=title,
                    target_language=target_language,
                )
                results_file.write_text(translated_article)
                time.sleep(project.get_settings().gpt_api_delay)


if __name__ == "__main__":
    app()
