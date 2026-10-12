"""
Entrypoint script for running RepoScore API via Uvicorn.
"""

import uvicorn
from backend.core.config import settings


def main() -> None:
    """Run the Uvicorn ASGI server."""
    uvicorn.run(
        "backend.api.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
