# Constraints 测试选项清单

> 说明：
> - 本文档面向后续批量提示词测试设计，按“测试覆盖”而不是“自然语言说法穷举”整理。
> - 连续数值字段不需要穷举全部范围，使用代表值覆盖即可。
> - 当前正式字段定义参考 `backend/src/closedloop/contracts/state.py`，工具入参参考 `backend/src/closedloop/graph/tools/plan_tool.py`。

## `group_type`

- 可选值：
  - `family`
  - `friends`


## `budget`

可选值：任何小数，但是本身的餐厅没有及其高端的方案




- 说明：
  - 该字段本质上是连续数值，不需要穷举。
  - 使用上述几个预算档位做批测通常已经足够。

## `dietary_restrictions`

- 当前重点支持值：
  - `辣`
  - `海鲜`
  - `生冷`
  - `甜`
  - `快餐`
  - `牛`
  - `垃圾食品`


## `preferred_distance`

- 可选值：
  - `<2km`
  - `2km-5km`
  - `>5km`

- 提示词判断口径：用户强调“就附近/走路/不想太远/两公里内”选 `<2km`；用户强调“别太远/打车一会儿/几公里内”选 `2km-5km`；用户强调“远一点/开车也行/不介意远”选 `>5km`；没提默认 `2km-5km`

## `time_period`

- 支持格式：
  - `HH:MM`
  - `HH:MM-HH:MM`

- 推荐测试值：开始时间覆盖 `11:00/14:00/16:00`；不预设早餐/宵夜；整体希望 22 点左右结束（可用 `11:00-22:00` 作为窗口样例）


## `duration_hours`

- 推荐测试值：不指定 + 固定 4 小时/6 小时 + 范围 4-6 小时（写法示例：`null` / `[4.0,4.0]` / `[6.0,6.0]` / `[4.0,6.0]`）




## `activity_preferences`

- 当前代码里较明确能识别的偏好簇：
  - `打卡`
  - `安静`
  - `亲子`
  - `室内`
  - `热闹`
  - `不排队`

- 推荐测试值：空集 + 单项（`打卡/安静/亲子/室内/热闹/不排队`）+ 组合（`安静+室内`）

## `adult_count`

- 可选值：
  整数

## `child_count`

- 可选值：
  整数

 性别是用来未来拓展根据性别比例来区分推荐哪些活动（但是未必来的即了可测可不测）
## `adult_genders`

- 可选值：
  - `M`
  - `F`
  - `U`

用于来进行

## `child_profiles`

- 单项格式：
  - `[性别, 年龄]`

- 性别可选值：
  - `M`
  - `F`
  - `U`

- 年龄特殊值：
  - `-1` 表示未知
  - `0` 表示孕妇

- 推荐测试值：无孩子 + 年龄未知（`[["F",-1]]`）+ 幼儿（`3/6`）+ 大童（`10`）+ 孕妇（`[["U",0]]`）

## `commute_preference`

- 可选值：
  - `auto`
  - `walking`
  - `taxi`
  - `driving`

- 推荐测试值：`auto / walking / taxi / driving` 各跑一遍

## `preferred_pattern_steps`

- 当前推荐使用的 step 值：
  - `activity`
  - `gift_shop`
  - `restaurant`
  - `restaurant:breakfast`
  - `restaurant:lunch`
  - `restaurant:afternoon_tea`
  - `restaurant:dinner`
  - `restaurant:late_night`

- 推荐测试值：不指定 + 两步（玩→晚餐 / 午餐→玩）+ 三步（玩→玩→晚餐 / 玩→礼物→晚餐）+ 只写 `restaurant`

## `include_gift`

- 可选值：
  - `true`
  - `false`


## 可直接复制的最小测试集

```json
{
  "group_type": ["family", "friends"],
  "budget": [100, 200, 300, 400],
  "dietary_restrictions": [
    [],
    ["辣"],
    ["海鲜"],
    ["生冷"],
    ["甜"],
    ["快餐"],
    ["牛"],
    ["垃圾食品"],
    ["辣", "海鲜"]
  ],
  "preferred_distance": ["<2km", "2km-5km", ">5km"],
  "time_period": ["11:00", "14:00", "16:00", "11:00-22:00"],
  "duration_hours": [null, [2.0, 2.0], [4.0, 6.0], [6.0, 8.0]],
  "activity_preferences": [[], ["打卡"], ["安静"], ["浪漫"], ["亲子"], ["室内"], ["热闹"], ["不排队"]],
  "adult_count": [1, 2, 3, 4],
  "child_count": [0, 1, 2],
  "adult_genders": [["F"], ["M"], ["F", "M"], ["F", "F"], ["U", "U"]],
  "child_profiles": [[], [["F", -1]], [["F", 3]], [["F", 6]], [["M", 10]], [["U", 0]]],
  "commute_preference": ["auto", "walking", "taxi", "driving"],
  "preferred_pattern_steps": [
    null,
    ["activity", "restaurant:dinner"],
    ["restaurant:lunch", "activity"],
    ["activity", "activity", "restaurant:dinner"],
    ["activity", "gift_shop", "restaurant:dinner"],
    ["restaurant"]
  ],
  "include_gift": [true, false]
}
```
