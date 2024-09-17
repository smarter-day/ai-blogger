from concurrent.futures import ProcessPoolExecutor, as_completed
import os
import openai
from openai import OpenAI
import time
import json
from dotenv import load_dotenv

load_dotenv()

# OpenAI client initialization
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Constants for rate limits
GPT_API_DELAY = 3  # Delay between OpenAI requests (in seconds)
IMAGE_API_DELAY = 12  # Delay between image generation requests (in seconds)
MAX_CONCURRENT_JOBS = 2  # Limit to 2 concurrent fine-tuning jobs
CHECK_STATUS_DELAY = 30  # Delay to wait between fine-tuning job status checks
MAX_RETRIES = 5  # Set a maximum number of retries
BACKOFF_TIME = 60  # Start with 60 seconds backoff time

model = "gpt-4o-2024-08-06"

# Paths for input files and result folder
TITLES_FILE = "./titles.txt"
PROMPT_FILE = "./prompt.txt"
RESULTS_DIR = "./results"
TUNING_DIR = "./tuning"  # Folder for text files for fine-tuning
PROCESSED_FILE_LOG = "./processed_files.txt"  # Keeps track of files that were already fine-tuned
UPLOADED_FILE_LOG = "./uploaded_files.txt"  # Keeps track of uploaded file IDs

# Languages for translation
LANGUAGES = {
    'en': 'English',
    'ru': 'Russian',
    'hi': 'Hindi',
    'zh': 'Chinese',
    'pt': 'Portuguese',
    'he': 'Hebrew',
    'ar': 'Arabic',
    'ja': 'Japanese'
}

# Create results directory if not exists
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)


# Function to load the last saved progress
def load_progress():
    progress_file = os.path.join(RESULTS_DIR, "progress.json")
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            return json.load(f)
    return {}


# Function to save progress
def save_progress(progress):
    progress_file = os.path.join(RESULTS_DIR, "progress.json")
    with open(progress_file, "w") as f:
        json.dump(progress, f)


# Function to read input files
def load_input_files():
    with open(TITLES_FILE, "r") as f:
        titles = [line.strip() for line in f if line.strip()]

    with open(PROMPT_FILE, "r") as f:
        base_prompt = f.read().strip()

    return titles, base_prompt


# Function to check how many articles exist for a given title
def count_existing_articles(title_folder):
    article_files = [f for f in os.listdir(title_folder) if f.startswith("article_") and f.endswith(".md")]
    return len(article_files)


# Function to generate blog articles using OpenAI
def generate_blog_article(title, base_prompt, article_num, model_name):
    prompt = f"{base_prompt}\n\nWrite a blog article ({article_num}/10) for the title: '{title}'"
    response = client.chat.completions.create(
        messages=[{
            "role": "user",
            "content": prompt
        }],
        model=model_name
    )
    return response.choices[0].message.content


# Function to check for gaps in articles or translations
def check_missing_articles_and_translations(titles, base_prompt, model_name):
    for title in titles:
        title_folder = os.path.join(RESULTS_DIR, title)
        if not os.path.exists(title_folder):
            os.makedirs(title_folder)

        existing_articles_count = count_existing_articles(title_folder)
        for article_num in range(existing_articles_count + 1, 11):  # Max 10 articles per title
            article_file = os.path.join(title_folder, f"article_{article_num}.en.md")

            # Generate the English version if not exists
            if not os.path.exists(article_file):
                print(f"Generating article {article_num}/10 for: {title}")
                article = generate_blog_article(title, base_prompt, article_num, model_name)
                with open(article_file, "w") as f:
                    f.write(article)
                time.sleep(GPT_API_DELAY)

            # Generate translations
            for lang_code, lang_name in LANGUAGES.items():
                if lang_code != 'en':  # Skip English, already handled
                    translated_file = os.path.join(title_folder, f"article_{article_num}.{lang_code}.md")
                    if not os.path.exists(translated_file):
                        print(f"Translating article {article_num} to {lang_name}")
                        translation = translate_article(article, lang_name)
                        with open(translated_file, "w") as f:
                            f.write(translation)
                        time.sleep(GPT_API_DELAY)


# Function to translate an article to a target language
def translate_article(article, target_language):
    prompt = f"Translate the following article to {target_language}:\n\n{article}"
    response = client.chat.completions.create(
        messages=[{
            "role": "user",
            "content": prompt
        }],
        model="gpt-4o"
    )
    return response.choices[0].message.content


