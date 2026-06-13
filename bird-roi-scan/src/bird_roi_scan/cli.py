#!usr/bin/env python3
# bird_roi_scan/cli.py

import typer

app = typer.Typer()

@app.command()
def score():
    """Score species evidence for ROI inclusion."""
    pass

@app.command()
def report():
    """Generate markdown/CSV evidence reports."""
    pass

if __name__ == "__main__":
    app()