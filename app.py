
import streamlit as st
import pandas as pd
import random
import json
import time
import plotly.express as px
import plotly.graph_objects as go
from google import genai
from pydantic import BaseModel, Field

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="RevGuard AI - 3D Command Center",
    page_icon="💳",
    layout="wide",
)

# =========================================================
# PROFESSIONAL CUSTOM UI & THEME
# =========================================================

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 4rem;
    max-width: 1550px;
}
.hero {
    padding: 35px 40px;
    border-radius: 20px;
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    margin-bottom: 25px;
}
.hero-title {
    font-size: 38px;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 5px;
}
.hero-subtitle {
    color: #94a3b8;
    font-size: 15px;
}
.status-pill {
    display: inline-block;
    margin-top: 16px;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    background: rgba(16, 185, 129, 0.1);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.2);
}
.kpi-card {
    padding: 22px;
    border-radius: 16px;
    background: #131824;
    border: 1px solid rgba(255, 255, 255, 0.06);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    min-height: 120px;
}
.kpi-label {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 28px;
    font-weight: 800;
    color: #ffffff;
}
.kpi-note {
    color: #64748b;
    font-size: 11px;
    margin-top: 6px;
}
.section-title {
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
    margin-top: 35px;
    margin-bottom: 4px;
}
.section-subtitle {
    color: #64748b;
    font-size: 13px;
    margin-bottom: 18px;
}
.activity-card {
    background: #131824;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 8px;
}
.center-text {
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# PLOTLY 3D & 2D THEME HELPER
# =========================================================
def apply_plotly_theme(fig, height=350, is_3d=False):
    layout_config = dict(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#94a3b8", size=12),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    if is_3d:
        layout_config["scene"] = dict(
            xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.05)", title="Amount (₹)"),
            yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.05)", title="Success Rate"),
            zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.05)", title="Risk Score"),
        )
    fig.update_layout(**layout_config)
    return fig

# =========================================================
# SIDEBAR CONTROLS
# =========================================================

st.sidebar.header("⚙️ Configuration & Live Stream")

api_key = st.sidebar.text_input("Gemini API Key", type="password")
batch_choice = st.sidebar.selectbox("Batch Scale", ["Demo Batch (50 Txns)", "Standard Batch (250 Txns)", "Large Batch (500 Txns)"])
batch_size_map = {"Demo Batch (50 Txns)": 50, "Standard Batch (250 Txns)": 250, "Large Batch (500 Txns)": 500}
batch_size = batch_size_map[batch_choice]

st.sidebar.markdown("---")
st.sidebar.subheader("🔴 Live Polling Engine")
live_mode = st.sidebar.toggle("Enable Live Real-Time Stream", value=False)
refresh_rate = st.sidebar.slider("Refresh Interval (s)", 2, 10, 3)

confidence_threshold = st.sidebar.slider("Minimum AI confidence", 0.0, 1.0, 0.60, 0.05)
high_value_threshold = st.sidebar.number_input("High-value threshold (₹)", value=15000, step=1000)

# =========================================================
# GEMINI CLIENT & SCHEMAS
# =========================================================
client = None
ai_mode = "Simulation Mode"
if api_key:
    try:
        client = genai.Client(api_key=api_key)
        ai_mode = "Gemini AI Mode"
    except:
        client = None

class AIDecisionResponse(BaseModel):
    diagnosis: str = Field(description="Likely payment failure diagnosis.")
    risk_level: str = Field(description="Low, Medium, High, or Critical.")
    recommended_action: str = Field(description="Smart Retry, Send Payment Reminder, Request Card Update, or Escalate to Human.")
    reason: str = Field(description="Reason using actual transaction metrics.")
    confidence: float = Field(description="Confidence from 0.0 to 1.0.")

