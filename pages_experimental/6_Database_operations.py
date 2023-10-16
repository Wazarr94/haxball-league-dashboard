import io
import re
import traceback
from dataclasses import dataclass

import pandas as pd
import polars as pl
import streamlit as st
from st_pages import add_indentation
from streamlit.runtime.uploaded_file_manager import UploadedFile

from generated.prisma import Prisma
from generated.prisma.models import LeagueSeason
from utils.data import (
    get_divisions,
    get_matches,
    get_players,
    get_teams,
    init_connection,
)
from utils.utils import get_info_match, hide_streamlit_elements, settings

hide_streamlit_elements()
add_indentation()


@dataclass
class Input:
    excel: UploadedFile | None
    spreadsheet_url: str | None

    def get_url_final(self) -> str | None:
        if self.spreadsheet_url is None:
            return None

        spreadsheet_id = self.spreadsheet_url.split("/")[5]
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export"

    def get_dataframe_excel(self, sheet_name: str, **kwargs) -> pl.DataFrame | None:
        if self.excel is None:
            return None
        df_pd = pd.read_excel(self.excel, sheet_name=sheet_name, **kwargs)
        return pl.DataFrame(df_pd)

    def get_dataframe_spreadsheet(
        self, sheet_name: str, **kwargs
    ) -> pl.DataFrame | None:
        if self.spreadsheet_url is None:
            return None

        url_input = self.get_url_final()
        assert url_input is not None
        df_pd = pd.read_excel(url_input, sheet_name=sheet_name, **kwargs)
        return pl.DataFrame(df_pd)

    def get_dataframe(self, sheet_name: str, **kwargs) -> pl.DataFrame:
        if self.excel is not None:
            df = self.get_dataframe_excel(sheet_name, **kwargs)
        elif self.spreadsheet_url is not None:
            df = self.get_dataframe_spreadsheet(sheet_name, **kwargs)
        else:
            raise ValueError("No input provided")

        assert df is not None
        return df


def get_title(match: pd.DataFrame) -> str:
    # id = match[0]
    md = match[1]
    game_nb = match[2]
    t1 = match[3]
    t2 = match[4]
    if md.isdigit():
        title = f"MD {md} - {t1} vs {t2}"
    else:
        if game_nb > 1:
            title = f"{md} {game_nb} - {t1} vs {t2}"
        else:
            title = f"{md} - {t1} vs {t2}"
    return title


def create_season(db: Prisma, season_df: pl.DataFrame) -> LeagueSeason:
    name_season = season_df.get_column("name").item()
    season = db.leagueseason.create(data={"name": name_season})

    return season


def create_divisions(
    db: Prisma, divisions_df: pl.DataFrame, season: LeagueSeason
) -> int:
    data_divisions = divisions_df.select(
        "name", leagueSeasonId=pl.lit(season.id)
    ).to_dicts()

    divisions = db.leaguedivision.create_many(data=data_divisions)  # type: ignore

    return divisions


def create_teams(db: Prisma, teams_df: pl.DataFrame) -> int:
    data_teams = teams_df.select("name", "initials").to_dicts()
    teams = db.leagueteam.create_many(data=data_teams)  # type: ignore

    return teams


def create_team_divisions_relationship(db: Prisma, teams_df: pl.DataFrame) -> int:
    teams_db = db.leagueteam.find_many()
    teams_id = pl.DataFrame([dict(s) for s in teams_db]).select(
        "name", leagueTeamId=pl.col("id")
    )

    teams_df_id = teams_df.join(teams_id, on="name", how="inner").drop("name")

    divisions_db = db.leaguedivision.find_many()
    divisions_id = pl.DataFrame([dict(s) for s in divisions_db]).select(
        Division_name="name", leagueDivisionId=pl.col("id")
    )

    teams_id_divisions_id_df = teams_df_id.join(
        divisions_id, on="Division_name", how="inner"
    ).select("leagueTeamId", "leagueDivisionId")

    data_team_div = teams_id_divisions_id_df.to_dicts()
    team_divisions = db.leagueteamdivisions.create_many(data=data_team_div)  # type: ignore

    return team_divisions


