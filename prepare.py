import json
import os
import re
from pathlib import Path

import markdown_it
import mistune  # For Markdown parsing
import spacy
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Paths for tuning folder
project_id = os.getenv("PROJECT_ID")
project = f'./projects/{project_id}'
TUNING_DIR = f"{project}/tuning"

# Initialize Markdown parsers
markdown = mistune.create_markdown()
md = markdown_it.MarkdownIt()


# Function to clean up HTML tags and convert Markdown elements to plain text
def clean_html(text):
    soup = BeautifulSoup(text, "html.parser")

    # Format lists properly for <ul> or <ol>
    for ul in soup.find_all(["ul", "ol"]):
        items = ul.find_all("li")
        formatted_list = "\n".join(f"- {item.get_text(strip=True)}" for item in items)
        ul.replace_with(formatted_list)

    # Treat <p> or <h1>, <h2>, etc. as new paragraphs
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.insert_before("\n")  # Insert new line before paragraphs/headers
        tag.unwrap()  # Remove tag but keep content

    # Replace <br> with newlines
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # Get cleaned text
    cleaned_text = soup.get_text(separator=" ").strip()

    # Add space after colons if missing
    cleaned_text = re.sub(r"(:)(\S)", r"\1 \2", cleaned_text)

    # Clean up multiple consecutive spaces or tabs
    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    return cleaned_text


# Function to split text into smaller chunks, ensuring 3-4 sentences max per chunk
def split_into_paragraphs(text):
    sentences = list(nlp(text).sents)
    paragraphs = []
    current_paragraph = []

    for sentence in sentences:
        current_paragraph.append(sentence.text)
        # Split into chunks of 3-4 sentences
        if len(current_paragraph) >= 3:
            paragraphs.append(" ".join(current_paragraph))
            current_paragraph = []

    # Add any remaining sentences
    if current_paragraph:
        paragraphs.append(" ".join(current_paragraph))

    return paragraphs


# Function to detect if a text block is a paragraph
def is_paragraph(text):
    doc = nlp(text)
    sentences = list(doc.sents)
    return len(sentences) > 1  # Treat it as a paragraph if there is more than one sentence


# Function to detect whether a token is a header
def is_header(token):
    return token.type == 'heading_open'


# Function to extract the header level
def get_header_level(token):
    if token.tag.startswith('h'):
        return int(token.tag[1])
    return None


# Function to join consecutive headers if they are at the same level and there is no content between them
def join_consecutive_headers(headers):
    result = []
    prev_header = None

    for header in headers:
        if prev_header and header['level'] == prev_header['level'] and not prev_header.get('has_content', False):
            # Combine headers with '. ' if no content between them
            prev_header['header'] += '. ' + header['header']
        else:
            if prev_header:
                result.append(prev_header)
            prev_header = header

    if prev_header:
        result.append(prev_header)

    return result


# Function to build tree structure from markdown content
def build_tree_from_markdown(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Parse the markdown content into tokens
    tokens = md.parse(content)
    tree = []
    stack = []
    headers_at_same_level = []

    for token in tokens:
        if is_header(token):
            level = get_header_level(token)
            header_text = tokens[tokens.index(token) + 1].content  # Get the header text

            # Keep track of headers at the same level
            headers_at_same_level.append({"header": header_text, "children": [], "level": level, "has_content": False})

            # If new header level is lower or equal, pop the stack to find the right parent
            while stack and stack[-1]['level'] >= level:
                tree.append(stack.pop())

        elif token.type == 'paragraph_open':
            paragraph_text = tokens[tokens.index(token) + 1].content  # Get paragraph text
            paragraph_chunks = split_into_paragraphs(paragraph_text)  # Split paragraph into chunks

            # Attach paragraphs to the current header and mark that it has content
            if stack:
                for chunk in paragraph_chunks:
                    stack[-1]["children"].append({"paragraph": chunk})
                    stack[-1]["has_content"] = True

        # Process headers only after we are done processing possible content in between
        headers_at_same_level = join_consecutive_headers(headers_at_same_level)
        for header in headers_at_same_level:
            if stack:
                stack[-1]["children"].append(header)
            stack.append(header)
        headers_at_same_level = []

    # Append any remaining items in the stack to the tree
    while stack:
        tree.append(stack.pop())

    return tree


# Function to write the tree structure to JSONL
def write_tree_to_jsonl(node, jsonl_file, headers_hierarchy=None):
    if headers_hierarchy is None:
        headers_hierarchy = []

    if "header" in node:
        headers_hierarchy.append(node["header"])

    if "paragraph" in node:
        # Build the user message based on the headers hierarchy
        user_message = ": ".join(headers_hierarchy)
        json_data = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": node["paragraph"]}
            ]
        }
        jsonl_file.write(json.dumps(json_data) + "\n")

    # Traverse through the children recursively
    for child in node.get("children", []):
        write_tree_to_jsonl(child, jsonl_file, headers_hierarchy[:])  # Pass a copy of the hierarchy to avoid mutation


# Function to process Markdown files with tree structure and save to JSONL
def process_markdown_file(file_path, jsonl_file):
    tree = build_tree_from_markdown(file_path)

    # Write the tree to JSONL
    for node in tree:
        write_tree_to_jsonl(node, jsonl_file)


# Function to process all text and markdown files in the tuning directory
def process_all_text_files():
    for file_name in os.listdir(TUNING_DIR):
        if file_name.endswith(".txt") or file_name.endswith(".md"):
            file_path = os.path.join(TUNING_DIR, file_name)
            print(f"Processing {file_name}...")
            jsonl_file_path = Path(file_path).with_suffix('.jsonl')
            with open(jsonl_file_path, 'w') as jsonl_file:
                process_markdown_file(file_path, jsonl_file)
            print(f"Finished processing {file_name}")


if __name__ == "__main__":
    process_all_text_files()
