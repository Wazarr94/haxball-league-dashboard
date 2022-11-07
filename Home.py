import streamlit as st
import streamlit_authenticator as stauth
import yaml
from dotenv import load_dotenv

from utils.data import init_connection

from utils.utils import hide_streamlit_elements

load_dotenv()

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


def main():
    db = init_connection()
    st.session_state["db"] = db

    reload_data_btn = st.button("Reload data")
    if reload_data_btn:
        st.experimental_singleton.clear()

    st.write("# Home page")
    st.write("#### Welcome to the BFF dashboard")

    authenticator = init_login()
    authenticator.login("Admin login", "main")

    if st.session_state["authentication_status"]:
        st.write(f'Connected as *{st.session_state["name"]}*')
        authenticator.logout("Logout", "main")
    elif st.session_state["authentication_status"] == False:
        st.error("Username/password is incorrect")


if __name__ == "__main__":
    main()
