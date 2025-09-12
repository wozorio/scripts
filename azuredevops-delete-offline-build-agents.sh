#!/usr/bin/env bash

################################################################################
# Script Name    : azuredevops-delete-offline-build-agents.sh
# Description    : Used to batch delete offline build agents from a specified agent pool
# Args           : PERSONAL_ACCESS_TOKEN ORGANIZATION_NAME AGENT_POOL_NAME [API_VERSION]
# Author         : Wellington Ozorio <wozorio@duck.com>
################################################################################

set -o errexit
set -o pipefail
set -o nounset

log() {
    local MESSAGE="${1}"
    echo "${MESSAGE}" 1>&2
}

usage() {
    log "Usage: ${0} PERSONAL_ACCESS_TOKEN ORGANIZATION_NAME AGENT_POOL_NAME [API_VERSION]"
    exit 1
}

check_azure_devops_access() {
    local RESPONSE
    RESPONSE=$(curl --silent --header "${HEADER}" "${AGENT_POOLS_URI}" -o /dev/null --write-out "%{http_code}")

    if [[ ${RESPONSE} -lt 200 || ${RESPONSE} -gt 299 ]]; then
        log "ERROR: Failed accessing Azure DevOps API with HTTP code ${RESPONSE}"
        exit 1
    fi
}

get_agent_pool_id() {
    local AGENT_POOL
    AGENT_POOL=$(
        curl \
            --silent \
            --header "${HEADER}" "${AGENT_POOLS_URI}" |
            jq --arg AGENT_POOL_NAME "$AGENT_POOL_NAME" '.value[] | select(.name == $AGENT_POOL_NAME)'
    )

    if [[ -z "$AGENT_POOL" ]]; then
        log "ERROR: ${AGENT_POOL_NAME} agent pool not found in ${ORGANIZATION_NAME} organization"
        exit 1
    fi

    local AGENT_POOL_ID
    AGENT_POOL_ID=$(jq --raw-output '.id' <<<"${AGENT_POOL}")

    echo "${AGENT_POOL_ID}"
}

get_offline_agents() {
    local AGENT_POOL_ID="${1}"

    local AGENTS_URI="https://dev.azure.com/${ORGANIZATION_NAME}/_apis/distributedtask/pools/${AGENT_POOL_ID}/agents?api-version=${API_VERSION}"

    local OFFLINE_AGENTS
    OFFLINE_AGENTS=$(curl --silent --header "${HEADER}" "${AGENTS_URI}" | jq '.value[] | select(.status == "offline")')

    if [[ -z "${OFFLINE_AGENTS}" ]]; then
        log "INFO: No offline agents found in ${AGENT_POOL_NAME} agent pool"
        exit 0
    fi

    echo "${OFFLINE_AGENTS}"
}

delete_offline_agent() {
    local AGENT="${1}"
    local AGENT_POOL_ID="${2}"

    log "WARN: Deleting offline agent ID ${AGENT} from ${AGENT_POOL_NAME} agent pool in ${ORGANIZATION_NAME} organization"
    curl \
        --request DELETE \
        --url "https://dev.azure.com/${ORGANIZATION_NAME}/_apis/distributedtask/pools/${AGENT_POOL_ID}/agents/${AGENT}?api-version=${API_VERSION}" \
        --header "${HEADER}" \
        --silent \
        --fail >/dev/null || {
        log "ERROR: Failed deleting offline agent ID ${AGENT} from ${AGENT_POOL_NAME} agent pool in ${ORGANIZATION_NAME} organization"
        exit 1
    }
}

main() {
    if [[ "${#}" -ne 3 && "${#}" -ne 4 ]]; then
        usage
    fi

    PERSONAL_ACCESS_TOKEN="${1}"
    ORGANIZATION_NAME="${2}"
    AGENT_POOL_NAME="${3}"
    API_VERSION="${4:-"7.2-preview.1"}"

    AGENT_POOLS_URI="https://dev.azure.com/${ORGANIZATION_NAME}/_apis/distributedtask/pools?api-version=${API_VERSION}"
    BASE64_PAT=$(printf "%s" ":${PERSONAL_ACCESS_TOKEN}" | base64 -w 0)
    HEADER="Authorization: Basic ${BASE64_PAT}"

    check_azure_devops_access

    local AGENT_POOL_ID
    AGENT_POOL_ID=$(get_agent_pool_id)

    local OFFLINE_AGENTS
    OFFLINE_AGENTS=$(get_offline_agents "${AGENT_POOL_ID}")

    jq --raw-output '.id' <<<"${OFFLINE_AGENTS}" | while IFS= read -r AGENT; do
        delete_offline_agent "${AGENT}" "${AGENT_POOL_ID}"
    done
}

main "${@}"
