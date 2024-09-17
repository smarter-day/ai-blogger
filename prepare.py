import os
import json

# Paths for tuning folder
TUNING_DIR = "./tuning"


# Function to format the text lines into the desired JSON structure
def format_lines_to_json(lines):
    messages = [{"role": "system", "content": line.strip()} for line in lines if line.strip()]
    return {"messages": messages}


# Function to process a single text file and save as JSON
def process_text_file(file_path):
    json_data_list = []

    # Read the file line by line
    with open(file_path, 'r') as f:
        lines = f.readlines()

        # Split lines into bundles of 10
        for i in range(0, len(lines), 10):
            bundle = lines[i:i + 10]
            json_data = format_lines_to_json(bundle)
            json_data_list.append(json_data)

    # Create a corresponding JSON file
    json_file_path = file_path.replace(".txt", ".json")
    with open(json_file_path, 'w') as json_file:
        json.dump(json_data_list, json_file, indent=4)


# Function to process all .txt files in the tuning directory
def process_all_text_files():
    for file_name in os.listdir(TUNING_DIR):
        if file_name.endswith(".txt"):
            file_path = os.path.join(TUNING_DIR, file_name)
            print(f"Processing {file_name}...")
            process_text_file(file_path)
            print(f"Finished processing {file_name}")


if __name__ == "__main__":
    process_all_text_files()
