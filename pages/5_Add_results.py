import streamlit as st
from prisma import Prisma
from prisma.models import LeagueDivision, LeagueMatch, LeagueTeam
from prisma.types import PeriodWhereUniqueInput

from utils.data import (
    get_divisions,
    get_matches,
    get_periods,
    get_teams,
    init_connection,
)
from utils.utils import hide_streamlit_elements

hide_streamlit_elements()


def select_match(
    divisions: list[LeagueDivision],
    teams: list[LeagueTeam],
    matches: list[LeagueMatch],
):
    matchday_options = {
        div.id: list(
            dict.fromkeys([m.matchday for m in matches if m.leagueDivisionId == div.id])
        )
        for div in divisions
    }
    col1, col2, col3 = st.columns([3, 2, 9])
    with col1:
        div_name_select = st.selectbox(
            "Division",
            [d.name for d in divisions],
        )
        div_select = [d for d in divisions if d.name == div_name_select][0]
    with col2:
        st.text("")
        st.text("")
        use_team_filter = st.checkbox(
            "Filter team",
            True,
        )
    with col3:
        if use_team_filter:
            team_options = [t.name for t in teams if t.division.name in div_name_select]
        else:
            team_options = []
        team_options.sort()
        team_select = st.selectbox(
            "Team",
            team_options,
        )

    matchdays_options_div = matchday_options[div_select.id]
    matchday_select = st.select_slider("Matchday", options=matchdays_options_div)

    match_list_filter: list[LeagueMatch] = []
    for m in matches:
        if m.matchday != matchday_select:
            continue
        if m.LeagueDivision.name != div_name_select:
            continue
        if team_select is None or any([md.team.name == team_select for md in m.detail]):
            match_list_filter.append(m)

    match_to_edit_title = st.selectbox("Match", [m.title for m in match_list_filter])
    match_list = [m for m in match_list_filter if m.title == match_to_edit_title]
    if len(match_list) == 0:
        return None
    return match_list[0]


def get_idx_starting_red_team(match: LeagueMatch):
    idx = [i for i, d in enumerate(match.detail) if d.startsRed][0]
    return idx


def radio_team_starts(match: LeagueMatch) -> bool:
    opt_start = [match.detail[0].team, match.detail[1].team]
    opt_start_name = [t.name for t in opt_start]
    t_name_starts = st.radio(
        "Team that started the first period in red team",
        options=opt_start_name,
        horizontal=True,
        index=get_idx_starting_red_team(match),
    )
    idx_team_starts = [i for i, t in enumerate(opt_start) if t.name == t_name_starts][0]
    return idx_team_starts == 0


def radio_defwin(match: LeagueMatch) -> int:
    opt_start_name = [None, match.detail[0].team.name, match.detail[1].team.name]
    team_defwin = st.radio(
        "Defwin for",
        options=opt_start_name,
        horizontal=True,
        index=match.defwin,
    )
    defwin = [i for i, k in enumerate(opt_start_name) if k == team_defwin][0]
    return defwin


def get_periods_id_match(match: LeagueMatch):
    if len(match.periods) == 0:
        return "", "", ""
    if len(match.periods) == 1:
        return str(match.periods[0].id), "", ""
    if len(match.periods) == 2:
        return str(match.periods[0].id), str(match.periods[1].id), ""
    return str(match.periods[0].id), str(match.periods[1].id), str(match.periods[2].id)


def process_edit(
    db: Prisma,
    match: LeagueMatch,
    first_team_starts: bool,
    defwin: int,
    red_score_adjustment: int,
    blue_score_adjustment: int,
    period1_id: str,
    period2_id: str,
    period3_id: str,
    replay_url: str,
):

    db.leaguematchdetail.update(
        where={
            "leagueMatchId_leagueTeamId": {
                "leagueMatchId": match.id,
                "leagueTeamId": match.detail[0].leagueTeamId,
            }
        },
        data={"startsRed": first_team_starts},
    )

    db.leaguematchdetail.update(
        where={
            "leagueMatchId_leagueTeamId": {
                "leagueMatchId": match.id,
                "leagueTeamId": match.detail[1].leagueTeamId,
            }
        },
        data={"startsRed": not first_team_starts},
    )

    periods: list[PeriodWhereUniqueInput] = []
    if period1_id != "":
        periods.append({"id": int(period1_id)})
    if period2_id != "":
        periods.append({"id": int(period2_id)})
    if period3_id != "":
        periods.append({"id": int(period3_id)})

    db.leaguematch.update(
        where={
            "id": match.id,
        },
        data={
            "defwin": defwin,
            "addRed": red_score_adjustment,
            "addBlue": blue_score_adjustment,
            "periods": {
                "set": periods,
            },
            "replayURL": replay_url,
        },
    )

    get_matches.clear()
    get_periods.clear()

    return get_matches(db), get_periods(db)


def main():
    if "db" not in st.session_state:
        db = init_connection()
        st.session_state["db"] = db

    db: Prisma = st.session_state["db"]

    if not st.session_state["authentication_status"]:
        st.error("You are not allowed to see this page")
        return

    matches_list = get_matches(db)
    teams_list = get_teams(db)
    divisions_list = get_divisions(db)
    periods_list = get_periods(db)

    st.write("# Add results")

    match_to_edit = select_match(divisions_list, teams_list, matches_list)
    if match_to_edit is None:
        return

    with st.container():
        st.write("### General")
        first_team_starts = radio_team_starts(match_to_edit)
        defwin = radio_defwin(match_to_edit)
        st.write("### Score adjustment")
        col1, col2 = st.columns(2)
        teams_match = [
            match_to_edit.detail[0].team.name,
            match_to_edit.detail[1].team.name,
        ]
        with col1:
            red_score_adjustment = st.number_input(
                teams_match[0],
                value=match_to_edit.addRed,
                step=1,
            )
        with col2:
            blue_score_adjustment = st.number_input(
                teams_match[1],
                value=match_to_edit.addBlue,
                step=1,
            )

        st.write("### Periods")
        all_periods_id = [p.id for p in periods_list]
        game_periods_id = get_periods_id_match(match_to_edit)
        can_submit = True

        period1_id = st.text_input("Period 1 id", game_periods_id[0])
        if period1_id != "" and int(period1_id) not in all_periods_id:
            can_submit = False
            st.error("Period 1 id invalid!")

        period2_id = st.text_input("Period 2 id", game_periods_id[1])
        if period2_id != "" and int(period2_id) not in all_periods_id:
            can_submit = False
            st.error("Period 2 id invalid!")

        period3_id = st.text_input("Period 3 id", game_periods_id[2])
        if period3_id != "" and int(period3_id) not in all_periods_id:
            can_submit = False
            st.error("Period 3 id invalid!")

        st.write("### Replay link")

        replay_url = st.text_input("Replay", match_to_edit.replayURL)

        submitted = st.button("Submit")
        if submitted:
            if not can_submit:
                st.error("Error: Fix the periods id")
            else:
                matches_list, periods_list = process_edit(
                    db,
                    match_to_edit,
                    first_team_starts,
                    defwin,
                    red_score_adjustment,
                    blue_score_adjustment,
                    period1_id,
                    period2_id,
                    period3_id,
                    replay_url,
                )
                st.success("Game processed")


if __name__ == "__main__":
    main()