def create_players(db: Prisma, players_df: pl.DataFrame) -> int:
    players_df_filter = players_df.filter(pl.col("Player").is_not_null())

    data_players_raw = players_df_filter.select(
        name="Player",
        nicks=pl.concat_list([pl.col("Player"), pl.col("^nick.*$")]),
    ).to_dicts()

    data_players = [
        {
            "name": player.get("name"),
            "nicks": [nick for nick in player.get("nicks", []) if nick is not None],
        }
        for player in data_players_raw
    ]

    players = db.leagueplayer.create_many(data=data_players)  # type: ignore

    return players


def create_team_players_relationship(db: Prisma, players_df: pl.DataFrame) -> int:
    players_df_filter = players_df.filter(pl.col("Player").is_not_null())

    players_db = db.leagueplayer.find_many()
    players_id = pl.DataFrame([dict(s) for s in players_db]).select(
        Player="name", leaguePlayerId=pl.col("id")
    )

    players_id_df = (
        players_df_filter.join(players_id, on="Player", how="inner")
        .with_columns(
            pl.col("old team 1").fill_null(""),
            pl.col("old team 2").fill_null(""),
        )
        .drop("Player")
    )

    teams_db = db.leagueteam.find_many()
    teams_id = pl.DataFrame([dict(s) for s in teams_db]).select(
        Team="name", leagueTeamId=pl.col("id")
    )

    players_id_active_team_id_df = players_id_df.join(
        teams_id, on="Team", how="inner"
    ).select("leaguePlayerId", "leagueTeamId", active=pl.lit(True))

    data_list_active = players_id_active_team_id_df.to_dicts()
    active_players = db.leagueplayerteams.create_many(data=data_list_active)  # type: ignore

    players_id_old_team_1_id_df = players_id_df.join(
        teams_id, left_on="old team 1", right_on="Team", how="inner"
    ).select("leaguePlayerId", "leagueTeamId", active=pl.lit(False))

    players_id_old_team_2_id_df = players_id_df.join(
        teams_id, left_on="old team 2", right_on="Team", how="inner"
    ).select("leaguePlayerId", "leagueTeamId", active=pl.lit(False))

    data_list_inactive_1 = players_id_old_team_1_id_df.to_dicts()
    data_list_inactive_2 = players_id_old_team_2_id_df.to_dicts()
    data_list_inactive = data_list_inactive_1 + data_list_inactive_2

    inactive_players = db.leagueplayerteams.create_many(data=data_list_inactive)  # type: ignore

    return active_players + inactive_players


def create_matches(db: Prisma, matches_df: pl.DataFrame) -> int:
    matches_df_final = get_matches_title_df(matches_df)

    divisions_db = db.leaguedivision.find_many()
    divisions_df = pl.DataFrame([dict(s) for s in divisions_db]).select(
        Division_name="name", leagueDivisionId=pl.col("id")
    )

    data_matches = (
        matches_df_final.join(divisions_df, on="Division_name", how="inner")
        .select(
            id=pl.col("id"),
            date=pl.col("Date_Time"),
            matchday=pl.col("Matchday"),
            gameNumber=pl.col("Game_number"),
            title=pl.col("title"),
            leagueDivisionId=pl.col("leagueDivisionId"),
            defwin=pl.col("Defwin"),
            addRed=pl.col("Add_red"),
            addBlue=pl.col("Add_blue"),
            replayURL=pl.col("Replay"),
            periods=pl.concat_list([pl.col("^Period.*$")]),
        )
        .to_dicts()
    )

    data_update_matches = [
        (
            {"id": match.get("id")},
            {
                "periods": {
                    "set": [
                        {"id": period}
                        for period in match.get("periods", [])
                        if period is not None
                    ]
                }
            },
        )
        for match in data_matches
    ]
    # remove entries from the list with no periods
    data_update_matches = [
        data_match
        for data_match in data_update_matches
        if data_match[1]["periods"]["set"]
    ]

    for data_match in data_matches:
        data_match.pop("periods")

    matches = db.leaguematch.create_many(data=data_matches)  # type: ignore

    periods_db = db.period.find_many()
    all_periods_id = [p.id for p in periods_db]

    for data_match in data_update_matches:
        if data_match[1]["periods"]["set"]:
            for period in data_match[1]["periods"]["set"]:
                if period["id"] not in all_periods_id:
                    raise ValueError(f"Period {period} does not exist in database.")

        db.leaguematch.update(where=data_match[0], data=data_match[1])  # type: ignore

    return matches


