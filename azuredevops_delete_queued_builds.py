#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-devops",
#     "click",
#     "msrest",
# ]
# ///

__author__ = "Wellington Ozorio <wozorio@duck.com>"

import os
import sys
import time

import click
from azure.devops.connection import Connection
from azure.devops.v7_1.build.build_client import BuildClient
from azure.devops.v7_1.build.models import Build
from msrest.authentication import BasicAuthentication


@click.command()
@click.argument("organization")
@click.argument("project")
def main(organization: str, project: str) -> None:
    """Batch delete queued builds ("pipeline runs") in Azure DevOps."""
    check_azure_devops_ext_pat_env_var()

    build_client = get_build_client(organization)

    queued_builds = get_queued_builds(build_client, project)
    for build_id in queued_builds:
        try:
            delete_build(build_client, project, build_id)
        except Exception as error:  # noqa: BLE001
            log(f"Failed to delete build {build_id}: {error}")


def log(message: str) -> None:
    """Log a diagnostic message to stderr."""
    click.echo(message, err=True)


def check_azure_devops_ext_pat_env_var() -> None:
    """Check whether the environment variable with Azure DevOps PAT is set."""
    if "AZURE_DEVOPS_EXT_PAT" not in os.environ:
        log("AZURE_DEVOPS_EXT_PAT environment variable is not set")
        sys.exit(1)


def get_build_client(organization: str) -> BuildClient:
    """Return an authenticated Azure DevOps build client for the given organization."""
    credentials = BasicAuthentication("", os.environ["AZURE_DEVOPS_EXT_PAT"])
    connection = Connection(
        base_url=f"https://dev.azure.com/{organization}",
        creds=credentials,
    )
    return connection.clients.get_build_client()


def get_queued_builds(build_client: BuildClient, project: str) -> list[int]:
    """Return the IDs of all queued builds."""
    log("Fetching list of queued builds")
    builds = build_client.get_builds(project=project, status_filter="notStarted")

    if not builds:
        log("No queued builds found to be deleted")
        return []

    return [build.id for build in builds]


def delete_build(build_client: BuildClient, project: str, build_id: int) -> None:
    """Delete a build."""
    cancel_build(build_client, project, build_id)

    log(f"Deleting queued build {build_id}")
    build_client.delete_build(project=project, build_id=build_id)


def cancel_build(build_client: BuildClient, project: str, build_id: int) -> None:
    """Cancel a build."""
    log(f"Cancelling build {build_id}")
    build_client.update_build(
        build=Build(status="cancelling"),
        project=project,
        build_id=build_id,
    )

    timeout_in_seconds = 180
    deadline = time.monotonic() + timeout_in_seconds

    while time.monotonic() < deadline:
        build = build_client.get_build(project=project, build_id=build_id)
        # Build status
        # https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/update-build?view=azure-devops-rest-7.1#buildstatus
        if build.status == "completed":
            return
        log(f"Waiting for build {build_id} to be cancelled")
        time.sleep(1)

    error_message = f"Timed out waiting for build {build_id} to be cancelled"
    raise RuntimeError(error_message)


if __name__ == "__main__":
    main()
