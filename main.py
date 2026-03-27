import asyncio

import click


@click.group()
def cli():
    """temporal-agents CLI."""
    pass


@cli.command()
@click.argument('resource', default='requests')
@click.option('--status', default='pending', help='Filter by status')
def hitl(resource: str, status: str):
    """HITL management commands."""
    if resource == 'list':
        async def _run():
            from temporal_agents.activities.hitl_db import list_hitl_requests
            requests = await list_hitl_requests(status=status)
            if not requests:
                click.echo("No HITL requests found.")
                return
            click.echo(f"{'ID':<36} {'PRIORITY':<10} {'STATUS':<12} {'WORKFLOW':<20} {'DESCRIPTION'}")
            click.echo("-" * 100)
            for r in requests:
                click.echo(f"{str(r.id):<36} {r.priority:<10} {r.status:<12} {r.workflow_id:<20} {r.description}")
        asyncio.run(_run())
    else:
        click.echo(f"Unknown resource: {resource}. Use 'list'.")


def main():
    cli()


if __name__ == "__main__":
    main()
