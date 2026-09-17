"""Central runtime configuration, loaded once from the environment."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Alpaca
    alpaca_api_key: str = Field(alias="ALPACA_API_KEY")
    alpaca_secret_key: str = Field(alias="ALPACA_SECRET_KEY")
    alpaca_paper: bool = Field(default=True, alias="ALPACA_PAPER")
    alpaca_data_feed: str = Field(default="IEX", alias="ALPACA_DATA_FEED")

    # OpenAI
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_decision_model: str = Field(default="gpt-4o-mini", alias="OPENAI_DECISION_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )

    # Pinecone
    pinecone_api_key: str = Field(alias="PINECONE_API_KEY")
    pinecone_index_name: str = Field(default="alphadesk-news", alias="PINECONE_INDEX_NAME")
    pinecone_cloud: str = Field(default="aws", alias="PINECONE_CLOUD")
    pinecone_region: str = Field(default="us-east-1", alias="PINECONE_REGION")

    # Tavily
    tavily_api_key: str = Field(alias="TAVILY_API_KEY")

    # Postgres / TimescaleDB
    database_url: str = Field(
        default="postgresql+asyncpg://alphadesk:alphadesk@localhost:5432/alphadesk",
        alias="DATABASE_URL",
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Strategy
    tickers: str = Field(default="AAPL,NVDA,TSLA,MSFT,AMZN", alias="TICKERS")
    cycle_interval_minutes: int = Field(default=15, alias="CYCLE_INTERVAL_MINUTES")
    max_position_pct: float = Field(default=0.15, alias="MAX_POSITION_PCT")
    max_total_exposure_pct: float = Field(default=0.60, alias="MAX_TOTAL_EXPOSURE_PCT")
    max_drawdown_pct: float = Field(default=0.10, alias="MAX_DRAWDOWN_PCT")

    # Safety
    dry_run: bool = Field(default=True, alias="DRY_RUN")

    # Server
    port: int = Field(default=8002, alias="PORT")

    @property
    def ticker_list(self) -> list[str]:
        return [t.strip().upper() for t in self.tickers.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    # pydantic-settings' default precedence puts real OS environment variables ABOVE
    # the .env file — so a same-named var exported globally in the user's shell profile
    # (e.g. ~/.zshrc, for an unrelated project) would silently win over this project's
    # .env. For a trading app, "silently using the wrong account's API key" is a real
    # safety issue, not a cosmetic one — force this project's .env to take precedence.
    load_dotenv(".env", override=True)
    return Settings()
