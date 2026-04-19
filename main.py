import asyncio

import click


@click.group()
def cli():
    """temporal-agentic-workflow CLI."""
    pass


@cli.command()
@click.argument("resource", default="list")
@click.option("--status", default="pending", help="Filter by status")
@click.option("--type", "task_type", default=None, help="Filter by type: task or hitl")
def tasks(resource: str, status: str, task_type: str):
    """Task management commands."""
    if resource == "list":

        async def _run():
            from temporal_agents.activities.tasks import list_tasks

            all_tasks = await list_tasks(status=status)
            if task_type:
                all_tasks = [t for t in all_tasks if t.type == task_type]
            if not all_tasks:
                click.echo("No tasks found.")
                return
            click.echo(
                f"{'ID':<36} {'PRI':<5} {'TYPE':<6} {'STATUS':<12} {'PROJECT':<12} {'TITLE'}"
            )
            click.echo("-" * 110)
            for t in all_tasks:
                wf = f" [{t.workflow_id}]" if t.workflow_id else ""
                click.echo(
                    f"{str(t.id):<36} {t.priority:<5} {t.type:<6} {t.status:<12} {t.project:<12} {t.title}{wf}"
                )

        asyncio.run(_run())
    else:
        click.echo(f"Unknown resource: {resource}. Use 'list'.")


def main():
    cli()


if __name__ == "__main__":
    main()
