#!.venv/bin/python
import json

import openai
import typer
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.table import Table

from library.ai import simple_ask
from library.project import Project

# Initialize Typer app
app = typer.Typer()
console = Console()
load_dotenv()


# Define your categories
CATEGORIES = [
    "Productivity Strategies & Time Management",
    "Task Management & Organization",
    "Habit Formation & Behavioral Science",
    "Mindfulness & Well-being",
    "Remote Work & Collaboration",
    "Tools & Technology",
    "Personal Development & Motivation",
    "Leadership & Management",
    "Health & Energy Management",
    "Success Stories & Case Studies"
]

# Function to read the content of the markdown file
def read_markdown_file(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        raise typer.Exit(code=1)


# Main function to process the markdown file
@app.command()
def estimate_post(
    project_id: str = typer.Argument(..., help="Project identifier"),
    post: str = typer.Option(..., help="Full path to the markdown file of the post"),
):
    project = Project(project_id)
    settings = project.get_settings()
    post_content = read_markdown_file(post)

    # Create the prompt for the AI
    prompt = f"""
    You are a blog post categorizer and meta tag generator. Follow these instructions EXACTLY:

    1. Use the following list of categories:
    {', '.join(CATEGORIES)}

    2. Analyze the blog post text provided below and select the single most appropriate category from the list.

    3. Generate an SEO-optimized meta title that is strictly between 50 and 60 characters.

    4. Generate an SEO-optimized meta description that is strictly between 100 and 150 characters.

    5. Follow Google's best practices for meta titles and descriptions: https://developers.google.com/search/docs/appearance/title-link#page-titles.

    6. Your output must be valid JSON with exactly these keys: "category", "meta_title", and "meta_description". Do not include any extra text, markdown, or explanation.

    Blog Post:
    {post_content}

    Respond ONLY with a JSON object like this (don't wrap it with any "```" decorators or json prefixes. Respond me only as json):
    {{
        "category": "Selected Category",
        "meta_title": "Generated Meta Title",
        "meta_description": "Generated Meta Description"
    }}
    """

    response = simple_ask(
        client=project.get_openai_client(),
        model_name=settings.gpt_model,
        prompt=prompt,
    )

    # Parse the AI's response
    try:
        console.print(response)
        result = json.loads(response)
        category = result.get("category", "N/A")
        meta_title = result.get("meta_title", "N/A")
        meta_description = result.get("meta_description", "N/A")
    except Exception as e:
        console.print(f"[red]Error parsing AI response: {e}[/red]")
        raise typer.Exit(code=1)

    # Display the result in a table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Field")
    table.add_column("Content")
    table.add_row("Category", category)
    table.add_row("Meta Title", meta_title)
    table.add_row("Meta Description", meta_description)

    console.print(table)

if __name__ == "__main__":
    app()