def create_matches_details(db: Prisma, matches_df: pl.DataFrame) -> int:
    matches_title_df = get_matches_title_df(matches_df)

    teams_db = db.leagueteam.find_many()
    teams_df = pl.DataFrame([dict(s) for s in teams_db]).select(
        Team_name="name", leagueTeamId=pl.col("id")
    )

    matches_filter_df = (
        matches_title_df.join(
            teams_df,
            left_on="Team1_name",
            right_on="Team_name",
            how="semi",
        )
        .join(
            teams_df,
            left_on="Team2_name",
            right_on="Team_name",
            how="semi",
        )
        .select(
            leagueMatchId=pl.col("id"),
            startsRed=(~pl.col("Inverse")),
            home=(pl.lit(True)),
            Team1_name=pl.col("Team1_name"),
            Team2_name=pl.col("Team2_name"),
        )
    )

    matches_team1_df = matches_filter_df.join(
        teams_df,
        left_on="Team1_name",
        right_on="Team_name",
        how="inner",
    ).select(pl.exclude("^Team.*$"))
    data_matches_team_1 = matches_team1_df.to_dicts()

    matches_team2_df = matches_filter_df.join(
        teams_df,
        left_on="Team2_name",
        right_on="Team_name",
        how="inner",
    ).select(pl.exclude("^Team.*$"))
    data_matches_team_2 = matches_team2_df.to_dicts()

    data_matches = data_matches_team_1 + data_matches_team_2
    matches_details = db.leaguematchdetail.create_many(data=data_matches)  # type: ignore

    return matches_details


def clear_league_db(db: Prisma) -> None:
    db.leagueplayer.delete_many(where={})
    db.leagueteam.delete_many(where={})
    db.leagueplayerteams.delete_many(where={})
    db.leaguedivision.delete_many(where={})
    db.leaguematch.delete_many(where={})
    db.leaguematchdetail.delete_many(where={})
    db.leagueseason.delete_many(where={})

    st.cache_resource.clear()


def confirm_clear_league_db(db: Prisma) -> None:
    col1, col2 = st.columns([2, 1])
    col1.warning("Are you sure you want to clear the league database?")
    btn = col2.button("Confirm")
    if btn:
        clear_league_db(db)
        st.success("League database cleared")


def clear_league_db_system(db: Prisma) -> None:
    st.button("Clear league database", on_click=confirm_clear_league_db, args=(db,))


def get_season_df(input_league: Input) -> pl.DataFrame:
    dtype = {"name": str}
    usecols = list(dtype.keys())
    return input_league.get_dataframe("Season", usecols=usecols, dtype=dtype)


def get_divisions_df(input_league: Input) -> pl.DataFrame:
    dtype = {"name": str}
    usecols = list(dtype.keys())
    return input_league.get_dataframe("Divisions", usecols=usecols, dtype=dtype)


def get_teams_df(input_league: Input) -> pl.DataFrame:
    dtype = {"Division_name": str, "name": str, "initials": str}
    usecols = list(dtype.keys())
    return input_league.get_dataframe("Teams", usecols=usecols, dtype=dtype)


def get_players_df(input_league: Input) -> pl.DataFrame:
    dtype = {
        "Player": str,
        "Team": str,
        "old team 1": str,
        "old team 2": str,
        "nick1": str,
        "nick2": str,
        "nick3": str,
        "nick4": str,
        "nick5": str,
        "nick6": str,
        "nick7": str,
        "nick8": str,
        "nick9": str,
        "nick10": str,
    }
    usecols = list(dtype.keys())
    return input_league.get_dataframe(
        "Players", usecols=usecols, dtype=dtype, skiprows=1
    )


def get_matches_df(input_league: Input) -> pl.DataFrame:
    dtype = {
        "Matchday": str,
        "Game_number": int,
        "Date": str,
        "Time": str,
        "Team1_name": str,
        "Team2_name": str,
        "Division_name": str,
        "Period1_id": float,
        "Period2_id": float,
        "Period3_id": float,
        "Inverse": float,
        "Defwin": float,
        "Add_red": float,
        "Add_blue": float,
        "Replay": str,
    }
    usecols = list(dtype.keys())
    return input_league.get_dataframe(
        "Matches", usecols=usecols, dtype=dtype, parse_dates=[["Date", "Time"]]
    )


