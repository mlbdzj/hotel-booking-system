"""初始化数据库表结构与演示数据。"""

import logging
from datetime import date, timedelta

from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import Booking, Hotel, Knowledge, RoomType, User

logger = logging.getLogger("hotel-agent")


HOTEL_SEEDS = [
    {
        "name": "杭州西湖智选假日酒店",
        "city": "杭州",
        "address": "西湖区文三路 88 号",
        "star": 5,
        "room_count": 180,
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "description": "步行 10 分钟可达西湖景区，含自助早餐与健身房，适合商务与亲子出行。",
    },
    {
        "name": "上海外滩云舍酒店",
        "city": "上海",
        "address": "黄浦区中山东一路 12 号",
        "star": 4,
        "room_count": 120,
        "check_in_time": "15:00",
        "check_out_time": "12:00",
        "description": "坐落外滩核心地段，客房可观浦江夜景，配备行政酒廊与会议厅。",
    },
    {
        "name": "成都宽窄巷子花园酒店",
        "city": "成都",
        "address": "青羊区长顺上街 66 号",
        "star": 4,
        "room_count": 96,
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "description": "紧邻宽窄巷子，庭院式设计，提供川式早餐与茶室。",
    },
    {
        "name": "三亚亚龙湾海景度假酒店",
        "city": "三亚",
        "address": "亚龙湾国家旅游度假区",
        "star": 5,
        "room_count": 260,
        "check_in_time": "15:00",
        "check_out_time": "12:00",
        "description": "私属沙滩与无边泳池，含亲子俱乐部与海景餐厅，适合度假长住。",
    },
]

# (酒店名, 房型名, 编号, 床型, 价格/晚, 可住人数, 房量, 状态, 描述)
ROOM_TYPE_SEEDS = [
    ("杭州西湖智选假日酒店", "高级大床房", "RT-HZ-001", "1.8m 大床", 458, 2, 40, "open", "含双早，可免费使用健身房。"),
    ("杭州西湖智选假日酒店", "高级双床房", "RT-HZ-002", "1.2m 双床", 498, 2, 35, "open", "适合双人同住，房间面积 32㎡。"),
    ("杭州西湖智选假日酒店", "湖景套房", "RT-HZ-003", "1.8m 大床", 988, 3, 12, "open", "独立客厅，可加床，含行政酒廊礼遇。"),
    ("上海外滩云舍酒店", "城市景观大床房", "RT-SH-001", "1.8m 大床", 688, 2, 30, "open", "高层城市景观，28㎡，含双早。"),
    ("上海外滩云舍酒店", "江景双床房", "RT-SH-002", "1.2m 双床", 788, 2, 24, "open", "可看浦江夜景，含双早。"),
    ("上海外滩云舍酒店", "外滩套房", "RT-SH-003", "1.8m 大床", 1688, 3, 8, "maintenance", "套房维护中，暂不接受预订。"),
    ("成都宽窄巷子花园酒店", "花园大床房", "RT-CD-001", "1.8m 大床", 398, 2, 28, "open", "庭院景观，含川式早餐。"),
    ("成都宽窄巷子花园酒店", "家庭房", "RT-CD-002", "1.5m 双床 + 加床", 568, 4, 16, "open", "适合一家四口，含四早。"),
    ("三亚亚龙湾海景度假酒店", "海景大床房", "RT-SY-001", "1.8m 大床", 1088, 2, 60, "open", "正面海景，含双早与沙滩服务。"),
    ("三亚亚龙湾海景度假酒店", "海景双床房", "RT-SY-002", "1.35m 双床", 1188, 2, 50, "open", "海景阳台，含双早。"),
    ("三亚亚龙湾海景度假酒店", "泳池别墅", "RT-SY-003", "2m 大床", 2888, 4, 10, "closed", "别墅已停售，等待翻新。"),
]

