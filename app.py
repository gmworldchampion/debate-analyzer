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
# Utilities: parsing & cleaning
# -----------------------
def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = df.columns.astype(str)
    cols = cols.str.strip()
    cols = cols.str.replace(r"\s+", " ", regex=True)
    cols = cols.str.replace('"', "")
    df.columns = cols
    return df

def find_column(columns, *keywords):
    cols = list(columns)
    for col in cols:
        low = col.lower()
        if all(k.lower() in low for k in keywords):
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

# -----------------------
# UI: Add tournament
# -----------------------
st.sidebar.header("Add / Manage Tournaments")
tname = st.sidebar.text_input("Tournament name (e.g. MinneApple)", key="tinput")
uploaded = st.sidebar.file_uploader("Upload round CSVs for this tournament (select multiple)", accept_multiple_files=True, type=["csv"], key="upload")
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
        # Clear uploader safely
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
st.sidebar.markdown("Tips:\n- Upload all round CSVs for a tournament at once.\n- If header names look messy, this app will attempt to detect Af/Neg points & speakers.")

# -----------------------
# Main area: Process / Analysis
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
    cross_team_tournaments_attended = defaultdict(int)
    cross_speaker_speaks_by_tournament = defaultdict(lambda: defaultdict(float))
    cross_speaker_rounds_by_tournament = defaultdict(lambda: defaultdict(int))
    cross_speaker_wins = defaultdict(int)
    cross_speaker_rounds = defaultdict(int)

    for tournament_name, rounds in st.session_state.tournaments.items():
        st.header(f"🏟️ Tournament: {tournament_name}")
        team_wins = defaultdict(int)
        team_rounds = defaultdict(int)
        team_speaks = defaultdict(float)
        speaker_total_speaks = defaultdict(float)
        speaker_rounds = defaultdict(int)
        speaker_wins = defaultdict(int)

        for df in rounds:
            cols = df.columns.tolist()
            aff_col = find_column(cols, "aff") or find_column(cols, "aff", "team")
            neg_col = find_column(cols, "neg") or find_column(cols, "neg", "team")
            win_col = find_column(cols, "win") or find_column(cols, "winner")
            aff_points_col = next((c for c in cols if "aff" in c.lower() and "point" in c.lower()), None)
            neg_points_col = next((c for c in cols if "neg" in c.lower() and "point" in c.lower()), None)
            if not aff_col:
                aff_col = next((c for c in cols if c.lower().startswith("aff")), None)
            if not neg_col:
                neg_col = next((c for c in cols if c.lower().startswith("neg")), None)

            for _, row in df.iterrows():
                aff_team = str(row.get(aff_col, "")).strip()
                neg_team = str(row.get(neg_col, "")).strip()
                winner_val = str(row.get(win_col, "")).strip() if win_col else ""
                aff_win = 1 if winner_val.lower().startswith("aff") else 0
                neg_win = 1 if winner_val.lower().startswith("neg") else 0

                aff_blob = row.get(aff_points_col, "") if aff_points_col else ""
                neg_blob = row.get(neg_points_col, "") if neg_points_col else ""

                aff_pairs = extract_name_score_pairs(aff_blob)
                neg_pairs = extract_name_score_pairs(neg_blob)

                if not aff_pairs:
                    aff_nums = extract_numbers(aff_blob)
                    if aff_nums:
                        team_aff_speaks = sum(aff_nums)/len(aff_nums)
                        aff_pairs = [("Aff Speaker 1", team_aff_speaks/2), ("Aff Speaker 2", team_aff_speaks/2)]
                if not neg_pairs:
                    neg_nums = extract_numbers(neg_blob)
                    if neg_nums:
                        team_neg_speaks = sum(neg_nums)/len(neg_nums)
                        neg_pairs = [("Neg Speaker 1", team_neg_speaks/2), ("Neg Speaker 2", team_neg_speaks/2)]

                aff_team_speaks_round = sum(score for _, score in aff_pairs) if aff_pairs else 0.0
                neg_team_speaks_round = sum(score for _, score in neg_pairs) if neg_pairs else 0.0

                if aff_team:
                    team_wins[aff_team] += aff_win
                    team_rounds[aff_team] += 1
                    team_speaks[aff_team] += aff_team_speaks_round
                if neg_team:
                    team_wins[neg_team] += neg_win
                    team_rounds[neg_team] += 1
                    team_speaks[neg_team] += neg_team_speaks_round

                for name, score in aff_pairs:
                    name = name.strip()
                    if name:
                        speaker_total_speaks[name] += score
                        speaker_rounds[name] += 1
                        if aff_win:
                            speaker_wins[name] += 1
                for name, score in neg_pairs:
                    name = name.strip()
                    if name:
                        speaker_total_speaks[name] += score
                        speaker_rounds[name] += 1
                        if neg_win:
                            speaker_wins[name] += 1

        # Per-tournament team leaderboard
        team_rows = []
        for team in team_rounds:
            wins = team_wins.get(team, 0)
            rounds_played = team_rounds.get(team, 0)
            speaks = team_speaks.get(team, 0.0)
            win_pct = wins / rounds_played if rounds_played > 0 else 0.0
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

        speaker_rows = []
        for name, total in speaker_total_speaks.items():
            speaker_rows

