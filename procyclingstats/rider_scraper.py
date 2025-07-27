import calendar
from typing import Any, Dict, List, Optional
import re
from selectolax.parser import HTMLParser

from .scraper import Scraper
from .table_parser import TableParser
from .utils import get_day_month, parse_table_fields_args


class Rider(Scraper):
    """
    Scraper for rider HTML page.
    
    To parse results from specific season, pass URL with the season, e.g.
    ``rider/tadej-pogacar/2021``, and use the ``Rider.results`` method. But it
    might be easier to just use the ``RiderResults`` scraping class for that
    purpose.

    Usage:

    >>> from procyclingstats import Rider
    >>> rider = Rider("rider/tadej-pogacar")
    >>> rider.birthdate()
    '1998-9-21'
    >>> rider.parse()
    {
        'birthdate': '1998-9-21',
        'height': 1.76,
        'name': 'Tadej  Pogačar',
        'nationality': 'SI',
        ...
    }
    """
    def birthdate(self) -> str:
        """
        Parses rider's birthdate from HTML.

        :return: birthday of the rider in ``YYYY-MM-DD`` format.
        """
        bd_node = self._get_rider_content_node().css_first("div > ul > li")
        day_str = bd_node.css(".mr3")[0].text()
        day = "".join(c for c in day_str if c.isdigit())
        month_str = bd_node.css(".mr3")[1].text()
        month = list(calendar.month_name).index(month_str)
        year = int(bd_node.css(".mr3")[2].text())
        return f"{year}-{month}-{day}"

    def place_of_birth(self) -> Optional[str]:
        """
        Parses rider's place of birth from HTML

        :return: rider's place of birth (town only).
        """
        possibilities = self._get_rider_content_node().css("div > a")
        if len(possibilities) <= 1:
            return None
        return possibilities[1].text()

    def name(self) -> str:
        """
        Parses rider's name from HTML.

        :return: Rider's name.
        """
        raw_name = self.html.css_first(".titleCont > .page-title > .title > h1").text()
        return re.sub(r'\s+', ' ', raw_name).strip()

    def weight(self) -> Optional[float]:
        """
        Parses rider's weight from HTML.

        :return: Rider's weight in kilograms.
        """
        extra = 0
        if "Passed" in self._get_rider_content_node().text():
            extra = 1
        weight_cont = self._get_rider_content_node().css("div > ul.list")[2 + extra]
        weight_html = weight_cont.css("li .mr3")[0]
        return float(weight_html.text())

    def height(self) -> Optional[float]:
        """
        Parses rider's height from HTML.

        :return: Rider's height in meters.
        """
        extra = 0
        if "Passed" in self._get_rider_content_node().text():
            extra = 1
        height_cont = self._get_rider_content_node().css("div > ul.list")[2 + extra]
        height_html = height_cont.css("li > .mr3")[1]
        return float(height_html.text())

    def nationality(self) -> str:
        """
        Parses rider's nationality from HTML.

        :return: Rider's current nationality as 2 chars long country code in
            uppercase.
        """
        # normal layout
        nationality_html = self._get_rider_content_node().css_first(".flag")
        if nationality_html is None:
        # special layout
            nationality_html = self._get_rider_content_node().css_first("span > span")
        flag_class = nationality_html.attributes['class']
        return flag_class.split(" ")[-1].upper() # type:ignore

    def image_url(self) -> Optional[str]:
        """
        Parses URL of rider's PCS image.

        :return: Relative URL of rider's image. None if image is not available.
        """
        image_html = self.html.css_first("div > a > img")
        if not image_html:
            return None
        return image_html.attributes['src']

    def teams_history(self, *args: str) -> List[Dict[str, Any]]:
        """
        Parses rider's team history throughout career.

        :param args: Fields that should be contained in returned table. When
            no args are passed, all fields are parsed.

            - team_name:
            - team_url:
            - season:
            - class: Team's class, e.g. ``WT``.
            - since: First day for rider in current season in the team in
              ``MM-DD`` format, most of the time ``01-01``.
            - until: Last day for rider in current season in the team in
              ``MM-DD`` format, most of the time ``12-31``.

        :raises ValueError: When one of args is of invalid value.
        :return: Table with wanted fields.
        """
        available_fields = (
            "season",
            "since",
            "until",
            "team_name",
            "team_url",
            "class"
        )
        fields = parse_table_fields_args(args, available_fields)
        seasons_html_table = self.html.css_first("ul.rdr-teams2")
        # Filter out invalid items that do not have a season div ('Suspended...')
        valid_items = [li for li in seasons_html_table.css("li.main") if li.css_first("div.season")]
        filtered_ul_html = "<ul class='rdr-teams2'>{}</ul>".format("".join(li.html for li in valid_items))
        # Parse a new HTML string with the filtered items
        filtered_ul_node = HTMLParser(filtered_ul_html).css_first("ul.rdr-teams2")
        table_parser = TableParser(filtered_ul_node)
        casual_fields = [f for f in fields
                         if f in ("season", "team_name", "team_url")]
        if casual_fields:
            table_parser.parse(casual_fields)
        # add classes for row validity checking
        classes = table_parser.parse_extra_column(
            1,
            lambda x: re.search(r"\(([^0-9][A-Z]+)\)", x).group(1) if x and re.search(r"\(([^0-9][A-Z]+)\)", x) else None
        )
        table_parser.extend_table("class", classes)
        if "since" in fields:
            until_dates = table_parser.parse_extra_column(-2,
                lambda x: get_day_month(x) if "as from" in x else "01-01")
            table_parser.extend_table("since", until_dates)
        if "until" in fields:
            until_dates = table_parser.parse_extra_column(-2,
                lambda x: get_day_month(x) if "until" in x else "12-31")
            table_parser.extend_table("until", until_dates)
        table = [row for row in table_parser.table if row['class']]
        # remove class field if isn't needed
        if "class" not in fields:
            for row in table:
                row.pop("class")
        return table

    def points_per_season_history(self, *args: str) -> List[Dict[str, Any]]:
        """
        Parses rider's points per season history.

        :param args: Fields that should be contained in returned table. When
            no args are passed, all fields are parsed.

            - season:
            - points: PCS points gained throughout the season.
            - rank: PCS ranking position after the season.

        :raises ValueError: When one of args is of invalid value.
        :return: Table with wanted fields.
        """
        available_fields = (
            "season",
            "points",
            "rank"
        )
        fields = parse_table_fields_args(args, available_fields)
        points_table_html = self.html.css_first("div.mt20 > table")
        table_parser = TableParser(points_table_html)
        table_parser.parse(fields)
        return table_parser.table

    def points_per_speciality(self) -> Dict[str, int]:
        """
        Parses rider's points per specialty from HTML.

        :return: Dict mapping rider's specialties and points gained.
            Dict keys: one_day_races, gc, time_trial, sprint, climber, hills
        """
        specialty_html = self.html.css(".pps .xvalue")
        pnts = [int(e.text()) for e in specialty_html]
        keys = ["one_day_races", "gc", "time_trial", "sprint", "climber", "hills"]
        return dict(zip(keys, pnts))
    
    def season_results(self, *args: str) -> List[Dict[str, Any]]:
        """
        Parses rider's results from season specified in URL. If no URL is
        specified, results from current season are parsed.

        :param args: Fields that should be contained in returned table. When
            no args are passed, all fields are parsed.

            - result: Rider's result. None if not rated.
            - gc_position: GC position after the stage. None if the race is
                one day race, after last stage, or if stage is points
                classification etc...
            - stage_url:
            - stage_name:
            - distance: Distance of the stage, if is given. Otherwise None.
            - date: Date of the stage in YYYY-MM-DD format. None if the stage
                is GC, points classification etc...
            - pcs_points:
            - uci_points:

        :raises ValueError: When one of args is of invalid value.
        :return: Table with wanted fields.
        """
        available_fields = (
            "result",
            "gc_position",
            "stage_url",
            "stage_name",
            "distance",
            "date",
            "pcs_points",
            "uci_points"
        )
        fields = parse_table_fields_args(args, available_fields)
        casual_fields = ["stage_url", "stage_name"]
        for field in list(casual_fields):
            if field not in fields:
                casual_fields.remove(field)

        results_html = self.html.css_first("table.rdrResults")
        for tr in results_html.css("tbody > tr"):
            if not tr.css("td")[1].text():
                tr.remove()

        # Clean string when there's an additional crossed-out value. Takes most recent updated value
        clean_crossed_out_val = lambda x: x.strip().split(' ')[-1]

        table_parser = TableParser(results_html)
        if casual_fields:
            table_parser.parse(casual_fields)
        if "date" in fields:
            try:
                year = self.html.css_first(".rdrSeasonNav > li.cur > a").text()
                dates = table_parser.parse_extra_column("Date", str)
                for i, date in enumerate(dates):
                    if date:
                        splitted_date = date.split(".")
                        dates[i] = f"{year}-{splitted_date[1]}-{splitted_date[0]}"
                    else:
                        dates[i] = None
                table_parser.extend_table("date", dates)
            except AttributeError:
                pass
        if "result" in fields:
            results = table_parser.parse_extra_column("Result", lambda x:
                int(x) if x.isnumeric() else None)
            table_parser.extend_table("result", results)
        if "gc_position" in fields:
            gc_positions = table_parser.parse_extra_column(2, lambda x:
                int(x) if x.isnumeric() else None)
            table_parser.extend_table("gc_position", gc_positions)
        if "distance" in fields:
            distances = table_parser.parse_extra_column("Distance", lambda x:
                float(clean_crossed_out_val(x)) if x.split(".")[0].isnumeric() else None)
            table_parser.extend_table("distance", distances)
        if "pcs_points" in fields:
            pcs_points = table_parser.parse_extra_column("PCS", lambda x:
                float(clean_crossed_out_val(x)) if x.isnumeric() else 0)
            table_parser.extend_table("pcs_points", pcs_points)
        if "uci_points" in fields:
            uci_points = table_parser.parse_extra_column("UCI", lambda x:
                float(clean_crossed_out_val(x)) if x.isnumeric() else 0)
            table_parser.extend_table("uci_points", uci_points)
            
        return table_parser.table

    def _get_rider_content_node(self):
        return self.html.css("div.page-content > div > .borderbox > .borderbox")[2]

