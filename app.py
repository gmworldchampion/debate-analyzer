import streamlit as st
import pandas as pd

st.title("🏆 Debate Tournament Analyzer")

uploaded_files = st.file_uploader(
    "Upload multiple Tabroom CSVs", 
    accept_multiple_files=True, 
    type="csv"
)

# Add a start button
if uploaded_files and st.button("Start Analysis"):
    # Combine all uploaded CSVs
    dfs = [pd.read_csv(f) for f in uploaded_files]
    all_data = pd.concat(dfs)
    all_data.columns = [c.strip().lower() for c in all_data.columns]

    st.success("✅ Done! Results:")

    # -------- TEAM LEADERBOARD --------
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
        st.dataframe(team_leaderboard[["team", "win_rate", "speaks", "prediction_score"]].head(10))

    # -------- SPEAKER LEADERBOARD --------
    if "speaker" in all_data.columns and "speaks" in all_data.columns:
        speaker_stats = all_data.groupby("speaker").agg({
            "speaks": "mean",
            "rounds": "sum"
        }).reset_index()
        speaker_leaderboard = speaker_stats.sort_values("speaks", ascending=False)

        st.subheader("Speaker Leaderboard")
        st.dataframe(speaker_leaderboard.head(10))

