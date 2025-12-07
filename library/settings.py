import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

from library.env import get_env_var


class PostType(Enum):
    BLOG = "blog"
    DISCORD = "discord"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    SHORT = "short"
    X_SHORT = "x-short"


class Settings:
    def __init__(self, project_id: str):
        self.project_id = project_id

        # Load the project's env file if it exists
        project_env_path = Path(f"./projects/{project_id}/project.env")
        if project_env_path.exists():
            load_dotenv(project_env_path)

        self.project_base = Path(f"./projects/{project_id}")

        # Directories for generated posts per type
        self.results_dir = self.project_base / os.environ.get("RESULTS_DIR", "results")
        self.post_dirs = {
            PostType.BLOG: self.results_dir / os.environ.get("BLOG_POSTS_DIR", "blog"),
            PostType.FACEBOOK: self.results_dir / os.environ.get("FACEBOOK_POSTS_DIR", "facebook"),
            PostType.LINKEDIN: self.results_dir / os.environ.get("LINKEDIN_POSTS_DIR", "linkedin"),
            PostType.DISCORD: self.results_dir / os.environ.get("DISCORD_POSTS_DIR", "discord"),
            PostType.REDDIT: self.results_dir / os.environ.get("REDDIT_POSTS_DIR", "reddit"),
            PostType.TELEGRAM: self.results_dir / os.environ.get("TELEGRAM_POSTS_DIR", "telegram"),
            PostType.TWITTER: self.results_dir / os.environ.get("TWITTER_POSTS_DIR", "twitter"),
            PostType.SHORT: self.results_dir / os.environ.get("SHORT_POSTS_DIR", "short"),
            PostType.X_SHORT: self.results_dir / os.environ.get("X_SHORT_POSTS_DIR", "x-short"),
        }

        # Prompt files per post type
        self.prompts_dir = self.project_base / get_env_var("PROMPTS_DIR", "prompts")
        self.post_prompt_files = {
            PostType.BLOG: self.prompts_dir / get_env_var("BLOG_PROMPT_FILENAME", PostType.BLOG.value + ".md"),
            PostType.FACEBOOK: self.prompts_dir / get_env_var("FACEBOOK_PROMPT_FILENAME", PostType.FACEBOOK.value + ".md"),
            PostType.LINKEDIN: self.prompts_dir / get_env_var("LINKEDIN_PROMPT_FILENAME", PostType.LINKEDIN.value + ".md"),
            PostType.DISCORD: self.prompts_dir / get_env_var("DISCORD_PROMPT_FILENAME", PostType.DISCORD.value + ".md"),
            PostType.REDDIT: self.prompts_dir / get_env_var("REDDIT_PROMPT_FILENAME", PostType.REDDIT.value + ".md"),
            PostType.TELEGRAM: self.prompts_dir / get_env_var("TELEGRAM_PROMPT_FILENAME", PostType.TELEGRAM.value + ".md"),
            PostType.TWITTER: self.prompts_dir / get_env_var("TWITTER_PROMPT_FILENAME", PostType.TWITTER.value + ".md"),
            PostType.SHORT: self.prompts_dir / get_env_var("SHORT_POST_PROMPT_FILE", PostType.SHORT.value + ".md"),
            PostType.X_SHORT: self.prompts_dir / get_env_var("X_SHORT_POST_PROMPT_FILE", PostType.X_SHORT.value + ".md"),
        }

        self.tuning_dir = self.project_base / get_env_var("TUNING_DIR", "tuning")
        self.db_file = self.project_base / get_env_var("DB_FILE", "database.db")

        # Post-specific settings
        self.titles_file = self.project_base / get_env_var("TITLES_FILE", "titles.txt")
        self.total_articles_per_title = int(get_env_var("TOTAL_ARTICLES_PER_TITLE", 1))

        # GPT-related settings
        self.gpt_api_delay = int(get_env_var("GPT_API_DELAY", 3))
        self.fine_tuning_check_status_delay = int(get_env_var("FINE_TUNING_CHECK_STATUS_DELAY", 10))
        self.max_retries = int(get_env_var("MAX_RETRIES", 5))
        self.backoff_time = int(get_env_var("BACKOFF_TIME", 60))
        self.fine_tuning_max_concurrent_jobs = int(get_env_var("FINE_TUNING_MAX_CONCURRENT_JOBS", 2))
        self.gpt_model = get_env_var("GPT_MODEL")
        self.humanize_api_token = get_env_var("HUMANIZE_API_TOKEN")
        self.humanize_provider = get_env_var("HUMANIZE_PROVIDER", "rephrasy")
        self.rephrasy_api_key = get_env_var("REPHRASY_API_KEY")
        self.rephrasy_api_url = get_env_var(
            "REPHRASY_API_URL",
            "https://v2-humanizer.rephrasy.ai/api"
        )
        self.rephrasy_model = get_env_var("REPHRASY_MODEL", "undetectable")
        self.rephrasy_language = get_env_var("REPHRASY_LANGUAGE", "")
        self.rephrasy_words = get_env_var("REPHRASY_WORDS", "false")
        self.rephrasy_costs = get_env_var("REPHRASY_COSTS", "false")
