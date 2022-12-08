import os
import subprocess

import streamlit as st


def generate_prisma_client():
    print("GENERATING PRISMA CLIENT")
    subprocess.call(["prisma", "generate"])
    print("GENERATED PRISMA CLIENT")
    
generate_prisma_client()


try:
    from prisma import Prisma
except RuntimeError:
    from prisma_cleanup import cleanup

    cleanup()
    print("GOT RUNTIME ERROR")
    generate_prisma_client()
    from prisma import Prisma

from prisma.models import LeagueDivision  # noqa


@st.experimental_singleton
def init_connection():
    url = os.environ["DATABASE_URL"]
    db = Prisma(
        datasource={
            "url": url,
        }
    )
    db.connect()
    return db


@st.experimental_singleton
def get_matches(_db: Prisma):
    matches = _db.leaguematch.find_many(
        include={
            "LeagueDivision": True,
            "detail": {
                "include": {
                    "team": True,
                }
            },
            "periods": {
                "include": {
                    "PlayerStats": {
                        "include": {
                            "Player": {
                                "include": {
                                    "goalDetail": {
                                        "include": {
                                            "goal": True,
                                        }
                                    },
                                }
                            },
                        }
                    }
                }
            },
        },
        order={"id": "asc"},
    )
    for m in matches:
        m.detail.sort(key=lambda d: not d.home)
        m.periods.sort(key=lambda p: p.id)
    return matches


@st.experimental_singleton
def get_divisions(_db: Prisma) -> list[LeagueDivision]:
    divisions = _db.leaguedivision.find_many(
        order={"id": "asc"},
    )
    return divisions


@st.experimental_singleton
def get_teams(_db: Prisma):
    teams = _db.leagueteam.find_many(
        include={
            "division": True,
            "players": {
                "include": {
                    "player": True,
                }
            },
        },
        order={"id": "asc"},
    )
    return teams


@st.experimental_singleton
def get_players(_db: Prisma):
    players = _db.leagueplayer.find_many(
        include={
            "teams": {
                "include": {
                    "team": True,
                }
            }
        },
        order={"id": "asc"},
    )
    return players


@st.experimental_singleton
def get_periods(_db: Prisma):
    periods = _db.period.find_many(
        order={"id": "asc"},
    )
    return periods
