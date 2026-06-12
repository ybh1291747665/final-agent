"""final-agent CLI — 期末复习 RAG Agent 入口."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before anything else
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env" if (_PROJECT_ROOT / ".env").exists() else ".env")

import typer

from final_agent.ingestion import import_document
from final_agent.knowledge import build, bm25_load
from final_agent.retrieval import search as retrieval_search
from final_agent.generation import answer_question, generate_review
from final_agent.settings import load_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("final-agent")

app = typer.Typer(name="final-agent", help="期末复习 RAG Agent")


@app.command()
def ingest(
    path: str = typer.Argument(..., help="Path to .pdf or .md file"),
):
    """Import a PDF or Markdown file into the knowledge base."""
    settings = load_settings()
    logger.info("Ingesting: %s", path)
    chunks = import_document(path, settings=settings)
    summary = build(chunks, source_path=path, settings=settings)
    typer.echo(f"Ingested {summary['chunks']} chunks from {Path(path).name}")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Your question"),
    top_k: int = typer.Option(10, help="Number of chunks to retrieve"),
):
    """Ask a question and get a cited answer."""
    settings = load_settings()
    bm25_load([], settings=settings)

    results = retrieval_search(question, settings=settings, top_k=top_k)
    if not results:
        typer.echo("No relevant chunks found.")
        return

    typer.echo(f"Retrieved {len(results)} chunks:\n")
    for r in results:
        c = r.chunk
        heading = " > ".join(c.heading_path) if c.heading_path else "(top)"
        typer.echo(f"  [{c.chunk_id[:8]}] ({r.source}, {r.score:.3f}) {heading}: {c.text[:100]}...")
    typer.echo()

    typer.echo("--- Answer ---\n")
    ans = answer_question(question, results, settings=settings)
    typer.echo(ans.answer)
    typer.echo(f"\nCitations: {ans.citations}")


@app.command()
def review(
    topic: str = typer.Argument(..., help="Topic to review"),
    top_k: int = typer.Option(15, help="Number of chunks to retrieve"),
):
    """Generate a structured review summary for a topic."""
    settings = load_settings()
    bm25_load([], settings=settings)

    results = retrieval_search(topic, settings=settings, top_k=top_k)
    if not results:
        typer.echo("No relevant chunks found.")
        return

    typer.echo("--- Review ---\n")
    ans = generate_review(topic, results, settings=settings)
    typer.echo(ans.answer)


@app.command()
def ui(
    port: int = typer.Option(8501, help="Streamlit port"),
):
    """Launch the Streamlit web UI."""
    ui_path = Path(__file__).resolve().parent / "ui" / "app.py"
    project_root = str(Path(__file__).resolve().parent.parent.parent)
    typer.echo(f"Starting Streamlit on http://localhost:{port}")
    subprocess.run([
        "streamlit", "run", str(ui_path),
        "--server.port", str(port),
    ], env={**__import__("os").environ, "FINAL_AGENT_ROOT": project_root})


if __name__ == "__main__":
    app()
