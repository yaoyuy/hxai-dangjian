"""数据库模型层。

设计要点（为第二阶段预留）：
1. 用 SQLAlchemy ORM 写，不写 SQLite 专有 SQL，换 MySQL 时只改 .env。
2. 支部（Branch）先做单支部，但保留 branch_id 外键，将来多支部只加数据不改表。
3. 角色（role）字段预留 super_admin / branch_admin / member 三档。
4. 学习时长、报名、阅读量都落库，统计看板全部实时聚合，不写死。
"""
from __future__ import annotations

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def now() -> datetime:
    return datetime.now()


class Branch(db.Model):
    """党支部。第一阶段只有一条记录，第二阶段扩展为多支部。"""

    __tablename__ = "branch"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=now)

    members = db.relationship("User", back_populates="branch")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "code": self.code}


class User(db.Model):
    """党员/用户。

    role: super_admin（超级管理员）/ branch_admin（支部管理员）/ member（普通党员）
    第一阶段统一挂在单支部下；openid 字段留给第二阶段微信网页授权写入。
    """

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    real_name = db.Column(db.String(64), nullable=False, default="")
    role = db.Column(db.String(20), nullable=False, default="member")
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=True)
    openid = db.Column(db.String(64), unique=True, nullable=True)
    phone = db.Column(db.String(20), default="")
    # 年龄段：35岁以下 / 36-50岁 / 51岁以上（看板"党员构成"用，真实字段，不写死）
    age_group = db.Column(db.String(20), default="35岁以下")
    is_test_account = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now)
    last_login_at = db.Column(db.DateTime, nullable=True)

    branch = db.relationship("Branch", back_populates="members")
    enrollments = db.relationship("Enrollment", back_populates="user")
    study_records = db.relationship("StudyRecord", back_populates="user")

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self) -> bool:
        return self.role in ("super_admin", "branch_admin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "real_name": self.real_name,
            "role": self.role,
            "branch": self.branch.name if self.branch else "",
            "age_group": self.age_group,
            "is_test_account": self.is_test_account,
        }


class Category(db.Model):
    """学习专栏分类：理论学习 / 党史学习 / 云党课 / 重要文件。"""

    __tablename__ = "category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(30), unique=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    articles = db.relationship("Article", back_populates="category")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "code": self.code}


class Article(db.Model):
    """学习专栏文章。status: draft（草稿）/ published（已发布）。"""

    __tablename__ = "article"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500), default="")
    content = db.Column(db.Text, default="")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    cover_url = db.Column(db.String(300), default="")
    media_type = db.Column(db.String(20), default="text")  # text / video
    video_url = db.Column(db.String(300), default="")
    duration_min = db.Column(db.Integer, default=0)
    study_minutes = db.Column(db.Integer, default=5)  # 计入学习时长的分钟数
    status = db.Column(db.String(20), default="draft", index=True)
    is_demo = db.Column(db.Boolean, default=False)  # 是否为测试数据
    view_count = db.Column(db.Integer, default=0)
    published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    category = db.relationship("Category", back_populates="articles")
    study_records = db.relationship("StudyRecord", back_populates="article")

    def to_dict(self, with_content: bool = False) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "category": self.category.name if self.category else "",
            "category_id": self.category_id,
            "cover_url": self.cover_url,
            "media_type": self.media_type,
            "video_url": self.video_url,
            "duration_min": self.duration_min,
            "study_minutes": self.study_minutes,
            "status": self.status,
            "is_demo": self.is_demo,
            "view_count": self.view_count,
            "published_at": self.published_at.strftime("%Y-%m-%d") if self.published_at else "",
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else "",
        }
        if with_content:
            data["content"] = self.content
        return data