def get_matches_title_df(matches_df: pl.DataFrame) -> pl.DataFrame:
    matches_df_filter = matches_df.with_row_count("id", offset=1).filter(
        (pl.col("Team1_name") != "-") & (pl.col("Team2_name") != "-")
    )

    matches_df_fix = matches_df_filter.with_columns(
        pl.col("id").cast(int),
        pl.col("Game_number").cast(int),
        pl.col("^Period.*$").cast(int),
        pl.col("^Add_.*$").cast(int).fill_null(0),
        pl.col("Defwin").cast(int).fill_null(0),
        pl.col("Replay").fill_null(""),
        pl.col("Inverse").cast(bool).fill_null(False),
    )

    matches_df_id_list = matches_df_fix.get_column("id").to_list()
    matches_df_title_list = (
        matches_df_filter.select(
            "id", "Matchday", "Game_number", "Team1_name", "Team2_name"
        )
        .to_pandas()
        .apply(get_title, axis=1)
        .to_list()
    )

    matches_df_title = pl.DataFrame(
        {"id": matches_df_id_list, "title": matches_df_title_list}
    )

    matches_df_final = matches_df_fix.join(matches_df_title, on="id", how="inner")
    return matches_df_final


def treat_input(db: Prisma, input_league: Input) -> bool:
    with st.spinner("Processing file..."):
        season_df = get_season_df(input_league)
        divisions_df = get_divisions_df(input_league)
        teams_df = get_teams_df(input_league)
        players_df = get_players_df(input_league)
        matches_df = get_matches_df(input_league)

    with st.spinner("Clearing database..."):
        clear_league_db(db)

    with st.spinner("Creating database entries..."):
        try:
            season = create_season(db, season_df)
        except Exception as e:
            st.error(f"Error while creating season. Clearing database.\n\n{e}")
            traceback.print_exc()
            clear_league_db(db)
            return False

        try:
            create_divisions(db, divisions_df, season)
        except Exception as e:
            st.error(f"Error while creating divisions. Clearing database.\n\n{e}")
            traceback.print_exc()
            clear_league_db(db)
            return False

        try:
            create_teams(db, teams_df)
        except Exception as e:
            st.error(f"Error while creating teams. Clearing database.\n\n{e}")
            traceback.print_exc()
            clear_league_db(db)
            return False

        try:
            create_team_divisions_relationship(db, teams_df)
        except Exception as e:
            st.error(
                "Error while creating team divisions relationship. "
                + f"Clearing database.\n\n{e}"
            )
            traceback.print_exc()
            clear_league_db(db)
            return False

        try:
            create_players(db, players_df)
        except Exception as e:
            st.error(
                "Error while creating players. " + f"Clearing database.\n\n{e}",
            )
            traceback.print_exc()
            clear_league_db(db)
            return False

        try:
            create_team_players_relationship(db, players_df)
        except Exception as e:
            st.error(
                f"Error while creating team players relationship. Clearing database.\n\n{e}"
            )
            traceback.print_exc()
            clear_league_db(db)
            return False

        try:
            create_matches(db, matches_df)
        except Exception as e:
            st.error(f"Error while creating matches. Clearing database.\n\n{e}")
            traceback.print_exc()
            clear_league_db(db)
            return False

        try:
            create_matches_details(db, matches_df)
        except Exception as e:
            st.error(f"Error while creating match details. Clearing database.\n\n{e}")
            traceback.print_exc()
            clear_league_db(db)
            return False

    st.cache_resource.clear()
    return True


def download_league_data(
    divisions_df: pl.DataFrame,
    teams_df: pl.DataFrame,
    matches_df: pl.DataFrame,
    players_df: pl.DataFrame,
) -> io.BytesIO:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        divisions_df.to_pandas().to_excel(writer, sheet_name="Divisions", index=False)
        div_worksheet = writer.sheets["Divisions"]
        div_worksheet.autofit()

        teams_df.to_pandas().to_excel(writer, sheet_name="Teams", index=False)
        teams_worksheet = writer.sheets["Teams"]
        teams_worksheet.autofit()

        matches_df.to_pandas().to_excel(writer, sheet_name="Matches", index=False)
        matches_worksheet = writer.sheets["Matches"]
        matches_worksheet.autofit()

        players_df.to_pandas().to_excel(writer, sheet_name="Players", index=False)
        players_worksheet = writer.sheets["Players"]
        players_worksheet.autofit()

    return buffer


