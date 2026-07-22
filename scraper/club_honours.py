"""Club honour rolls — premierships and major individual medals per club.

Compiled from Wikipedia's award lists (see SOURCES) and emitted to
data/club_honours.json for the club-page header. This is reference data, not a
live scrape: the award histories change at most once a year, so the lists are
held here explicitly and validated on build (e.g. premiership years must sum to
the number of VFL/AFL seasons played).

Conventions:
- Brisbane (BRI) = Brisbane Bears + Brisbane Lions. Fitzroy is a separate,
  now-defunct entity and is NOT folded into Brisbane (matches how the AFL keeps
  the premiership tallies).
- Sydney (SYD) includes South Melbourne. Western Bulldogs (WB) includes
  Footscray. North Melbourne (NM) includes the Kangaroos era.
- Coleman Medal is the leading-goalkicker award since 1955 only; earlier
  leading goalkickers are not Coleman medallists and are excluded.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "club_honours.json"

SOURCES = {
    "premierships": "https://en.wikipedia.org/wiki/List_of_VFL/AFL_premiers",
    "brownlow": "https://en.wikipedia.org/wiki/List_of_Brownlow_Medal_winners",
    "coleman": "https://en.wikipedia.org/wiki/Coleman_Medal",
    "norm_smith": "https://en.wikipedia.org/wiki/Norm_Smith_Medal",
    "rising_star": "https://en.wikipedia.org/wiki/AFL_Rising_Star",
}

PREMIERSHIPS = {
    "CAR": [1906, 1907, 1908, 1914, 1915, 1938, 1945, 1947, 1968, 1970, 1972, 1979, 1981, 1982, 1987, 1995],
    "COL": [1902, 1903, 1910, 1917, 1919, 1927, 1928, 1929, 1930, 1935, 1936, 1953, 1958, 1990, 2010, 2023],
    "ESS": [1897, 1901, 1911, 1912, 1923, 1924, 1942, 1946, 1949, 1950, 1962, 1965, 1984, 1985, 1993, 2000],
    "HAW": [1961, 1971, 1976, 1978, 1983, 1986, 1988, 1989, 1991, 2008, 2013, 2014, 2015],
    "MEL": [1900, 1926, 1939, 1940, 1941, 1948, 1955, 1956, 1957, 1959, 1960, 1964, 2021],
    "RIC": [1920, 1921, 1932, 1934, 1943, 1967, 1969, 1973, 1974, 1980, 2017, 2019, 2020],
    "GEE": [1925, 1931, 1937, 1951, 1952, 1963, 2007, 2009, 2011, 2022],
    "BRI": [2001, 2002, 2003, 2024, 2025],
    "SYD": [1909, 1918, 1933, 2005, 2012],
    "NM": [1975, 1977, 1996, 1999],
    "WCE": [1992, 1994, 2006, 2018],
    "WB": [1954, 2016],
    "ADE": [1997, 1998],
    "STK": [1966],
    "PA": [2004],
    "FRE": [], "GCS": [], "GWS": [], "TAS": [],
}

BROWNLOW = {
    "ADE": [(2003, "Mark Ricciuto")],
    "BRI": [(1996, "Michael Voss"), (2001, "Jason Akermanis"), (2002, "Simon Black"), (2020, "Lachie Neale"), (2023, "Lachie Neale")],
    "CAR": [(1947, "Bert Deacon"), (1961, "John James"), (1964, "Gordon Collis"), (1994, "Greg Williams"), (2010, "Chris Judd"), (2022, "Patrick Cripps"), (2024, "Patrick Cripps")],
    "COL": [(1927, "Syd Coventry"), (1929, "Albert Collier"), (1930, "Harry Collier"), (1939, "Marcus Whelan"), (1940, "Des Fothergill"), (1972, "Len Thompson"), (1979, "Peter Moore"), (2003, "Nathan Buckley"), (2011, "Dane Swan")],
    "ESS": [(1934, "Dick Reynolds"), (1937, "Dick Reynolds"), (1938, "Dick Reynolds"), (1952, "Bill Hutchison"), (1953, "Bill Hutchison"), (1976, "Graham Moss"), (1993, "Gavin Wanganeen"), (1996, "James Hird")],
    "FRE": [(2015, "Nat Fyfe"), (2019, "Nat Fyfe")],
    "GEE": [(1924, "Edward Greeves"), (1951, "Bernie Smith"), (1962, "Alistair Lord"), (1989, "Paul Couch"), (2007, "Jimmy Bartel"), (2009, "Gary Ablett Jr"), (2016, "Patrick Dangerfield")],
    "GCS": [(2013, "Gary Ablett Jr"), (2025, "Matt Rowell")],
    "HAW": [(1949, "Col Austen"), (1986, "Robert DiPierdomenico"), (1987, "John Platten"), (1999, "Shane Crawford"), (2012, "Sam Mitchell"), (2018, "Tom Mitchell")],
    "MEL": [(1926, "Ivor Warne-Smith"), (1928, "Ivor Warne-Smith"), (1946, "Don Cordner"), (1982, "Brian Wilson"), (1984, "Peter Moore"), (1991, "Jim Stynes"), (2000, "Shane Woewodin")],
    "NM": [(1965, "Noel Teasdale"), (1973, "Keith Greig"), (1974, "Keith Greig"), (1978, "Malcolm Blight"), (1983, "Ross Glendinning")],
    "PA": [(2021, "Ollie Wines")],
    "RIC": [(1930, "Stan Judkins"), (1948, "Bill Morris"), (1952, "Roy Wright"), (1954, "Roy Wright"), (1971, "Ian Stewart"), (2012, "Trent Cotchin"), (2017, "Dustin Martin")],
    "STK": [(1925, "Colin Watson"), (1957, "Brian Gleeson"), (1958, "Neil Roberts"), (1959, "Verdun Howell"), (1965, "Ian Stewart"), (1966, "Ian Stewart"), (1967, "Ross Smith"), (1987, "Tony Lockett"), (1997, "Robert Harvey"), (1998, "Robert Harvey")],
    "SYD": [(1940, "Herbie Matthews"), (1949, "Ron Clegg"), (1955, "Fred Goldsmith"), (1959, "Bob Skilton"), (1963, "Bob Skilton"), (1968, "Bob Skilton"), (1970, "Peter Bedford"), (1977, "Graham Teasdale"), (1981, "Barry Round"), (1986, "Greg Williams"), (1988, "Gerard Healy"), (1995, "Paul Kelly"), (2003, "Adam Goodes"), (2006, "Adam Goodes")],
    "WCE": [(2004, "Chris Judd"), (2005, "Ben Cousins"), (2014, "Matt Priddis")],
    "WB": [(1930, "Allan Hopkins"), (1941, "Norman Ware"), (1956, "Peter Box"), (1960, "John Schultz"), (1975, "Gary Dempsey"), (1980, "Kelvin Templeton"), (1985, "Brad Hardie"), (1990, "Tony Liberatore"), (1992, "Scott Wynd"), (2008, "Adam Cooney")],
    "GWS": [], "TAS": [],
}

COLEMAN = {
    "GEE": [(1955, "Neil Rayson"), (1962, "Doug Wade"), (1967, "Doug Wade"), (1969, "Doug Wade"), (1976, "Larry Donohue"), (1993, "Gary Ablett Sr"), (1994, "Gary Ablett Sr"), (1995, "Gary Ablett Sr"), (2020, "Tom Hawkins"), (2025, "Jeremy Cameron")],
    "ESS": [(1959, "John Evans"), (1960, "John Evans"), (1966, "Ted Fordham"), (2000, "Matthew Lloyd"), (2001, "Matthew Lloyd"), (2003, "Matthew Lloyd")],
    "HAW": [(1963, "John Peck"), (1964, "John Peck"), (1965, "John Peck"), (1968, "Peter Hudson"), (1970, "Peter Hudson"), (1971, "Peter Hudson"), (1975, "Leigh Matthews"), (1977, "Peter Hudson"), (1988, "Jason Dunstall"), (1989, "Jason Dunstall"), (1992, "Jason Dunstall"), (2008, "Lance Franklin"), (2011, "Lance Franklin"), (2013, "Jarryd Roughead")],
    "STK": [(1956, "Bill Young"), (1987, "Tony Lockett"), (1991, "Tony Lockett"), (2004, "Fraser Gehrig"), (2005, "Fraser Gehrig")],
    "COL": [(1958, "Ian Brewer"), (1972, "Peter McKenna"), (1973, "Peter McKenna"), (1986, "Brian Taylor")],
    "MEL": [(1961, "Athol Webb"), (2002, "David Neitz")],
    "NM": [(1974, "Doug Wade"), (1982, "Malcolm Blight"), (1990, "John Longmire")],
    "RIC": [(1980, "Michael Roach"), (1981, "Michael Roach"), (2010, "Jack Riewoldt"), (2012, "Jack Riewoldt"), (2018, "Jack Riewoldt")],
    "WB": [(1957, "Jack Collins"), (1978, "Kelvin Templeton"), (1979, "Kelvin Templeton"), (1985, "Simon Beasley")],
    "WCE": [(1999, "Scott Cummings"), (2015, "Josh Kennedy"), (2016, "Josh Kennedy")],
    "SYD": [(1996, "Tony Lockett"), (1998, "Tony Lockett"), (2014, "Lance Franklin"), (2017, "Lance Franklin")],
    "CAR": [(2006, "Brendan Fevola"), (2009, "Brendan Fevola"), (2021, "Harry McKay"), (2022, "Charlie Curnow"), (2023, "Charlie Curnow")],
    "ADE": [(1997, "Tony Modra")],
    "BRI": [(2007, "Jonathan Brown")],
    "GWS": [(2019, "Jeremy Cameron"), (2024, "Jesse Hogan")],
    "MEL2": [],  # placeholder, ignored
    "GCS": [], "PA": [], "FRE": [], "TAS": [],
}
COLEMAN.pop("MEL2", None)

NORM_SMITH = {
    "ADE": [(1997, "Andrew McLeod"), (1998, "Andrew McLeod")],
    "BRI": [(2001, "Shaun Hart"), (2003, "Simon Black"), (2024, "Will Ashcroft"), (2025, "Will Ashcroft")],
    "CAR": [(1979, "Wayne Harmes"), (1981, "Bruce Doull"), (1987, "David Rhys-Jones"), (1995, "Greg Williams")],
    "COL": [(1990, "Tony Shaw"), (2002, "Nathan Buckley"), (2010, "Scott Pendlebury"), (2023, "Bobby Hill")],
    "ESS": [(1984, "Billy Duckworth"), (1985, "Simon Madden"), (1993, "Michael Long"), (2000, "James Hird")],
    "GEE": [(1989, "Gary Ablett Sr"), (2007, "Steve Johnson"), (2009, "Paul Chapman"), (2011, "Jimmy Bartel"), (2022, "Isaac Smith")],
    "HAW": [(1983, "Colin Robertson"), (1986, "Gary Ayres"), (1988, "Gary Ayres"), (1991, "Paul Dear"), (2008, "Luke Hodge"), (2013, "Brian Lake"), (2014, "Luke Hodge"), (2015, "Cyril Rioli")],
    "MEL": [(2021, "Christian Petracca")],
    "NM": [(1996, "Glenn Archer"), (1999, "Shannon Grant")],
    "PA": [(2004, "Byron Pickett")],
    "RIC": [(1980, "Kevin Bartlett"), (1982, "Maurice Rioli"), (2017, "Dustin Martin"), (2019, "Dustin Martin"), (2020, "Dustin Martin")],
    "STK": [(2010, "Lenny Hayes")],
    "SYD": [(2012, "Ryan O'Keefe")],
    "WCE": [(1992, "Peter Matera"), (1994, "Dean Kemp"), (2005, "Chris Judd"), (2006, "Andrew Embley"), (2018, "Luke Shuey")],
    "WB": [(2016, "Jason Johannisen")],
    "FRE": [], "GCS": [], "GWS": [], "TAS": [],
}

RISING_STAR = {
    "ADE": [(2012, "Daniel Talia")],
    "BRI": [(1993, "Nathan Buckley"), (1994, "Chris Scott"), (2009, "Daniel Rich"), (2014, "Lewis Taylor")],
    "CAR": [(2019, "Sam Walsh")],
    "COL": [(2018, "Jaidyn Stephenson"), (2022, "Nick Daicos")],
    "ESS": [(2011, "Dyson Heppell"), (2017, "Andrew McGrath")],
    "FRE": [(2000, "Paul Hasleby"), (2008, "Rhys Palmer"), (2020, "Caleb Serong"), (2025, "Murphy Reid")],
    "GEE": [(2007, "Joel Selwood"), (2024, "Oliver Dempsey")],
    "GCS": [(2013, "Jaeger O'Meara")],
    "HAW": [(1995, "Nick Holland"), (2003, "Sam Mitchell")],
    "MEL": [(2004, "Jared Rivers"), (2015, "Jesse Hogan"), (2021, "Luke Jackson")],
    "NM": [(1998, "Byron Pickett"), (2023, "Harry Sheezel")],
    "PA": [(1997, "Michael Wilson"), (2006, "Danyle Pearce")],
    "RIC": [(2005, "Brett Deledio")],
    "STK": [(2001, "Justin Koschitzke"), (2002, "Nick Riewoldt")],
    "SYD": [(1999, "Adam Goodes"), (2010, "Daniel Hannebery"), (2016, "Callum Mills")],
    "WCE": [(1996, "Ben Cousins")],
    "GWS": [], "TAS": [],
}

ABBREVS = list(PREMIERSHIPS)
AWARDS = {"brownlow": BROWNLOW, "coleman": COLEMAN, "norm_smith": NORM_SMITH, "rising_star": RISING_STAR}


def _entries(pairs):
    return [{"y": y, "p": p} for y, p in sorted(pairs, reverse=True)]


def build():
    clubs = {}
    for ab in ABBREVS:
        awards = {}
        for name, table in AWARDS.items():
            awards[name] = _entries(table.get(ab, []))
        clubs[ab] = {
            "premierships": sorted(PREMIERSHIPS[ab], reverse=True),
            "flags": len(PREMIERSHIPS[ab]),
            "awards": awards,
        }
    return {"attribution": "Compiled from Wikipedia award lists.",
            "sources": SOURCES, "clubs": clubs}


def validate(payload):
    # VFL/AFL has been played every year from 1897; premiership years across the
    # current clubs plus Fitzroy's 8 must equal the number of seasons to 2025.
    seasons = 2025 - 1897 + 1
    total = sum(c["flags"] for c in payload["clubs"].values()) + 8  # + Fitzroy
    assert total == seasons, f"premiership years {total} != {seasons} seasons"
    all_years = [y for c in payload["clubs"].values() for y in c["premierships"]]
    assert len(all_years) == len(set(all_years)), "duplicate premiership year across clubs"


def main():
    payload = build()
    validate(payload)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    tallies = {a: sum(len(c["awards"][a]) for c in payload["clubs"].values()) for a in AWARDS}
    print(f"wrote {OUT}")
    print("premierships:", sum(c["flags"] for c in payload["clubs"].values()), "(+8 Fitzroy = 129 seasons)")
    print("award winners:", tallies)


if __name__ == "__main__":
    main()
