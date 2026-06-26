from outreach_system.api.webhooks import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn

    from outreach_system.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "webhook_server:app",
        host=settings.webhook_host,
        port=settings.webhook_port,
        reload=False,
    )