# Function to check for gaps in articles and translations
def check_missing_articles_and_translations(titles, base_prompt, model_name):
    for title in titles:
        title_folder = os.path.join(RESULTS_DIR, title)
        if not os.path.exists(title_folder):
            os.makedirs(title_folder)

        # Check for existing articles in each language and generate missing ones
        for article_num in range(1, 11):  # Check up to 10 articles per title
            article_file = os.path.join(title_folder, f"article_{article_num}.en.md")

            # Generate the English version if not exists
            if not os.path.exists(article_file):
                print(f"Generating English article {article_num}/10 for: {title}")
                article = generate_blog_article(title, base_prompt, article_num, model_name)
                with open(article_file, "w") as f:
                    f.write(article)
                time.sleep(GPT_API_DELAY)

            # Generate translations for each language
            for lang_code, lang_name in LANGUAGES.items():
                if lang_code != 'en':  # Skip English, already handled
                    translated_file = os.path.join(title_folder, f"article_{article_num}.{lang_code}.md")
                    if not os.path.exists(translated_file):
                        print(f"Translating article {article_num} to {lang_name}")
                        translation = translate_article(article, lang_name)
                        with open(translated_file, "w") as f:
                            f.write(translation)
                        time.sleep(GPT_API_DELAY)


# Function to translate an article to a target language
def translate_article(article, target_language):
    prompt = f"Translate the following article to {target_language}:\n\n{article}"
    response = client.chat.completions.create(
        messages=[{
            "role": "user",
            "content": prompt
        }],
        model="gpt-4o"
    )
    return response.choices[0].message.content


# Function to load processed files list
def load_processed_files():
    if not os.path.exists(PROCESSED_FILE_LOG):
        return set()

    with open(PROCESSED_FILE_LOG, "r") as f:
        return set(line.strip() for line in f)


# Function to load uploaded files list
def load_uploaded_files():
    if not os.path.exists(UPLOADED_FILE_LOG):
        return {}

    with open(UPLOADED_FILE_LOG, "r") as f:
        return dict(line.strip().split(',') for line in f if line.strip())


# Function to check if a fine-tuning job has already been created for the uploaded file ID
def check_existing_fine_tuning_job(file_id):
    """
    Function to check if a fine-tuning job has already been created for the uploaded file ID.
    If the job exists and is running or pending, we skip creating a new job.
    """
    try:
        # Fetch the list of all fine-tuning jobs
        fine_tuning_jobs = client.fine_tuning.jobs.list()

        # Check if there's an existing fine-tuning job for this file_id
        for job in fine_tuning_jobs.data:
            if job.training_file == file_id and job.status in ['running', 'pending']:
                print(f"Existing fine-tuning job {job.id} for file ID {file_id} is {job.status}. Skipping...")
                return True
        return False
    except Exception as e:
        print(f"Error while checking fine-tuning jobs: {str(e)}")
        return False


# Function to create JSONL file for fine-tuning in chat format
def create_jsonl_chat_format(text_content, output_file):
    """
    Converts the given text content into a JSONL format suitable for fine-tuning a chat model.
    Each line in the input text file is treated as a user message, and the assistant responds with pre-defined content.
    """
    with open(output_file, "w") as f_out:
        for line in text_content.split("\n"):
            if line.strip():
                json_data = {
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": line.strip()},
                        {"role": "assistant", "content": "Here is some valuable information."}
                    ]
                }
                f_out.write(json.dumps(json_data) + "\n")


# Function to save uploaded file ID
def save_uploaded_file(file_name, file_id):
    """
    Saves the uploaded file name and corresponding file ID to a log file.
    This is to prevent re-uploading files that are already uploaded.
    """
    with open(UPLOADED_FILE_LOG, "a") as f:
        f.write(f"{file_name},{file_id}\n")


def wait_for_available_slot():
    """
    Waits until an available fine-tuning slot is open (less than 3 active fine-tuning jobs).
    """
    while True:
        try:
            # List the active fine-tuning jobs (limit to 3 most recent)
            active_jobs = client.fine_tuning.jobs.list(limit=3)
            running_jobs = [job for job in active_jobs.data if job.status in ['running', 'pending']]

            # If fewer than 3 jobs are running, a slot is available
            if len(running_jobs) < 3:
                print(f"Available fine-tuning slot found. Active jobs: {len(running_jobs)}")
                return
            else:
                print(f"Waiting for available fine-tuning slot. Active jobs: {len(running_jobs)}")
                time.sleep(CHECK_STATUS_DELAY)  # Wait before checking again
        except Exception as e:
            print(f"Error while checking fine-tuning jobs: {str(e)}. Retrying in {CHECK_STATUS_DELAY} seconds.")
            time.sleep(CHECK_STATUS_DELAY)


