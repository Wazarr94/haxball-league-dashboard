import io
import os
import re
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import polars as pl
import streamlit as st
from st_pages import add_indentation

from generated.prisma import Prisma
from generated.prisma.models import LeagueSeason
from generated.prisma.types import (
    LeagueMatchCreateWithoutRelationsInput,
    LeagueMatchDetailCreateWithoutRelationsInput,
)
from utils.data import (
    get_divisions,
    get_matches,
    get_players,
    get_teams,
    init_connection,
)
from utils.utils import get_info_match, hide_streamlit_elements

hide_streamlit_elements()
add_indentation()


@dataclass
class UploadedFile:
    id: int
    name: str
    type: str
    size: int


@dataclass
class Input:
    excel: UploadedFile | None
    spreadsheet_url: str | None

    def get_url_final(self) -> str | None:
        if self.spreadsheet_url is None:
            return None
        spreadsheet_id = self.spreadsheet_url.split("/")[5]
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv"

    def get_dataframe_excel(self, sheet_name: str, **kwargs) -> pd.DataFrame | None:
        if self.excel is None:
            return None

        return pd.read_excel(self.excel, sheet_name=sheet_name, **kwargs)

    def get_dataframe_spreadsheet(
        self, sheet_name: str, **kwargs
    ) -> pd.DataFrame | None:
        if self.spreadsheet_url is None:
            return None

        url_input = self.get_url_final()
        url = f"{url_input}&sheet={sheet_name}"
        return pd.read_csv(url, **kwargs)

    def get_dataframe(self, sheet_name: str, **kwargs) -> pd.DataFrame:
        if self.excel is not None:
            df = self.get_dataframe_excel(sheet_name, **kwargs)
        elif self.spreadsheet_url is not None:
            df = self.get_dataframe_spreadsheet(sheet_name, **kwargs)
        else:
            raise ValueError("No input provided")

        assert df is not None
        return df


def get_title(match: pd.DataFrame):
    md: str = match["Matchday"]
    game_nb = match["Game_number"]
    t1 = match["Team1_name"]
    t2 = match["Team2_name"]
    if md.isdigit():
        title = f"MD {md} - {t1} vs {t2}"
    else:
        if game_nb > 1:
            title = f"{md} {game_nb} - {t1} vs {t2}"
        else:
            title = f"{md} - {t1} vs {t2}"
    return title


def create_season(db: Prisma, input_league: Input) -> LeagueSeason:
    season_df = input_league.get_dataframe("Season", dtype={"name": str})

    season = db.leagueseason.create(data={"name": season_df["name"][0]})

    return season


def create_divisions(db: Prisma, input_league: Input, season: LeagueSeason) -> int:
    divisions_df = input_league.get_dataframe("Divisions", dtype={"name": str})

    divisions = db.leaguedivision.create_many(
        data=[
            {"name": name, "leagueSeasonId": season.id} for name in divisions_df["name"]
        ]
    )

    return divisions


def create_teams(db: Prisma, input_league: Input) -> int:
    teams_df = input_league.get_dataframe("Teams", dtype={"Division_name": str})

    teams_df = teams_df.drop(columns=["Division_name"])
    teams = db.leagueteam.create_many(data=teams_df.to_dict("records"))

    return teams


def create_team_divisions_relationship(db: Prisma, input_league: Input) -> int:
    teams_df = input_league.get_dataframe("Teams", dtype={"Division_name": str})

    teams_class = db.leagueteam.find_many()
    teams_dict = (
        pd.DataFrame([dict(s) for s in teams_class])
        .loc[:, ["id", "name"]]
        .set_index("name")
        .to_dict("dict")["id"]
    )

    teams_df["team_id"] = teams_df["name"].apply(
        lambda x: teams_dict[str(x)] if str(x) in teams_dict.keys() else -1
    )

    teams_df = teams_df.set_index("team_id")
    teams_df = teams_df.drop(columns=["name"])

    divisions_class = db.leaguedivision.find_many()
    divisions_dict = (
        pd.DataFrame([dict(s) for s in divisions_class])
        .loc[:, ["id", "name"]]
        .set_index("name")
        .to_dict("dict")["id"]
    )

    teams_divisions_df = teams_df["Division_name"].apply(
        lambda x: divisions_dict[x] if x in divisions_dict.keys() else -1
    )

    data_list = []
    for k, v in teams_divisions_df.items():
        if k != -1 and v != -1:
            data_point = {"leagueTeamId": k, "leagueDivisionId": v}
            data_list.append(data_point)

    team_divisions = db.leagueteamdivisions.create_many(data=data_list)

    return team_divisions


