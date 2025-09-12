#!/usr/bin/env bash

################################################################################
# Script Name    : azuredevops-delete-queued-builds.sh
# Description    : Used to batch delete queued builds ("pipeline runs")
# Args           : PERSONAL_ACCESS_TOKEN ORGANIZATION_NAME PROJECT_NAME [API_VERSION]
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
    log "Usage: ${0} PERSONAL_ACCESS_TOKEN ORGANIZATION_NAME PROJECT_NAME [API_VERSION]"
    exit 1
}

check_azure_devops_access() {
    local RESPONSE
    RESPONSE=$(curl --silent --header "${HEADER}" "${NOT_STARTED_BUILDS_URI}" -o /dev/null --write-out "%{http_code}")

    if [[ ${RESPONSE} -lt 200 || ${RESPONSE} -gt 299 ]]; then
        log "ERROR: Failed accessing Azure DevOps API with HTTP code ${RESPONSE}"
        exit 1
    fi
}

get_queued_builds() {
    local QUEUED_BUILDS
    QUEUED_BUILDS=$(curl --silent --header "${HEADER}" "${NOT_STARTED_BUILDS_URI}" | jq '.value[].id')

    if [[ -z "${QUEUED_BUILDS}" ]]; then
        log "INFO: No queued builds found to be deleted"
        exit 0
    fi
}

delete_queued_build() {
    local BUILD="${1}"

    log "WARN: Deleting ${BUILD} queued build"
    curl \
        --request DELETE \
        --url "https://dev.azure.com/${ORGANIZATION_NAME}/${PROJECT_NAME}/_apis/build/builds/${BUILD}?api-version=${API_VERSION}" \
        --header "${HEADER}" \
        --silent \
        --fail >/dev/null || {
        log "ERROR: Failed deleting ${BUILD} queued build"
        exit 1
    }
}

main() {
    if [[ "${#}" -ne 3 && "${#}" -ne 4 ]]; then
        usage
    fi

    PERSONAL_ACCESS_TOKEN="${1}"
    ORGANIZATION_NAME="${2}"
    PROJECT_NAME="${3}"
    API_VERSION="${4:-"7.1-preview.7"}"

    NOT_STARTED_BUILDS_URI="https://dev.azure.com/${ORGANIZATION_NAME}/${PROJECT_NAME}/_apis/build/builds?statusFilter=notStarted&${API_VERSION}"
    BASE64_PAT=$(printf "%s" ":${PERSONAL_ACCESS_TOKEN}" | base64 | tr -d '\n')
    HEADER="Authorization: Basic ${BASE64_PAT}"

    check_azure_devops_access

    local QUEUED_BUILDS
    QUEUED_BUILDS=$(get_queued_builds)

    jq --raw-output <<<"${QUEUED_BUILDS}" | while IFS= read -r BUILD; do
        delete_queued_build "${BUILD}"
    done
}

main "${@}"
