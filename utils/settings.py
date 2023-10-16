from pydantic import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SPREADSHEET_URL: str

    class Config:
        env_file = ".streamlit/secrets.toml"
        env_file_encoding = "utf-8"


settings = Settings()
