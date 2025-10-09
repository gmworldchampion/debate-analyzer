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
    numbers = re.findall(r"\d+\.?\d*", points_str)
    numbers = [float(n) for n in numbers]
    if numbers:
        return sum(numbers) / len(numbers)
    return 0

if uploaded_files and st.button("Start Analysis"):
    dfs = [pd.read_csv(f) for f in uploaded_files]
    all_data = pd.concat(dfs, ignore_index=True)

    # Clean column names
    all_data.columns = all_data.columns.str.strip()
    all_data.columns = all_data.columns.str.replace(r"\s+", " ", regex=True)
    all_data.columns = all_data.columns.str.replace('"', '')

    # Debug: show available columns
    st.write("Detected columns:", list(all_data.columns))

    # Try to detect the 'Aff Points' and 'Neg Points' columns dynamically
    aff_col = next((c for c in all_data.columns if "Aff" in c and "Point" in c), None)
    neg_col = next((c for c in all_data.columns if "Neg" in c and "Point" in c), None)

    if not aff_col or not neg_col:
        st.error("Couldn't find 'Aff Points' or 'Neg Points' columns. Please check the column names above.")
        st.stop()

    team_records = []
    speaker_records = []

    for idx, row in all_data.iterrows():
        aff_team = row["Aff"]
        neg_team = row["Neg"]
        winner = str(row["Win"]).strip()

        aff_win = 1 if winner == "Aff" else 0
        neg_win = 1 if winner == "Neg" else 0

        aff_speaks = extract_speaker_points(str(row[aff_col]))
        neg_speaks = extract_speaker_points(str(row[neg_col]))

        team_records.append({"team": aff_team, "wins": aff_win, "losses": 1 - aff_win, "speaks": aff_speaks})
        team_records.append({"team": neg_team, "wins": neg_win, "losses": 1 - neg_win, "speaks": neg_speaks})

        aff_speakers = re.findall(r"([A-Za-z][A-Za-z\s]+)\s+\d+\.?\d*", str(row[aff_col]))
        neg_speakers = re.findall(r"([A-Za-z][A-Za-z\s]+)\s+\d+\.?\d*", str(row[neg_col]))

        for spk_name, spk_score in zip(aff_speakers, re.findall(r"\d+\.?\d*", str(row[aff_col]))):
            speaker_records.append({"speaker": spk_name.strip(), "speaks": float(spk_score), "rounds": 1})
        for spk_name, spk_score in zip(neg_speakers, re.findall(r"\d+\.?\d*", str(row[neg_col]))):
            speaker_records.append({"speaker": spk_name.strip(), "speaks": float(spk_score), "rounds": 1})

    # Team leaderboard
    team_df = pd.DataFrame(team_records)
    team_stats = team_df.groupby("team").agg({
        "wins": "sum",
        "losses": "sum",
        "speaks": "mean"
    }).reset_index()
    team_stats["win_rate"] = team_stats["wins"] / (team_stats["wins"] + team_stats["losses"])
    team_stats["prediction_score"] = (0.6 * team_stats["win_rate"]) + (0.4 * (team_stats["speaks"] / 30))
    team_leaderboard = team_stats.sort_values("prediction_score", ascending=False)

    st.success("✅ Done! Results:")
    st.subheader("Team Leaderboard + Predictions")
    st.dataframe(team_leaderboard[["team", "win_rate", "speaks", "prediction_score"]].head(10))

    # Speaker leaderboard
    speaker_df = pd.DataFrame(speaker_records)
    speaker_stats = speaker_df.groupby("speaker").agg({
        "speaks": "mean",
        "rounds": "sum"
    }).reset_index()
    speaker_leaderboard = speaker_stats.sort_values("speaks", ascending=False)

    st.subheader("Speaker Leaderboard")
    st.dataframe(speaker_leaderboard.head(10))

