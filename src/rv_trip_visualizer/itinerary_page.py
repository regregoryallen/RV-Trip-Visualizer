"""Renders a merged stay list into a standalone, year-grouped HTML page.

assets/itinerary_page_shell.html is the editable page template (styling) -
this module only swaps in the data and title.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL_PATH = os.path.join(HERE, "assets", "itinerary_page_shell.html")


def _fmt_date(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def render(stays: list[dict], out_path: str, title: str) -> None:
    by_year = defaultdict(list)
    for s in stays:
        by_year[s["arrival"].year].append(s)

    total_nights = sum(s["nights"] for s in stays)
    total_miles = sum(s["miles"] for s in stays)
    all_states = {s["state"] for s in stays}
    longest = max(stays, key=lambda s: s["nights"])

    year_blocks = []
    for year in sorted(by_year):
        year_stays = by_year[year]
        y_nights = sum(s["nights"] for s in year_stays)
        y_miles = sum(s["miles"] for s in year_stays)
        y_states = sorted({s["state"] for s in year_stays})
        rows = "".join(f'''<tr>
          <td class="dates">{_fmt_date(s["arrival"])}<span class="arrow">→</span>{_fmt_date(s["departure"])}</td>
          <td class="num">{s["nights"]}</td>
          <td class="city">{html.escape(s["city"])}</td>
          <td class="state">{html.escape(s["state"])}</td>
          <td class="num">{round(s["miles"]):,}</td>
        </tr>''' for s in year_stays)
        year_blocks.append(f'''
    <details class="year-block" open>
      <summary>
        <span class="year-num">{year}</span>
        <span class="year-stats">{y_nights} nights · {len(year_stays)} stops · {len(y_states)} states · {round(y_miles):,} miles</span>
      </summary>
      <div class="tablewrap">
        <table>
          <thead><tr><th>Dates</th><th class="num">Nights</th><th>City</th><th>State</th><th class="num">Miles</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </details>''')

    stat_cards = f'''
    <div class="stat"><div class="n">{len(stays)}</div><div class="l">Stops logged</div></div>
    <div class="stat"><div class="n">{total_nights:,}</div><div class="l">Nights accounted for</div></div>
    <div class="stat"><div class="n">{round(total_miles):,}</div><div class="l">Miles traveled</div></div>
    <div class="stat"><div class="n">{len(all_states)}</div><div class="l">States / regions</div></div>
    <div class="stat"><div class="n">{longest["nights"]}</div><div class="l">Longest stay ({html.escape(longest["city"])}, {html.escape(longest["state"])})</div></div>
    '''

    shell = open(SHELL_PATH).read()
    out = (
        shell
        .replace("<!--TITLE-->", html.escape(title))
        .replace("<!--STATS-->", stat_cards.strip())
        .replace("<!--YEARS-->", "\n".join(year_blocks))
    )
    with open(out_path, "w") as f:
        f.write(out)
