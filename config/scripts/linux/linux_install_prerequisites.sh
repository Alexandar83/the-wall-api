#!/bin/bash

# Script to install and configure system prerequisites for a Django project on Linux.
# It ensures necessary packages, tools, and configurations are set up, including PostgreSQL libraries,
# Python build tools, and Poetry for dependency management.
#
# Stages:
# 1. Update package lists.
# 2. Install system dependencies (build-essential, libpq-dev, python3-dev).
# 3. Install Poetry for Python dependency management.
# 4. Add Poetry to PATH.
# 5. Optionally create an application group for shared resource access based on deployment mode.
#
# Usage:
#   ./linux_install_prerequisites.sh --deployment_mode=<mode>
#   <mode>: -Optional- specific behavior only for value 'demo', otherwise ignored
#
# Dependencies:
#   - common_utils.sh


# Constants
PREREQUISITES_FAIL_MESSAGE="Error: System prerequisites script NOT COMPLETED!"
SUCCESS_MESSAGE="Info: System prerequisites installation COMPLETED successfully!"
POETRY_INSTALL_COMMAND="curl -sSL https://install.python-poetry.org | python3 -"

# Utility function for error message output and exit
exit_on_failure() {
    local message=$1
    [[ -n "$message" ]] && echo "Error: $message"
    echo "$PREREQUISITES_FAIL_MESSAGE"
    echo
    exit 1
}

update_package_lists() {
    echo
    echo "=== STAGE 1 ==="
    echo "Updating package lists..."
    echo
    sudo apt update || exit_on_failure "Failed to update package lists."
    echo "Package lists updated successfully."
}

# Install Tools and libraries for PostgreSQL development:
# build-essential   Compilers for building dependencies.
# libpq-dev         PostgreSQL client libraries and headers.
# python3-dev       Python headers for building C extensions.
install_system_dependencies() {
    echo
    echo "=== STAGE 2 ==="
    echo "Installing system dependencies for PostgreSQL and Python builds..."
    echo
    sudo apt install -y build-essential libpq-dev python3-dev || exit_on_failure "Failed to install system dependencies."
    echo "System dependencies installed successfully."
}

install_poetry() {
    echo
    echo "=== STAGE 3 ==="
    echo "Installing Poetry..."
    echo
    eval $POETRY_INSTALL_COMMAND || exit_on_failure "Failed to install Poetry."
    echo "Poetry installed successfully."
}

manage_add_poetry_to_path() {
    local utils_path="$(dirname "$0")/common_utils.sh"
    source "$utils_path" || exit_on_failure "Failed to source $utils_path."
    add_poetry_to_path || exit_on_failure "Failed to add Poetry to PATH."
}

# App group creation to provide shared access to the mounted (in the docker compose) logs directory
manage_create_app_group() {
    echo
    echo "=== STAGE 4 ==="
    echo "Creating app group..."
    echo

    local deployment_mode=$1
    # create_app_group has a default behavior in case of deployment_mode not set

    source "$(dirname "$0")/common_utils.sh" || exit_on_failure "Failed to source common_utils.sh."
    create_app_group "$deployment_mode"
    local return_code=$?
    # create_app_group may return 2 in some cases
    if [[ $return_code -eq 1 ]]; then
        exit_on_failure "Failed to create app group."
    # Avoid message duplication
    elif [[ $return_code -eq 11 ]]; then
        exit_on_failure
    fi
}

# Main script execution
main() {
    echo
    echo "Info: Starting system prerequisites installation for Linux..."
    echo

    update_package_lists

    install_system_dependencies

    install_poetry

    manage_add_poetry_to_path

    manage_create_app_group "$DEPLOYMENT_MODE"

    echo "$SUCCESS_MESSAGE"
    echo
    echo "Next steps:"
    echo "1. If Poetry is freshly installed, run 'source ~/.bashrc' or restart your shell."
    echo "2. Run 'poetry install' to install Python dependencies."
    echo "3. Run 'source config/scripts/common/poetry_shell.sh' to start a virtual environment."
    if [[ "$DEPLOYMENT_MODE" != "demo" ]]; then
        echo "4. Run script 'config/scripts/docker/docker-compose-dev+migrations.sh' to start the app in PROJECT_MODE='dev'."
    fi
    echo
}

for arg in "$@"; do
  case $arg in
    --deployment_mode=*)
      DEPLOYMENT_MODE="${arg#*=}"
      ;;
  esac
done

main