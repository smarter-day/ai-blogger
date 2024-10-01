import typer

prompt_file = "./projects/productivity/prompts/article_prompt.md"

with open(prompt_file, "r") as file:
    prompt = file.read()


def main(article_title: str = "", target_language: str = "English"):
    print(prompt.format(
        article_title=article_title,
        target_language=target_language,
    ))


if __name__ == "__main__":
    typer.run(main)
