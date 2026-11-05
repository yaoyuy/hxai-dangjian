"""接口包：按业务模块拆分 blueprint。"""
from .articles import bp as articles_bp
from .activities import bp as activities_bp
from .ledger import bp as ledger_bp
from .stats import bp as stats_bp
from .auth_api import bp as auth_bp
from .wechat_api import bp as wechat_bp
from .party import bp as party_bp
from .gallery import bp as gallery_bp

ALL_BLUEPRINTS = (
    articles_bp,
    activities_bp,
    ledger_bp,
    stats_bp,
    auth_bp,
    wechat_bp,
    party_bp,
    gallery_bp,
)
