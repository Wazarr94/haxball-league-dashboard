from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from prisma import Prisma
from prisma.types import (
    LeagueMatchCreateWithoutRelationsInput,
    LeagueMatchDetailCreateWithoutRelationsInput,
    LeagueTeamCreateWithoutRelationsInput,
)
from st_pages import add_indentation

from utils.data import init_connection
from utils.utils import hide_streamlit_elements

hide_streamlit_elements()
add_indentation()


@dataclass
class UploadedFile:
    id: int
    name: str
    type: str
    size: int


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


def create_divisions(db: Prisma, excel: UploadedFile) -> int:
    divisions_df = pd.read_excel(
        excel,
        "Divisions",
        dtype={"name": str},
    )

    divisions = db.leaguedivision.create_many(
        data=[{"name": name} for name in divisions_df["name"]]
    )

    return divisions


def create_teams(db: Prisma, excel: UploadedFile) -> int:
    teams_df = pd.read_excel(
        excel,
        "Teams",
        dtype={"Division_name": str},
    )

    divisions_class = db.leaguedivision.find_many()
    divisions_df = (
        pd.DataFrame([dict(s) for s in divisions_class])
        .iloc[:, :2]
        .rename(columns={"id": "Division_id", "name": "Division_name"})
    )

    teams_dict_records = teams_df.merge(
        divisions_df, how="left", on="Division_name"
    ).to_dict("records")

    data_list: list[LeagueTeamCreateWithoutRelationsInput] = [
        {
            "name": x["name"],
            "leagueDivisionId": x["Division_id"],
            "initials": x["initials"],
        }
        for x in teams_dict_records
    ]

    teams = db.leagueteam.create_many(data=data_list)

    return teams


def create_players(db: Prisma, excel: UploadedFile) -> int:
    players_df = pd.read_excel(
        excel, "Players", na_values="---", dtype=object
    ).set_index("PLAYER")

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


def create_team_players_relationship(db: Prisma, excel: UploadedFile) -> int:
    players_df = pd.read_excel(excel, "Players", na_values="---")

    players_class = db.leagueplayer.find_many()
    players_dict = (
        pd.DataFrame([dict(s) for s in players_class])
        .loc[:, ["id", "name"]]
        .set_index("name")
        .to_dict("dict")["id"]
    )

    players_df["player_id"] = players_df["PLAYER"].apply(
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

    players_teams_df = players_df["TEAM"].apply(
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


def create_matches(db: Prisma, excel: UploadedFile) -> int:
    matches_df = pd.read_excel(
        excel,
        "Matches",
        dtype={"Division_name": str, "Matchday": str},
    )

    matches_df["Title"] = matches_df.apply(get_title, axis=1)
    matches_df["Defwin"] = matches_df["Defwin"].fillna(0)
    matches_df["Add_red"] = matches_df["Add_red"].fillna(0)
    matches_df["Add_blue"] = matches_df["Add_blue"].fillna(0)
    matches_df["Replay"] = matches_df["Replay"].fillna("")

    divisions_class = db.leaguedivision.find_many()
    divisions_df = (
        pd.DataFrame([dict(s) for s in divisions_class])
        .iloc[:, :2]
        .rename(columns={"id": "Division_id", "name": "Division_name"})
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
            "date": datetime.combine(x["Date"], x["Time"]),
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


def create_matches_details(db: Prisma, excel: UploadedFile) -> int:
    matches_df = pd.read_excel(
        excel,
        "Matches",
        dtype={"Division_name": str, "Matchday": str},
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


def clear_db(db: Prisma) -> None:
    db.leagueplayer.delete_many(where={})
    db.leagueteam.delete_many(where={})
    db.leagueplayerteams.delete_many(where={})
    db.leaguedivision.delete_many(where={})
    db.leaguematch.delete_many(where={})
    db.leaguematchdetail.delete_many(where={})


def clear_db_system(db: Prisma) -> None:
    button = st.button("Clear database")
    if button:
        clear_db(db)
        st.success("Database cleared")


def treat_excel_file(db: Prisma, excel_file: UploadedFile) -> bool:
    try:
        create_divisions(db, excel_file)
    except Exception as e:
        st.error(f"Error while creating divisions. Clearing database.\n {e}")
        clear_db(db)
        return False

    try:
        create_teams(db, excel_file)
    except Exception as e:
        st.error(f"Error while creating teams. Clearing database.\n {e}")
        clear_db(db)
        return False

    try:
        create_players(db, excel_file)
    except Exception as e:
        st.error(f"Error while creating players. Clearing database.\n {e}")
        clear_db(db)
        return False

    try:
        create_team_players_relationship(db, excel_file)
    except Exception as e:
        st.error(
            f"Error while creating team players relationship. Clearing database.\n {e}"
        )
        clear_db(db)
        return False

    try:
        create_matches(db, excel_file)
    except Exception as e:
        st.error(f"Error while creating matches. Clearing database.\n {e}")
        clear_db(db)
        return False

    try:
        create_matches_details(db, excel_file)
    except Exception as e:
        st.error(f"Error while creating match details. Clearing database.\n {e}")
        clear_db(db)
        return False

    return True


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

    clear_db_system(db)

    excel_file = st.file_uploader("Upload excel file", type=["xlsx"])
    if excel_file:
        success = treat_excel_file(db, excel_file)
        if success:
            st.success("File processed")


if __name__ == "__main__":
    main()
