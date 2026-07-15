#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "betterstack-uptime",
#     "click",
# ]
# ///

__author__ = "Wellington Ozorio <wozorio@duck.com>"

import os
import sys
from fnmatch import fnmatch

import click
from betterstack.uptime import UptimeAPI
from betterstack.uptime.objects import Incident


@click.command()
@click.argument("incident_name_pattern")
@click.option("--dry-run", is_flag=True, default=False)
def main(incident_name_pattern: str, dry_run: bool) -> None:
    """Batch delete incidents from BetterStack Uptime by name glob patterns like *502* or Production*."""
    if "BETTERSTACK_TOKEN" not in os.environ:
        log("Environment variable BETTERSTACK_TOKEN is not set")
        sys.exit(1)

    api = UptimeAPI(os.environ["BETTERSTACK_TOKEN"])

    incidents_to_delete = get_incidents(api, incident_name_pattern)

    if not incidents_to_delete:
        log("No incidents found to be deleted")
        return

    for incident in incidents_to_delete:
        delete_incident(incident, dry_run)


def log(message: str) -> None:
    """Log a message to stderr."""
    click.echo(message, err=True)


def get_incidents(api: UptimeAPI, pattern: str) -> list[Incident]:
    """Return all incidents whose name matches the provided pattern and the status is not Acknowledged or Resolved."""
    incidents = Incident.get_all_instances(api)
    return [
        incident
        for incident in incidents
        if incident.name and fnmatch(incident.name, pattern) and not (incident.is_acknowledged or incident.is_resolved)
    ]


def delete_incident(incident: Incident, dry_run: bool) -> None:
    """Delete a single incident, or just log it if dry_run is True."""
    action = "Would delete" if dry_run else "Deleting"
    log(f"{action} incident {incident.id}: {incident.name}")
    if not dry_run:
        incident.delete()


if __name__ == "__main__":
    main()
