# app.py
import streamlit as st
import pandas as pd
import re
from collections import defaultdict

st.set_page_config(page_title="Debate Tournament Analyzer", layout="wide")
st.title("🏆 Debate Tournament Analyzer (Multi-Tournament, Tabroom CSVs)")

# -----------------------
# Utilities: parsing & cleaning
# -----------------------
def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to reduce header variability from Tabroom."""
    cols = df.columns.astype(str)
    cols = cols.str.strip()
    cols = cols.str.replace(r"\s+", " ", regex=True)   # collapse whitespace & tabs to single space
    cols = cols.str.replace('"', "")
    df.columns = cols
    return df

def find_column(columns, *keywords):
    """Find a column name that contains all keywords (case-insensitive). Returns None if not found."""
    cols = list(columns)
    for col in cols:
        low = col.lower()
        if all(k.lower() in low for k in keywords):
            return col
    return None

# robust name-score extraction: returns list of (name,score) pairs found in a text blob
def extract_name_score_pairs(text):
    text = str(text)
    # find pairs like "Name    29.5" possibly repeated; name may contain letters, periods, apostrophes, hyphens
    # We will find all numbers, and then look backwards for the name just before the number.
    num_pattern = r"(\d+(?:\.\d+)?)"
    # Find all occurrences of "some text" followed by whitespace then a number
    # We'll use a regex that captures "name (lots of non-digit chars) number"
    pattern = re.compile(r"([A-Za-z\.\'\-\s]{2,}?)\s+" + num_pattern)
    pairs = pattern.findall(text)
    # pattern.findall returns list of tuples (name, number)
    result = []
    for p in pairs:
        name = p[0].strip()
        score = float(p[1])
        if name:
            # cleanup a bit: collapse multiple spaces in name
            name = re.sub(r"\s+", " ", name)
            result.append((name, score))
    return result

# fallback: extract all numbers (averaging) if names are not parseable
def extract_numbers(text):
    nums = re.findall(r"\d+(?:\.\d+)?", str(text))
    return [float(n) for n in nums]

# -----------------------
# Session state initialization
# -----------------------
if "tournaments" not in st.session_state:
    # structure: { tournament_name: [ list_of_round_dfs ] }
    st.session_state.tournaments = {}

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
        # read each CSV, clean columns, and store list
        rounds = []
        for f in uploaded:
            try:
                df = pd.read_csv(f)
            except Exception as e:
                # try with engine python if needed
                try:
                    df = pd.read_csv(f, engine="python")
                except Exception as e2:
                    st.sidebar.error(f"Failed to read {f.name}: {e}")
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

    # clear uploader widget workaround by resetting the key (Streamlit quirk)
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

    # Aggregators for cross-tournament stats
    cross_team_wins = defaultdict(int)
    cross_team_rounds = defaultdict(int)
    cross_team_speaks_total = defaultdict(float)  # total speaks sum across tournaments
    cross_team_tournaments_attended = defaultdict(int)  # number of tournaments where team appeared

    cross_speaker_speaks_by_tournament = defaultdict(lambda: defaultdict(float))
    cross_speaker_rounds_by_tournament = defaultdict(lambda: defaultdict(int))
    # For per-speaker wins: count wins and rounds
    cross_speaker_wins = defaultdict(int)
    cross_speaker_rounds = defaultdict(int)

    # Process each tournament individually and display tables
    for tournament_name, rounds in st.session_state.tournaments.items():
        st.header(f"🏟️ Tournament: {tournament_name}")

        # per-tournament accumulators
        team_wins = defaultdict(int)
        team_rounds = defaultdict(int)
        team_speaks = defaultdict(float)   # sum of speaks across rounds (both partners combined)

        speaker_total_speaks = defaultdict(float)  # sum of speaks for that tournament (per speaker)
        speaker_rounds = defaultdict(int)
        speaker_wins = defaultdict(int)

        # For each round dataframe in this tournament
        for df in rounds:
            # try to detect useful columns
            cols = df.columns.tolist()
            # Candidate team columns (Aff, Neg)
            aff_col = find_column(cols, "aff") or find_column(cols, "aff ", "team") or find_column(cols, "aff", "team")
            neg_col = find_column(cols, "neg") or find_column(cols, "neg ", "team") or find_column(cols, "neg", "team")
            win_col = find_column(cols, "win") or find_column(cols, "winner")

            # Candidate points columns (aff points / neg points)
            aff_points_col = next((c for c in cols if "aff" in c.lower() and "point" in c.lower()), None)
            neg_points_col = next((c for c in cols if "neg" in c.lower() and "point" in c.lower()), None)
            # fallback names
            if not aff_col:
                aff_col = next((c for c in cols if c.lower().startswith("aff")), None)
            if not neg_col:
                neg_col = next((c for c in cols if c.lower().startswith("neg")), None)
            if not win_col:
                win_col = next((c for c in cols if "win" in c.lower()), None)

            # If we still don't find teams, try common names
            if not aff_col or not neg_col:
                st.warning(f"Could not detect Aff/Neg team columns reliably in one round of {tournament_name}. Columns: {cols}")
                continue

            # iterate rows
            for _, row in df.iterrows():
                try:
                    aff_team = str(row.get(aff_col, "")).strip()
                    neg_team = str(row.get(neg_col, "")).strip()
                except Exception:
                    continue

                # decide winner
                winner_val = str(row.get(win_col, "")).strip() if win_col else ""
                aff_win = 1 if winner_val.lower().startswith("aff") else 0
                neg_win = 1 if winner_val.lower().startswith("neg") else 0

                # extract points & name-score pairs
                aff_blob = row.get(aff_points_col, "") if aff_points_col else ""
                neg_blob = row.get(neg_points_col, "") if neg_points_col else ""

                aff_pairs = extract_name_score_pairs(aff_blob)
                neg_pairs = extract_name_score_pairs(neg_blob)

                # If name-score pairs empty, fallback to numbers only (split evenly if necessary)
                if not aff_pairs:
                    aff_nums = extract_numbers(aff_blob)
                    if aff_nums:
                        # take average as team speaks for this round, and distribute equally among 2 speakers if we can't get names
                        team_aff_speaks = sum(aff_nums)/len(aff_nums)
                        aff_pairs = [("Aff Speaker 1", team_aff_speaks/2), ("Aff Speaker 2", team_aff_speaks/2)]
                if not neg_pairs:
                    neg_nums = extract_numbers(neg_blob)
                    if neg_nums:
                        team_neg_speaks = sum(neg_nums)/len(neg_nums)
                        neg_pairs = [("Neg Speaker 1", team_neg_speaks/2), ("Neg Speaker 2", team_neg_speaks/2)]

                # Team speaks this round = sum of partner scores
                aff_team_speaks_round = sum(score for _, score in aff_pairs) if aff_pairs else 0.0
                neg_team_speaks_round = sum(score for _, score in neg_pairs) if neg_pairs else 0.0

                # Update team aggregates
                if aff_team:
                    team_wins[aff_team] += aff_win
                    team_rounds[aff_team] += 1
                    team_speaks[aff_team] += aff_team_speaks_round
                if neg_team:
                    team_wins[neg_team] += neg_win
                    team_rounds[neg_team] += 1
                    team_speaks[neg_team] += neg_team_speaks_round

                # Update speaker aggregates for this tournament
                for name, score in aff_pairs:
                    name = name.strip()
                    if not name:
                        continue
                    speaker_total_speaks[name] += score
                    speaker_rounds[name] += 1
                    # speaker wins: if team won, count a win for each speaker on that team this round
                    if aff_win:
                        speaker_wins[name] += 1
                for name, score in neg_pairs:
                    name = name.strip()
                    if not name:
                        continue
                    speaker_total_speaks[name] += score
                    speaker_rounds[name] += 1
                    if neg_win:
                        speaker_wins[name] += 1

        # Build per-tournament team table
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
            # For cross-tournament aggregators
            cross_team_wins[team] += wins
            cross_team_rounds[team] += rounds_played
            cross_team_speaks_total[team] += speaks

        team_df = pd.DataFrame(team_rows)
        if not team_df.empty:
            # sort by win% desc, tie -> total speaks desc
            team_df = team_df.sort_values(by=["Win%", "Total Speaks"], ascending=[False, False]).reset_index(drop=True)
            st.subheader("🏅 Team Leaderboard (this tournament)")
            st.dataframe(team_df)
        else:
            st.info("No team data collected for this tournament (check CSV headers).")

        # Build per-tournament speaker table (total speaks across rounds in tournament)
        speaker_rows = []
        for name, total in speaker_total_speaks.items():
            speaker_rows.append({
                "Speaker": name,
                "Total Speaks (This Tournament)": round(total, 2),
                "Rounds": speaker_rounds.get(name, 0),
                "Wins": speaker_wins.get(name, 0)
            })
            # cross-tourney accumulators: record this tournament's total for averaging later
            cross_speaker_speaks_by_tournament[name][tournament_name] = cross_speaker_speaks_by_tournament[name].get(tournament_name, 0.0) + total
            cross_speaker_rounds_by_tournament[name][tournament_name] = cross_speaker_rounds_by_tournament[name].get(tournament_name, 0) + speaker_rounds.get(name, 0)
            cross_speaker_wins[name] += speaker_wins.get(name, 0)
            cross_speaker_rounds[name] += speaker_rounds.get(name, 0)

        speaker_df = pd.DataFrame(speaker_rows)
        if not speaker_df.empty:
            speaker_df = speaker_df.sort_values(by="Total Speaks (This Tournament)", ascending=False).reset_index(drop=True)
            st.subheader("🎤 Speaker Leaderboard (this tournament)")
            st.dataframe(speaker_df)
        else:
            st.info("No speaker data collected for this tournament.")

        # Mark that teams attended this tournament (for averaging)
        for team in team_rounds.keys():
            cross_team_tournaments_attended[team] += 1

        st.markdown("---")

    # -----------------------
    # Cross-tournament leaderboards
    # -----------------------
    st.header("🌍 Cross-Tournament Rankings")

    # Teams: overall win% (tie -> total speaks across tournaments)
    cross_team_rows = []
    for team, wins in cross_team_wins.items():
        rounds = cross_team_rounds.get(team, 0)
        speaks = cross_team_speaks_total.get(team, 0.0)
        tournaments_attended = cross_team_tournaments_attended.get(team, 0)
        win_pct = wins / rounds if rounds > 0 else 0.0
        # For the user's request for per-tournament averaging of speaks when comparing? 
        # They asked: teams ranked by win% then speaker points for all tournaments — we'll use total speaks across tournaments for tie-break.
        cross_team_rows.append({
            "Team": team,
            "Wins": wins,
            "Rounds": rounds,
            "Win%": round(win_pct, 4),
            "Total Speaks (All Tournaments)": round(speaks, 2),
            "Tournaments Attended": tournaments_attended
        })

    cross_team_df = pd.DataFrame(cross_team_rows)
    if not cross_team_df.empty:
        cross_team_df = cross_team_df.sort_values(by=["Win%", "Total Speaks (All Tournaments)"], ascending=[False, False]).reset_index(drop=True)
        st.subheader("🏆 Best Teams Across All Tournaments")
        st.dataframe(cross_team_df)
    else:
        st.info("No cross-tournament team data available.")

    # Speakers: compute per-tournament totals then average across tournaments attended
    speaker_overall_rows = []
    for name, tournament_map in cross_speaker_speaks_by_tournament.items():
        # tournament_map: {tournament_name: total_speaks_in_that_tournament}
        tournaments_attended = len(tournament_map)
        if tournaments_attended == 0:
            continue
        total_sum = sum(tournament_map.values())
        avg_per_tournament = total_sum / tournaments_attended
        wins = cross_speaker_wins.get(name, 0)
        rounds_total = cross_speaker_rounds.get(name, 0)
        win_pct = wins / rounds_total if rounds_total > 0 else 0.0
        speaker_overall_rows.append({
            "Speaker": name,
            "Avg Speaks per Tournament": round(avg_per_tournament, 3),
            "Total Speaks (All Tournaments)": round(total_sum, 2),
            "Tournaments Attended": tournaments_attended,
            "Win% (overall)": round(win_pct, 4)
        })

    speaker_overall_df = pd.DataFrame(speaker_overall_rows)
    if not speaker_overall_df.empty:
        # sort by avg speaks desc, tie -> overall win% desc
        speaker_overall_df = speaker_overall_df.sort_values(by=["Avg Speaks per Tournament", "Win% (overall)"], ascending=[False, False]).reset_index(drop=True)
        st.subheader("🎙️ Best Speakers Across All Tournaments (Avg per Tournament)")
        st.dataframe(speaker_overall_df)
    else:
        st.info("No cross-tournament speaker data available.")

    st.success("✅ Done! All results processed.")

# -----------------------
# End UI
# -----------------------
st.markdown("---")
st.write("Questions / next steps: I can add export buttons, filters (limit top N), or a compact leaderboard view. Want any of those?")
