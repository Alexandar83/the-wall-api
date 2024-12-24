#!/bin/bash

# Script to automatically configure the ALLOWED_HOSTS setting for a Django application running on WSL2.
# It retrieves the current WSL2 IP, ensures it is correctly added to the ALLOWED_HOSTS in the environment file,
# and cleans up any outdated WSL2 IP addresses from the list.
#
# Usage:
#   ./refresh_allowed_hosts_wsl2.sh --deployment_mode=<mode>
#   <mode>: -Required- Supported values are 'dev' or 'prod_v2'
#
# Dependencies:
#   - common_utils.sh


exit_on_failure() {
    local message=$1
    echo
    echo "Error: $message"
    echo
    exit 1
}

# Add the current WSL2 IP in the ALLOWED_HOSTS of the django app
allowed_hosts_update() {
    local deployment_mode=$1
    
    # Fetch the WSL2 IP address
    local wsl2_ip=$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1)

    # Validate the WSL2 IP
    if [[ -z "$wsl2_ip" ]]; then
        exit_on_failure "Failed to retrieve WSL2 IP address. Ensure the 'eth0' interface is active."
    fi

    # Locate the dev.env file
    local project_root
    project_root=$(resolve_project_root) || {
        if [[ "$deployment_mode" != "prod_v2" ]]; then
            echo
            echo "Error: Failed to resolve project root."
            return $?
        else
            # Fallback rule, in case the repo is not cloned
            project_root=$(dirname "$(dirname "$(dirname "$0")")")
        fi
    }
    
    get_env_file "$project_root" "$deployment_mode" || {
        echo
        return $?
    }
    
    # LINUX_ENV_FILE is exported in get_env_file
    local env_file=$LINUX_ENV_FILE

    # Read current ALLOWED_HOSTS
    local current_hosts=$(grep -E "^ALLOWED_HOSTS=" "$env_file" | cut -d'=' -f2)

    # Count occurrences of wsl2_ip in current_hosts
    local count=$(echo "$current_hosts" | grep -o "$wsl2_ip" | wc -l)

    # Check if the WSL2 IP is already in ALLOWED_HOSTS
    if [[ $count -ne 1 ]]; then
        allowed_hosts_refresh "$current_hosts" "$wsl2_ip" "$env_file" || return 1
    fi

    echo
    echo "****************************************************"
    echo "*                                                  *"
    echo "*                WSL2 setup                        *"
    echo "*                                                  *"
    echo "*   App accessible at: http://$wsl2_ip:8000   *"
    echo "*                                                  *"
    echo "*                                                  *"
    echo "****************************************************"
    echo
}

allowed_hosts_refresh() {
    
    # Detect and remove old WSL2 IPs matching the common 172.31.x.x pattern
    local current_hosts=$1
    local wsl2_ip=$2
    local env_file=$3
    local line_ending
    local updated_hosts
    
    # Detect the global line-ending style of the file
    if file "$env_file" | grep -q "CRLF"; then
        file_line_ending=$'\r\n'  # File uses CRLF
    else
        file_line_ending=$'\n'    # File uses LF
    fi

    # Strip out any trailing CR for processing the specific line
    current_hosts=$(echo "$current_hosts" | tr -d '\r')
    
    if [[ -z "$current_hosts" ]]; then
        echo
        echo "ALLOWED_HOSTS is empty. Adding $wsl2_ip as the first entry."
        updated_hosts="$wsl2_ip"
    else
        # Remove old WSL2 IPs matching the common 172.31.x.x pattern
        updated_hosts=$(echo "$current_hosts" | sed -E "s/172\.31\.[0-9]+\.[0-9]+//g")
        # Clean up any stray commas from the previous step
        updated_hosts=$(echo "$updated_hosts" | sed -E 's/,{2,}/,/g' | sed -E 's/^,|,$//g')
    fi

    # Append the new WSL2 IP to the ALLOWED_HOSTS
    if [[ -z "$updated_hosts" ]]; then
        updated_hosts="$wsl2_ip"
    else
        updated_hosts="$updated_hosts,$wsl2_ip"
    fi

    local escaped_hosts=$(printf '%s' "$updated_hosts" | sed 's/[&/\]/\\&/g')
    sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$escaped_hosts|" "$env_file"

    # Update ALLOWED_HOSTS while ensuring consistent global line-ending format
    sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$escaped_hosts|" "$env_file"

    # Fix the line ending of the updated line
    if [[ "$file_line_ending" == $'\r\n' ]]; then
        sed -i "s|ALLOWED_HOSTS=.*|&\r|" "$env_file"
    fi
}

main () {
    source "$(dirname "$0")/common_utils.sh"

    validate_deployment_mode "$DEPLOYMENT_MODE"

    allowed_hosts_update $DEPLOYMENT_MODE
}

for arg in "$@"; do
  case $arg in
    --deployment_mode=*)
      DEPLOYMENT_MODE="${arg#*=}"
      ;;
  esac
done

main