# =========================================================
# TOOLS & PROCESSOR
# =========================================================
class AgentTools:
    @staticmethod
    def calculate_risk_score(amount, customer_history, failure_reason, high_value_cutoff=15000):
        score = 20
        if amount > high_value_cutoff: score += 35
        elif amount > 5000: score += 20
        if customer_history["success_rate"] < 0.50: score += 35
        elif customer_history["success_rate"] < 0.70: score += 25
        if failure_reason in ["fraud_flagged", "security_challenge"]: score = 95
        elif failure_reason == "card_expired": score += 15
        return max(0, min(100, score))

    @staticmethod
    def diagnose_trend(customer_history):
        lifetime = customer_history["success_rate"]
        recent = customer_history.get("recent_success_rate", lifetime)
        return round(lifetime - recent, 2), f"Behavior stable around {lifetime*100:.0f}% success."

    @staticmethod
    def run_recovery_simulation(action, risk_score, failure_reason, retry_count, success_rate, previous_recovery_attempts, tenure_months):
        if action == "Escalate to Human" or retry_count >= 3:
            return False, 0.0, "Manual review required.", None
        probability = 0.75 if failure_reason == "gateway_timeout" else 0.45
        recovered = random.random() < probability
        return recovered, probability, f"Simulated execution result: {'Success'}.", None

def process_transaction(row, client, confidence_threshold, high_value_threshold):
    tx_id, customer_name, amount, reason, retries = row["transaction_id"], row["customer_name"], row["amount"], row["failure_reason"], row["retry_count"]
    success_rate = row["success_rate"]
    
    customer_history = {"success_rate": success_rate, "failed_payments": row["failed_payments"], "previous_recovery_attempts": row["previous_recovery_attempts"]}
    trend_delta, trend_note = AgentTools.diagnose_trend(customer_history)
    customer_history["trend_delta"] = trend_delta
    risk_score = AgentTools.calculate_risk_score(amount, customer_history, reason, high_value_threshold)
    
    recommendation, confidence, ai_risk_level = "Smart Retry", 0.85, "Medium"
    if reason in ["fraud_flagged", "security_challenge"]:
        recommendation, confidence = "Escalate to Human", 0.95
    elif reason == "card_expired":
        recommendation, confidence = "Request Card Update", 0.90

    final_action = recommendation
    guardrail_status = "Passed Guardrails"
    if reason in ["fraud_flagged", "security_challenge"] or retries >= 3 or confidence < confidence_threshold:
        guardrail_status = "🛑 Policy Guardrail Triggered"
        final_action = "Escalate to Human"

    recovered, recovery_probability, msg, stage_detail = AgentTools.run_recovery_simulation(
        final_action, risk_score, reason, retries, success_rate, row["previous_recovery_attempts"], row["customer_tenure_months"]
    )
    recovered_amount = amount if recovered else 0

    return {
        "transaction_id": tx_id, "customer": customer_name, "amount": amount, "failure_reason": reason,
        "risk_score": risk_score, "risk_level": ai_risk_level, "ai_recommendation": recommendation,
        "final_action": final_action, "overridden": final_action != recommendation, "guardrail_status": guardrail_status,
        "recovered": recovered, "recovered_amount": recovered_amount, "confidence": confidence * 100,
        "recovery_probability": recovery_probability * 100, "execution_message": msg
    }

@st.cache_data
def generate_dataset(size):
    names = ["Aarav Sharma", "Priya Patel", "Rohan Gupta", "Ananya Singh", "Vikram Kumar", "Neha Verma"]
    reasons = ["insufficient_funds", "card_expired", "gateway_timeout", "fraud_flagged", "bank_server_down"]
    data = []
    for i in range(1, size + 1):
        total_p = random.randint(5, 30)
        failed_p = random.randint(1, 10)
        data.append({
            "transaction_id": f"TXN_2026_{1000+i}",
            "customer_id": f"CUST_{random.randint(1000,9999)}",
            "customer_name": random.choice(names),
            "amount": random.choice([499, 999, 2499, 7999, 18999]),
            "failure_reason": random.choice(reasons),
            "success_rate": round((total_p - failed_p) / total_p, 2),
            "recent_success_rate": 0.8,
            "failed_payments": failed_p,
            "previous_recovery_attempts": random.randint(0, 2),
            "retry_count": random.randint(0, 3),
            "customer_tenure_months": random.randint(1, 24),
            "customer_tenure_months": random.randint(1, 24)
        })
    return pd.DataFrame(data)

# =========================================================
# DASHBOARD LAYOUT & LIVE LOOP
# =========================================================

