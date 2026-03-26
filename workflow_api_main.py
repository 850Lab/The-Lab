"""CLI entry: `python workflow_api_main.py` (requires uvicorn)."""

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.workflow_app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
