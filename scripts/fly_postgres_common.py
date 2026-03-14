import os

DB_APP_ENV_VAR_BY_ENV = {
    "dev": "FLY_DB_APP_NAME_DEV",
    "prod": "FLY_DB_APP_NAME_PROD",
}


def get_db_app(environment: str) -> str:
    if environment not in DB_APP_ENV_VAR_BY_ENV:
        raise ValueError(f"Unsupported environment: {environment}")
    env_var = DB_APP_ENV_VAR_BY_ENV[environment]
    app_name = os.getenv(env_var, "").strip()
    if not app_name:
        raise ValueError(
            f"Missing required env var {env_var} for environment '{environment}'."
        )
    return app_name


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
