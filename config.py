"""配置加载模块。

所有可变参数都来自环境变量（.env 文件），代码里不写死域名、端口、账号、密钥。
第二阶段切换到学校服务器时，只需要改 .env，不需要改代码。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# 首次运行自动从 .env.example 生成 .env，避免"忘了复制模板导致起不来"。
# 生成后请按实际环境修改 .env（域名、端口、数据库、AppID、密钥都只放这里）。
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE = BASE_DIR / ".env.example"
if not ENV_FILE.exists() and ENV_EXAMPLE.exists():
    ENV_FILE.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
load_dotenv(ENV_FILE)


def _env(key: str, default: str = "") -> str:
    value = os.getenv(key, default)
    return value.strip() if isinstance(value, str) else value


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env(key, "true" if default else "false").lower()
    return raw in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def build_database_uri() -> str:
    """根据 DB_ENGINE 生成数据库连接串。

    - sqlite：本地零配置，直接落地到项目 data/ 目录
    - mysql：学校服务器常用，换库只改 .env，不动代码
    """
    engine = _env("DB_ENGINE", "sqlite").lower()
    if engine in ("mysql", "mariadb"):
        host = _env("MYSQL_HOST")
        dbname = _env("MYSQL_DB")
        user = _env("MYSQL_USER")
        password = _env("MYSQL_PASSWORD")
        port = _env_int("MYSQL_PORT", 3306)
        charset = _env("MYSQL_CHARSET", "utf8mb4")
        if not (host and dbname and user):
            # 缺参数时明确报错，而不是偷偷回退到 SQLite，避免学校环境连错库
            raise RuntimeError(
                "DB_ENGINE=mysql 但缺少 MYSQL_HOST / MYSQL_DB / MYSQL_USER，请检查 .env"
            )
        return (
            f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}"
            f"?charset={charset}"
        )
    # 默认 SQLite
    sqlite_path = _env("SQLITE_PATH", "data/dangjian.db")
    path = Path(sqlite_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def _upload_dir() -> Path:
    raw = _env("UPLOAD_DIR", "data/uploads")
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_public_base_url() -> str:
    """对外访问地址（用于生成绝对链接、推送菜单、网页授权回调）。

    优先级：
    1. .env 里的 PUBLIC_BASE_URL（正式部署时填学校域名，这是唯一权威来源）；
    2. 本地测试没填时，退回 tools/keep_online.sh 写出的 .tunnel_url
       （当前公网隧道域名）。这样隧道换域名后链接会自动跟上，不用手改 .env。
    注意：这里只是"本地没有配置时的兜底"，不会覆盖 .env 里已经填好的值。
    """
    configured = _env("PUBLIC_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")

    tunnel_file = BASE_DIR / ".tunnel_url"
    if tunnel_file.exists():
        host = tunnel_file.read_text(encoding="utf-8", errors="ignore").strip()
        if host:
            return host if host.startswith("http") else f"https://{host}"
    return ""


class Config:
    """Flask 配置对象。"""

    # 基础
    SECRET_KEY = _env("SECRET_KEY", "dev-only-change-me")
    SITE_NAME = _env("SITE_NAME", "智慧党建")
    BRANCH_NAME = _env("BRANCH_NAME", "第一党支部")
    APP_ENV = _env("APP_ENV", "local")
    PUBLIC_BASE_URL = resolve_public_base_url()

    # 数据库（SQLAlchemy 统一抽象，SQLite / MySQL 可平滑切换）
    SQLALCHEMY_DATABASE_URI = build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # 上传
    UPLOAD_DIR = str(_upload_dir())
    MAX_CONTENT_LENGTH = _env_int("MAX_UPLOAD_MB", 20) * 1024 * 1024
    ALLOWED_UPLOAD_EXT = {
        e.strip().lower()
        for e in _env("ALLOWED_UPLOAD_EXT", "doc,docx,pdf,xls,xlsx,ppt,pptx,txt,csv,md").split(",")
        if e.strip()
    }

    # 微信
    WECHAT_APPID = _env("WECHAT_APPID")
    WECHAT_APPSECRET = _env("WECHAT_APPSECRET")
    WECHAT_TOKEN = _env("WECHAT_TOKEN")
    WECHAT_AES_KEY = _env("WECHAT_AES_KEY")
    LOGIN_MODE = _env("LOGIN_MODE", "test")
    ALLOW_TEST_LOGIN = _env_bool("ALLOW_TEST_LOGIN", True)

    # 初始管理员（只在数据库为空时创建，账号密码来自 .env）
    ADMIN_USERNAME = _env("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = _env("ADMIN_PASSWORD", "Admin@123456")
    ADMIN_REAL_NAME = _env("ADMIN_REAL_NAME", "系统管理员")
    AUTO_SEED = _env_bool("AUTO_SEED", True)

    # 展示
    SHOW_DEMO_BADGE = _env_bool("SHOW_DEMO_BADGE", True)
    TEST_DATA_LABEL = "测试数据"
    JSON_AS_ASCII = False
    TEMPLATES_AUTO_RELOAD = True
