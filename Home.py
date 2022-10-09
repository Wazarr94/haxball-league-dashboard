import streamlit as st
from prisma import Prisma
from dotenv import load_dotenv
import os

from utils.utils import hide_streamlit_elements

load_dotenv()

hide_streamlit_elements()


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


def main():
    db = init_connection()
    st.session_state["db"] = db

    st.write("# Home page")
    st.write("#### Welcome to the BFF dashboard")


if __name__ == "__main__":
    main()
