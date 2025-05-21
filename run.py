import uvicorn


def main():
    """Run the uvicorn server with the FastAPI application."""
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
