# app.py
import streamlit as st
import pandas as pd
import numpy as np

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

def parse_csv(file):
    """
    Parse Tabroom CSV into standardized format:
    Columns: Individual, School, Partner, Win, PtsPm-1HL, PtsPm-2HL, PtsPM, Z1, OSdPm, RandPm, Tournament, Level
    """
    df = pd.read_csv(file)
    records = []
    tournament_name = file.name.split(".")[0]
    
    for idx, row in df.iterrows():
        winner = row['Win']
        aff_names = row['Aff'].split()  # Simplified parsing, may need adjustment
        neg_names = row['Neg'].split()
        # For simplicity, points are parsed as numeric averages
        aff_points = np.mean([float(p) for p in str(row.get('Aff Points', "0")).split() if p.strip().replace('.', '').isdigit()])
        neg_points = np.mean([float(p) for p in str(row.get('Neg Points', "0")).split() if p.strip().replace('.', '').isdigit()])
        
        for name in aff_names:
            records.append({
                "Individual": name.strip(),
                "School": row['Aff'],
                "Partner": [n for n in aff_names if n != name],
                "Win": 1 if winner == "Aff" else 0,
                "Points": aff_points,
                "Tournament": tournament_name,
            })
        for name in neg_names:
            records.append({
                "Individual": name.strip(),
                "School": row['Neg'],
                "Partner": [n for n in neg_names if n != name],
                "Win": 1 if winner == "Neg" else 0,
                "Points": neg_points,
                "Tournament": tournament_name,
            })
    return pd.DataFrame(records)

def calculate_individual_skill(df, recent_n):
    """
    Calculates weighted individual skill based on last N tournaments
    """
    # Only last N tournaments
    tournaments = df['Tournament'].unique()[-recent_n:]
    df_recent = df[df['Tournament'].isin(tournaments)]
    
    # Aggregate metrics
    skill_df = df_recent.groupby('Individual').agg(
        Wins=('Win', 'sum'),
        Rounds=('Win', 'count'),
        AvgPoints=('Points', 'mean'),
    ).reset_index()
    skill_df['WinRate'] = skill_df['Wins'] / skill_df['Rounds']
    
    # Weighted skill: AvgPoints * WinRate
    skill_df['SkillScore'] = skill_df['AvgPoints'] * skill_df['WinRate']
    
    # Sorting with tie-breakers: Wins > WinRate > AvgPoints
    skill_df = skill_df.sort_values(
        by=['SkillScore', 'Wins', 'WinRate', 'AvgPoints'], ascending=False
    ).reset_index(drop=True)
    
    return skill_df

def calculate_team_skill(df, recent_n):
    """
    Calculates team skill for all duos, with partial inference
    """
    tournaments = df['Tournament'].unique()[-recent_n:]
    df_recent = df[df['Tournament'].isin(tournaments)]
    
    team_records = {}
    
    # Create duos
    for idx, row in df_recent.iterrows():
        for partner in row['Partner']:
            duo = tuple(sorted([row['Individual'], partner]))
            if duo not in team_records:
                team_records[duo] = {'Points': [], 'Wins': []}
            team_records[duo]['Points'].append(row['Points'])
            team_records[duo]['Wins'].append(row['Win'])
    
    # Compute team skill
    teams = []
    for duo, metrics in team_records.items():
        avg_points = np.mean(metrics['Points'])
        wins = sum(metrics['Wins'])
        rounds = len(metrics['Wins'])
        win_rate = wins / rounds if rounds > 0 else 0
        skill_score = avg_points * win_rate
        teams.append({
            "Member1": duo[0],
            "Member2": duo[1],
            "Wins": wins,
            "Rounds": rounds,
            "WinRate": win_rate,
            "TeamSkill": skill_score
        })
    
    team_df = pd.DataFrame(teams)
    team_df = team_df.sort_values(
        by=['TeamSkill', 'Wins', 'WinRate'], ascending=False
    ).reset_index(drop=True)
    return team_df

# ----------------------------
# MAIN APP LOGIC
# ----------------------------
if uploaded_files:
    # Parse all CSVs
    dfs = [parse_csv(file) for file in uploaded_files]
    full_df = pd.concat(dfs, ignore_index=True)
    
    # Individual skill
    ind_skill = calculate_individual_skill(full_df, num_recent_tournaments)
    st.subheader("Top Individuals")
    st.dataframe(ind_skill)
    
    # Team skill
    team_skill = calculate_team_skill(full_df, num_recent_tournaments)
    st.subheader("Top Teams (Duos)")
    st.dataframe(team_skill)
    
else:
    st.info("Please upload Tabroom CSV files to see rankings.")
