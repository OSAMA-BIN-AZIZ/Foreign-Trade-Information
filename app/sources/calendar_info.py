from datetime import date

_WEEKDAY = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def format_gregorian(d: date) -> str:
    return f"{d.month}月{d.day}日 {_WEEKDAY[d.weekday()]}"


def format_lunar(d: date) -> str:
    # placeholder for extensibility
    return "农历三月初一"
