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

# pylint: disable=missing-module-docstring

__author__ = "Wellington Ozorio <wozorio@duck.com>"

import time

import click
from azure.devops.connection import Connection
from azure.devops.v7_1.build.build_client import BuildClient
from azure.devops.v7_1.build.models import Build
from msrest.authentication import BasicAuthentication


@click.command()
@click.argument("personal_access_token")
@click.argument("organization")
@click.argument("project")
def main(personal_access_token: str, organization: str, project: str) -> None:
    """Batch delete queued builds ("pipeline runs") in Azure DevOps."""
    build_client = get_build_client(organization, personal_access_token)

    queued_builds = get_queued_builds(build_client, project)
    for build_id in queued_builds:
        delete_build(build_client, project, build_id)


def log(message: str) -> None:
    """Log a diagnostic message to stderr."""
    click.echo(message, err=True)


def get_build_client(organization: str, personal_access_token: str) -> BuildClient:
    """Return an authenticated Azure DevOps build client for the given organization."""
    credentials = BasicAuthentication("", personal_access_token)
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

    start = time.monotonic()
    timeout_in_seconds = 180

    deadline = start + timeout_in_seconds

    while start < deadline:
        build = build_client.get_build(project=project, build_id=build_id)
        # Build status
        # https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/update-build?view=azure-devops-rest-7.1#buildstatus
        if build.status == "completed":
            return
        log(f"Waiting for build {build_id} to be cancelled")
        time.sleep(5)

    log(f"Timed out waiting for build {build_id} to be cancelled")
    exit(1)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
