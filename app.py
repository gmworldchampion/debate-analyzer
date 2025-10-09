import streamlit as st
import pandas as pd
import re
from io import StringIO

# --- Helper to extract numeric speaker points ---
def extract_speaker_points(points_str):
    try:
        return float(re.findall(r"\d+(?:\.\d+)?", str(points_str))[0])
    except:
        return 0.0

# --- Header ---
st.title("🏆 Multi-Tournament Debate Leaderboard Analyzer")

st.markdown("""
Upload CSV files for each round **within each tournament**, then click **Start**.  
You’ll get:
- Round-by-round team results  
- Speaker points leaderboard  
- Cross-tournament stats (top speakers & teams)
""")

# --- Data structure to hold tournaments ---
if "tournaments" not in st.session_state:
    st.session_state.tournaments = {}

# --- Add new tournament section ---
tournament_name = st.text_input("🏟️ Tournament name (e.g. MinneApple, Blake, Roseville):")

if tournament_name:
    uploaded_files = st.file_uploader(
        f"Upload round CSVs for {tournament_name} (one per round):",
        accept_multiple_files=True,
        type=["csv"]
    )

    if uploaded_files:
        rounds = []
        for file in uploaded_files:
            df = pd.read_csv(file)
            rounds.append(df)
        st.session_state.tournaments[tournament_name] = rounds
        st.success(f"✅ Added {len(rounds)} rounds for {tournament_name}")

# --- Start button ---
if st.button("🚀 Start Analysis"):
    all_team_results = []
    all_speaker_results = []

    # --- Process tournaments ---
    for tournament, rounds in st.session_state.tournaments.items():
        st.subheader(f"📊 Tournament: {tournament}")

        team_speaks = {}
        speaker_speaks = {}

        # Process each round
        for df in rounds:
            for _, row in df.iterrows():
                # Extract Aff and Neg teams + points
                aff_team = str(row.get("Aff", "Unknown")).strip()
                neg_team = str(row.get("Neg", "Unknown")).strip()
                aff_points = extract_speaker_points(row.get("Aff Points", 0))
                neg_points = extract_speaker_points(row.get("Neg Points", 0))
                aff_speakers = [s.strip() for s in str(row.get("Aff Speakers", "")).split(",")]
                neg_speakers = [s.strip() for s in str(row.get("Neg Speakers", "")).split(",")]

                # Update team speaks
                team_speaks[aff_team] = team_speaks.get(aff_team, 0) + aff_points
                team_speaks[neg_team] = team_speaks.get(neg_team, 0) + neg_points

                # Update speaker speaks
                for s in aff_speakers:
                    speaker_speaks[s] = speaker_speaks.get(s, 0) + (aff_points / len(aff_speakers) if aff_speakers else 0)
                for s in neg_speakers:
                    speaker_speaks[s] = speaker_speaks.get(s, 0) + (neg_points / len(neg_speakers) if neg_speakers else 0)

        # --- Tournament leaderboards ---
        team_df = pd.DataFrame(list(team_speaks.items()), columns=["Team", "Total Speaks"]).sort_values(by="Total Speaks", ascending=False)
        speaker_df = pd.DataFrame(list(speaker_speaks.items()), columns=["Speaker", "Total Speaks"]).sort_values(by="Total Speaks", ascending=False)

        st.write("🏅 **Team Leaderboard:**")
        st.dataframe(team_df)

        st.write("🎤 **Speaker Leaderboard:**")
        st.dataframe(speaker_df)

        all_team_results.extend(team_df.values.tolist())
        all_speaker_results.extend(speaker_df.values.tolist())

    # --- Global leaderboards ---
    st.header("🌍 Cross-Tournament Rankings")

    # Combine across tournaments
    global_teams = pd.DataFrame(all_team_results, columns=["Team", "Total Speaks"]).groupby("Team", as_index=False).sum()
    global_speakers = pd.DataFrame(all_speaker_results, columns=["Speaker", "Total Speaks"]).groupby("Speaker", as_index=False).sum()

    global_teams = global_teams.sort_values(by="Total Speaks", ascending=False)
    global_speakers = global_speakers.sort_values(by="Total Speaks", ascending=False)

    st.subheader("🏆 Best Teams Across All Tournaments")
    st.dataframe(global_teams)

    st.subheader("🎙️ Best Speakers Across All Tournaments")
    st.dataframe(global_speakers)

    st.success("✅ Done! Results below 🎉")

