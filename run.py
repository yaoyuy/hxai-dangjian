"""本地启动入口。

用法：
    python run.py

它会：
1. 读取 .env（没有 .env 时用 .env.example 里的默认值）
2. 建表 + 首次初始化数据
3. 启动 Flask 开发服务器
"""
from __future__ import annotations

import os

from app import app

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "5000"))
    env = os.getenv("APP_ENV", "local")
    print("=" * 60)
    print(f"  {app.config['SITE_NAME']} · 智慧党建系统（第一阶段）")
    print(f"  环境: {env}   数据库: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[0]}")
    print(f"  本机访问:  http://{host}:{port}/")
    print(f"  后台看板:  http://{host}:{port}/dashboard")
    print(f"  测试登录:  http://{host}:{port}/login")
    print(f"  微信接入:  http://{host}:{port}/api/wechat/status")
    print("=" * 60)
    app.run(host=host, port=port, debug=(env == "local"))