def create_players(db: Prisma, input_league: Input) -> int:
    players_df = input_league.get_dataframe(
        "Players", na_values=["---", "", np.nan], dtype=object, skiprows=1
    ).set_index("Player")

    players_nicks_records = players_df.loc[
        :, players_df.columns.str.startswith("nick")
    ].T.to_dict("list")

    data_list = []
    for name, list_nicks in players_nicks_records.items():
        valid_list_nicks = {str(nick) for nick in list_nicks if nick is not np.nan}
        data_point_player = {"name": str(name), "nicks": valid_list_nicks}
        data_list.append(data_point_player)

    players = db.leagueplayer.create_many(data=data_list)

    return players


def create_team_players_relationship(db: Prisma, input_league: Input) -> int:
    players_df = input_league.get_dataframe(
        "Players", na_values=["---", "", np.nan], dtype=object, skiprows=1
    ).set_index("Player")

    st.write(players_df)

    players_class = db.leagueplayer.find_many()
    players_dict = (
        pd.DataFrame([dict(s) for s in players_class])
        .loc[:, ["id", "name"]]
        .set_index("name")
        .to_dict("dict")["id"]
    )

    players_df["player_id"] = players_df["Player"].apply(
        lambda x: players_dict[str(x)] if str(x) in players_dict.keys() else -1
    )

    players_df = players_df.iloc[:, 1:].set_index("player_id")

    teams_class = db.leagueteam.find_many()
    teams_dict = (
        pd.DataFrame([dict(s) for s in teams_class])
        .loc[:, ["id", "name"]]
        .set_index("name")
        .to_dict("dict")["id"]
    )

    players_teams_df = players_df["Team"].apply(
        lambda x: teams_dict[x] if x in teams_dict.keys() else -1
    )

    data_list_active = []
    for k, v in players_teams_df.items():
        if k != -1 and v != -1:
            data_point = {"leaguePlayerId": k, "leagueTeamId": v, "active": True}
            data_list_active.append(data_point)

    active_players = db.leagueplayerteams.create_many(data=data_list_active)

    players_old_teams_df = players_df.loc[
        :, players_df.columns.str.contains("team")
    ].applymap(lambda x: teams_dict[x] if x in teams_dict.keys() else -1)

    data_list_inactive = []
    for col in players_old_teams_df.columns:
        for k, v in players_old_teams_df[col].items():
            if k != -1 and v != -1:
                data_point = {"leaguePlayerId": k, "leagueTeamId": v, "active": False}
                data_list_inactive.append(data_point)

    inactive_players = db.leagueplayerteams.create_many(data=data_list_inactive)

    return active_players + inactive_players


def create_matches(db: Prisma, input_league: Input) -> int:
    matches_df = input_league.get_dataframe(
        "Matches", dtype={"Division_name": str, "Matchday": str}
    )

    matches_df = (
        pl.DataFrame(matches_df)
        .filter((pl.col("Team1_name") != "-") & (pl.col("Team2_name") != "-"))
        .to_pandas()
    )

    matches_df["Title"] = matches_df.apply(get_title, axis=1)
    matches_df["Defwin"] = matches_df["Defwin"].fillna(0)
    matches_df["Add_red"] = matches_df["Add_red"].fillna(0)
    matches_df["Add_blue"] = matches_df["Add_blue"].fillna(0)
    matches_df["Replay"] = matches_df["Replay"].fillna("")

    divisions_class = db.leaguedivision.find_many()
    divisions_df = pd.DataFrame([dict(s) for s in divisions_class]).rename(
        columns={"id": "Division_id", "name": "Division_name"}
    )

    matches_dict_records = matches_df.merge(
        divisions_df, how="left", on="Division_name"
    ).to_dict("records")

    data_list: list[LeagueMatchCreateWithoutRelationsInput] = [
        {
            "id": x["id"],
            "leagueDivisionId": int(x["Division_id"]),
            "matchday": x["Matchday"],
            "gameNumber": x["Game_number"],
            "date": datetime.combine(
                x["Date"],
                datetime.strptime(x["Time"], "%I:%M:%S %p").time(),
            ),
            "title": x["Title"],
            "defwin": x["Defwin"],
            "addRed": x["Add_red"],
            "addBlue": x["Add_blue"],
            "replayURL": x["Replay"],
        }
        for x in matches_dict_records
    ]

    matches = db.leaguematch.create_many(data=data_list)
    return matches


