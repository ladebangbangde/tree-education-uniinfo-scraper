from __future__ import annotations

import typer
from .db import Base, engine
from .logger import logger
# Import models so metadata is populated for create-tables.
from . import models  # noqa: F401
from .tasks.crawl_all import crawl_all as crawl_all_task
from .tasks.crawl_programmes import crawl_programmes as crawl_programmes_task
from .tasks.crawl_programme_detail import crawl_programme_detail as crawl_programme_detail_task
from .tasks.crawl_universities import crawl_universities as crawl_universities_task
from .tasks.crawl_university_detail import crawl_university_detail as crawl_university_detail_task
from .tasks.retry_failed import retry_failed as retry_failed_task

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


@app.command("crawl-all")
def crawl_all(
    country: str = typer.Option("united-kingdom"),
    university_limit: int = typer.Option(50, min=1),
    programme_limit: int = typer.Option(50, min=1),
    detail_limit: int = typer.Option(500, min=1),
    skip_universities: bool = typer.Option(False),
    skip_programmes: bool = typer.Option(False),
    skip_details: bool = typer.Option(False),
) -> None:
    result = crawl_all_task(
        country=country,
        university_limit=university_limit,
        programme_limit=programme_limit,
        detail_limit=detail_limit,
        skip_universities=skip_universities,
        skip_programmes=skip_programmes,
        skip_details=skip_details,
    )
    typer.echo(
        "crawl-all completed: "
        f"universities_total={result.universities_total}, "
        f"universities_success={result.universities_success}, "
        f"universities_failed={result.universities_failed}, "
        f"programmes_success={result.programmes_success}, "
        f"programmes_failed={result.programmes_failed}, "
        f"details_success={result.details_success}, "
        f"details_failed={result.details_failed}"
    )


@app.command("retry-failed")
def retry_failed(limit: int = typer.Option(20, min=1)) -> None:
    result = retry_failed_task(limit=limit)
    typer.echo(
        "retry-failed completed: "
        f"total={result.total}, "
        f"success={result.success}, "
        f"failed={result.failed}, "
        f"dead={result.dead}"
    )


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
