import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

DB_PATH = 'golf.db'
COURSES_CSV = 'courses.csv'


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS rounds (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               course TEXT,
               played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS holes (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               round_id INTEGER,
               hole INTEGER,
               strokes INTEGER,
               fir INTEGER,
               gir INTEGER,
               putts INTEGER,
               weather TEXT,
               FOREIGN KEY(round_id) REFERENCES rounds(id)
           )"""
    )
    conn.commit()
    conn.close()


def load_courses():
    if os.path.exists(COURSES_CSV):
        return pd.read_csv(COURSES_CSV)
    return pd.DataFrame(columns=["course_name", "hole", "par", "yardage", "layout_image"])


def save_round(course: str, hole_data: list):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO rounds(course) VALUES (?)", (course,))
    round_id = cur.lastrowid
    for h in hole_data:
        cur.execute(
            """INSERT INTO holes(round_id, hole, strokes, fir, gir, putts, weather)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                round_id,
                h["hole"],
                h["strokes"],
                h["fir"],
                h["gir"],
                h["putts"],
                h["weather"],
            ),
        )
    conn.commit()
    conn.close()
    return round_id


def load_rounds_summary():
    conn = sqlite3.connect(DB_PATH)
    query = (
        "SELECT r.id, r.played_at, r.course, "
        "SUM(h.strokes) AS strokes, SUM(h.fir) AS fir, "
        "SUM(h.gir) AS gir, SUM(h.putts) AS putts "
        "FROM rounds r JOIN holes h ON r.id = h.round_id "
        "GROUP BY r.id ORDER BY r.played_at DESC"
    )
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def load_holes():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM holes", conn)
    conn.close()
    return df


init_db()
courses_df = load_courses()

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Record New Round", "Past Rounds", "Statistics"])

if page == "Record New Round":
    st.title("Record a New Round")
    if courses_df.empty:
        st.warning("No courses available.")
    else:
        course_names = courses_df["course_name"].unique()
        course = st.selectbox("Select Course", course_names)
        course_holes = courses_df[courses_df["course_name"] == course].sort_values(
            "hole"
        )
        img = course_holes["layout_image"].dropna().unique()
        if len(img) and img[0]:
            st.image(img[0])

        with st.form("round_form"):
            for _, row in course_holes.iterrows():
                st.subheader(
                    f"Hole {row.hole} (Par {row.par}) - {row.yardage} yds"
                )
                st.number_input(
                    "Strokes",
                    min_value=1,
                    step=1,
                    key=f"strokes_{row.hole}",
                )
                st.checkbox(
                    "Fairway in Regulation", key=f"fir_{row.hole}")
                st.checkbox(
                    "Green in Regulation", key=f"gir_{row.hole}" )
                st.number_input(
                    "Putts",
                    min_value=0,
                    step=1,
                    key=f"putts_{row.hole}",
                )
                st.selectbox(
                    "Weather",
                    ["Dry", "Wet", "Windy", "Other"],
                    key=f"weather_{row.hole}",
                )
                st.markdown("---")
            submitted = st.form_submit_button("Save Round")
        if submitted:
            data = []
            for _, row in course_holes.iterrows():
                data.append(
                    {
                        "hole": int(row.hole),
                        "strokes": int(st.session_state[f"strokes_{row.hole}"]),
                        "fir": int(st.session_state.get(f"fir_{row.hole}", False)),
                        "gir": int(st.session_state.get(f"gir_{row.hole}", False)),
                        "putts": int(st.session_state[f"putts_{row.hole}"]),
                        "weather": st.session_state[f"weather_{row.hole}"],
                    }
                )
            save_round(course, data)
            total_strokes = sum(d["strokes"] for d in data)
            total_fir = sum(d["fir"] for d in data)
            total_gir = sum(d["gir"] for d in data)
            total_putts = sum(d["putts"] for d in data)
            st.success("Round saved!")
            st.subheader("Summary")
            st.write(f"Total Score: {total_strokes}")
            st.write(f"Fairways Hit: {total_fir}")
            st.write(f"Greens in Regulation: {total_gir}")
            st.write(f"Total Putts: {total_putts}")

elif page == "Past Rounds":
    st.title("Past Rounds")
    summary_df = load_rounds_summary()
    if summary_df.empty:
        st.write("No rounds recorded yet.")
    else:
        st.dataframe(summary_df)

elif page == "Statistics":
    st.title("Aggregated Statistics")
    summary_df = load_rounds_summary()
    if summary_df.empty:
        st.write("No data available.")
    else:
        holes_df = load_holes()
        total_rounds = len(summary_df)
        avg_score = summary_df["strokes"].mean()
        avg_putts = summary_df["putts"].mean()
        fir_pct = (
            holes_df["fir"].sum() / len(holes_df) * 100 if not holes_df.empty else 0
        )
        gir_pct = (
            holes_df["gir"].sum() / len(holes_df) * 100 if not holes_df.empty else 0
        )
        st.metric("Total Rounds", total_rounds)
        st.metric("Average Score", f"{avg_score:.1f}")
        st.metric("Average Putts", f"{avg_putts:.1f}")
        st.metric("Fairway %", f"{fir_pct:.1f}%")
        st.metric("GIR %", f"{gir_pct:.1f}%")
