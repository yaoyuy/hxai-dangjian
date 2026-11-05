"""管理命令（不依赖 flask cli，直接 python manage.py xxx）。

命令：
    python manage.py initdb       建表
    python manage.py seed         写入初始化测试数据
    python manage.py reset        清空并重建（危险，本地用）
    python manage.py stats        打印当前数据统计
    python manage.py accounts     列出可登录账号
"""
from __future__ import annotations

import sys

from app import create_app
from backend.extensions import db


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    app = create_app()

    with app.app_context():
        if cmd == "initdb":
            db.create_all()
            print("建表完成")
            return 0

        if cmd == "seed":
            from backend.seed import seed

            info = seed(app, force=True)
            print("初始化数据完成：", info)
            return 0

        if cmd == "reset":
            confirm = input("将删除全部本地数据，确认请输入 yes：").strip()
            if confirm != "yes":
                print("已取消")
                return 1
            db.drop_all()
            db.create_all()
            from backend.seed import seed

            print("重建完成：", seed(app, force=True))
            return 0

        if cmd == "stats":
            from backend.models import (
                Activity, Article, Enrollment, LedgerFile, StudyRecord, User,
            )

            print("党员/用户数:", User.query.count())
            print("已发布文章:", Article.query.filter_by(status="published").count())
            print("草稿文章:  ", Article.query.filter_by(status="draft").count())
            print("活动数:    ", Activity.query.count())
            print("有效报名:  ", Enrollment.query.filter_by(status="confirmed").count())
            print("学习记录:  ", StudyRecord.query.count())
            print("台账文件:  ", LedgerFile.query.count())
            return 0

        if cmd == "accounts":
            from backend.models import User

            for u in User.query.all():
                print(f"{u.username:12s} {u.real_name:8s} {u.role:14s} 测试账号={u.is_test_account}")
            return 0

    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
