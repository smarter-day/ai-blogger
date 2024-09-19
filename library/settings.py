import os
from pathlib import Path

from dotenv import load_dotenv

from library.env import get_env_var


class Settings:
    def __init__(self, project_id: str):
        self.project_id = project_id

        # Load the project's env file if it exists, and override root credentials if needed
        project_env_path = Path(f'./projects/{project_id}/project.env')
        load_dotenv(project_env_path) if project_env_path.exists() else {}

        # Load necessary project paths and settings
        self.project_base = Path(f"./projects/{project_id}")
        self.results_dir = self.project_base / os.environ.get("RESULTS_DIR", "results")
        self.prompts_dir = self.project_base / get_env_var("PROMPTS_DIR", "prompts")
        self.tuning_dir = self.project_base / get_env_var("TUNING_DIR", "tuning")
        self.db_file = self.project_base / get_env_var("DB_FILE", "database.db")

        # Project-specific.
        # TODO: move to a child class
        self.total_articles_per_title = int(get_env_var("TOTAL_ARTICLES_PER_TITLE", 3))
        self.titles_file = self.project_base / get_env_var("TITLES_FILE", "titles.txt")
        self.article_prompt_file = self.prompts_dir / get_env_var("ARTICLE_PROMPT_FILE", "article_prompt.md")
        self.translation_prompt_file = self.prompts_dir / get_env_var("TRANSLATION_PROMPT_FILE",
                                                                      "translation_prompt.txt")
        self.summary_jsonl_file = self.tuning_dir / get_env_var("SUMMARY_JSONL_FILE", "summary.jsonl")

        # GPT-related settings (can be overridden by the project env)
        self.gpt_api_delay = int(get_env_var("GPT_API_DELAY", 3))
        self.fine_tuning_check_status_delay = int(get_env_var("FINE_TUNING_CHECK_STATUS_DELAY", 10))
        self.max_retries = int(get_env_var("MAX_RETRIES", 5))
        self.backoff_time = int(get_env_var("BACKOFF_TIME", 60))
        self.fine_tuning_max_concurrent_jobs = int(get_env_var("FINE_TUNING_MAX_CONCURRENT_JOBS", 2))
        self.fine_tuning_base_model = get_env_var("FINE_TUNING_BASE_MODEL")
