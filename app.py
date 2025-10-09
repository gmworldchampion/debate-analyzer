# app.py
import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="Debate Skill Ranking", layout="wide")
st.title("Debate Skill Ranking App")

# ----------------------------
# USER INPUT
# ----------------------------
st.sidebar.header("Settings")
num_recent_tournaments = st.sidebar.number_input(
    "Number of recent tournaments to consider", min_value=1, max_value=10, value=2
)

uploaded_files = st.sidebar.file_uploader(
    "Upload Tabroom CSVs (multiple)", type="csv", accept_multiple_files=True
)

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------

def extract_names_points(cell):
    """Extract list of (name, points) from the CSV cell."""
    # Matches sequences like "First Last 29.5"
    pattern = r'([A-Z][A-Za-z\-\']+(?:\s[A-Z][A-Za-z\-\']+)*)\s+(\d+\.?\d*)'
    matches = re.findall(pattern, str(cell))
    return [(m[0].strip(), float(m[1])) for m in matches]

def parse_csv(file):
    """Parse CSV into standard format."""
    df = pd.read_csv(file)
    tournament_name = file.name.split(".")[0]
    records = []

    for _, row in df.iterrows():
        # Aff side
        aff_entries = extract_names_points(row.get('Aff								Points', ''))
        aff_names = [n for n, _ in aff_entries]
        aff_points = [p for _, p in aff_entries]

        # Neg side
        neg_entries = extract_names_points(row.get('Neg								Points', ''))
        neg_names = [n for n, _ in neg_entries]
        neg_points = [p for _, p in neg_entries]

        winner = row['Win']

        for i, name in enumerate(aff_names):
            records.append({
                'Individual': name,
                'School': row['Aff'],
                'Partner': [n for n in aff_names if n != name],
                'Win': 1 if winner == 'Aff' else 0,
                'Points': aff_points[i],
                'Tournament': tournament_name
            })

        for i, name in enumerate(neg_names):
            records.append({
                'Individual': name,
                'School': row['Neg'],
                'Partner': [n for n in neg_names if n != name],
                'Win': 1 if winner == 'Neg' else 0,
                'Points': neg_points[i],
                'Tournament': tournament_name
            })

    return pd.DataFrame(records)

def aggregate_individuals(df, recent_n):
    tournaments = df['Tournament'].unique()[-recent_n:]
    df_recent = df[df['Tournament'].isin(tournaments)]

    skill_df = df_recent.groupby('Individual').agg(
        Wins=('Win', 'sum'),
        Rounds=('Win', 'count'),
        AvgPoints=('Points', 'mean')
    ).reset_index()
    skill_df['WinRate'] = skill_df['Wins'] / skill_df['Rounds']
    skill_df['SkillScore'] = skill_df['AvgPoints'] * skill_df['WinRate']

    # Sorting with tie-breakers
    skill_df = skill_df.sort_values(
        by=['SkillScore', 'Wins', 'WinRate', 'AvgPoints'],
        ascending=False
    ).reset_index(drop=True)

    return skill_df

def aggregate_teams(df, recent_n):
    tournaments = df['Tournament'].unique()[-recent_n:]
    df_recent = df[df['Tournament'].isin(tournaments)]

    team_dict = {}

    for _, row in df_recent.iterrows():
        for partner in row['Partner']:
            duo = tuple(sorted([row['Individual'], partner]))
            if duo not in team_dict:
                team_dict[duo] = {'Points': [], 'Wins': []}
            team_dict[duo]['Points'].append(row['Points'])
            team_dict[duo]['Wins'].append(row['Win'])

    teams = []
    for duo, metrics in team_dict.items():
        avg_points = np.mean(metrics['Points'])
        wins = sum(metrics['Wins'])
        rounds = len(metrics['Wins'])
        win_rate = wins / rounds if rounds > 0 else 0
        skill_score = avg_points * win_rate
        teams.append({
            'Member1': duo[0],
            'Member2': duo[1],
            'Wins': wins,
            'Rounds': rounds,
            'WinRate': win_rate,
            'TeamSkill': skill_score
        })

    team_df = pd.DataFrame(teams)
    team_df = team_df.sort_values(
        by=['TeamSkill', 'Wins', 'WinRate'],
        ascending=False
    ).reset_index(drop=True)
    return team_df

# ----------------------------
# MAIN APP
# ----------------------------
if uploaded_files:
    # Parse CSVs tournament by tournament
    all_dfs = [parse_csv(f) for f in uploaded_files]
    full_df = pd.concat(all_dfs, ignore_index=True)

    # Final rankings only
    st.subheader("Top Individuals")
    ind_df = aggregate_individuals(full_df, num_recent_tournaments)
    st.dataframe(ind_df)

    st.subheader("Top Teams (Duos)")
    team_df = aggregate_teams(full_df, num_recent_tournaments)
    st.dataframe(team_df)

else:
    st.info("Upload CSV files to generate rankings.")
