# AI Blogger Project

This project is an AI-powered article generator that fine-tunes models using OpenAI's API. The system generates and translates articles across multiple languages and supports managing multiple distinct projects. Each project has its own configuration, fine-tuning datasets, and article prompts, providing flexibility for creating unique content streams.

## Features

- Fine-tunes AI models with custom datasets.
- Supports multiple projects with isolated settings, titles, and output directories.
- Generates and translates articles using AI-powered prompts.
- Automatically translates generated articles into multiple languages.
- Manages fine-tuning job statuses and efficiently uploads new training files only when necessary.
- **Publishes blog posts to HubSpot CMS** with automatic markdown-to-HTML conversion.

## Multi-Project Approach

The system is designed to handle multiple distinct projects, each with its own dataset, prompts, and article generation pipeline. Each project is maintained in its own directory, allowing you to easily manage different streams of content.

### Project Structure

Each project is stored in its own directory under a common root folder. For example:

```
projects/
│
├── productivity/
│   ├── tuning/              # Fine-tuning data
│   ├── results/             # Generated articles
│   ├── titles.txt           # List of article titles
│   ├── prompts/             # Custom prompt files for articles
│   ├── .env                 # Environment variables specific to this project
│
└── tech/
    ├── tuning/
    ├── results/
    ├── titles.txt
    ├── prompts/
    ├── .env
```

Each project has its own environment settings, training data, and output directories, allowing multiple distinct projects to run independently within the system.

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-blogger.git
cd ai-blogger
```

### 2. Virtual Environment

Create a Python virtual environment and activate it.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
```

### 4. AI Support

Download the required spaCy language model for text processing:

```bash
python -m spacy download en_core_web_sm
```

### 5. Prepare Project Configuration

1. Copy the example environment file:

    ```bash
    cp .env.example .env
    ```

2. Edit the `.env` file and configure the necessary environment variables, such as OpenAI API keys, paths, and project-specific settings.

### 6. Prepare Data

Use the data preparation script to process the training data into the format needed for fine-tuning:

```bash
python3 prepare.py
```

The preparation script processes Markdown and text files, converting them into a format suitable for AI fine-tuning. Markdown files are parsed to retain their hierarchical structure, and plain text files are cleaned up for valuable content extraction.

## Running the Project

### 1. Fine-Tune a Model and Generate Articles

To fine-tune the model and generate articles for a specific project, run the main script and provide the project ID:

```bash
python3 main.py <project_id>
```

For example, to run the `productivity` project:

```bash
python3 main.py productivity
```

This will:

- Combine fine-tuning files for the project.
- Upload the training file (if necessary) and wait for an available fine-tuning slot.
- Start the fine-tuning process if the training data has changed.
- Generate articles based on the titles in the `titles.txt` file and article prompts.
- Translate the generated articles into multiple languages, as specified in the project settings.

### 2. Workflow Details

- **Fine-Tuning**: The system checks for changes in the fine-tuning dataset by comparing file hashes. If the dataset has changed, the system uploads the new dataset and fine-tunes the model. If there are no changes, the previous model is reused.
  
- **Article Generation**: Once the fine-tuning is complete (or reused), the system generates articles for each title listed in the `titles.txt` file. The article content is based on a customizable prompt provided in the project.

- **Translations**: Each article is automatically translated into multiple languages based on the configuration in the project's environment file (`.env`) or project settings.

## Translation Support

You can configure the languages to which articles will be translated by setting environment variables or adjusting the project's `.env` file.

```env
SUPPORTED_LANGUAGES=en,es,fr,de
```

This configuration will generate translations in English, Spanish, French, and German. You can add or remove languages by updating this setting.

## Project-Specific Configuration

Each project contains its own `.env` file, where you can configure settings such as the OpenAI API key, supported languages, fine-tuning settings, and more.

### Example Environment Variables (`.env`)

```env
OPENAI_API_KEY=your_openai_api_key
GPT_MODEL=gpt-3.5-turbo
SUPPORTED_LANGUAGES=en,es,fr,de
```

This `.env` file contains project-specific settings like API keys and the list of supported languages.

## Data Preparation Script (`prepare.py`)

The data preparation script (`prepare.py`) is used to process all text and Markdown files within a project's `tuning/` directory. This script reads files, cleans up HTML tags, processes Markdown hierarchies, and creates training data in JSONL format for fine-tuning. It ensures that the text is properly structured for AI fine-tuning.

### Usage

To run the data preparation script:

```bash
python3 prepare.py
```

This will process all `.txt` and `.md` files in the project's tuning directory, generating a `.jsonl` file that is ready for fine-tuning.

### Markdown Hierarchy Processing

For Markdown files, the script parses headers and treats them as context for paragraphs. For example, in a file with the following structure:

```markdown
# Header1
Paragraph 1
## Subheader1
Paragraph 2
```

The generated prompts will maintain the context of the headers and subheaders:

```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Header1: Subheader1"},
    {"role": "assistant", "content": "Header1: Subheader1: Paragraph 2"}
  ]
}
```

This hierarchical structure ensures that the AI model understands the context of the text during fine-tuning.

## Multi-Project Support

You can easily manage multiple projects within this system. Each project has its own set of configurations, tuning files, and output directories. To switch between projects, simply specify the project ID when running the script.

### Adding a New Project

1. Create a new project directory under the `projects/` folder.
2. Copy the necessary configuration files (such as `.env`, `titles.txt`, and prompts) from an existing project.
3. Modify the configuration and settings to suit the new project.
4. Run the new project using:

    ```bash
    python3 main.py <new_project_id>
    ```

## Publishing to HubSpot

The project includes a HubSpot publishing script that automatically publishes your generated blog posts to HubSpot CMS.

### Quick Start

```bash
# 1. Configure your HubSpot API token in project.env
# HUBSPOT_API_TOKEN=your-token-here

# 2. List available content groups (blogs)
./hubspot-publish.py list-groups productivity

# 3. Preview what would be published (dry run)
./publish-to-hubspot.sh --dry-run --limit 5

# 4. Publish posts
./publish-to-hubspot.sh --limit 10
```

### Features

- Automatically converts markdown to HTML
- Extracts metadata (title, category, description, keywords)
- Maps categories to HubSpot content groups
- Replaces `{url}` placeholders with your app URL
- Creates posts as DRAFTS for review
- Tracks published posts to prevent duplicates
- Selects the latest humanized English version of each post

For detailed instructions, see [HUBSPOT_PUBLISHING.md](HUBSPOT_PUBLISHING.md).

## License

PRIVATE