st.markdown(f"""
<div class="hero">
    <div class="hero-title">💳 RevGuard AI - 3D Command Center</div>
    <div class="hero-subtitle">Autonomous Financial Recovery & Real-Time Intelligence Engine</div>
    <div class="status-pill">🟢 Live Stream Core Active &nbsp;•&nbsp; 3D Visual Rendering Enabled</div>
</div>
""", unsafe_allow_html=True)

df_raw = generate_dataset(batch_size)
processed_data = [process_transaction(row, client, confidence_threshold, high_value_threshold) for _, row in df_raw.iterrows()]
df_processed = pd.DataFrame(processed_data)

# Container placeholders for live updates
placeholder = st.empty()

def render_dashboard_content(df):
    total_at_risk = df["amount"].sum()
    total_recovered = df["recovered_amount"].sum()
    recovered_count = df["recovered"].sum()
    recovery_rate = (total_recovered / total_at_risk * 100) if total_at_risk > 0 else 0

    with placeholder.container():
        # KPI Cards
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f'<div class="kpi-card"><div class="kpi-label">Revenue at Risk</div><div class="kpi-value">₹{total_at_risk:,}</div><div class="kpi-note">Active batch pool</div></div>', unsafe_allow_html=True)
        k2.markdown(f'<div class="kpi-card"><div class="kpi-label">Revenue Recovered</div><div class="kpi-value">₹{total_recovered:,}</div><div class="kpi-note">{recovered_count} successful nodes</div></div>', unsafe_allow_html=True)
        k3.markdown(f'<div class="kpi-card"><div class="kpi-label">Recovery Efficiency</div><div class="kpi-value">{recovery_rate:.1f}%</div><div class="kpi-note">Automated recovery ratio</div></div>', unsafe_allow_html=True)
        k4.markdown(f'<div class="kpi-card"><div class="kpi-label">Active Guardrails</div><div class="kpi-value">{(df["overridden"]).sum()}</div><div class="kpi-note">AI safety overrides</div></div>', unsafe_allow_html=True)

        # 3D Interactive Visualization
        st.markdown('<div class="section-title">🌐 3D Transaction Risk & Recovery Matrix</div>', unsafe_allow_html=True)
        fig_3d = px.scatter_3d(
            df, x="amount", y="success_rate" if "success_rate" in df else "confidence", z="risk_score",
            color="final_action", size="amount", opacity=0.8,
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        apply_plotly_theme(fig_3d, height=500, is_3d=True)
        st.plotly_chart(fig_3d, use_container_width=True)

        # Comparative Charts Section
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="section-title">📊 Action Distribution</div>', unsafe_allow_html=True)
            action_fig = px.bar(df["final_action"].value_counts().reset_index(), x="final_action", y="count", color="final_action", template="plotly_dark")
            apply_plotly_theme(action_fig, height=320)
            st.plotly_chart(action_fig, use_container_width=True)
        with c2:
            st.markdown('<div class="section-title">🔻 Recovery Funnel Conversion</div>', unsafe_allow_html=True)
            funnel_fig = go.Figure(go.Funnel(y=["Total Failed", "AI Processed", "Guardrail Cleared", "Recovered"], x=[len(df), len(df), len(df[df.guardrail_status == "Passed Guardrails"]), int(recovered_count)]))
            apply_plotly_theme(funnel_fig, height=320)
            st.plotly_chart(funnel_fig, use_container_width=True)

        # Live Activity Feed Stream
        st.markdown('<div class="section-title">⚡ Real-Time Stream Log</div>', unsafe_allow_html=True)
        for _, row in df.head(5).iterrows():
            st.markdown(f"""
            <div class="activity-card">
                <b>{row['transaction_id']}</b> &nbsp;•&nbsp; Amount: <b>₹{row['amount']:,}</b> &nbsp;•&nbsp; Reason: <code>{row['failure_reason']}</code> &nbsp;•&nbsp; Action: <b>{row['final_action']}</b>
            </div>
            """, unsafe_allow_html=True)

# Render initial or live loop
if live_mode:
    while True:
        # Simulate slight dynamic updates in a live production environment loop
        df_raw = generate_dataset(batch_size)
        df_processed = pd.DataFrame([process_transaction(row, client, confidence_threshold, high_value_threshold) for _, row in df_raw.iterrows()])
        render_dashboard_content(df_processed)
        time.sleep(refresh_rate)
else:
    render_dashboard_content(df_processed)
