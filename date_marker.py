"""Candidate native indicator source; requires target-client compilation validation."""
from workbook_data import parse_date


def marker_formula(start, end):
    start, end = parse_date(start), parse_date(end)
    if start > end:
        raise ValueError('起始时间不得晚于终止时间')
    def condition(value):
        return f'(YEAR={value.year}) AND (MONTH={value.month}) AND (DAY={value.day})'
    return '\n'.join([
        '{同花顺主图日期标记验证稿；需在目标版本编译验证}',
        '{仅匹配确切交易日期；休市或停牌日期无标记，不自动平移}',
        f'ST:={condition(start)};',
        f'EN:={condition(end)};',
        'STICKLINE(ST,LOW,HIGH,3,0),COLORRED;',
        'STICKLINE(EN,LOW,HIGH,3,0),COLORGREEN;',
        f"DRAWTEXT(ST,LOW,'起始 {start.isoformat()}'),COLORRED;",
        f"DRAWTEXT(EN,HIGH,'结束 {end.isoformat()}'),COLORGREEN;",
        '',
    ])
