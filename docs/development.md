# Development Guide

This guide provides instructions for setting up a development environment, running tests, and contributing to the Akita Meshtastic-Meshcore Bridge (AMMB) project.

## Setting Up Development Environment

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/akita-meshtastic-meshcore-bridge.git](https://github.com/YOUR_USERNAME/akita-meshtastic-meshcore-bridge.git)
    cd akita-meshtastic-meshcore-bridge
    ```

2.  **Create and activate a Python virtual environment:**
    ```bash
    python -m venv venv
    # On Windows: .\venv\Scripts\activate
    # On Linux/macOS: source venv/bin/activate
    ```
    Using a virtual environment isolates project dependencies.

3.  **Install runtime and development dependencies:**
    ```bash
    pip install -r requirements-dev.txt
    ```
    This installs `meshtastic`, `pyserial`, `pypubsub`, `pytest`, `pytest-cov`, `flake8`, and `mypy`.

## Running Tests

The project uses `pytest` for automated testing.

1.  **Ensure your virtual environment is active.**
2.  **Navigate to the project root directory.**
3.  **Run pytest:**
    ```bash
    pytest
    ```
    This will discover and run all tests located in the `tests/` directory.

4.  **Run tests with coverage report:**
    ```bash
    pytest --cov=ammb --cov-report term-missing
    ```
    This runs the tests and generates a report showing which lines of the source code in the `ammb/` directory were executed by the tests.

## Code Style and Linting

We use `flake8` for checking code style against PEP 8 guidelines and common errors.

1.  **Ensure your virtual environment is active.**
2.  **Navigate to the project root directory.**
3.  **Run flake8:**
    ```bash
    flake8 ammb/ tests/ run_bridge.py
    ```
    This will report any style violations or potential errors. Aim for zero reported issues.

## Static Type Checking

We use `mypy` for static type checking to catch potential type-related errors before runtime.

1.  **Ensure your virtual environment is active.**
2.  **Navigate to the project root directory.**
3.  **Run mypy:**
    ```bash
    mypy ammb/ run_bridge.py
    ```
    This will analyze the type hints in the code and report any inconsistencies or errors. Aim for zero reported issues.

## Contribution Guidelines

We welcome contributions! Please follow these steps:

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally: `git clone https://github.com/YOUR_FORK_USERNAME/akita-meshtastic-meshcore-bridge.git`
3.  **Create a new branch** for your feature or bug fix: `git checkout -b feature/your-feature-name` or `git checkout -b fix/issue-description`.
4.  **Set up your development environment** as described above.
5.  **Make your changes.** Ensure you:
    * Follow the existing code style.
    * Add tests for new features or bug fixes.
    * Update documentation (`README.md`, `docs/*.md`) if necessary.
    * Ensure all tests pass (`pytest`).
    * Ensure linters pass (`flake8 ammb/ tests/ run_bridge.py`).
    * Ensure type checks pass (`mypy ammb/ run_bridge.py`).
6.  **Commit your changes** with clear and descriptive commit messages.
7.  **Push your branch** to your fork: `git push origin feature/your-feature-name`.
8.  **Open a Pull Request (PR)** from your fork's branch to the `main` branch of the original repository.
9.  **Clearly describe** the changes made in the PR description and link to any relevant issues.
10. **Respond to feedback** or requested changes during the code review process.

## Adding New Meshcore Protocols

To support a different serial protocol for Meshcore:

1.  Create a new class in `ammb/protocol.py` that inherits from `MeshcoreProtocolHandler`.
2.  Implement the `encode(self, data: dict) -> bytes | None` method to convert the bridge's standard message dictionary into bytes according to your protocol.
3.  Implement the `decode(self, line: bytes) -> dict | None` method to parse incoming bytes (likely read line-by-line or based on delimiters/length depending on the protocol) into a dictionary that includes at least `destination_meshtastic_id` and `payload` keys for successful forwarding to Meshtastic.
4.  Update the `get_protocol_handler` factory function in `ammb/protocol.py` to recognize a new protocol name (e.g., `your_protocol_name`) and return an instance of your new class.
5.  Add the new protocol name as an option for the `MESHCORE_PROTOCOL` setting in `docs/configuration.md` and `examples/config.ini.example`.
6.  Add tests for your new protocol handler in `tests/test_protocol.py`.
