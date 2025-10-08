import streamlit as st
import pandas as pd

st.title("🏆 Debate Tournament Analyzer")

uploaded_files = st.file_uploader(
    "Upload multiple Tabroom CSVs", 
    accept_multiple_files=True, 
    type="csv"
)

if uploaded_files:
    dfs = [pd.read_csv(f) for f in uploaded_files]
    all_data = pd.concat(dfs)
    all_data.columns = [c.strip().lower() for c in all_data.columns]

    # Team leaderboard
    if "team" in all_data.columns and "wins" in all_data.columns:
        team_stats = all_data.groupby("team").agg({
            "wins": "sum",
            "losses": "sum",
            "speaks": "mean"
        }).reset_index()
        team_stats["win_rate"] = team_stats["wins"] / (team_stats["wins"] + team_stats["losses"])
        team_stats["prediction_score"] = (0.6 * team_stats["win_rate"]) + (0.4 * (team_stats["speaks"] / 30))
        team_leaderboard = team_stats.sort_values("prediction_score", ascending=False)
        st.subheader("Team Leaderboard + Predictions")
        st.dataframe(team_leaderboard[["team", "win_rate"_]()]()_