KNOWLEDGE_SEEDS = [
    {
        "category": "预订流程",
        "question": "怎么预订酒店房间？",
        "answer": "进入「酒店管理」页面选择门店，点击「立即预订」，在弹窗中选择入住日期、退房日期、房型与间数，填写入住人数和特殊要求后点击「提交订单」。提交后状态为「待确认」，酒店确认后预订生效。也可以直接告诉智能助手，例如「帮我订下周五入住两晚的杭州西湖智选假日酒店大床房，2 个人」。",
        "keywords": "预订,怎么订,订房,下单,订酒店",
    },
    {
        "category": "预订流程",
        "question": "在哪里查看我的订单？",
        "answer": "点击左侧「我的订单」，可以按状态筛选查看全部订单，包含酒店、房型、入住退房日期、晚数、间数、总价与确认意见；待确认或已确认的订单可以在这里直接取消。",
        "keywords": "我的订单,订单记录,查看订单,订单状态",
    },
    {
        "category": "预订流程",
        "question": "入住和退房时间是什么时候？",
        "answer": "入住时间通常为 14:00 之后，退房时间为次日 12:00 之前；部分门店（如上海外滩云舍酒店、三亚亚龙湾海景度假酒店）入住时间为 15:00。具体以订单卡片和酒店详情中的说明为准，如需提前入住或延迟退房可联系前台。",
        "keywords": "入住时间,退房时间,几点入住,几点退房",
    },
    {
        "category": "预订流程",
        "question": "订单提交后多久会被确认？",
        "answer": "系统没有自动确认，需要酒店工作人员在「订单确认」页面处理。通常在提交后当天完成确认，建议至少提前 1 天预订；临近入住的订单会优先处理。",
        "keywords": "多久确认,确认时间,什么时候确认",
    },
    {
        "category": "预订流程",
        "question": "怎么取消订单？",
        "answer": "在「我的订单」页面找到状态为「待确认」或「已确认」的订单，点击「取消订单」并确认即可；也可以让智能助手帮你取消。已拒绝、已取消、已完成的订单无法再操作。",
        "keywords": "取消订单,退订,取消预订,不去了",
    },
    {
        "category": "预订流程",
        "question": "订单被拒绝了怎么办？",
        "answer": "在「我的订单」页面的「确认意见」列可以看到拒绝原因（例如房量不足、特殊要求无法满足）。根据原因调整日期、房型或间数后重新下单即可；如有疑问可联系酒店前台。",
        "keywords": "拒绝,被拒,订单被拒,确认意见",
    },
    {
        "category": "房型与房量",
        "question": "房型的房量和剩余房量怎么看？",
        "answer": "每个房型都有固定房量（库存间数）。在酒店详情与预订弹窗中，可以看到所选日期内的剩余房量；系统按下单日期的区间统计占用间数，剩余房量不足时无法下单，避免超卖。",
        "keywords": "房量,剩余房,库存,还有房吗,满房",
    },
    {
        "category": "房型与房量",
        "question": "一间房可以住几个人？",
        "answer": "以房型的「可住人数」为准：常见大床房/双床房可住 2 人，家庭房可住 4 人，套房可住 3 人。入住人数不能超过「可住人数 × 间数」，人数较多时建议加订房间。",
        "keywords": "几个人,能住几人,加人,超员",
    },
    {
        "category": "房型与房量",
        "question": "房价是怎么计算的？",
        "answer": "总价 = 房型单价（每晚）× 入住晚数 × 间数。下单时系统会自动计算并在订单卡片上显示总价，例如 458 元/晚的高级大床房，住 2 晚 1 间，总价为 916 元。",
        "keywords": "价格,房价,多少钱,总价,计算",
    },
    {
        "category": "房型与房量",
        "question": "可以加床吗？",
        "answer": "部分房型支持加床（例如杭州西湖智选假日酒店的湖景套房），加床会占用可住人数上限，并可能产生额外费用。下单时请在「特殊要求」中注明「需要加床」，由酒店确认后生效。",
        "keywords": "加床,加人,婴儿床",
    },
    {
        "category": "支付与发票",
        "question": "需要先付押金吗？",
        "answer": "系统当前只做预订登记，不在线收款。到店后按酒店规定支付房费与押金，退房时押金原路退还；企业协议客户可走月结，具体联系前台。",
        "keywords": "押金,付款,支付,到店付",
    },
    {
        "category": "支付与发票",
        "question": "可以开发票吗？",
        "answer": "可以。退房时在前台提供开票信息（单位名称、税号）即可开具增值税普通发票或专用发票；需要提前开票的请在订单「特殊要求」中注明，由酒店协助处理。",
        "keywords": "发票,开票,报销,税号",
    },
    {
        "category": "入住须知",
        "question": "可以带宠物入住吗？",
        "answer": "除三亚亚龙湾海景度假酒店的部分房型外，多数门店暂不接待宠物。若需携带宠物，请先联系酒店前台确认房型与清洁费标准，并在订单特殊要求中注明。",
        "keywords": "宠物,带狗,带猫,宠物友好",
    },
    {
        "category": "入住须知",
        "question": "入住需要带什么证件？",
        "answer": "入住时需出示本人有效身份证件（身份证/护照），一人一证；未携带证件无法办理入住。如需增加同住人，请在订单特殊要求中提前说明。",
        "keywords": "证件,身份证,登记,入住材料",
    },
    {
        "category": "入住须知",
        "question": "可以提前入住或延迟退房吗？",
        "answer": "视当日房态而定。提前入住可能需要加收费用，延迟退房超过 18:00 通常按全天房费计算。请在订单特殊要求中注明，或提前联系酒店前台确认。",
        "keywords": "提前入住,延迟退房,加时,晚点退房",
    },
    {
        "category": "账号问题",
        "question": "怎么修改个人信息或登录密码？",
        "answer": "点击右上角头像，选择「个人信息」可以修改姓名、手机号和邮箱；选择「修改密码」可以修改登录密码，需要先输入原密码，修改成功后系统会自动退出登录。",
        "keywords": "修改密码,个人信息,改资料,账号设置",
    },
    {
        "category": "账号问题",
        "question": "忘记密码了怎么办？",
        "answer": "系统暂不支持自助找回密码，请联系酒店管理员，在「会员管理」页面为你重置密码。",
        "keywords": "忘记密码,找回密码,重置密码,密码错误",
    },
    {
        "category": "管理员指南",
        "question": "酒店管理员如何确认订单？",
        "answer": "管理员登录后进入「订单确认」页面，可按状态、酒店、入住日期和会员筛选订单。对待确认的订单点击「确认」或「拒绝」，可填写确认意见；确认时系统会再次校验该房型的剩余房量，避免超卖。",
        "keywords": "确认订单,订单确认,管理员确认,拒绝订单",
    },
    {
        "category": "管理员指南",
        "question": "管理员可以维护哪些基础数据？",
        "answer": "管理员可以维护三类数据：1）「酒店管理」新增、编辑、删除门店（城市、地址、星级、客房数、入住退房时间、营业状态）；2）「房型管理」维护房型（床型、价格、可住人数、房量、状态）；3）「会员管理」新增会员、修改角色与状态、重置密码。删除酒店前需先删除其房型，存在订单的酒店或房型不能删除。",
        "keywords": "管理员,维护,新增酒店,新增房型,会员管理",
    },
    {
        "category": "系统说明",
        "question": "首页看板统计了什么？",
        "answer": "首页展示门店数、房型数、会员数（仅管理员）、待确认订单、今日入住订单、今日入住率，以及按本周入住订单数排名的门店排行和最近订单。普通用户看到的订单统计仅包含自己的订单。",
        "keywords": "看板,统计,入住率,首页数据,多少条",
    },
]


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_schema_updates() -> None:
    """为已存在的旧表补充后续新增的字段（幂等，可重复执行）。"""
    additions = [
        ("chat_message", "action", "ALTER TABLE chat_message ADD COLUMN action TEXT NULL"),
    ]
    with engine.begin() as connection:
        for table, column, statement in additions:
            exists = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = :table AND column_name = :column"
                ),
                {"table": table, "column": column},
            ).scalar()
            if not exists:
                connection.execute(text(statement))
                logger.info("已为表 %s 补充字段 %s", table, column)


