from __future__ import annotations
from pathlib import Path
import sys,streamlit as st
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import config
from core.database import ReviewDatabase
st.set_page_config(page_title="PR-CoPilot Agent",page_icon="🤖",layout="wide")
db=ReviewDatabase(config.DATABASE_PATH)
st.title("🤖 PR-CoPilot Agent")
st.caption("Live metrics from the SQLite review store")
s=db.stats(); a,b,c,d=st.columns(4)
a.metric("PRs Reviewed",s["reviews"]); b.metric("Total Findings",s["findings"]); c.metric("Security",s["security"]); d.metric("Performance + Architecture",s["performance"]+s["architecture"])
st.divider(); st.subheader("Recent Reviews")
rows=db.recent_reviews(50)
st.dataframe(rows,use_container_width=True,hide_index=True) if rows else st.info("No reviews recorded yet.")