class Activity(db.Model):
    """三会一课 / 主题党日 / 志愿服务等活动。

    kind: meeting（会议）/ party_day（主题党日）/ volunteer（志愿服务）/ study（学习）
    """

    __tablename__ = "activity"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    kind = db.Column(db.String(30), default="meeting", index=True)
    summary = db.Column(db.String(500), default="")
    content = db.Column(db.Text, default="")
    cover_url = db.Column(db.String(300), default="")
    location = db.Column(db.String(200), default="")
    start_at = db.Column(db.DateTime, nullable=True)
    end_at = db.Column(db.DateTime, nullable=True)
    signup_deadline = db.Column(db.DateTime, nullable=True)
    capacity = db.Column(db.Integer, default=0)  # 0 表示不限
    target = db.Column(db.String(200), default="全体党员、入党积极分子")
    status = db.Column(db.String(20), default="open", index=True)  # open / closed / finished
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now)

    enrollments = db.relationship(
        "Enrollment", back_populates="activity", cascade="all, delete-orphan"
    )

    @property
    def enrolled_count(self) -> int:
        """报名人数实时从数据库统计，不存冗余计数。"""
        return Enrollment.query.filter_by(activity_id=self.id, status="confirmed").count()

    KIND_LABELS = {
        "meeting": "三会一课",
        "party_day": "主题党日",
        "volunteer": "志愿服务",
        "study": "集中学习",
    }
    STATUS_LABELS = {"open": "进行中", "closed": "已截止", "finished": "已完成"}

    @property
    def kind_label(self) -> str:
        """中文类型名，模板里直接显示。"""
        return self.KIND_LABELS.get(self.kind, self.kind or "")

    @property
    def status_label(self) -> str:
        return self.STATUS_LABELS.get(self.status, self.status or "")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "summary": self.summary,
            "cover_url": self.cover_url,
            "location": self.location,
            "start_at": self.start_at.strftime("%Y-%m-%d %H:%M") if self.start_at else "",
            "end_at": self.end_at.strftime("%Y-%m-%d %H:%M") if self.end_at else "",
            "capacity": self.capacity,
            "enrolled_count": self.enrolled_count,
            "target": self.target,
            "status": self.status,
            "is_demo": self.is_demo,
        }


class Enrollment(db.Model):
    """报名记录。唯一约束保证同一活动同一用户只报名一次。"""

    __tablename__ = "enrollment"
    __table_args__ = (
        db.UniqueConstraint("activity_id", "user_id", name="uq_enrollment_activity_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), default="confirmed")  # confirmed / cancelled
    remark = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=now)

    activity = db.relationship("Activity", back_populates="enrollments")
    user = db.relationship("User", back_populates="enrollments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "activity_id": self.activity_id,
            "user_id": self.user_id,
            "user_name": self.user.real_name if self.user else "",
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
        }


class StudyRecord(db.Model):
    """学习记录：谁在什么时候学了哪篇文章、学了多久。看板据此实时统计。"""

    __tablename__ = "study_record"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("article.id"), nullable=False)
    minutes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=now, index=True)

    user = db.relationship("User", back_populates="study_records")
    article = db.relationship("Article", back_populates="study_records")


class LedgerFile(db.Model):
    """电子台账文件。文件本体落在 UPLOAD_DIR，元信息入库。"""

    __tablename__ = "ledger_file"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(255), nullable=False)       # 磁盘上的真实文件名
    original_name = db.Column(db.String(255), nullable=False)  # 用户上传时的原始文件名
    category = db.Column(db.String(30), default="材料", index=True)
    ext = db.Column(db.String(10), default="")
    size_bytes = db.Column(db.Integer, default=0)
    uploader_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    is_demo = db.Column(db.Boolean, default=False)
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=now)

    uploader = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "original_name": self.original_name,
            "category": self.category,
            "ext": self.ext,
            "size_bytes": self.size_bytes,
            "size_text": human_size(self.size_bytes),
            "uploader": self.uploader.real_name if self.uploader else "系统",
            "download_count": self.download_count,
            "is_demo": self.is_demo,
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else "",
        }


class GalleryPhoto(db.Model):
    """党建风采图片。"""

    __tablename__ = "gallery_photo"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    image_url = db.Column(db.String(300), default="")
    description = db.Column(db.String(500), default="")
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "image_url": self.image_url,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else "",
        }


# ---------- 角色 / 状态的中文名（后台、接口、模板共用一份，避免各写各的） ----------
ROLE_LABELS = {"super_admin": "超级管理员", "branch_admin": "支部管理员", "member": "普通党员"}
DUE_STATUS_LABELS = {"paid": "已缴", "unpaid": "未缴", "late": "补缴"}
DUE_METHODS = ["现金", "微信", "银行代扣", "其他"]
TRANSFER_STATUS_LABELS = {"pending": "待审核", "approved": "已通过", "rejected": "已驳回"}
TRANSFER_DIRECTION_LABELS = {"in": "转入", "out": "转出"}


class SysSetting(db.Model):
    """系统设置（键值对表）。

    微信 AppID / AppSecret / Token / EncodingAESKey 等"部署时才确定"的参数存这里，
    在后台「微信设置」页填写、保存即生效：不用改代码，也不用改 .env
    （.env 在部分环境里受安全策略保护、改不动）。

    第二阶段换成学校公众号时，只需要在后台把这些参数重填一遍。
    """

    __tablename__ = "sys_setting"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, default="")
    group = db.Column(db.String(30), default="wechat")
    label = db.Column(db.String(120), default="")
    is_secret = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    def to_dict(self, include_secret: bool = False) -> dict:
        from .settings_store import mask
        value = self.value or ""
        if self.is_secret and not include_secret:
            value = mask(value)
        return {
            "id": self.id,
            "key": self.key,
            "value": value,
            "group": self.group,
            "label": self.label,
            "is_secret": self.is_secret,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M") if self.updated_at else "",
        }


