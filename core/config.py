"""
Configuration management cho Smart Home system
Uses pydantic-settings for environment variable handling
"""
from functools import lru_cache
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="smarthome", alias="DB_NAME")
    db_user: str = Field(default="postgres", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


class MQTTSettings(BaseSettings):
    """MQTT configuration"""
    mqtt_broker: str = Field(default="10.0.18.255", alias="MQTT_BROKER")
    mqtt_port: int = Field(default=1883, alias="MQTT_PORT")
    mqtt_username: Optional[str] = Field(default=None, alias="MQTT_USERNAME")
    mqtt_password: Optional[str] = Field(default=None, alias="MQTT_PASSWORD")
    mqtt_keepalive: int = Field(default=60, alias="MQTT_KEEPALIVE")
    mqtt_qos: int = Field(default=1, alias="MQTT_QOS")
    mqtt_retain: bool = Field(default=True, alias="MQTT_RETAIN")
    mqtt_client_id: str = Field(default="smarthome_backend", alias="MQTT_CLIENT_ID")


class RedisSettings(BaseSettings):
    """Redis configuration for state store"""
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_url: Optional[str] = None

    @property
    def connection_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


class QdrantSettings(BaseSettings):
    """Qdrant vector database configuration"""
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_grpc_port: int = Field(default=6334, alias="QDRANT_GRPC_PORT")
    qdrant_collection: str = Field(default="smarthome_memory", alias="QDRANT_COLLECTION")
    qdrant_api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")


class ThingsBoardSettings(BaseSettings):
    """ThingsBoard IoT platform configuration"""
    tb_url: str = Field(default="http://10.0.18.255:8080", alias="TB_URL")
    tb_user: Optional[str] = Field(default=None, alias="TB_USER")
    tb_pass: Optional[str] = Field(default=None, alias="TB_PASS")
    tb_device_id: Optional[str] = Field(default=None, alias="DEVICE_ID")


class Settings(BaseSettings):
    """Main application settings"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # App settings
    app_name: str = Field(default="SmartHome AI", alias="APP_NAME")
    app_version: str = Field(default="2.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # API settings
    api_host: str = Field(default="localhost", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    mqtt: MQTTSettings = Field(default_factory=MQTTSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    thingsboard: ThingsBoardSettings = Field(default_factory=ThingsBoardSettings)

    # External API keys
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    weather_api_key: Optional[str] = Field(default=None, alias="WEATHER_API_KEY")
    picovoice_access_key: Optional[str] = Field(default=None, alias="PICOVOICE_ACCESS_KEY")

    # Agent settings
    agent_model: str = Field(default="gemini-2.5-flash", alias="AGENT_MODEL")
    agent_session_timeout: int = Field(default=3600, alias="AGENT_SESSION_TIMEOUT")

    # Memory settings
    memory_retention_days: int = Field(default=30, alias="MEMORY_RETENTION_DAYS")
    memory_embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="MEMORY_EMBEDDING_MODEL")


@lru_cache()
def get_config() -> Settings:
    """
    Get cached configuration singleton
    Load from environment variables and .env file
    """
    return Settings()
