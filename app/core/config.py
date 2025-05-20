from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "CodeDocGen API"
    DEBUG: bool = False

    # Bitbucket credentials (consider using environment variables or a secrets manager)
    BITBUCKET_USERNAME: str | None = None
    BITBUCKET_APP_PASSWORD: str | None = None # Or token

    # Confluence settings
    CONFLUENCE_URL: str | None = None # e.g., "https://your-domain.atlassian.net/wiki"
    CONFLUENCE_USERNAME: str | None = None
    CONFLUENCE_API_TOKEN: str | None = None
    CONFLUENCE_SPACE_KEY: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings() 