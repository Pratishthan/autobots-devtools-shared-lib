import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file."""
    try:
        with open(file_path) as f:
            content = f.read()
        return content
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return f"Error reading file: {e}"


@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file."""
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        logger.error(f"Error writing to file {file_path}: {e}")
        return f"Error writing to file: {e}"


@tool
def list_files(directory_path: str) -> str:
    """List all files in a directory."""
    import os

    try:
        files = os.listdir(directory_path)
        return "\n".join(files)
    except Exception as e:
        logger.error(f"Error listing files in {directory_path}: {e}")
        return f"Error listing files: {e}"


def load_prompt(prompt_name: str) -> str:
    """Read the prompt from the prompt.txt file."""
    try:
        with open(f"prompts/{prompt_name}.md") as f:
            content = f.read()
        return content
    except Exception as e:
        logger.error(f"Error reading prompt.txt: {e}")
        return f"Error reading prompt.txt: {e}"
