from typing import Optional

import streamlit as st
from prisma import Prisma
from prisma.models import LeagueDivision, LeaguePlayer, LeagueTeam

from utils.data import get_divisions, get_players, get_teams, init_connection
from utils.utils import hide_streamlit_elements

hide_streamlit_elements()


def select_team(teams: list[LeagueTeam], divisions: list[LeagueDivision]):
    col1, col2, col3 = st.columns([2, 3, 9])
    with col1:
        st.text("")
        st.text("")
        use_team_filter = st.checkbox(
            "Filter team",
            False,
        )
    with col2:
        div_filter = [d.name for d in divisions] if use_team_filter else []
        div_select = st.selectbox(
            "Division",
            div_filter,
        )
    with col3:
        if use_team_filter:
            team_options = [t.name for t in teams if t.division.name in div_select]
            team_options.sort()
        else:
            team_options = []
        team_name_select = st.selectbox(
            "Team",
            team_options,
        )
    team_list = [t for t in teams if t.name == team_name_select]
    if len(team_list) == 0:
        return None
    return team_list[0]


def select_player(team: Optional[LeagueTeam], players: list[LeaguePlayer]):
    if team is None:
        players_list = [p for p in players]
    else:
        players_list = [tp.player for tp in team.players if tp.active]
    players_name_list = [p.name for p in players_list]
    player_name_select = st.selectbox(
        "Player",
        players_name_list,
    )
    player_obj = [p for p in players_list if p.name == player_name_select][0]
    return player_obj


def get_current_team(player: LeaguePlayer):
    current_team_list = [t for t in player.teams if t.active]
    if len(current_team_list) == 0:
        current_team = None
    else:
        current_team = current_team_list[0]
    return current_team


def select_new_team(player: LeaguePlayer, teams: list[LeagueTeam]):
    current_team = get_current_team(player)
    team_options = [None] + [t for t in teams if t.id != current_team.leagueTeamId]
    new_team = st.selectbox("New team", team_options, format_func=lambda t: None if t is None else t.name)
    
    return new_team


def process_new_player(db: Prisma, player_name: str, team: LeagueTeam):
    player = db.leagueplayer.create(
        data={
            "name": player_name,
            "nicks": [player_name],
        }
    )
    db.leagueplayerteams.create(
        data={
            "active": True,
            "leaguePlayerId": player.id,
            "leagueTeamId": team.id,
        }
    )

    get_players.clear()
    return get_players(db)


def process_new_nick(db: Prisma, player: LeaguePlayer, nick: str):
    nicks_player = [n for n in player.nicks]
    nicks_player.append(nick.strip())

    db.leagueplayer.update(
        where={"id": player.id},
        data={
            "nicks": {"set": nicks_player},
        },
    )

    get_players.clear()
    return get_players(db)


def process_delete_nick(db: Prisma, player: LeaguePlayer, nick: str):
    nicks_player = [n for n in player.nicks]
    nicks_player.remove(nick)

    db.leagueplayer.update(
        where={"id": player.id},
        data={
            "nicks": {"set": nicks_player},
        },
    )

    get_players.clear()
    return get_players(db)


def process_new_team(
    db: Prisma,
    player: LeaguePlayer,
    new_team: Optional[LeagueTeam],
):
    current_team = get_current_team(player)
    
    if current_team is not None:
        db.leagueplayerteams.upsert(
            where={
                "leaguePlayerId": player.id,
                "leagueTeamId": current_team.id,
            },
            data={
                "active": False
            }
        )
    
    if new_team is not None:
        db.leagueplayerteams.upsert(
            where={
                "leaguePlayerId": player.id,
                "leagueTeamId": new_team.id,
            },
            data={
                "active": True
            }
        )

    get_teams.clear()
    return get_teams(db)


def main():
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

    teams_list = get_teams(db)
    divisions_list = get_divisions(db)
    players_list = get_players(db)

    st.write("# Edit player details")

    team = select_team(teams_list, divisions_list)

    st.write("## Add new player")
    player_name = st.text_input("Player name", "")
    player_submitted = st.button("Add player", disabled=(team is None))
    if team is None:
        st.warning("Cannot add player without the team filter")
    if player_submitted:
        players_list = process_new_player(db, player_name, team)

    st.write("## Edit player")
    player = select_player(team, players_list)
    if player is None:
        return

    st.write(f"### {player.name}")

    st.write("#### Nicks")
    for nick in player.nicks:
        col1, col2 = st.columns([9, 1])
        col1.write(f"- {nick}")
        players_list = col2.button("X", key=nick, on_click=process_delete_nick, args=[db, player, nick])
    
    new_nick = st.text_input("New nick", "")
    nick_submitted = st.button("Add nick")
    if nick_submitted:
        players_list = process_new_nick(db, player, new_nick)

    st.write("#### Team")
    new_team = select_new_team(player, teams_list)
    team_submitted = st.button("Change team")
    if team_submitted:
        teams_list = process_new_team(db, player, new_team)


if __name__ == "__main__":
    main()
