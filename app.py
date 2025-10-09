# app.py
import streamlit as st
import pandas as pd
import re
from collections import defaultdict

st.set_page_config(page_title="Debate Tournament Analyzer", layout="wide")
st.title("🏆 Debate Tournament Analyzer (Multi-Tournament, Tabroom CSVs)")

# -----------------------
# Session state initialization
# -----------------------
for key in ["tournaments", "upload"]:
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state.tournaments is None:
    st.session_state.tournaments = {}

# -----------------------
# Utilities
# -----------------------
def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = df.columns.astype(str)
    cols = cols.str.strip()
    cols = cols.str.replace(r"\s+", " ", regex=True)
    cols = cols.str.replace('"', "")
    df.columns = cols
    return df

def find_best_column(cols, keywords):
    cols_lower = [c.lower().strip() for c in cols]
    for col, col_lower in zip(cols, cols_lower):
        if all(k.lower() in col_lower for k in keywords):
            return col
    return None

def extract_name_score_pairs(text):
    text = str(text)
    num_pattern = r"(\d+(?:\.\d+)?)"
    pattern = re.compile(r"([A-Za-z\.\'\-\s]{2,}?)\s+" + num_pattern)
    pairs = pattern.findall(text)
    result = []
    for p in pairs:
        name = p[0].strip()
        score = float(p[1])
        if name:
            name = re.sub(r"\s+", " ", name)
            result.append((name, score))
    return result

def extract_numbers(text):
    nums = re.findall(r"\d+(?:\.\d+)?", str(text))
    return [float(n) for n in nums]

def get_team_speaks(row, col):
    text = row.get(col, "")
    pairs = extract_name_score_pairs(text)
    if pairs:
        return sum(score for _, score in pairs)
    nums = extract_numbers(text)
    return sum(nums) if nums else 0.0

# -----------------------
# Sidebar: Add tournaments
# -----------------------
st.sidebar.header("Add / Manage Tournaments")
tname = st.sidebar.text_input("Tournament name (e.g. MinneApple)", key="tinput")
uploaded = st.sidebar.file_uploader(
    "Upload round CSVs for this tournament (select multiple)", 
    accept_multiple_files=True, type=["csv"], key="upload"
)
append_or_overwrite = st.sidebar.radio("If tournament exists:", ("Append rounds to existing", "Overwrite existing tournament"), index=0)

if st.sidebar.button("Add Tournament"):
    if not tname:
        st.sidebar.error("Please enter a tournament name.")
    elif not uploaded:
        st.sidebar.error("Please upload at least one round CSV.")
    else:
        rounds = []
        for f in uploaded:
            try:
                df = pd.read_csv(f)
            except Exception:
                try:
                    df = pd.read_csv(f, engine="python")
                except Exception as e2:
                    st.sidebar.error(f"Failed to read {f.name}: {e2}")
                    continue
            df = clean_columns(df)
            rounds.append(df)
        if not rounds:
            st.sidebar.error("No valid CSVs uploaded.")
        else:
            if tname in st.session_state.tournaments and append_or_overwrite.startswith("Append"):
                st.session_state.tournaments[tname].extend(rounds)
                st.sidebar.success(f"Appended {len(rounds)} rounds to '{tname}'. Now has {len(st.session_state.tournaments[tname])} rounds.")
            else:
                st.session_state.tournaments[tname] = rounds
                st.sidebar.success(f"Stored {len(rounds)} rounds for '{tname}'.")
        st.session_state.upload = None

# Show current tournaments
st.sidebar.markdown("### Uploaded tournaments")
if st.session_state.tournaments:
    for name in list(st.session_state.tournaments.keys()):
        cols = st.sidebar.columns((3,1))
        cols[0].write(f"**{name}** — {len(st.session_state.tournaments[name])} rounds")
        if cols[1].button("Remove", key=f"rm_{name}"):
            del st.session_state.tournaments[name]
            st.sidebar.success(f"Removed tournament {name}")
            st.experimental_rerun()