class Whitelist(db.Model):
    """微信登录白名单。

    个人订阅号拿不到 openid；小程序和第二阶段学校认证号可以。
    白名单保证"只有名单里的微信才能进系统"，避免任何人拿到链接就能注册成党员。
    可以先只填姓名 + 手机号，openid 留空：用户第一次用微信登录时自动补上，
    也可以由管理员手工填一个 openid 做联调。
    """

    __tablename__ = "login_whitelist"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    phone = db.Column(db.String(20), default="")
    openid = db.Column(db.String(64), unique=True, nullable=True, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=True)
    role = db.Column(db.String(20), default="member")
    note = db.Column(db.String(200), default="")
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)  # 绑定到的系统账号
    is_demo = db.Column(db.Boolean, default=False)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=now)

    branch = db.relationship("Branch")
    user = db.relationship("User")

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def status_label(self) -> str:
        return "启用" if self.is_active else "停用"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "openid": self.openid or "",
            "has_openid": bool(self.openid),
            "role": self.role,
            "role_label": self.role_label,
            "note": self.note,
            "is_active": bool(self.is_active),
            "status_label": self.status_label,
            "user_id": self.user_id,
            "user_name": (self.user.real_name or self.user.username) if self.user else "",
            "last_login_at": self.last_login_at.strftime("%Y-%m-%d %H:%M") if self.last_login_at else "",
            "is_demo": bool(self.is_demo),
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else "",
        }


class PartyDue(db.Model):
    """党费缴纳记录：一个人 + 一个期间（YYYY-MM）一条。"""

    __tablename__ = "party_due"
    __table_args__ = (db.UniqueConstraint("user_id", "period", name="uq_due_user_period"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    period = db.Column(db.String(7), nullable=False, index=True)  # YYYY-MM
    amount = db.Column(db.Numeric(10, 2), default=0)  # 金额（元）
    method = db.Column(db.String(20), default="现金")  # 现金 / 微信 / 银行代扣 / 其他
    status = db.Column(db.String(20), default="unpaid", index=True)  # paid / unpaid / late
    paid_at = db.Column(db.DateTime, nullable=True)
    note = db.Column(db.String(200), default="")
    operator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)  # 登记人
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User", foreign_keys=[user_id])
    operator = db.relationship("User", foreign_keys=[operator_id])

    @property
    def status_label(self) -> str:
        return DUE_STATUS_LABELS.get(self.status, self.status)

    @property
    def amount_float(self) -> float:
        return float(self.amount or 0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": (self.user.real_name or self.user.username) if self.user else "",
            "period": self.period,
            "amount": self.amount_float,
            "amount_text": f"{self.amount_float:.2f}",
            "method": self.method,
            "status": self.status,
            "status_label": self.status_label,
            "paid_at": self.paid_at.strftime("%Y-%m-%d") if self.paid_at else "",
            "note": self.note,
            "is_demo": bool(self.is_demo),
        }


class OrgTransfer(db.Model):
    """组织关系转接申请（转入 / 转出）。"""

    __tablename__ = "org_transfer"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    direction = db.Column(db.String(10), default="in")  # in=转入 / out=转出
    from_org = db.Column(db.String(120), default="")
    to_org = db.Column(db.String(120), default="")
    reason = db.Column(db.String(300), default="")
    status = db.Column(db.String(20), default="pending", index=True)  # pending / approved / rejected
    apply_at = db.Column(db.DateTime, default=now)
    review_at = db.Column(db.DateTime, nullable=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    review_note = db.Column(db.String(200), default="")
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User", foreign_keys=[user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])

    @property
    def direction_label(self) -> str:
        return TRANSFER_DIRECTION_LABELS.get(self.direction, self.direction)

    @property
    def status_label(self) -> str:
        return TRANSFER_STATUS_LABELS.get(self.status, self.status)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": (self.user.real_name or self.user.username) if self.user else "",
            "direction": self.direction,
            "direction_label": self.direction_label,
            "from_org": self.from_org,
            "to_org": self.to_org,
            "reason": self.reason,
            "status": self.status,
            "status_label": self.status_label,
            "apply_at": self.apply_at.strftime("%Y-%m-%d %H:%M") if self.apply_at else "",
            "review_at": self.review_at.strftime("%Y-%m-%d %H:%M") if self.review_at else "",
            "reviewer": (self.reviewer.real_name or self.reviewer.username) if self.reviewer else "",
            "review_note": self.review_note,
            "is_demo": bool(self.is_demo),
        }


def human_size(num: int) -> str:
    if not num:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"
