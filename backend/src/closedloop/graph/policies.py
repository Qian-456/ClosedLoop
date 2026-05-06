import re
from typing import TypedDict, Optional

class Pattern(TypedDict):
    id: str
    group: str
    duration_range: tuple[float, float]
    steps: list[str]
    desc: str
    start_time_pref: list[str]

PATTERNS: list[Pattern] = [
    {
        "id": "FAM-S-01",
        "group": "family_kids",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "先玩后歇脚 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-S-02-A",
        "group": "family_kids",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "activity",
            "activity",
            "gift_shop"
        ],
        "desc": "畅玩 + 小惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-S-02-D",
        "group": "family_kids",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "activity",
            "activity",
            "gift_shop"
        ],
        "desc": "畅玩 + 小惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FAM-S-03-L",
        "group": "family_kids",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "gift_shop"
        ],
        "desc": "午餐 + 轻玩 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FAM-S-03-D",
        "group": "family_kids",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "晚餐 + 轻玩 + 惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FAM-S-04",
        "group": "family_kids",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "activity",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "轻玩 + 晚餐 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-M-01",
        "group": "family_kids",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "gift_shop"
        ],
        "desc": "标准下午亲子 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-M-02",
        "group": "family_kids",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "玩 + 歇脚 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-M-03",
        "group": "family_kids",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "gift_shop",
            "restaurant:dinner"
        ],
        "desc": "玩 + 惊喜 + 晚餐",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-M-04-L",
        "group": "family_kids",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "gift_shop"
        ],
        "desc": "午餐 + 玩 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FAM-M-04-D",
        "group": "family_kids",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "晚餐 + 玩 + 惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FAM-M-05-L",
        "group": "family_kids",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:lunch",
            "activity",
            "gift_shop"
        ],
        "desc": "玩 + 午餐 + 轻玩 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FAM-M-05-A",
        "group": "family_kids",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "玩 + 晚餐 + 轻玩 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-M-06",
        "group": "family_kids",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "玩 + 歇脚 + 晚餐 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-L-01",
        "group": "family_kids",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "gift_shop"
        ],
        "desc": "完整亲子下午",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-L-02",
        "group": "family_kids",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "玩歇玩晚餐 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-L-03",
        "group": "family_kids",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop",
            "restaurant:dinner"
        ],
        "desc": "玩歇惊喜晚餐",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-L-04-L",
        "group": "family_kids",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:lunch",
            "activity",
            "gift_shop"
        ],
        "desc": "玩午餐轻玩惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FAM-L-04-A",
        "group": "family_kids",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "玩晚餐轻玩惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-L-05-L",
        "group": "family_kids",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "午餐玩歇惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FAM-L-05-D",
        "group": "family_kids",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "晚餐玩歇惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FAM-L-06",
        "group": "family_kids",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop",
            "activity"
        ],
        "desc": "增强型",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FAM-XL-01",
        "group": "family_kids",
        "duration_range": [
            6.0,
            24.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "完整闭环",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FAM-XL-02",
        "group": "family_kids",
        "duration_range": [
            6.0,
            24.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "午餐玩歇玩午餐(含晚餐) + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FAM-XL-03",
        "group": "family_kids",
        "duration_range": [
            6.0,
            24.0
        ],
        "steps": [
            "activity",
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "玩午餐玩歇惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "TEEN-S-01",
        "group": "family_teens",
        "duration_range": [
            2.5,
            4.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "gift_shop"
        ],
        "desc": "玩歇玩 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "TEEN-S-02-L",
        "group": "family_teens",
        "duration_range": [
            2.5,
            4.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "gift_shop"
        ],
        "desc": "午餐玩 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "TEEN-S-02-D",
        "group": "family_teens",
        "duration_range": [
            2.5,
            4.0
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "晚餐玩 + 惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "TEEN-S-03",
        "group": "family_teens",
        "duration_range": [
            2.5,
            4.0
        ],
        "steps": [
            "activity",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "玩晚餐 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "TEEN-M-01",
        "group": "family_teens",
        "duration_range": [
            4.0,
            6.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "gift_shop"
        ],
        "desc": "午餐玩歇玩 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "TEEN-M-02-L",
        "group": "family_teens",
        "duration_range": [
            4.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:lunch",
            "activity",
            "gift_shop"
        ],
        "desc": "玩午餐玩 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "TEEN-M-02-A",
        "group": "family_teens",
        "duration_range": [
            4.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "玩晚餐玩 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "TEEN-M-03",
        "group": "family_teens",
        "duration_range": [
            4.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "gift_shop"
        ],
        "desc": "玩歇玩礼物",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "TEEN-M-04",
        "group": "family_teens",
        "duration_range": [
            4.0,
            6.0
        ],
        "steps": [
            "activity",
            "gift_shop",
            "restaurant:dinner",
            "activity"
        ],
        "desc": "玩礼物晚餐玩",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "TEEN-M-05",
        "group": "family_teens",
        "duration_range": [
            4.0,
            6.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop",
            "activity"
        ],
        "desc": "完整社交型家庭",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-S-01-L",
        "group": "friends",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "gift_shop"
        ],
        "desc": "午餐为主 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-S-01-D",
        "group": "friends",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "晚餐为主 + 惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FRD-S-02",
        "group": "friends",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "玩乐为主 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-S-03",
        "group": "friends",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "restaurant:afternoon_tea",
            "activity",
            "gift_shop"
        ],
        "desc": "下午茶社交 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-S-04-A",
        "group": "friends",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "restaurant:afternoon_tea",
            "gift_shop",
            "activity"
        ],
        "desc": "惊喜小聚",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-S-04-D",
        "group": "friends",
        "duration_range": [
            2.5,
            3.5
        ],
        "steps": [
            "restaurant:afternoon_tea",
            "gift_shop",
            "activity"
        ],
        "desc": "惊喜小聚",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FRD-M-01-A",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "先玩后晚餐 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-M-01-D",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "先玩后晚餐 + 惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FRD-M-02-L",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "gift_shop"
        ],
        "desc": "先午餐后玩 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-M-02-D",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "先晚餐后玩 + 惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FRD-M-03",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "gift_shop"
        ],
        "desc": "玩 + 歇 + 玩 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-M-04-L",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:lunch",
            "activity",
            "gift_shop"
        ],
        "desc": "玩 + 午餐 + 续摊 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-M-04-A",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "玩 + 晚餐 + 续摊 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-M-05-L",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "午餐 + 玩 + 甜品 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-M-05-D",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "晚餐 + 玩 + 甜品 + 惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FRD-M-06",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "activity",
            "gift_shop",
            "restaurant:dinner"
        ],
        "desc": "玩 + 惊喜 + 晚餐",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-M-07-L",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "restaurant:lunch",
            "gift_shop",
            "activity"
        ],
        "desc": "午餐 + 惊喜 + 玩",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-M-07-D",
        "group": "friends",
        "duration_range": [
            3.5,
            5.0
        ],
        "steps": [
            "restaurant:dinner",
            "gift_shop",
            "activity"
        ],
        "desc": "晚餐 + 惊喜 + 玩",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FRD-L-01",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "玩歇玩晚餐 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-L-02-L",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "gift_shop"
        ],
        "desc": "午餐玩歇玩 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-L-02-D",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "gift_shop"
        ],
        "desc": "晚餐玩歇玩 + 惊喜",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FRD-L-03-L",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "玩午餐玩歇 + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-L-03-A",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:dinner",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop"
        ],
        "desc": "玩晚餐玩歇 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-L-04",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "gift_shop",
            "restaurant:dinner",
            "activity"
        ],
        "desc": "玩惊喜晚餐玩",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-L-05-L",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "gift_shop",
            "restaurant:afternoon_tea"
        ],
        "desc": "午餐玩惊喜歇",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-L-05-D",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "gift_shop",
            "restaurant:afternoon_tea"
        ],
        "desc": "晚餐玩惊喜歇",
        "start_time_pref": [
            "dinner"
        ]
    },
    {
        "id": "FRD-L-06",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop",
            "restaurant:dinner"
        ],
        "desc": "玩歇惊喜晚餐",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-L-07",
        "group": "friends",
        "duration_range": [
            5.0,
            6.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "gift_shop",
            "activity"
        ],
        "desc": "增强型",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-XL-01",
        "group": "friends",
        "duration_range": [
            6.0,
            24.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "restaurant:dinner",
            "gift_shop"
        ],
        "desc": "午餐玩歇玩午餐(含晚餐) + 惊喜",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-XL-02",
        "group": "friends",
        "duration_range": [
            6.0,
            24.0
        ],
        "steps": [
            "activity",
            "restaurant:afternoon_tea",
            "activity",
            "restaurant:dinner",
            "activity",
            "gift_shop"
        ],
        "desc": "玩歇玩晚餐续摊 + 惊喜",
        "start_time_pref": [
            "afternoon_tea"
        ]
    },
    {
        "id": "FRD-XL-03",
        "group": "friends",
        "duration_range": [
            6.0,
            24.0
        ],
        "steps": [
            "activity",
            "restaurant:lunch",
            "activity",
            "gift_shop",
            "restaurant:afternoon_tea"
        ],
        "desc": "玩午餐玩惊喜歇",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-XL-04-L",
        "group": "friends",
        "duration_range": [
            6.0,
            24.0
        ],
        "steps": [
            "restaurant:lunch",
            "activity",
            "gift_shop",
            "restaurant:afternoon_tea",
            "activity"
        ],
        "desc": "午餐玩惊喜甜品玩",
        "start_time_pref": [
            "lunch"
        ]
    },
    {
        "id": "FRD-XL-04-D",
        "group": "friends",
        "duration_range": [
            6.0,
            24.0
        ],
        "steps": [
            "restaurant:dinner",
            "activity",
            "gift_shop",
            "restaurant:afternoon_tea",
            "activity"
        ],
        "desc": "晚餐玩惊喜甜品玩",
        "start_time_pref": [
            "dinner"
        ]
    }
]

