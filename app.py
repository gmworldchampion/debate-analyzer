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
selected_school = st.sidebar.multiselect("Filter by school", [])

uploaded_files = st.sidebar.file_uploader(
    "Upload Tabroom CSVs (multiple)", type="csv", accept_multiple_files=True
)

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------

def extract_names_points(cell):
    """Extract list of (name, points) from the CSV cell."""
    pattern = r'([A-Z][A-Za-z\-\']+(?:\s[A-Z][A-Za-z\-\']+)*)\s+(\d+\.?\d*)'
    matches = re.findall(pattern, str(cell))
    return [(m[0].strip(), float(m[1])) for m in matches]

def infer_level_from_year(filename):
    """Infer level from tournament year in filename or rules you provide."""
    # Example: Varsity = current year, JV = last year, Novice = two years ago
    # Adjust as needed
    import datetime
    year = int(re.findall(r'(\d{4})', filename)[0]) if re.findall(r'(\d{4})', filename) else 2025
    current_year = datetime.datetime.now().year
    if year == current_year:
        return 'Varsity', 3
    elif year == current_year - 1:
        return 'JV', 2
    else:
        return 'Novice', 1

def parse_csv(file):
    """Parse CSV into standardized format with level weighting."""
    df = pd.read_csv(file)
    tournament_name = file.name.split(".")[0]
    level, level_weight = infer_level_from_year(file.name)
    records = []

    for _, row in df.iterrows():
        aff_entries = extract_names_points(row.get('Aff								Points', ''))
        neg_entries = extract_names_points(row.get('Neg								Points', ''))
        aff_names = [n for n, _ in aff_entries]
        neg_names = [n for n, _ in neg_entries]
        aff_points = [p for _, p in aff_entries]
        neg_points = [p for _, p in neg_entries]

        winner = row['Win']

        for i, name in enumerate(aff_names):
            records.append({
                'Individual': name,
                'School': row['Aff'],
                'Partner': [n for n in aff_names if n != name],
                'Win': 1 if winner == 'Aff' else 0,
                'Points': aff_points[i],
                'Tournament': tournament_name,
                'LevelWeight': level_weight
            })
        for i, name in enumerate(neg_names):
            records.append({
                'Individual': name,
                'School': row['Neg'],
                'Partner': [n for n in neg_names if n != name],
                'Win': 1 if winner == 'Neg' else 0,
                'Points': neg_points[i],
                'Tournament': tournament_name,
                'LevelWeight': level_weight
            })
    return pd.DataFrame(records)

def aggregate_individuals(df, recent_n):
    tournaments = df['Tournament'].unique()[-recent_n:]
    df_recent = df[df['Tournament'].isin(tournaments)].copy()
    
    # Apply recency weighting: most recent tournament weight = 1.0, previous = 0.8, etc.
    tournament_weights = {t: 1.0 - 0.2*i for i, t in enumerate(reversed(tournaments))}
    df_recent['RecencyWeight'] = df_recent['Tournament'].map(tournament_weights)
    
    df_recent['WeightedScore'] = df_recent['Points'] * df_recent['Win'] * df_recent['LevelWeight'] * df_recent['RecencyWeight']
    
    skill_df = df_recent.groupby('Individual').agg(
        Wins=('Win', 'sum'),
        Rounds=('Win', 'count'),
        AvgPoints=('Points', 'mean'),
        SkillScore=('WeightedScore', 'sum')
    ).reset_index()
    skill_df['WinRate'] = skill_df['Wins'] / skill_df['Rounds']
    
    # Sorting with tie-breakers
    skill_df = skill_df.sort_values(
        by=['SkillScore', 'Wins', 'WinRate', 'AvgPoints'],
        ascending=False
    ).reset_index(drop=True)
    
    # Filter by school if selected
    if selected_school:
        skill_df = skill_df[skill_df['Individual'].isin(df[df['School'].isin(selected_school)]['Individual'])]
    
    return skill_df

def aggregate_teams(df, recent_n):
    tournaments = df['Tournament'].unique()[-recent_n:]
    df_recent = df[df['Tournament'].isin(tournaments)].copy()
    tournament_weights = {t: 1.0 - 0.2*i for i, t in enumerate(reversed(tournaments))}
    df_recent['RecencyWeight'] = df_recent['Tournament'].map(tournament_weights)

    team_dict = {}
    for _, row in df_recent.iterrows():
        for partner in row['Partner']:
            duo = tuple(sorted([row['Individual'], partner]))
            if duo not in team_dict:
                team_dict[duo] = {'Points': [], 'Wins': [], 'Weights': []}
            team_dict[duo]['Points'].append(row['Points'])
            team_dict[duo]['Wins'].append(row['Win'])
            team_dict[duo]['Weights'].append(row['LevelWeight'] * row['RecencyWeight'])
    
    teams = []
    for duo, metrics in team_dict.items():
        weighted_points = [p * w for p, w in zip(metrics['Points'], metrics['Weights'])]
        avg_points = np.sum(weighted_points) / sum(metrics['Weights'])
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
    all_dfs = [parse_csv(f) for f in uploaded_files]
    full_df = pd.concat(all_dfs, ignore_index=True)

    st.subheader("Top Individuals")
    ind_df = aggregate_individuals(full_df, num_recent_tournaments)
    st.dataframe(ind_df)

    st.subheader("Top Teams (Duos)")
    team_df = aggregate_teams(full_df, num_recent_tournaments)
    st.dataframe(team_df)

else:
    st.info("Upload CSV files to generate rankings.")