else:
    st.sidebar.write("_No tournaments uploaded yet._")

st.sidebar.markdown("---")
st.sidebar.markdown("Tips:\n- Upload all round CSVs for a tournament at once.\n- Header names may vary; the app will attempt to detect Aff/Neg points & speakers.")

# -----------------------
# Main area: Process & Analysis
# -----------------------
st.markdown("## Manage & Process")
st.write("Add tournaments on the left. When ready, click **Process All Tournaments** to compute per-tournament leaderboards and cross-tournament rankings.")

if st.button("🚀 Process All Tournaments"):
    if not st.session_state.tournaments:
        st.error("No tournaments available. Please add at least one tournament from the sidebar.")
        st.stop()

    # Cross-tournament aggregators
    cross_team_wins = defaultdict(int)
    cross_team_rounds = defaultdict(int)
    cross_team_speaks_total = defaultdict(float)
    cross_speaker_speaks_total = defaultdict(float)
    cross_speaker_rounds_total = defaultdict(int)

    for tournament_name, rounds in st.session_state.tournaments.items():
        st.header(f"🏟️ Tournament: {tournament_name}")

        # Reset per-tournament variables
        team_wins = defaultdict(int)
        team_rounds = defaultdict(int)
        team_speaks = defaultdict(float)
        speaker_total_speaks = defaultdict(float)
        speaker_rounds = defaultdict(int)
        speaker_wins = defaultdict(int)

        # Process each round
        for df in rounds:
            cols = df.columns.tolist()
            aff_col = find_best_column(cols, ["aff"])
            neg_col = find_best_column(cols, ["neg"])
            win_col = find_best_column(cols, ["win"])
            aff_points_col = find_best_column(cols, ["aff","point"])
            neg_points_col = find_best_column(cols, ["neg","point"])

            if not aff_col or not neg_col:
                st.warning(f"Could not find Aff/Neg columns in a round of {tournament_name}. Skipping this round.")
                continue

            for _, row in df.iterrows():
                aff_team = str(row.get(aff_col, "")).strip()
                neg_team = str(row.get(neg_col, "")).strip()
                winner_val = str(row.get(win_col, "")).strip() if win_col else ""
                aff_win = 1 if winner_val.lower().startswith("aff") else 0
                neg_win = 1 if winner_val.lower().startswith("neg") else 0

                aff_team_speaks_round = get_team_speaks(row, aff_points_col) if aff_points_col else 0
                neg_team_speaks_round = get_team_speaks(row, neg_points_col) if neg_points_col else 0

                # Team aggregation
                if aff_team:
                    team_wins[aff_team] += aff_win
                    team_rounds[aff_team] += 1
                    team_speaks[aff_team] += aff_team_speaks_round
                if neg_team:
                    team_wins[neg_team] += neg_win
                    team_rounds[neg_team] += 1
                    team_speaks[neg_team] += neg_team_speaks_round

                # Speaker aggregation
                # For simplicity, assume 2 speakers per team equally share points if names not given
                if aff_points_col:
                    aff_nums = extract_numbers(row.get(aff_points_col, ""))
                    if aff_nums:
                        per_speaker = sum(aff_nums)/len(aff_nums)/2
                        speaker_total_speaks[f"{aff_team} Speaker 1"] += per_speaker
                        speaker_total_speaks[f"{aff_team} Speaker 2"] += per_speaker
                        speaker_rounds[f"{aff_team} Speaker 1"] += 1
                        speaker_rounds[f"{aff_team} Speaker 2"] += 1
                if neg_points_col:
                    neg_nums = extract_numbers(row.get(neg_points_col, ""))
                    if neg_nums:
                        per_speaker = sum(neg_nums)/len(neg_nums)/2
                        speaker_total_speaks[f"{neg_team} Speaker 1"] += per_speaker
                        speaker_total_speaks[f"{neg_team} Speaker 2"] += per_speaker
                        speaker_rounds[f"{neg_team} Speaker 1"] += 1
                        speaker_rounds[f"{neg_team} Speaker 2"] += 1

        # -----------------------
        # Per-tournament team leaderboard
        # -----------------------
        team_rows = []
        for team in team_rounds:
            wins = team_wins[team]
            rounds_played = team_rounds[team]
            speaks = team_speaks[team]
            win_pct = wins / rounds_played if rounds_played else 0
            team_rows.append({
                "Team": team,
                "Wins": wins,
                "Rounds": rounds_played,
                "Win%": round(win_pct, 3),
                "Total Speaks": round(speaks, 2)
            })
            cross_team_wins[team] += wins
            cross_team_rounds[team] += rounds_played
            cross_team_speaks_total[team] += speaks

        team_df = pd.DataFrame(team_rows)
        if not team_df.empty:
            team_df = team_df.sort_values(by=["Win%", "Total Speaks"], ascending=[False, False]).reset_index(drop=True)
            st.subheader("🏅 Team Leaderboard (this tournament)")
            st.dataframe(team_df)
        else:
            st.info("No valid team data for this tournament.")

        # -----------------------
        # Per-tournament speaker leaderboard
        # -----------------------
        speaker_rows = []
        for speaker, speaks in speaker_total_speaks.items():
            rounds_played = speaker_rounds[speaker]
            avg = speaks / rounds_played if rounds_played else 0
            speaker_rows.append({
                "Speaker": speaker,
                "Total Speaks": round(speaks,2),
                "Rounds": rounds_played,
                "Average": round(avg,2)
            })
            cross_speaker_speaks_total[speaker] += speaks
            cross_speaker_rounds_total[speaker] += rounds_played

        speaker_df = pd.DataFrame(speaker_rows)
        if not speaker_df.empty:
            speaker_df = speaker_df.sort_values(by=["Total Speaks", "Average"], ascending=[False, False]).reset_index(drop=True)
            st.subheader("🏅 Speaker Leaderboard (this tournament)")
            st.dataframe(speaker_df)
        else:
            st.info("No valid speaker data for this tournament.")

    # -----------------------
    # Cross-tournament rankings
    # -----------------------
    st.header("🌐 Cross-Tournament Rankings")

    # Top Teams
    cross_team_rows = []
    for team, rounds_played in cross_team_rounds.items():
        wins = cross_team_wins[team]
        speaks = cross_team_speaks_total[team]
        win_pct = wins / rounds_played if rounds_played else 0
        cross_team_rows.append({
            "Team": team,
            "Wins": wins,
            "Rounds": rounds_played,
            "Win%": round(win_pct,3),
            "Total Speaks": round(speaks,2)
        })
    cross_team_df = pd.DataFrame(cross_team_rows)
    if not cross_team_df.empty:
        cross_team_df = cross_team_df.sort_values(by=["Win%", "Total Speaks"], ascending=[False, False]).reset_index(drop=True)
        st.subheader("🏆 Top Teams Across Tournaments")
        st.dataframe(cross_team_df)
    else:
        st.info("No team data across tournaments.")

    # Top Speakers
    cross_speaker_rows = []
    for speaker, total_speaks in cross_speaker_speaks_total.items():
        rounds_played = cross_speaker_rounds_total[speaker]
        avg = total_speaks / rounds_played if rounds_played else 0
        cross_speaker_rows.append({
            "Speaker": speaker,
            "Total Speaks": round(total_speaks,2),
            "Rounds": rounds_played,
            "Average": round(avg,2)
        })
    cross_speaker_df = pd.DataFrame(cross_speaker_rows)
    if not cross_speaker_df.empty:
        cross_speaker_df = cross_speaker_df.sort_values(by=["Total Speaks","Average"], ascending=[False, False]).reset_index(drop=True)
        st.subheader("🏆 Top Speakers Across Tournaments")
        st.dataframe(cross_speaker_df)
    else:
        st.info("No speaker data across tournaments.")

    st.success("✅ Processing complete!")