# Function to check fine-tuning job status
def check_fine_tuning_status(fine_tune_id):
    """
    Checks the status of the fine-tuning job.
    Continues to poll the job status until it succeeds or fails.
    """
    while True:
        try:
            fine_tune_status = client.fine_tuning.jobs.retrieve(fine_tune_id)
            status = fine_tune_status.status

            if status == 'succeeded':
                print(f"Fine-tuning job {fine_tune_id} succeeded.")
                return True
            elif status == 'failed':
                print(f"Fine-tuning job {fine_tune_id} failed: {fine_tune_status.error}")
                return False
            else:
                print(f"Fine-tuning job {fine_tune_id} is {status}. Waiting...")
                time.sleep(CHECK_STATUS_DELAY)  # Wait before checking again
        except Exception as e:
            print(f"Error while checking fine-tuning job status: {str(e)}")
            time.sleep(CHECK_STATUS_DELAY)


# Function to save processed file
def save_processed_file(file_name):
    """
    Marks a file as processed by adding its name to a log file.
    This ensures the same file is not processed multiple times.
    """
    with open(PROCESSED_FILE_LOG, "a") as f:
        f.write(file_name + "\n")


def fine_tune_single_file(file_path, model, retries=0):
    try:
        # Skip processing if the file has already been fine-tuned
        if file_path in load_processed_files():
            print(f"{file_path} has already been fine-tuned. Skipping...")
            return

        # Check if file is already uploaded
        uploaded_files = load_uploaded_files()
        if file_path in uploaded_files:
            file_id = uploaded_files[file_path]
            print(f"{file_path} has already been uploaded. Using existing file ID: {file_id}.")

            # Check if a fine-tuning job is already running or pending for this file
            if check_existing_fine_tuning_job(file_id):
                return  # Skip creating a new fine-tuning job if one is already running
        else:
            # Upload the file if not uploaded yet
            with open(file_path, "r") as f:
                text_content = f.read()

            jsonl_file = file_path + ".jsonl"
            create_jsonl_chat_format(text_content, jsonl_file)

            print(f"Uploading {jsonl_file} for fine-tuning.")
            with open(jsonl_file, 'rb') as f:
                response = client.files.create(file=f, purpose='fine-tune')
            file_id = response.id
            save_uploaded_file(file_path, file_id)

        # Wait for an available fine-tuning slot before proceeding
        wait_for_available_slot()

        # Start the fine-tuning process
        print(f"Starting fine-tuning for {file_path} with file ID {file_id}.")
        fine_tune_response = client.fine_tuning.jobs.create(
            training_file=file_id,
            model=model
        )
        fine_tune_id = fine_tune_response.id
        print(f"Fine-tuning job {fine_tune_id} started.")

        # Wait for the job to complete
        if check_fine_tuning_status(fine_tune_id):
            save_processed_file(file_path)

    except openai.RateLimitError as e:
        if retries < MAX_RETRIES:
            backoff_time = BACKOFF_TIME * (2 ** retries)  # Exponential backoff
            print(f"Rate limit hit: {str(e)}. Retrying after {backoff_time} seconds...")
            time.sleep(backoff_time)
            fine_tune_single_file(file_path, model, retries + 1)
        else:
            print(f"Max retries reached for {file_path}. Skipping...")

    except Exception as e:
        print(f"Error occurred: {str(e)}. Retrying...")
        time.sleep(10)  # General retry after error
        fine_tune_single_file(file_path, model, retries)


# Main script logic
def main():
    processed_files = load_processed_files()
    files_to_tune = [os.path.join(TUNING_DIR, file_name) for file_name in os.listdir(TUNING_DIR) if
                     file_name not in processed_files and str(file_name).endswith('.json')]

    with ProcessPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as executor:
        futures = [executor.submit(fine_tune_single_file, file_path, model) for file_path in files_to_tune]

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error in fine-tuning job: {str(e)}")

    print("All fine-tuning jobs have been processed.")

    titles, base_prompt = load_input_files()
    progress = load_progress()
    start_index = progress.get("last_completed_index", 0)

    # Check for missing articles and translations
    check_missing_articles_and_translations(titles, base_prompt, model)

    for i, title in enumerate(titles[start_index:], start=start_index):
        title_folder = os.path.join(RESULTS_DIR, title)
        if not os.path.exists(title_folder):
            os.makedirs(title_folder)

        existing_articles_count = count_existing_articles(title_folder)

        max_articles = 20
        for article_num in range(existing_articles_count + 1, max_articles + 1):
            if not os.path.exists(os.path.join(title_folder, f"article_{article_num}.md")):
                print(f"Generating article {article_num}/{max_articles} for: {title}")
                article = generate_blog_article(title, base_prompt, article_num, model)
                article_file = os.path.join(title_folder, f"article_{article_num}.md")
                with open(article_file, "w") as f:
                    f.write(article)

                time.sleep(GPT_API_DELAY)

        progress["last_completed_index"] = i + 1
        save_progress(progress)

    print("All titles have been processed.")


if __name__ == "__main__":
    main()
