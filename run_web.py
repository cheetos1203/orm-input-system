from __future__ import annotations

import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()

    # reload=True and workers>1 cannot be used together
    use_workers = settings.app_workers if not settings.app_reload else 1
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
        workers=use_workers,
    )


if __name__ == "__main__":
    main()

