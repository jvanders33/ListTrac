"""
AFL Rising Star nominees — from Wikipedia's per-year articles.

Draftguru's pick pages don't record Rising Star nominations, so the per-pick
"% nominated" stat needs this second source. Each year since 1994 has a
"{year} AFL Rising Star" article with a Nominations table (Player | Round |
Club); we only need the names. Names are matched to draftees later via
identity.normalize_name, so spelling drift between Wikipedia and Draftguru
is handled the same way as every other cross-source join in this project.
"""
import re
import time
import urllib.request

HEADERS = {"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}
FIRST_YEAR = 1994  # award introduced


def fetch_nominees(year: int) -> list[str]:
    """Nominee names for one season. Empty list if the page/table is missing."""
    url = f"https://en.wikipedia.org/wiki/{year}_AFL_Rising_Star"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    except Exception:
        return []
    time.sleep(0.5)  # politeness delay

    i = html.find('id="Nominations"')
    if i == -1:
        i = html.find('id="Nominees"')
    if i == -1:
        return []
    # section runs until the next h2; page layouts vary by era — some put a
    # "Key" table first, some order columns Round|Player instead of Player|Round
    chunk = html[i:]
    nxt = chunk.find("<h2", 10)
    if nxt != -1:
        chunk = chunk[:nxt]

    names: list[str] = []
    for table in re.findall(r"<table[^>]*>(.*?)</table>", chunk, re.S):
        player_col = None
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
            cells = [re.sub(r"<[^>]+>", "", c).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
            if player_col is None:
                if "Player" in cells:
                    player_col = cells.index("Player")
                continue
            if len(cells) > player_col:
                name = re.sub(r"\[\d+\]", "", cells[player_col]).strip().strip("^").strip()
                if name and not name.isdigit() and len(name) < 50:
                    names.append(name)
    return list(dict.fromkeys(names))


def fetch_all(last_year: int) -> dict[int, list[str]]:
    """{season: [nominee names]} for every award year up to last_year."""
    out = {}
    for year in range(FIRST_YEAR, last_year + 1):
        out[year] = fetch_nominees(year)
        print(f"  rising star {year}: {len(out[year])} nominees")
    return out


if __name__ == "__main__":
    for y in (1994, 2010, 2024):
        names = fetch_nominees(y)
        print(y, len(names), names[:4])
