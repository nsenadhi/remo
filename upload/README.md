# REMONI Project Setup

This guide will help you set up and run the REMONI project on your local machine.

## Prerequisites

Ensure you have the following installed on your system:
- Python 3
- `pip` (Python package installer)

## Setup Instructions

1. **Update your package list:**

    ```sh
    sudo apt-get update
    ```

2. **Install the Python virtual environment package:**

    ```sh
    sudo apt-get install python3-venv
    ```

3. **Navigate to the `remoni` project directory:**

    ```sh
    cd simple_remoni
    ```

4. **Create a virtual environment:**

    ```sh
    python3 -m venv venv
    ```

5. **Activate the virtual environment:**

    ```sh
    source venv/bin/activate
    ```

6. **Install the required Python packages:**

    ```sh
    pip install -r requirements.txt
    ```

7. **Start the application using Gunicorn:**

    ```sh
    gunicorn -k eventlet -w 1 -b 0.0.0.0:8080 app:app --timeout 120
    ```

## Notes

- Ensure that the `requirements.txt` file is present in the `remoni` directory. This file should contain all the necessary Python packages required for the project.
- The application will be accessible at `http://0.0.0.0:8080` after starting Gunicorn.
