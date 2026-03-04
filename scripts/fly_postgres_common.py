DB_APP_BY_ENV = {
    "dev": "pax-tt-db-dev",
    "prod": "pax-tt-db-prod",
}


def get_db_app(environment: str) -> str:
    if environment not in DB_APP_BY_ENV:
        raise ValueError(f"Unsupported environment: {environment}")
    return DB_APP_BY_ENV[environment]


def build_ssh_console_command(environment: str, remote_command: str) -> list[str]:
    app = get_db_app(environment)
    return [
        "fly",
        "ssh",
        "console",
        "-a",
        app,
        "-C",
        remote_command,
    ]
