"""自然语言预订解析自检：打印几组口语描述的解析结果，便于调整规则。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.booking import parse_booking_text  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

SAMPLES = [
    "帮我订下周五入住两晚的杭州西湖智选假日酒店高级大床房，2个人，需要安静楼层",
    "下周三入住，住 3 晚，上海外滩云舍酒店江景双床房，2 位客人",
    "帮我预订明天入住 1 晚的成都宽窄巷子花园酒店家庭房，4 个人",
    "9 月 24 号入住、26 号退房，三亚亚龙湾海景度假酒店海景大床房，2 人",
    "帮我订两间杭州西湖智选假日酒店的高级双床房，下周六入住三晚，一共 4 个人",
]


def main() -> None:
    with SessionLocal() as db:
        for text in SAMPLES:
            parsed = parse_booking_text(db, text)
            print(text)
            print(
                f"  酒店={parsed['hotel_name'] or '未识别'}"
                f" | 房型={parsed['room_type_name'] or '未识别'}"
                f" | 入住={parsed['check_in_date'] or '未识别'}"
                f" | 退房={parsed['check_out_date'] or '未识别'}"
                f" | 晚数={parsed['nights']}"
                f" | 间数={parsed['rooms']}"
                f" | 人数={parsed['guests']}"
                f" | 特殊要求={parsed['special_request'] or '无'}"
            )


if __name__ == "__main__":
    main()
