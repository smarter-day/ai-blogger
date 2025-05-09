#!.venv/bin/python

import time
from typing import List

import typer
from dotenv import load_dotenv

from library import ai, env
from library.env import set_languages
from library.project import Project
from library.settings import PostType

app = typer.Typer()
load_dotenv()


@app.command()
def generate(
    project_id: str = typer.Argument(..., help="Project identifier"),
    post_types: str = typer.Option(
        "",
        "--post-types",
        help="Types of post to generate: blog, facebook, linkedin, short, or x-short. Comma-separated"
    ),
    languages: str = typer.Option(
        "",
        "--languages",
        help="Target languages for the generated posts. Comma-separated"
    )
):
    """
    Generate posts in multiple target languages.
    """
    if not post_types:
        post_types = [post_type.value for post_type in PostType]
        post_types = ','.join(post_types)

    post_types_list: List[PostType] = []
    for t in post_types.lower().split(','):
        try:
            pt = PostType(str(t).strip())
            post_types_list.append(pt)
        except ValueError:
            typer.echo(f"Invalid post type: {t}. Must be one of: long, short, or x-short.")
            raise typer.Exit(code=1)

    project = Project(project_id)
    settings = project.get_settings()

    titles = settings.titles_file.read_text().splitlines()
    total_articles = settings.total_articles_per_title

    if languages:
        set_languages(languages)

    for title in titles:
        if title.startswith('#') or not title.strip():
            # typer.echo(f"Skipping: {title}")
            continue
        for i in range(1, total_articles + 1):
            for language_code, target_language in env.get_languages().items():
                for pt in post_types_list:
                    prompt_file = settings.post_prompt_files[pt]
                    if not prompt_file.exists():
                        typer.echo(f"Prompt file for {pt.value} posts not found: {prompt_file}")
                        raise typer.Exit(code=1)
                    prompt = prompt_file.read_text()

                    # Use the proper directory for the post type and title subfolder.
                    output_dir = project.get_output_directory(pt) / title
                    output_dir.mkdir(parents=True, exist_ok=True)
                    output_file = output_dir / f"result_{i}.{language_code}.md"
                    if not (output_file.exists() and output_file.read_text()):
                        typer.echo(
                            f"Generating '{pt.value}' post {i}/{total_articles} for '{title}' in {target_language}..."
                        )
                        generated_post = ai.simple_ask(
                            client=project.get_openai_client(),
                            model_name=settings.gpt_model,
                            prompt=prompt,
                            article_title=title,
                            target_language=target_language,
                        )
                        output_file.write_text(generated_post)
                        typer.echo(f"Generated post saved to: {output_file}")

                    # Humanize the generated post contents
                    humanized_file = output_file.parent / f"{output_file.stem}.humanized.md"
                    if not (humanized_file.exists() and humanized_file.read_text()):
                        typer.echo(f'Humanizing post contents for: {humanized_file}')
                        ai.humanize(
                            project=project,
                            humanized_output_file=humanized_file,
                            generated_post=output_file.read_text(),
                        )
                    else:
                        continue

                    humanized_reviewed_file = output_file.parent / f"{output_file.stem}.humanized.reviewed.md"
                    if not (humanized_reviewed_file.exists() and humanized_reviewed_file.read_text()):
                        typer.echo(f'Reviewing humanized contents with GPT for: {humanized_file}')
                        humanized_reviewed_content = ai.simple_ask(
                            client=project.get_openai_client(),
                            model_name=settings.gpt_model,
                            prompt="""You are an expert text editor tasked with reviewing the provided text carefully. Your goal is to enhance readability, correct grammar, remove unnecessary or strange characters, and maintain proper text formatting without altering the original meaning, words, or key information.

Specifically, you must:
- Correct any spelling, grammar, or punctuation errors.
- Remove extraneous characters, symbols, or formatting artifacts.
- Ensure consistent and clear formatting, including paragraphs, spacing, and alignment.
- Identify headings within the text. If headings are not clearly formatted as such, prepend them with an appropriate number of '#' characters (Markdown syntax) so they match the hierarchy and formatting style of other headings in the document.
- Preserve all original content and meaning precisely—do not alter phrasing, wording, or informational content beyond these formatting and clarity improvements.

Only perform these actions; do not add, remove, or modify the content's meaning, context, or details in any other way.

Here is the text to edit:

{content}
""",
                            content=humanized_file.read_text(),
                        )
                        humanized_reviewed_file.write_text(humanized_reviewed_content)
                        typer.echo(f"Reviewed humanized data and saved to: {humanized_reviewed_file}")

                    time.sleep(settings.gpt_api_delay)


if __name__ == "__main__":
    app()
