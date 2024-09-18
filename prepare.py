import os
import json
import re
from pathlib import Path

import spacy
import mistune  # For Markdown parsing
from bs4 import BeautifulSoup  # For cleaning up HTML tags
from dotenv import load_dotenv

load_dotenv()

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Paths for tuning folder
project_id = os.getenv("PROJECT_ID")
project = f'./projects/{project_id}'
TUNING_DIR = f"{project}/tuning"

# Initialize Markdown parser
markdown = mistune.create_markdown()


# Function to clean up HTML tags and convert Markdown elements to plain text
def clean_html(text):
    soup = BeautifulSoup(text, "html.parser")

    # For <ul> or <ol>, format lists properly
    for ul in soup.find_all(["ul", "ol"]):
        items = ul.find_all("li")
        formatted_list = "\n".join(f"- {item.get_text(strip=True)}" for item in items)
        ul.replace_with(formatted_list)

    # For <p> or <h1>, <h2>, etc., treat them as new paragraphs
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.insert_before("\n")  # Insert new line before paragraphs/headers
        tag.unwrap()  # Remove tag but keep content

    # For <br>, replace with newlines
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # Get cleaned text
    cleaned_text = soup.get_text(separator=" ").strip()

    # Add a space after colons if not followed by a space (e.g., "Task Duration:The time" -> "Task Duration: The time")
    cleaned_text = re.sub(r"(:)(\S)", r"\1 \2", cleaned_text)

    return cleaned_text


# Function to process Markdown files with hierarchical structure for headers
def process_markdown_file(file_path, jsonl_file):
    # Read the file content
    with open(file_path, 'r') as f:
        content = f.read()

    # Parse the markdown content into HTML
    parsed_content = markdown(content)

    # Clean the parsed markdown/HTML into plain text
    cleaned_content = clean_html(parsed_content)

    lines = cleaned_content.splitlines()  # Split into lines

    # Initialize to store headers hierarchy
    headers_stack = []

    for line in lines:
        line = line.strip()

        # Detect headers based on their markdown level (h1 to h6)
        header_match = re.match(r"^(#+)\s*(.*)", line)
        if header_match:
            level = len(header_match.group(1))
            header_text = header_match.group(2)

            # Update headers stack based on the level of the header
            headers_stack = headers_stack[:level - 1] + [header_text]  # Maintain only the headers up to the current level

        # If it's a paragraph, create the prompt structure based on the current headers stack or the paragraph itself
        elif is_paragraph(line):
            if headers_stack:
                user_message = ": ".join(headers_stack)
                assistant_message = f"{user_message}: {line}"
            else:
                # If there are no headers, use the paragraph as the prompt
                user_message = line
                assistant_message = line

            # Generate JSONL data
            json_data = {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_message}
                ]
            }
            jsonl_file.write(json.dumps(json_data) + "\n")


# Function to process a single file (supports both .txt and .md) and save as JSONL
def process_text_file(file_path):
    jsonl_file_path = Path(file_path).with_suffix('.jsonl')
    with open(jsonl_file_path, 'w') as jsonl_file:
        # Detect whether it's a Markdown file by extension
        if file_path.endswith(".md"):
            process_markdown_file(file_path, jsonl_file)
        else:
            # Standard text processing for .txt files
            with open(file_path, 'r') as f:
                content = f.read()

            # Clean the content and split into lines
            cleaned_content = clean_html(content)
            lines = cleaned_content.splitlines()

            current_list = []
            for line in lines:
                prompt = line.strip()
                # Skip short or non-valuable text
                if is_non_valuable_text(prompt):
                    continue

                # Detect if the line is a list item
                if is_list_item(prompt):
                    current_list.append(prompt)
                else:
                    # If it's a paragraph, process it
                    if current_list:
                        # Write the entire list as one JSONL entry
                        process_list_as_prompt(current_list, jsonl_file)
                        current_list = []

                    if is_paragraph(prompt):
                        json_data = {
                            "messages": [
                                {"role": "system", "content": "You are a helpful assistant."},
                                {"role": "user", "content": prompt},
                                {"role": "assistant", "content": prompt}  # Customize if needed
                            ]
                        }
                        jsonl_file.write(json.dumps(json_data) + "\n")

            # Process any remaining list items
            if current_list:
                process_list_as_prompt(current_list, jsonl_file)


# Function to filter non-valuable text
def is_non_valuable_text(text):
    """
    Identify whether the text is too short or non-valuable for tuning.
    """
    # Skip lines with very short length or less than 2 words
    doc = nlp(text)
    if len(text) < 10 or len(doc) < 2:
        return True
    return False


# Function to detect list items (e.g., bullet points or numbered lists)
def is_list_item(text):
    """
    Detect whether the line is a part of a list (e.g., starts with bullet points or numbers).
    """
    return text.startswith("-") or text.startswith("*") or text[0].isdigit()


# Function to detect if a text block is a paragraph
def is_paragraph(text):
    """
    Use spaCy to determine whether the text is a coherent paragraph (more than a few sentences).
    """
    doc = nlp(text)
    sentences = list(doc.sents)  # Convert the generator to a list
    return len(sentences) > 1  # If more than one sentence, treat it as a paragraph


# Function to process a list as a prompt in the tuning file
def process_list_as_prompt(list_items, jsonl_file):
    """
    Process a detected list and write it as a JSONL entry with context.
    """
    full_list = "\n".join(list_items)
    json_data = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": full_list},
            {"role": "assistant", "content": full_list}  # Customize if needed
        ]
    }
    jsonl_file.write(json.dumps(json_data) + "\n")


# Function to process all text and markdown files in the tuning directory
def process_all_text_files():
    for file_name in os.listdir(TUNING_DIR):
        if file_name.endswith(".txt") or file_name.endswith(".md"):
            file_path = os.path.join(TUNING_DIR, file_name)
            print(f"Processing {file_name}...")
            process_text_file(file_path)
            print(f"Finished processing {file_name}")


if __name__ == "__main__":
    process_all_text_files()
