#!/bin/bash

# Shared utility functions for Linux scripts, including:
# - Resolving project root, managing environment files, and setting directory permissions.
# To use: source this file in your scripts.

print_result() {   
    local message=$1
    echo
    echo "$message"
}

# Linux: Add Poetry to PATH to enable the 'poetry' command
add_poetry_to_path() {
    local shell_config
    local poetry_bin_dir="$HOME/.local/bin"

    # Check if the Poetry bin directory is already in PATH
    if [[ ":$PATH:" != *":$poetry_bin_dir:"* ]]; then
        echo "Adding Poetry to PATH..."

        # Detect the active shell's configuration file
        if [[ -n "$ZSH_VERSION" ]]; then
            shell_config="$HOME/.zshrc"
        elif [[ -n "$BASH_VERSION" ]]; then
            shell_config="$HOME/.bashrc"
        else
            shell_config="$HOME/.profile"  # Fallback
        fi

        # Add Poetry's bin directory to PATH
        echo "export PATH=\"$poetry_bin_dir:\$PATH\"" >> "$shell_config"

        echo "Poetry's bin directory '$poetry_bin_dir' added to PATH."
        echo
        echo ">>>>>> PLEASE RESTART YOUR SHELL or run 'source $shell_config'. <<<<<<"
    else
        echo "Poetry's bin directory is already in PATH."
    fi
}

# == App group creation ==

# Linux (DEV): Create a new group to provide shared access to the mounted 
# logs directory for both the non-root app user of the celery services' containers
# and the root user
create_app_group() {
    local deployment_mode=$1
    if [[ "$deployment_mode" == "demo" ]]; then
        print_result "Info: --deployment_mode is set to 'demo', skipping app group creation."
        return 2
    fi

    # Validate environment and load configurations
    local project_root
    project_root=$(resolve_project_root) || return $?

    validate_and_load_env "$project_root" || return $?

    validate_env_vars "APP_GROUP_NAME" "APP_GROUP_ID" || return $?

    local group_name="$APP_GROUP_NAME"
    local group_id="$APP_GROUP_ID"

    validate_group_name "$group_name" || return $?
    validate_group_id "$group_id" || return $?
    check_group_existence "$group_name" "$group_id" || return $?

    create_group "$group_name" "$group_id" || return $?
    add_root_to_group "$group_name" || return $?

    echo "Info: App group '$group_name' created with ID '$group_id'."
    echo "Info: Root user added to group '$group_name'."
    echo
}

validate_group_name() {
    local group_name=$1
    if [[ ! "$group_name" =~ ^[a-zA-Z0-9._-]+$ ]]; then
        print_result "Error: Invalid APP_GROUP_NAME '$group_name'. Only letters, numbers, dots, underscores, and hyphens are allowed."
        return 1
    fi
}

validate_group_id() {
    local group_id=$1
    if ! [[ "$group_id" =~ ^[0-9]+$ ]]; then
        print_result "Error: Invalid APP_GROUP_ID '$group_id'. Must be a numeric value."
        return 1
    fi
}

check_group_existence() {
    local group_name=$1
    local group_id=$2
    if getent group | grep -qE "^${group_name}:.*:${group_id}:"; then
        print_result "Info: The group with ID '$group_id' and name '$group_name' is already configured."
        return 2
    fi
    if getent group "$group_id" >/dev/null 2>&1; then
        print_result "Error: Group ID '$group_id' already exists."
        return 1
    fi
    if getent group "$group_name" >/dev/null 2>&1; then
        print_result "Error: Group name '$group_name' already exists."
        return 1
    fi
}

create_group() {
    local group_name=$1
    local group_id=$2
    sudo groupadd --gid "$group_id" "$group_name" || {
        print_result "Error: Failed to create group '$group_name'."
        return 11
    }
}

add_root_to_group() {
    local group_name=$1
    sudo usermod -aG "$group_name" root || {
        sudo groupdel "$group_name"
        print_result "Error: Failed to add root user to group '$group_name' - group was removed."
        return 1
    }
}

# == App group creation end ==

# Navigate to the root of the project using the
# poetry.lock or requirements.txt file
resolve_project_root() {
    local script_dir="$(cd "$(dirname "$0")" && pwd)"
    local project_root="$script_dir"

    while [ "$project_root" != "/" ]; do
        if [[ -f "$project_root/poetry.lock" ]] || [[ -f "$project_root/requirements.txt" ]]; then
            echo "$project_root"
            return 0
        fi
        project_root="$(dirname "$project_root")"
    done

    # Fallback logic if no match is found
    >&2 echo "Error: Failed to resolve project root."
    return 1
}


# Locate the env. file and source the env. vars in it
validate_and_load_env() {
    local project_root=$1
    
    # deployment_mode is not needed here
    get_env_file "$project_root" || return $?
      
    source "$LINUX_ENV_FILE"
}

get_env_file() {
    local project_root=$1
    local deployment_mode=$2
    local env_file_name
    local env_file

    # always use the_wall_api_dev.env for linux_install_prerequisites.sh
    if [[ -z "$deployment_mode" ]] || [[ "$deployment_mode" == "dev" ]]; then
        env_file_name="the_wall_api_dev.env"
    elif [[ "$deployment_mode" == "demo" ]]; then
        env_file_name="the_wall_api_dev.env.example"
    elif [[ "$deployment_mode" == "prod_v2" ]]; then
        env_file_name="the_wall_api_prod.env"
    else
        print_result "Error: Invalid --deployment_mode '$deployment_mode'."
        echo "Supported values: demo, dev, prod_v2"
        return 1
    fi
    
    env_file=$(find "$project_root" -type f -name "$env_file_name" 2>/dev/null | head -n 1)
    
    if [[ -z "$env_file" ]]; then
        print_result "Error: Environment file '$env_file_name' not found in project!"
        return 1
    fi

    export LINUX_ENV_FILE="$env_file"

    return 0
}

# Verify that the required environment variables are set
validate_env_vars() {
    local error_message="is not set in environment file '$LINUX_ENV_FILE'"

    for env_var in "$@"; do
        if [[ -z "${!env_var}" ]]; then
            print_result "Error: Environment variable '$env_var' $error_message"
            echo "Info:  Required env. vars. for the process to continue: "$@"."
            return 1
        fi
    done
}
