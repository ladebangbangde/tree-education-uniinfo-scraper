from __future__ import annotations

import typer
from .db import Base, engine
from .logger import logger
# Import models so metadata is populated for create-tables.
from . import models  # noqa: F401
from .tasks.crawl_programmes import crawl_programmes as crawl_programmes_task
from .tasks.crawl_programme_detail import crawl_programme_detail as crawl_programme_detail_task
from .tasks.crawl_universities import crawl_universities as crawl_universities_task
from .tasks.crawl_university_detail import crawl_university_detail as crawl_university_detail_task

app = typer.Typer(help="Tree Education public university information scraper")


@app.command("init-db")
def init_db() -> None:
    """Create database tables using SQLAlchemy metadata."""
    Base.metadata.create_all(bind=engine)
    typer.echo("Database tables are ready")


@app.command("crawl-universities")
def crawl_universities(country: str = typer.Option("united-kingdom"), limit: int = typer.Option(10, min=1)) -> None:
    count = crawl_universities_task(country=country, limit=limit)
    typer.echo(f"Persisted {count} universities")


@app.command("crawl-university-detail")
def crawl_university_detail(university_id: int = typer.Option(..., min=1)) -> None:
    crawl_university_detail_task(university_id=university_id)
    typer.echo(f"Crawled university detail for id={university_id}")


@app.command("crawl-programmes")
def crawl_programmes(university_id: int = typer.Option(..., min=1), limit: int = typer.Option(20, min=1)) -> None:
    count = crawl_programmes_task(university_id=university_id, limit=limit)
    typer.echo(f"Persisted {count} programmes")


@app.command("crawl-programme-detail")
def crawl_programme_detail(programme_id: int = typer.Option(..., min=1)) -> None:
    success = crawl_programme_detail_task(programme_id=programme_id)
    if success:
        typer.echo(f"Crawled programme detail for id={programme_id}")
    else:
        typer.echo(f"Programme detail crawl failed or was skipped for id={programme_id}")


if __name__ == "__main__":
    logger.info("Starting CLI")
    app()
