import os

from library import constants


def get_env_var(key: str, default=None) -> str:
    """
    Get environment variables from the project-specific env file or fallback to root env.
    """
    return os.getenv(key, default)


def set_env_var(key: str, value):
    os.environ.setdefault(key, value)
    os.environ[key] = value


def get_api_key() -> str:
    """
    Retrieves the OpenAI API key from the project environment, or falls back to the root .env.
    """
    return get_env_var("OPENAI_API_KEY")


def get_languages() -> dict:
    lang_mapping = constants.LANGUAGES_MAPPING
    langs = get_env_var("TRANSLATION_LANGUAGES", "").split(",")
    return {lang.strip(): lang_mapping.get(lang.strip(), lang.strip()) for lang in langs}

def set_languages(languages: str) -> dict:
    set_env_var("TRANSLATION_LANGUAGES", languages.strip())
    return get_languages()
