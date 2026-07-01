#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "betterstack-uptime",
#     "click",
# ]
# ///

import os
import sys

import click
from betterstack.uptime import UptimeAPI
from betterstack.uptime.objects import Incident


@click.command()
@click.argument("incident_name")
def main(incident_name: str) -> None:
    """Delete incidents from BetterStack Uptime by name."""
    if "BETTERSTACK_TOKEN" not in os.environ:
        log("Environment variable BETTERSTACK_TOKEN is not set")
        sys.exit(1)

    api = UptimeAPI(os.environ["BETTERSTACK_TOKEN"])

    incidents_to_delete = get_incidents(api, incident_name)

    if not incidents_to_delete:
        log("No incidents found to be deleted")
        return

    for incident in incidents_to_delete:
        delete_incident(incident)


def log(message: str) -> None:
    """Log a message to stderr."""
    click.echo(message, err=True)


def get_incidents(api: UptimeAPI, name: str) -> list[Incident]:
    """Return all incidents whose name matches the provided name argument."""
    incidents = Incident.get_all_instances(api)
    return [incident for incident in incidents if name == incident.name and incident.status.lower() != "resolved"]


def delete_incident(incident: Incident) -> None:
    """Delete a single incident."""
    log(f"Deleting incident {incident.id}: {incident.name}")
    incident.delete()


if __name__ == "__main__":
    main()