def download_league_data_system(db: Prisma) -> None:
    divisions_list = get_divisions(db)
    teams_list = get_teams(db)
    matches_list = get_matches(db)
    players_list = get_players(db)

    if len(divisions_list) == 0:
        dnames_df = pl.DataFrame({"name": []})
    else:
        div_clean = [{"name": d.name} for d in divisions_list]
        dnames_df = pl.DataFrame(div_clean)

    if len(teams_list) == 0:
        teams_df = pl.DataFrame({"name": []})
    else:
        teams_clean = [
            {
                "Division_name": [td.division.name for td in t.divisions],
                "name": t.name,
                "initials": t.initials,
            }
            for t in teams_list
        ]
        teams_df = pl.DataFrame(teams_clean).explode("Division_name")
    if len(players_list) == 0:
        players_df = pl.DataFrame({"Player": []})
    else:
        players_clean = [
            {
                "Player": p.name,
                "nicks": p.nicks,
                "active_team": [pt.team.name for pt in p.teams if pt.active],
                "old_teams": [pt.team.name for pt in p.teams if not pt.active],
            }
            for p in players_list
        ]
        players_df = (
            pl.DataFrame(players_clean)
            .with_columns(
                [pl.col("nicks").arr.get(i - 1).alias(f"nick{i}") for i in range(1, 7)],
            )
            .with_columns(
                pl.col("active_team").arr.get(0).alias("Team"),
            )
            .with_columns(
                [
                    pl.col("old_teams").arr.get(j - 1).alias(f"old team{j}")
                    for j in range(1, 3)
                ],
            )
            .select(pl.exclude(["nicks", "active_team", "old_teams"]))
        )

    if len(matches_list) == 0:
        matches_df = pl.DataFrame({"id": []})
    else:
        matches_clean = [
            {
                "id": m.id,
                "Matchday": m.matchday,
                "Date": m.date.date(),
                "Time": m.date.time(),
                "Team1_name": re.match(r".* - (.+) vs (.+)", m.title).group(1),
                "Team2_name": re.match(r".* - (.+) vs (.+)", m.title).group(2),
                "Division_name": m.LeagueDivision.name,
                "Period1_id": m.periods[0].id if len(m.periods) > 0 else None,
                "Period2_id": m.periods[1].id if len(m.periods) > 1 else None,
                "Period3_id": m.periods[2].id if len(m.periods) > 2 else None,
                "Score1": get_info_match(m).score[0] if m.periods else None,
                "Score2": get_info_match(m).score[1] if m.periods else None,
                "Inverse": not m.detail[0].startsRed if m.detail else None,
                "Defwin": m.defwin,
                "Add_red": m.addRed,
                "Add_blue": m.addBlue,
                "Replay": m.replayURL,
            }
            for m in matches_list
        ]
        matches_df = pl.DataFrame(matches_clean)

    col1, col2 = st.columns([1, 2])
    col1.download_button(
        label="Download data as Excel",
        data=download_league_data(dnames_df, teams_df, matches_df, players_df),
        file_name="FUTLIFE_league.xlsx",
        mime="application/vnd.ms-excel",
        disabled=True,
    )
    col2.warning("Download is temporarily broken")

    return


def main() -> None:
    if "db" not in st.session_state:
        db = init_connection()
        st.session_state["db"] = db

    db: Prisma = st.session_state["db"]
    print(settings)

    if (
        "authentication_status" not in st.session_state
        or not st.session_state["authentication_status"]
    ):
        st.error("You are not allowed to see this page")
        return

    st.title("Admin page")

    st.write("## Download data")

    download_league_data_system(db)

    st.write("## Database management")

    st.write("### Delete league database")

    clear_league_db_system(db)

    st.write("### Update league database")

    col, _ = st.columns([1, 2])
    select_method = col.selectbox(
        "Select input method",
        ["Google Sheets", "Excel file"],
    )
    if select_method == "Google Sheets":
        url_input = st.text_input(
            "Enter spreadsheet URL",
            value=settings.SPREADSHEET_URL,
        )
        input_league = Input(excel=None, spreadsheet_url=url_input)
    else:
        excel_file = st.file_uploader("Upload excel file", type=["xlsx"])
        input_league = Input(excel=excel_file, spreadsheet_url=None)

    disabled = (input_league.excel is None and select_method == "Excel file") or (
        (input_league.spreadsheet_url == "" or input_league.spreadsheet_url is None)
        and select_method == "Google Sheets"
    )
    btn_update = st.button(
        "Update database",
        disabled=disabled,
    )
    if btn_update:
        success = treat_input(db, input_league)
        if success:
            st.success("File processed")


if __name__ == "__main__":
    main()