def create_matches_details(db: Prisma, input_league: Input) -> int:
    matches_df = input_league.get_dataframe(
        "Matches", dtype={"Division_name": str, "Matchday": str}
    )

    matches_df = (
        pl.DataFrame(matches_df)
        .filter((pl.col("Team1_name") != "-") & (pl.col("Team2_name") != "-"))
        .to_pandas()
    )

    matches_df["Title"] = matches_df.apply(get_title, axis=1)

    teams_class = db.leagueteam.find_many()
    teams_dict = (
        pd.DataFrame([dict(s) for s in teams_class])
        .loc[:, ["id", "name"]]
        .set_index("name")
        .to_dict("dict")["id"]
    )

    matches_df["Team1_name"] = matches_df["Team1_name"].apply(
        lambda x: teams_dict[x] if x in teams_dict.keys() else -1
    )

    matches_df["Team2_name"] = matches_df["Team2_name"].apply(
        lambda x: teams_dict[x] if x in teams_dict.keys() else -1
    )

    matches_title_class = db.leaguematch.find_many()
    matches_title_df = pd.DataFrame([dict(s) for s in matches_title_class]).loc[
        :, ["id"]
    ]

    matches_dict_records = matches_df.merge(
        matches_title_df, how="left", on="id"
    ).to_dict("records")

    data_list: list[LeagueMatchDetailCreateWithoutRelationsInput] = []
    for x in matches_dict_records:
        if x["Team1_name"] != -1:
            data_point_1: LeagueMatchDetailCreateWithoutRelationsInput = {
                "leagueMatchId": x["id"],
                "leagueTeamId": x["Team1_name"],
                "startsRed": True if x["Inverse"] == 0 else False,
                "home": True,
            }
            data_list.append(data_point_1)
        if x["Team2_name"] != -1:
            data_point_2: LeagueMatchDetailCreateWithoutRelationsInput = {
                "leagueMatchId": x["id"],
                "leagueTeamId": x["Team2_name"],
                "startsRed": False if x["Inverse"] == 0 else True,
                "home": False,
            }
            data_list.append(data_point_2)

    matches_details = db.leaguematchdetail.create_many(data=data_list)

    return matches_details


def clear_league_db(db: Prisma) -> None:
    db.leagueplayer.delete_many(where={})
    db.leagueteam.delete_many(where={})
    db.leagueplayerteams.delete_many(where={})
    db.leaguedivision.delete_many(where={})
    db.leaguematch.delete_many(where={})
    db.leaguematchdetail.delete_many(where={})
    db.leagueseason.delete_many(where={})


def confirm_clear_league_db(db: Prisma) -> None:
    col1, col2 = st.columns([2, 1])
    col1.warning("Are you sure you want to clear the league database?")
    btn = col2.button("Confirm")
    if btn:
        clear_league_db(db)
        st.success("League database cleared")


def clear_league_db_system(db: Prisma) -> None:
    st.button("Clear league database", on_click=confirm_clear_league_db, args=(db,))


def treat_input(db: Prisma, input_league: Input) -> bool:
    try:
        season = create_season(db, input_league)
    except Exception as e:
        st.error(f"Error while creating season. Clearing database.\n\n{e}")
        clear_league_db(db)
        return False

    try:
        create_divisions(db, input_league, season)
    except Exception as e:
        st.error(f"Error while creating divisions. Clearing database.\n\n{e}")
        clear_league_db(db)
        return False

    try:
        create_teams(db, input_league)
    except Exception as e:
        st.error(f"Error while creating teams. Clearing database.\n\n{e}")
        clear_league_db(db)
        return False

    try:
        create_team_divisions_relationship(db, input_league)
    except Exception as e:
        st.error(
            "Error while creating team divisions relationship. "
            + f"Clearing database.\n\n{e}"
        )
        clear_league_db(db)
        return False

    try:
        create_players(db, input_league)
    except Exception as e:
        st.error(
            "Error while creating players. " + f"Clearing database.\n\n{e}",
        )
        clear_league_db(db)
        return False

    try:
        create_team_players_relationship(db, input_league)
    except Exception as e:
        st.error(
            f"Error while creating team players relationship. Clearing database.\n\n{e}"
        )
        clear_league_db(db)
        return False

    try:
        create_matches(db, input_league)
    except Exception as e:
        st.error(f"Error while creating matches. Clearing database.\n\n{e}")
        clear_league_db(db)
        return False

    try:
        create_matches_details(db, input_league)
    except Exception as e:
        st.error(f"Error while creating match details. Clearing database.\n\n{e}")
        clear_league_db(db)
        return False

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

    st.write("### League database")

    clear_league_db_system(db)

    col, _ = st.columns([1, 2])
    select_method = col.selectbox(
        "Select input method",
        ["Google Spreadsheet", "Excel file"],
    )
    if select_method == "Google Spreadsheet":
        url_input = st.text_input(
            "Enter spreadsheet URL",
            value=os.environ["SPREADSHEET_URL"],
        )
        input_league = Input(excel=None, spreadsheet_url=url_input)
    else:
        excel_file = st.file_uploader("Upload excel file", type=["xlsx"])
        input_league = Input(excel=excel_file, spreadsheet_url=None)

    disabled = (input_league.excel is None and select_method == "Excel file") or (
        (input_league.spreadsheet_url == "" or input_league.spreadsheet_url is None)
        and select_method == "Google Spreadsheet"
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
