"""Render a contribution panel from the public GitHub calendar."""

from collections import defaultdict
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen


USER = "hao-527"
ROOT = Path(__file__).resolve().parents[1]
COLORS = ("#202e39", "#1a5b56", "#208f7d", "#4bd7ab", "#9bffe2")


class ContributionCalendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.counts = {}
        self.tooltip_id = None
        self.tooltip_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "ContributionCalendar-day" in attrs.get("class", "").split():
            self.cells[attrs["id"]] = (date.fromisoformat(attrs["data-date"]), int(attrs["data-level"]))
        if tag == "tool-tip" and attrs.get("for", "").startswith("contribution-day-component-"):
            self.tooltip_id = attrs["for"]
            self.tooltip_text = []

    def handle_data(self, data):
        if self.tooltip_id:
            self.tooltip_text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tooltip_id:
            match = re.match(r"(No|[\d,]+) contributions? on\b", "".join(self.tooltip_text).strip())
            if match:
                count = match[1]
                self.counts[self.tooltip_id] = 0 if count == "No" else int(count.replace(",", ""))
            self.tooltip_id = None


def fetch_days():
    request = Request(
        f"https://github.com/users/{USER}/contributions",
        headers={"Accept-Language": "en-US,en;q=0.9", "User-Agent": f"{USER}-profile-calendar"},
    )
    parser = ContributionCalendar()
    with urlopen(request, timeout=30) as response:
        parser.feed(response.read().decode("utf-8"))
    parser.close()
    if not 364 <= len(parser.cells) <= 371 or parser.cells.keys() - parser.counts.keys():
        raise ValueError("GitHub did not return a complete public contribution calendar")
    days = sorted((day, level, parser.counts[key]) for key, (day, level) in parser.cells.items())
    if any((right[0] - left[0]).days != 1 for left, right in zip(days, days[1:])):
        raise ValueError("The contribution calendar contains gaps or duplicate dates")
    if any(not 0 <= level < len(COLORS) or (level == 0) != (count == 0) for _, level, count in days):
        raise ValueError("The contribution calendar returned invalid activity levels")
    return days


def render(days):
    first, last = days[0][0], days[-1][0]
    sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    week_count = (last - sunday).days // 7 + 1
    week_width = 732 / week_count
    weeks = defaultdict(int)
    months = {}
    cells = []
    for day, level, count in days:
        week, weekday = divmod((day - sunday).days, 7)
        weeks[week] += count
        if day.day == 1 or day == first:
            months.setdefault(week, day)
        cells.append(
            f'<rect x="{74 + week * week_width:.2f}" y="{218 + weekday * 15}" '
            f'width="{week_width - 2:.2f}" height="12" rx="2" fill="{COLORS[level]}"/>'
        )

    max_week = max(weeks.values()) or 1
    columns = []
    for week, count in weeks.items():
        height = max(2, 56 * count / max_week)
        columns.append(
            f'<rect x="{74 + week * week_width:.2f}" y="{178 - height:.2f}" '
            f'width="{week_width - 2:.2f}" height="{height:.2f}" rx="2" '
            f'fill="{COLORS[3] if count else COLORS[0]}"/>'
        )

    month_labels = []
    next_label_x = 74
    for week, day in months.items():
        x = 74 + week * week_width
        if next_label_x <= x <= 781:
            month_labels.append(f'<text x="{x:.2f}" y="207">{day:%b}</text>')
            next_label_x = x + 35

    total = sum(weeks.values())
    active = sum(count > 0 for _, _, count in days)
    legend = "".join(
        f'<rect x="{709 + index * 15}" y="342" width="11" height="11" rx="2" fill="{color}"/>'
        for index, color in enumerate(COLORS)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 373" role="img" aria-labelledby="title desc">
  <title id="title">GitHub contribution radar</title>
  <desc id="desc">{total:,} publicly visible contributions across {active} active days, from {first} to {last}.</desc>
  <rect x="1" y="1" width="838" height="371" rx="18" fill="#0e171d" stroke="#32565a"/>
  <g font-family="ui-monospace, SFMono-Regular, Consolas, monospace">
    <circle cx="28" cy="28" r="4" fill="#79f9dc"/>
    <text x="41" y="33" fill="#79f9dc" font-size="14" letter-spacing="1">GITHUB ACTIVITY</text>
    <text x="806" y="33" fill="#b2c9cd" font-size="13" text-anchor="end">PUBLIC CONTRIBUTION CALENDAR</text>
    <path d="M24 48H816M24 331H816" stroke="#294243"/>
    <text x="27" y="88" fill="#e7fff9" font-weight="700" font-size="32">{total:,}</text>
    <text x="27" y="109" fill="#a8c2c8" font-size="13">CONTRIBUTIONS</text>
    <text x="293" y="88" fill="#e7fff9" font-weight="700" font-size="32">{active}</text>
    <text x="293" y="109" fill="#a8c2c8" font-size="13">ACTIVE DAYS</text>
    <text x="806" y="106" fill="#ffc77c" font-size="13" text-anchor="end">WEEKLY ACTIVITY</text>
    <path d="M74 122H806M74 150H806M74 178H806" stroke="#263d46" stroke-dasharray="3 4"/>
    {''.join(columns)}
    <g fill="#b2c9cd" font-size="12">
      {''.join(month_labels)}
      <text x="27" y="243">Mon</text><text x="27" y="273">Wed</text><text x="27" y="303">Fri</text>
    </g>
    {''.join(cells)}
    <text x="27" y="352" fill="#a8c2c8" font-size="13">{first}  /  {last}</text>
    <text x="665" y="352" fill="#a8c2c8" font-size="12">LESS</text>
    {legend}
    <text x="805" y="352" fill="#a8c2c8" font-size="12" text-anchor="end">MORE</text>
  </g>
</svg>
"""


if __name__ == "__main__":
    (ROOT / "assets" / "activity.svg").write_text(render(fetch_days()), encoding="utf-8")
