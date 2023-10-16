import streamlit as st
import streamlit_authenticator as stauth
import yaml
from st_pages import Page, Section, add_indentation, show_pages

from utils.data import init_connection
from utils.utils import hide_streamlit_elements

hide_streamlit_elements()


def init_login():
    with open("login.yaml") as file:
        config = yaml.load(file, Loader=yaml.SafeLoader)

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
        [],
    )
    return authenticator


def config_pages():
    add_indentation()
    show_pages(
        [
            Page("Home.py", "Home", "🏠"),
            Section("League", "⚽️"),
            Page("pages_experimental/1_Teams.py", "Teams", "👥"),
            Page("pages_experimental/2_Matches.py", "Matches", "📅"),
            Page("pages_experimental/3_Match_details.py", "Match details", "📊"),
            Page("pages_experimental/4_Statistics.py", "Statistics", "🏅"),
            Page("pages_experimental/5_Standings.py", "Standings", "🏆"),
            Section("Admin", "🔒"),
            Page(
                "pages_experimental/6_Database_operations.py",
                "Database operations",
                "💾",
            ),
        ]
    )


def main():
    config_pages()

    db = init_connection()
    st.session_state["db"] = db

    reload_data_btn = st.button("Reload data")
    if reload_data_btn:
        st.cache_resource.clear()

    st.write("# Home page")
    st.write("#### Welcome to the FUTLIFE dashboard")

    authenticator = init_login()
    authenticator.login("Admin login", "main")

    if st.session_state["authentication_status"]:
        st.write(f'Connected as *{st.session_state["name"]}*')
        authenticator.logout("Logout", "main")
    elif st.session_state["authentication_status"] is False:
        st.error("Username or password is incorrect")


if __name__ == "__main__":
    main()
