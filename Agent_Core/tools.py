from langchain_core.tools import tool
import subprocess
import logging
from datetime import datetime
from functools import wraps

# Simple logging setup
logger = logging.getLogger("tools")
logger.setLevel(logging.DEBUG)

# Console handler
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def log_tool_call(func):
    """Decorator to log tool calls and results."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        logger.info(f"[CALL] {tool_name} - args: {args}, kwargs: {kwargs}")
        try:
            result = func(*args, **kwargs)
            # Truncate long results for logging
            result_str = str(result)
            if len(result_str) > 200:
                result_str = result_str[:200] + "... [truncated]"
            logger.info(f"[RESULT] {tool_name} -> {result_str}")
            return result
        except Exception as e:
            logger.error(f"[ERROR] {tool_name} - {e}")
            raise
    return wrapper


@tool
@log_tool_call
def run_shell_code(command: str) -> dict:
    """Run Command in terminal and get output."""
    print("use the following command: " + command)
    try:
        a = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        return {"stdout": a.stdout, "stderr": a.stderr}
    except Exception as e:
        return str(e)


@tool
@log_tool_call
def run_python(code: str) -> str:
    """Run a small Python program and return its output."""

    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return result.stdout

        return f"Error:\n{result.stderr}"

    except subprocess.TimeoutExpired:
        return "Error: execution timed out."


@tool
@log_tool_call
def read_file(
    file_path: str,
    start_line: int | None = None,
    end_line: int | None = None
) -> str:
    """
    Read a text file.

    If no line numbers are provided, return the entire file.
    If start_line is provided, read from start_line to the end.
    If both start_line and end_line are provided, read only that range.
    """

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        start = 0 if start_line is None else start_line - 1
        end = len(lines) if end_line is None else end_line

        if start < 0 or start >= len(lines):
            return "Error: start_line is out of range."

        if end <= start or end > len(lines):
            return "Error: end_line is out of range."

        selected_lines = lines[start:end]

        return "".join(selected_lines)

    except FileNotFoundError:
        return f"Error: file not found: {file_path}"

    except Exception as e:
        return f"Error: {e}"


@tool
@log_tool_call
def write_file(
    file_path: str,
    content: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """
    Write content to a text file.

    No line numbers:
        Replace the entire file.

    Only start_line:
        Replace from start_line to the end.

    start_line + end_line:
        Replace only that line range.
    """

    try:
        if start_line is None:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Successfully wrote the entire file: {file_path}"

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        start = start_line - 1

        if start < 0 or start >= len(lines):
            return "Error: start_line is out of range."

        if end_line is None:
            end = len(lines)

        else:
            end = end_line

            if end <= start or end > len(lines):
                return "Error: end_line is out of range."

        # Convert content to lines
        new_content = content
        if not new_content.endswith("\n"):
            new_content += "\n"

        new_lines = new_content.splitlines(keepends=True)

        lines[start:end] = new_lines

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return (
            f"Successfully updated {file_path} "
            f"(lines {start_line}-{end_line or 'end'})"
        )

    except FileNotFoundError:
        return f"Error: file not found: {file_path}"

    except Exception as e:
        return f"Error: {e}"


@tool
@log_tool_call
def run_terminal(command: str) -> str:
    """
    Run a terminal command and return its output.
    """

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout

        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"

        output += f"\nExit code: {result.returncode}"

        return output

    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30 seconds."

    except Exception as e:
        return f"Error: {e}"