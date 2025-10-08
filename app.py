import streamlit as st
import pandas as pd
import re

st.title("🏆 Debate Tournament Analyzer (Tabroom CSVs)")

uploaded_files = st.file_uploader(
    "Upload multiple Tabroom round CSVs", 
    accept_multiple_files=True, 
    type="csv"
)

def extract_speaker_points(points_str):
    """Extract numeric speaker points from Tabroom points column"""
    # Find all numbers in the string
    numbers = re.findall(r"\d+\.?\d*", points_str)
    numbers = [float(n) for n in numbers]
    if numbers:
        return sum(numbers)/len(numbers)  # average if multiple points
    return 0

if uploaded_files and st.button("Start Analysis"):
    dfs = [pd.read_csv(f) for f in uploaded_files]
    all_data = pd.concat(dfs, ignore_index=True)
    all_data.columns = [c.strip() for c in all_data.columns]

    # Lists to store processed team and speaker data
    team_records = []
    speaker_records = []

    for idx, row in all_data.iterrows():
        # Team info
        aff_team = row["Aff"]
        neg_team = row["Neg"]
        winner = row["Win"]

        # Determine wins/losses
        aff_win = 1 if winner.strip() == "Aff" else 0
        neg_win = 1 if winner.strip() == "Neg" else 0

        # Extract average speaker points
        aff_speaks = extract_speaker_points(str(row["Aff Points"]))
        neg_speaks = extract_speaker_points(str(row["Neg Points"]))

        # Append team data
        team_records.append({"team": aff_team, "wins": aff_win, "losses": 1-aff_win, "speaks": aff_speaks})
        team_records.append({"team": neg_team, "wins": neg_win, "losses": 1-neg_win, "speaks": neg_speaks})

        # Extract individual speaker points
        aff_speakers = re.findall(r"([A-Za-z\s]+)\s+\d+\.?\d*", str(row["Aff Points"]))
        neg_speakers = re.findall(r"([A-Za-z\s]+)\s+\d+\.?\d*", str(row["Neg Points"]))

        for spk_name, spk_score in zip(aff_speakers, re.findall(r"\d+\.?\d*", str(row["Aff Points"]))):
            speaker_records.append({"speaker": spk_name.strip(), "speaks": float(spk_score), "rounds": 1})
        for spk_name, spk_score in zip(neg_speakers, re.findall(r"\d+\.?\d*", str(row["Neg Points"]))):
            speaker_records.append({"speaker": spk_name.strip(), "speaks": float(spk_score), "rounds": 1})

    # -------- TEAM LEADERBOARD --------
    team_df = pd.DataFrame(team_records)
    team_stats = team_df.groupby("team").agg({
        "wins": "sum",
        "losses": "sum",
        "speaks": "mean"
    }).reset_index()
    team_stats["win_rate"] = team_stats["wins"] / (team_stats["wins"] + team_stats["losses"])
    team_stats["prediction_score"] = (0.6 * team_stats["win_rate"]) + (0.4 * (team_stats["speaks"]/30))
    team_leaderboard = team_stats.sort_values("prediction_score", ascending=False)

    st.success("✅ Done! Results:")
    st.subheader("Team Leaderboard + Predictions")
    st.dataframe(team_leaderboard[["team", "win_rate", "speaks", "prediction_score"]].head(10))

    # -------- SPEAKER LEADERBOARD --------
    speaker_df = pd.DataFrame(speaker_records)
    speaker_stats = speaker_df.groupby("speaker").agg({
        "speaks": "mean",
        "rounds": "sum"
    }).reset_index()
    speaker_leaderboard = speaker_stats.sort_values("speaks", ascending=False)

    st.subheader("Speaker Leaderboard")
    st.dataframe(speaker_leaderboard.head(10))
