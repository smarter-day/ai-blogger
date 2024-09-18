import time

import typer
from dotenv import load_dotenv

from library import ai, env
from library.project import Project
from library.utils import get_file_hash

load_dotenv()


def run_project(project_id: str):
    project = Project(project_id)
    project.ensure_directories_exist()
    ai.combine_fine_tuning_files(project=project)

    summary_jsonl_file = project.get_settings().summary_jsonl_file
    summary_hash = get_file_hash(summary_jsonl_file)
    fine_tune_job, entry_hash = project.get_db().get_fine_tune_job_info(
        file_path=str(summary_jsonl_file),
    )

    # If hash does not match, upload the file before fine-tuning
    fine_tune_model = None
    if entry_hash != summary_hash:
        file_id = ai.upload_training_file(
            project=project,
            file_path=summary_jsonl_file,
        )
        if not file_id:
            print(f"Failed to upload file for fine-tuning: {str(summary_jsonl_file)}")
            exit(1)

        # When file uploaded, we wait for available slot
        ai.wait_for_available_fine_tuning_slot(project=project)

        # Fine-tune the uploaded file
        fine_tune_job = ai.fine_tune(
            project=project,
            file_id=file_id,
            model_name=project.get_settings().fine_tuning_base_model,
        )

        # Save fine-tuning job details in the database
        typer.echo(f"Fine-tuning started for {summary_jsonl_file}. "
                   f"Model: {project.get_settings().fine_tuning_base_model}. "
                   f"Fine tuning job ID: {fine_tune_job.id}")
        project.get_db().update_fine_tune_job_info(
            file_path=str(summary_jsonl_file),
            file_hash=summary_hash,
            fine_tuning_job=fine_tune_job
        )
        typer.echo(f"Saved in db fine-tuning job")

        # Wait for fine-tuning job to finish
        time.sleep(project.get_settings().fine_tuning_check_status_delay)
        fine_tune_job = ai.handle_fine_tuning_status(
            project=project,
            job_id=fine_tune_job.id,
            summary_jsonl_file=summary_jsonl_file,
            summary_hash=summary_hash,
        )
        if fine_tune_job:
            print(f"Fine-tuning completed successfully. Model: {fine_tune_job.fine_tuned_model}")
        else:
            print(f"Fine-tuning failed for {summary_jsonl_file}. Error: {fine_tune_job.error}")
            exit(1)

        typer.echo(f"Updating fine-tuning job details in db")
        project.get_db().update_fine_tune_job_info(
            file_path=str(summary_jsonl_file),
            file_hash=summary_hash,
            fine_tuning_job=fine_tune_job,
        )
        fine_tune_model = fine_tune_job.fine_tuned_model
        typer.echo(f"Updated fine-tuning job details in db")
    else:
        print(f"No changes detected in {summary_jsonl_file}. Skipping fine-tuning.")
        fine_tune_model = fine_tune_job.fine_tuned_model

    article_prompt = project.get_settings().article_prompt_file.read_text()
    titles = project.get_settings().titles_file.read_text().splitlines()
    for title in titles:
        total_articles_need = project.get_settings().total_articles_per_title
        for i in range(1, total_articles_need + 1):
            for language_code, target_language in env.get_languages().items():
                results_dir = project.get_settings().results_dir / title
                results_dir.mkdir(parents=True, exist_ok=True)
                results_file = results_dir / f"result_{i}.{language_code}.md"
                if results_file.exists():
                    continue
                typer.echo(f"Generating article {i}/{total_articles_need} for '{title}' in {target_language}...")
                translated_article = ai.simple_ask(
                    client=project.get_openai_client(),
                    model_name=fine_tune_model,
                    prompt=article_prompt,
                    target_language=target_language,
                )
                results_file.write_text(translated_article)
                time.sleep(project.get_settings().gpt_api_delay)


if __name__ == "__main__":
    typer.run(run_project)
