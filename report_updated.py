import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ==============================
# Streamlit App
# ==============================
st.set_page_config(
    page_title="Monthly Check-in Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Multi-Month Check-in Analysis Dashboard")

# Upload multiple Excel files
uploaded_files = st.file_uploader(
    "Upload one or more Excel files",
    type=["xlsx", "xls"],
    accept_multiple_files=True
)

if uploaded_files:
    dfs = []
    for file in uploaded_files:
        df = pd.read_excel(file)

        # Rename columns consistently
        df = df.rename(columns={
            "User Role": "Role",
            "User Name": "User",
            "Assigned Area": "Area",
            "Assigned Region": "Region",
            "Check-In Time": "CheckInTime",
            "Check-In Date": "CheckInDate"
        })

        # Parse date and time
        df["CheckInDate"] = pd.to_datetime(df["CheckInDate"]).dt.date
        df["CheckInTime"] = pd.to_datetime(df["CheckInTime"]).dt.time

        dfs.append(df)

    # Combine all months
    df = pd.concat(dfs, ignore_index=True)

    # ==============================
    # Configurable threshold time
    # ==============================
    threshold_time = st.time_input(
        "Select acceptable check-in threshold",
        value=datetime.strptime("09:00:00", "%H:%M:%S").time()
    )

    # Compute OnTime column
    df["OnTime"] = df["CheckInTime"].apply(lambda t: t <= threshold_time)

    # Add Month-Year column
    df["Month"] = pd.to_datetime(df["CheckInDate"]).dt.strftime("%Y-%m")

    # ==============================
    # Dimension selector
    # ==============================
    group_by_choice = st.radio(
        "Select Dimension for Analysis:",
        ["Area", "Region"],
        horizontal=True
    )

    # ==============================
    # Overall Summary Metrics
    # ==============================
    st.subheader("Overall Summary Across All Months")
    total_ra = df[df["Role"] == "RA"]["User"].nunique()
    total_sup = df[df["Role"] == "SUP"]["User"].nunique()
    total_checkins = len(df)
    total_true = df["OnTime"].sum()
    total_false = total_checkins - total_true
    true_pct = (total_true / total_checkins * 100) if total_checkins else 0
    false_pct = (total_false / total_checkins * 100) if total_checkins else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total RA Users", total_ra)
    col2.metric("Total SUP Users", total_sup)
    col3.metric("Total Check-ins", total_checkins)
    col4, col5 = st.columns(2)
    col4.metric("True Check-ins", f"{total_true} ({true_pct:.1f}%)")
    col5.metric("False Check-ins", f"{total_false} ({false_pct:.1f}%)")

    # ==============================
    # Monthly Trend Chart
    # ==============================
    st.subheader("Monthly False Check-in Trend")
    month_summary = df.groupby("Month").agg(
        Total_Checkins=("OnTime", "count"),
        False_Checkins=("OnTime", lambda x: (x == False).sum())
    ).reset_index()
    month_summary["False_%"] = (month_summary["False_Checkins"] /
                                month_summary["Total_Checkins"] * 100).round(1)

    fig_month = px.line(
        month_summary,
        x="Month",
        y="False_%",
        markers=True,
        text="False_%",
        title="False Check-ins (%) Over Months"
    )
    st.plotly_chart(fig_month, use_container_width=True)

    # ==============================
    # Per-Month Detailed Analysis
    # ==============================
    st.subheader(f"Detailed Monthly Analysis by {group_by_choice}")
    months = sorted(df["Month"].unique())
    for m in months:
        st.markdown(f"### {m}")
        mdf = df[df["Month"] == m]
        
        group_summary = mdf.groupby(group_by_choice).agg(
            Total_Checkins=("OnTime", "count"),
            False_Checkins=("OnTime", lambda x: (x == False).sum())
        ).reset_index()
        group_summary["False_%"] = (group_summary["False_Checkins"] /
                                    group_summary["Total_Checkins"] * 100).round(1)
        st.dataframe(group_summary.sort_values("False_%", ascending=False),
                     use_container_width=True)

        fig1 = px.bar(
            group_summary.sort_values("False_%", ascending=False),
            x="False_%",
            y=group_by_choice,
            orientation='h',
            text="False_%",
            color="False_%",
            color_continuous_scale="RdYlGn_r",
            labels={"False_%": "False %", group_by_choice: group_by_choice},
            title=f"False Check-ins by {group_by_choice} - {m}"
        )
        fig1.update_layout(
            yaxis=dict(autorange="reversed"),
            height=50 * len(group_summary),
            margin=dict(l=150, r=50, t=50, b=50)
        )
        fig1.update_traces(textposition='outside', marker_line_width=0.5, marker_line_color='black')
        st.plotly_chart(fig1, use_container_width=True)

    # ==============================
    # Late RA Users Threshold Across Months
    # ==============================
    st.subheader("Late RA Users per Month")
    threshold = st.slider("Select False % Threshold", 0, 100, 60, step=5)

    for m in months:
        st.markdown(f"### {m}")
        mdf = df[(df["Month"] == m) & (df["Role"] == "RA")]
        ra_users = mdf.groupby([group_by_choice, "User"]).agg(
            Total_Checkins=("OnTime", "count"),
            False_Checkins=("OnTime", lambda x: (x == False).sum())
        ).reset_index()
        ra_users["False_%"] = (ra_users["False_Checkins"] /
                               ra_users["Total_Checkins"] * 100).round(1)
        filtered_ra = ra_users[ra_users["False_%"] >= threshold]
        st.dataframe(filtered_ra.sort_values("False_%", ascending=False),
                     use_container_width=True)

        if not filtered_ra.empty:
            area_late_count = filtered_ra.groupby(group_by_choice)["User"].nunique().reset_index()
            area_late_count = area_late_count.rename(columns={"User": "RA_Count"})
            total_ra_per_area = mdf.groupby(group_by_choice)["User"].nunique()
            area_late_count["Percent"] = area_late_count.apply(
                lambda x: round((x["RA_Count"] / total_ra_per_area[x[group_by_choice]]) * 100, 1), axis=1
            )
            area_late_count["Area_Label"] = area_late_count.apply(
                lambda x: f"{x[group_by_choice]} (Total RA: {total_ra_per_area[x[group_by_choice]]})", axis=1
            )
            area_late_count = area_late_count.sort_values("RA_Count", ascending=False)

            fig2 = px.bar(
                area_late_count,
                x="RA_Count",
                y="Area_Label",
                orientation='h',
                text=area_late_count.apply(lambda x: f"{x['RA_Count']} ({x['Percent']}%)", axis=1),
                color="RA_Count",
                color_continuous_scale="RdYlGn_r",
                labels={"RA_Count": "Number of Late RA Users", "Area_Label": group_by_choice},
                title=f"Late RA Users by {group_by_choice} - {m} (≥ {threshold}% False)"
            )
            fig2.update_layout(
                yaxis=dict(autorange="reversed"),
                height=50 * len(area_late_count),
                margin=dict(l=150, r=50, t=50, b=50)
            )
            fig2.update_traces(textposition='outside', marker_line_width=0.5, marker_line_color='black')
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info(f"No {group_by_choice}s have RA users above {threshold}% late for {m}.")
