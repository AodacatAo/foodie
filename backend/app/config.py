"""应用配置：环境变量 + 项目根目录 .env。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent  # foodie/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "foodie"
    # 0.0.0.0 = 监听所有网卡，家里手机/平板可通过局域网 IP 访问
    host: str = "0.0.0.0"
    port: int = 8080

    # 访问密码：设置后所有 API 和媒体文件都需要登录（Cookie 30 天）。
    # 留空 = 不开启登录（仅适合纯局域网使用）。
    access_token: str | None = None
    data_dir: Path = BASE_DIR / "data"

    # LLM 提炼（DeepSeek，OpenAI 兼容协议）
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_enabled: bool = True  # 仅在配置了 API key 时生效

    # 小红书抓取（M2）
    xhs_cookie: str | None = None

    # 微信通知独立服务（解耦）：下单等事件经 HTTP 推送到 wechat-notify 容器
    wechat_notify_url: str | None = None  # 如 http://wechat-notify:8090/notify
    notify_token: str | None = None       # 与独立服务的 NOTIFY_TOKEN 一致

    @property
    def db_path(self) -> Path:
        return self.data_dir / "foodie.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def snapshot_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def llm_ready(self) -> bool:
        return self.llm_enabled and bool(self.deepseek_api_key)


settings = Settings()
