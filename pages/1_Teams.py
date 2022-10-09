# streamlit_app.py

import streamlit as st
from prisma import Prisma

from utils.utils import hide_streamlit_elements

hide_streamlit_elements()


@st.experimental_memo(ttl=600)
def get_teams(_db: Prisma):
    teams = _db.leagueteam.find_many(
        include={
            "division": True,
            "LeaguePlayerTeams": {
                "include": {
                    "player": True,
                }
            },
        }
    )
    return teams


@st.experimental_memo(ttl=600)
def get_divisions(_db: Prisma):
    divisions = _db.leaguedivision.find_many()
    return divisions


def main():
    if "db" not in st.session_state:
        return
    db: Prisma = st.session_state["db"]

    teams_list = get_teams(db)
    divisions_list = get_divisions(db)

    st.write("# Season 3 teams")

    col1, col2 = st.columns([4, 8])
    with col1:
        div_select = st.selectbox(
            "Division",
            [d.name for d in divisions_list],
        )
    with col2:
        team_options = [t.name for t in teams_list if t.division.name in div_select]
        team_options.sort()
        team_select = st.selectbox(
            "Team",
            team_options,
        )

    if team_select is not None:
        team_obj = [t for t in teams_list if t.name == team_select][0]
        active_players = [p.player for p in team_obj.LeaguePlayerTeams if p.active]
        former_players = [p.player for p in team_obj.LeaguePlayerTeams if not p.active]
        st.write(f"## {team_obj.name}")
        st.write(f"**Active players ({len(active_players)}/12):**")

        col1, col2 = st.columns(2)
        with col1:
            for player in active_players[::2]:
                st.write(f"- {player.name}")
        with col2:
            for player in active_players[1::2]:
                st.write(f"- {player.name}")

        st.write(f"**Former players:**")
        col1, col2 = st.columns(2)
        with col1:
            for player in former_players[::2]:
                st.write(f"- {player.name}")
        with col2:
            for player in former_players[1::2]:
                st.write(f"- {player.name}")


if __name__ == "__main__":
    main()