def parse_time_period(time_period: str) -> tuple[float, float]:
    """
    解析时间段字符串，返回 (start_time_hours, duration_hours)。
    根据 Constraints 结构，time_period 必然是 'HH:MM-HH:MM' 的精确格式。
    例如 "13:00-18:00" 返回 (13.0, 5.0)。
    """
    match = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", time_period)
    if match:
        start_h = int(match.group(1)) + int(match.group(2)) / 60.0
        end_h = int(match.group(3)) + int(match.group(4)) / 60.0
        
        # 跨天处理
        if end_h < start_h:
            end_h += 24.0
            
        return start_h, end_h - start_h

    # 理论上不会走到这里，作为容错返回默认值
    return 14.0, 6.0

def get_time_of_day(start_time_hours: float) -> str:
    """根据开始时间归类时段：breakfast, lunch, afternoon_tea, dinner, late_night"""
    if start_time_hours < 10.5:
        return "breakfast"
    elif start_time_hours < 14.0:
        return "lunch"
    elif start_time_hours < 17.0:
        return "afternoon_tea"
    elif start_time_hours < 21.0:
        return "dinner"
    else:
        return "late_night"

def match_patterns(
    group_type: str, 
    child_ages: list[int], 
    start_time_hours: float, 
    duration_hours: float
) -> list[Pattern]:
    """
    根据人群分类、开始时间和持续时间，匹配所有合适的 Pattern 列表。
    """
    # 1. 确定 group_category
    group_category = "friends"
    if group_type == "family":
        if child_ages and max(child_ages) >= 10:
            group_category = "family_teens"
        else:
            group_category = "family_kids"
            
    # 2. 确定 time_of_day
    time_of_day = get_time_of_day(start_time_hours)
    
    # 3. 筛选候选
    candidates = []
    for p in PATTERNS:
        if p["group"] != group_category:
            continue
        
        min_d, max_d = p["duration_range"]
        # 容差范围
        if min_d - 0.5 <= duration_hours <= max_d + 0.5:
            candidates.append(p)
            
    # 如果没有找到匹配时长的，放宽时长限制
    if not candidates:
        for p in PATTERNS:
            if p["group"] == group_category:
                candidates.append(p)
                
    if not candidates:
        # Fallback to a safe default
        return [PATTERNS[0]]
        
    # 4. 优先匹配 time_of_day
    preferred = [p for p in candidates if time_of_day in p["start_time_pref"]]
    
    # 返回所有满足条件的候选，如果有 preferred 则优先使用 preferred 集合，否则使用所有 candidates
    # 按时长差值升序排列
    if preferred:
        preferred.sort(key=lambda p: abs((p["duration_range"][0] + p["duration_range"][1])/2 - duration_hours))
        return preferred
    else:
        candidates.sort(key=lambda p: abs((p["duration_range"][0] + p["duration_range"][1])/2 - duration_hours))
        return candidates
