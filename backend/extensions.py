"""Flask 扩展实例集中定义，避免循环导入。"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