def seed_data() -> None:
    with SessionLocal() as db:
        if not db.scalar(select(func.count(User.id))):
            db.add_all(
                [
                    User(
                        username=settings.DEFAULT_ADMIN_USERNAME,
                        password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                        name="酒店管理员",
                        phone="13800000000",
                        email="admin@hotel.local",
                        role="admin",
                        status=1,
                    ),
                    User(
                        username=settings.DEFAULT_USER_USERNAME,
                        password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
                        name="张先生",
                        phone="13900000001",
                        email="guest@hotel.local",
                        role="user",
                        status=1,
                    ),
                ]
            )
            db.commit()
            logger.info("已初始化默认账号：%s / %s", settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_USER_USERNAME)

        if not db.scalar(select(func.count(Hotel.id))):
            db.add_all([Hotel(**seed) for seed in HOTEL_SEEDS])
            db.commit()
            logger.info("已初始化 %s 家酒店", len(HOTEL_SEEDS))

        if not db.scalar(select(func.count(RoomType.id))):
            hotel_map = {hotel.name: hotel.id for hotel in db.scalars(select(Hotel)).all()}
            db.add_all(
                [
                    RoomType(
                        hotel_id=hotel_map[hotel_name],
                        name=name,
                        code=code,
                        bed_type=bed_type,
                        price=price,
                        capacity=capacity,
                        quantity=quantity,
                        status=room_status,
                        description=description,
                    )
                    for hotel_name, name, code, bed_type, price, capacity, quantity, room_status, description in ROOM_TYPE_SEEDS
                ]
            )
            db.commit()
            logger.info("已初始化 %s 个房型", len(ROOM_TYPE_SEEDS))

        if not db.scalar(select(func.count(Booking.id))):
            hotel_map = {hotel.name: hotel.id for hotel in db.scalars(select(Hotel)).all()}
            room_map = {room.name: room for room in db.scalars(select(RoomType)).all()}
            guest = db.scalar(select(User).where(User.role == "user"))
            admin = db.scalar(select(User).where(User.role == "admin"))
            today = date.today()

            def make_booking(hotel_name, room_name, check_in, nights, rooms, guests, status, remark="", special=""):
                room = room_map[room_name]
                return Booking(
                    hotel_id=hotel_map[hotel_name],
                    room_type_id=room.id,
                    user_id=guest.id,
                    check_in_date=check_in,
                    check_out_date=check_in + timedelta(days=nights),
                    nights=nights,
                    rooms=rooms,
                    guests=guests,
                    total_amount=float(room.price) * nights * rooms,
                    special_request=special,
                    status=status,
                    remark=remark,
                    reviewer_id=admin.id if status in {"confirmed", "rejected"} else None,
                )

            db.add_all(
                [
                    make_booking("杭州西湖智选假日酒店", "高级大床房", today + timedelta(days=1), 2, 1, 2, "pending", special="希望安排安静楼层"),
                    make_booking("上海外滩云舍酒店", "江景双床房", today + timedelta(days=3), 1, 1, 2, "confirmed", remark="已为您保留江景房，祝入住愉快"),
                    make_booking("成都宽窄巷子花园酒店", "花园大床房", today - timedelta(days=5), 2, 1, 2, "completed", remark="已完成入住"),
                    make_booking("三亚亚龙湾海景度假酒店", "海景双床房", today + timedelta(days=10), 3, 2, 4, "rejected", remark="该日期房源紧张，建议改期", special="需要两间相邻房间"),
                ]
            )
            db.commit()
            logger.info("已初始化演示订单数据")

        if not db.scalar(select(func.count(Knowledge.id))):
            db.add_all([Knowledge(**seed) for seed in KNOWLEDGE_SEEDS])
            db.commit()
            logger.info("已初始化 %s 条客服知识库数据", len(KNOWLEDGE_SEEDS))


def init_database() -> None:
    create_tables()
    ensure_schema_updates()
    seed_data()
