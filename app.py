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
    page_title="RevGuard AI - Revenue Recovery Command Center",
    page_icon="💳",
    layout="wide",
)

# =========================================================
# PROFESSIONAL CUSTOM UI & THEME
# =========================================================

st.markdown("""
<style>
/* Global Styling & Background */
.block-container {
    padding-top: 2rem;
    padding-bottom: 4rem;
    max-width: 1550px;
}

/* Hero Banner */
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
    letter-spacing: -0.5px;
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
    letter-spacing: 0.3px;
    background: rgba(16, 185, 129, 0.1);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.2);
}

/* KPI Cards */
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
    letter-spacing: 0.5px;
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

/* Typography Headings */
.section-title {
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
    margin-top: 35px;
    margin-bottom: 4px;
    letter-spacing: -0.3px;
}

.section-subtitle {
    color: #64748b;
    font-size: 13px;
    margin-bottom: 18px;
}

/* Activity & Guardrail Containers */
.activity-card {
    background: #131824;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 8px;
}

.activity-id {
    font-weight: 700;
    color: #f8fafc;
    font-size: 14px;
}

.activity-meta {
    color: #94a3b8;
    font-size: 12px;
    margin-top: 4px;
}

.guardrail-box {
    background: linear-gradient(135deg, #1c1917 0%, #131824 100%);
    border: 1px solid rgba(245, 158, 11, 0.2);
    border-radius: 16px;
    padding: 22px;
}

.center-text {
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# PLOTLY THEME CONFIGURATION
# =========================================================
def apply_plotly_theme(fig, height=350):
    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#94a3b8", size=12),
        margin=dict(l=15, r=15, t=30, b=15),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(255,255,255,0.04)")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(255,255,255,0.04)")
    return fig

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header("⚙️ Configuration")

api_key = st.sidebar.text_input(
    "Gemini API Key",
    type="password",
    help="Optional. Leave blank to use the deterministic simulation engine."
)

batch_choice = st.sidebar.selectbox(
    "Batch Scale",
    [
        "Demo Batch (50 Txns)",
        "Standard Batch (250 Txns)",
        "Large Batch (500 Txns)",
        "Evaluation Batch (1000 Txns)",
    ],
)

batch_size_map = {
    "Demo Batch (50 Txns)": 50,
    "Standard Batch (250 Txns)": 250,
    "Large Batch (500 Txns)": 500,
    "Evaluation Batch (1000 Txns)": 1000,
}

batch_size = batch_size_map[batch_choice]

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Guardrails")

confidence_threshold = st.sidebar.slider(
    "Minimum AI confidence",
    0.0,
    1.0,
    0.60,
    0.05,
)

high_value_threshold = st.sidebar.number_input(
    "High-value threshold (₹)",
    min_value=1000,
    max_value=100000,
    value=15000,
    step=1000,
)

st.sidebar.markdown("---")
st.sidebar.subheader("💼 ROI Assumptions")

avg_human_review_cost = st.sidebar.number_input(
    "Human review cost (₹)",
    min_value=0,
    max_value=5000,
    value=150,
    step=50,
)

automation_cost_per_txn = st.sidebar.number_input(
    "Automation cost / transaction (₹)",
    min_value=0,
    max_value=1000,
    value=8,
    step=1,
)

# =========================================================
# GEMINI CLIENT
# =========================================================

client = None
ai_mode = "Simulation Mode"

if api_key:
    try:
        client = genai.Client(api_key=api_key)
        ai_mode = "Gemini AI Mode"
        st.sidebar.success("🟢 Gemini AI Active")
    except Exception as exc:
        st.sidebar.error(f"Gemini initialization failed: {exc}")
        client = None

if not client:
    st.sidebar.info("🔵 Simulation Mode Active")

# =========================================================
# AI RESPONSE SCHEMA
# =========================================================

class AIDecisionResponse(BaseModel):
    diagnosis: str = Field(description="Likely payment failure diagnosis.")
    risk_level: str = Field(description="Low, Medium, High, or Critical.")
    recommended_action: str = Field(
        description=(
            "Must be exactly one of: Smart Retry, "
            "Send Payment Reminder, Request Card Update, "
            "Escalate to Human."
        )
    )
    reason: str = Field(description="Reason using actual transaction metrics.")
    confidence: float = Field(description="Confidence from 0.0 to 1.0.")

# =========================================================
# AGENT TOOLS
# =========================================================

class AgentTools:

    @staticmethod
    def calculate_risk_score(
        amount,
        customer_history,
        failure_reason,
        high_value_cutoff=15000,
    ):
        score = 20

        if amount > high_value_cutoff:
            score += 35
        elif amount > 5000:
            score += 20
        else:
            score += 5

        success_rate = customer_history["success_rate"]

        if success_rate < 0.50:
            score += 35
        elif success_rate < 0.70:
            score += 25
        elif success_rate < 0.90:
            score += 15
        else:
            score -= 10

        if failure_reason in ["fraud_flagged", "security_challenge"]:
            score = 95
        elif failure_reason == "card_expired":
            score += 15
        elif failure_reason == "bank_server_down":
            score += 5

        score += customer_history["previous_recovery_attempts"] * 5

        if customer_history["failed_payments"] >= 10:
            score += 10

        trend_delta = customer_history.get("trend_delta", 0.0)

        if trend_delta > 0.15:
            score += 10
        elif trend_delta > 0.05:
            score += 5

        return max(0, min(100, score))

    @staticmethod
    def diagnose_trend(customer_history):
        lifetime = customer_history["success_rate"]
        recent = customer_history.get("recent_success_rate", lifetime)

        trend_delta = round(lifetime - recent, 2)

        if trend_delta > 0.15:
            note = (
                f"Recent payment behavior is worsening. "
                f"Recent success rate is {recent*100:.0f}% "
                f"versus lifetime {lifetime*100:.0f}%."
            )
        elif trend_delta < -0.15:
            note = (
                f"Recent payment behavior is improving. "
                f"Recent success rate is {recent*100:.0f}% "
                f"versus lifetime {lifetime*100:.0f}%."
            )
        else:
            note = (
                f"Recent payment behavior is stable around "
                f"{lifetime*100:.0f}% lifetime success."
            )

        return trend_delta, note

    @staticmethod
    def recovery_probability(
        action,
        risk_score,
        failure_reason,
        retry_count,
        success_rate,
        previous_recovery_attempts,
    ):
        if action == "Escalate to Human":
            return 0.0

        if retry_count >= 3:
            return 0.0

        if failure_reason in ["fraud_flagged", "security_challenge"]:
            return 0.0

        base = {
            "gateway_timeout": 0.82,
            "bank_server_down": 0.78,
            "insufficient_funds": 0.55,
            "card_expired": 0.15,
        }.get(failure_reason, 0.40)

        probability = base
        probability += (success_rate - 0.70) * 0.30
        probability -= (risk_score / 100) * 0.15
        probability -= previous_recovery_attempts * 0.05

        if action == "Smart Retry":
            probability += 0.05
        elif action == "Send Payment Reminder":
            probability += 0.02

        return max(0.02, min(0.95, probability))

    @staticmethod
    def simulate_card_update_workflow(
        success_rate,
        tenure_months,
        previous_recovery_attempts,
    ):
        update_probability = 0.40
        update_probability += (success_rate - 0.70) * 0.35

        if tenure_months >= 12:
            update_probability += 0.10
        elif tenure_months <= 2:
            update_probability -= 0.10

        update_probability -= previous_recovery_attempts * 0.05
        update_probability = max(0.05, min(0.90, update_probability))

        updated = random.random() < update_probability

        if not updated:
            return (
                False,
                update_probability,
                "Customer did not update the payment method. No retry attempted.",
                {
                    "stage": "card_update",
                    "customer_updated_card": False,
                    "update_probability": round(update_probability, 2),
                    "retry_probability": None,
                },
            )

        retry_probability = 0.80 + (success_rate - 0.70) * 0.20
        retry_probability = max(0.10, min(0.95, retry_probability))

        recovered = random.random() < retry_probability

        combined = update_probability * retry_probability

        return (
            recovered,
            combined,
            (
                f"Customer updated payment method. "
                f"Retry {'succeeded' if recovered else 'failed'}."
            ),
            {
                "stage": "card_update",
                "customer_updated_card": True,
                "update_probability": round(update_probability, 2),
                "retry_probability": round(retry_probability, 2),
            },
        )

    @staticmethod
    def run_recovery_simulation(
        action,
        risk_score,
        failure_reason,
        retry_count,
        success_rate,
        previous_recovery_attempts,
        tenure_months,
    ):
        if action == "Escalate to Human":
            return (
                False,
                0.0,
                "Transaction escalated to human review.",
                None,
            )

        if retry_count >= 3:
            return (
                False,
                0.0,
                "Maximum retry limit reached.",
                None,
            )

        if action == "Request Card Update":
            return AgentTools.simulate_card_update_workflow(
                success_rate,
                tenure_months,
                previous_recovery_attempts,
            )

        probability = AgentTools.recovery_probability(
            action,
            risk_score,
            failure_reason,
            retry_count,
            success_rate,
            previous_recovery_attempts,
        )

        recovered = random.random() < probability

        if recovered:
            message = (
                f"Recovery successful. Simulated probability "
                f"{probability:.2f}."
            )
        else:
            message = (
                f"Recovery attempt failed. Simulated probability "
                f"{probability:.2f}."
            )

        return recovered, probability, message, None

# =========================================================
# TRANSACTION PROCESSOR
# =========================================================

def process_transaction(
    row,
    client,
    confidence_threshold,
    high_value_threshold,
    force_confidence=None,
):
    tx_id = row["transaction_id"]
    customer_id = row["customer_id"]
    customer_name = row["customer_name"]

    amount = row["amount"]
    reason = row["failure_reason"]
    retries = row["retry_count"]

    success_rate = row["success_rate"]
    recent_success_rate = row.get(
        "recent_success_rate",
        success_rate,
    )

    previous_recovery_attempts = row[
        "previous_recovery_attempts"
    ]

    tenure_months = row[
        "customer_tenure_months"
    ]

    customer_history = {
        "success_rate": success_rate,
        "recent_success_rate": recent_success_rate,
        "previous_payment_count": row["previous_payment_count"],
        "successful_payments": row["successful_payments"],
        "failed_payments": row["failed_payments"],
        "customer_tenure_months": tenure_months,
        "previous_recovery_attempts": previous_recovery_attempts,
    }

    trend_delta, trend_note = AgentTools.diagnose_trend(
        customer_history
    )

    customer_history["trend_delta"] = trend_delta

    risk_score = AgentTools.calculate_risk_score(
        amount,
        customer_history,
        reason,
        high_value_cutoff=high_value_threshold,
    )

    recommendation = None
    diagnosis = ""
    reasoning = ""
    confidence = 0.0
    ai_risk_level = ""
    ai_error = None
    ai_decision_made = False

    # -----------------------------------------------------
    # AI DECISION
    # -----------------------------------------------------

    if client:
        try:
            prompt = f"""
You are a fintech revenue recovery decision agent.
Analyze this failed subscription payment.

Transaction:
- ID: {tx_id}
- Amount: ₹{amount}
- Failure reason: {reason}
- Retry count: {retries}
- Days since failure: {row.get('days_since_failure', 1)}

Customer:
- Customer ID: {customer_id}
- Customer Name: {customer_name}
- Subscription: {row.get('subscription_plan', 'N/A')}
- Payment Channel: {row.get('payment_channel', 'N/A')}
- Tenure: {tenure_months} months
- Previous payments: {row['previous_payment_count']}
- Successful payments: {row['successful_payments']}
- Failed payments: {row['failed_payments']}
- Historical success rate: {success_rate*100:.1f}%
- Recent success rate: {recent_success_rate*100:.1f}%
- Previous recovery attempts: {previous_recovery_attempts}

System risk score: {risk_score}/100

Trend:
{trend_note}

Allowed actions ONLY:
1. Smart Retry
2. Send Payment Reminder
3. Request Card Update
4. Escalate to Human

Rules:
- Security/fraud concerns should be escalated.
- Consider retry history.
- Consider customer history and recent trend.
- Consider transaction amount.
- Never invent an action outside the allowed list.
- Explain the recommendation using actual metrics.
"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": AIDecisionResponse,
                },
            )

            result = json.loads(response.text)

            diagnosis = result.get(
                "diagnosis",
                "Unknown failure",
            )

            recommendation = result.get(
                "recommended_action",
                "Escalate to Human",
            )

            allowed_actions = {
                "Smart Retry",
                "Send Payment Reminder",
                "Request Card Update",
                "Escalate to Human",
            }

            if recommendation not in allowed_actions:
                recommendation = "Escalate to Human"

            reasoning = result.get(
                "reason",
                "No explanation returned.",
            )

            confidence = float(
                result.get("confidence", 0.5)
            )

            confidence = max(
                0.0,
                min(1.0, confidence),
            )

            ai_risk_level = result.get(
                "risk_level",
                "Medium",
            )

            ai_decision_made = True

        except Exception as exc:
            recommendation = None
            ai_error = str(exc)

    # -----------------------------------------------------
    # DETERMINISTIC FALLBACK
    # -----------------------------------------------------

    if not recommendation:

        if (
            reason in [
                "fraud_flagged",
                "security_challenge",
            ]
            or risk_score >= 85
        ):
            diagnosis = (
                "Security or high-risk condition detected."
            )
            recommendation = "Escalate to Human"
            reasoning = (
                f"Risk score {risk_score}/100 requires "
                "human review."
            )
            confidence = 0.95

        elif reason == "card_expired":
            diagnosis = (
                "Payment credentials are outdated."
            )
            recommendation = "Request Card Update"
            reasoning = (
                f"Card expiry prevents payment. "
                f"Historical success rate is "
                f"{success_rate*100:.1f}%. {trend_note}"
            )
            confidence = 0.94

        elif reason in [
            "gateway_timeout",
            "bank_server_down",
        ]:
            diagnosis = (
                "Likely temporary payment infrastructure issue."
            )
            recommendation = "Smart Retry"
            reasoning = (
                f"Temporary failure with "
                f"{success_rate*100:.1f}% historical "
                f"payment success. {trend_note}"
            )
            confidence = 0.88

        elif retries >= 3:
            diagnosis = "Repeated payment failure."
            recommendation = "Escalate to Human"
            reasoning = (
                f"Retry count is {retries}; automation should stop."
            )
            confidence = 0.97

        else:
            diagnosis = "Temporary payment failure."
            recommendation = "Send Payment Reminder"
            reasoning = (
                f"Customer has {success_rate*100:.1f}% "
                f"historical payment success. {trend_note}"
            )
            confidence = 0.80

        ai_risk_level = (
            "Critical" if risk_score >= 90
            else "High" if risk_score >= 70
            else "Medium" if risk_score >= 40
            else "Low"
        )

    if force_confidence is not None:
        confidence = force_confidence

    # -----------------------------------------------------
    # POLICY GUARDRAILS
    # -----------------------------------------------------

    guardrail_result = "Passed Guardrails"
    final_action = recommendation

    if reason in [
        "fraud_flagged",
        "security_challenge",
    ]:
        guardrail_result = "🛑 Security Guardrail"
        final_action = "Escalate to Human"

    elif retries >= 3:
        guardrail_result = "🛑 Max-Retry Guardrail"
        final_action = "Escalate to Human"

    elif (
        amount > high_value_threshold
        and risk_score > 60
    ):
        guardrail_result = (
            "🛑 High-Value Approval Guardrail"
        )
        final_action = "Escalate to Human"

    elif confidence < confidence_threshold:
        guardrail_result = (
            "🛑 Low-Confidence Guardrail"
        )
        final_action = "Escalate to Human"

    overridden = final_action != recommendation

    # -----------------------------------------------------
    # RECOVERY
    # -----------------------------------------------------

    if final_action == "Escalate to Human":
        recovered = False
        recovery_probability = 0.0
        execution_message = (
            "Transaction escalated to human review."
        )
        stage_detail = None

    else:
        (
            recovered,
            recovery_probability,
            execution_message,
            stage_detail,
        ) = AgentTools.run_recovery_simulation(
            final_action,
            risk_score,
            reason,
            retries,
            success_rate,
            previous_recovery_attempts,
            tenure_months,
        )

    recovered_amount = amount if recovered else 0

    # -----------------------------------------------------
    # AUDIT
    # -----------------------------------------------------

    timestamp = time.strftime("%H:%M:%S")

    audit_log = (
        f"[{timestamp}] "
        f"TXN={tx_id} | "
        f"Customer={customer_id} | "
        f"Risk={risk_score}/100 | "
        f"AI_Action={recommendation} | "
        f"Final_Action={final_action} | "
        f"Overridden={'YES' if overridden else 'NO'} | "
        f"Confidence={confidence*100:.0f}% | "
        f"Guardrail={guardrail_result} | "
        f"Result={'SUCCESS' if recovered else 'FAILED'} | "
        f"Recovered=₹{recovered_amount:,}"
        + (
            f" | AI_ERROR={ai_error}"
            if ai_error
            else ""
        )
    )

    return {
        "transaction_id": tx_id,
        "customer": customer_name,
        "amount": amount,
        "failure_reason": reason,
        "risk_score": risk_score,
        "risk_level": ai_risk_level,
        "diagnosis": diagnosis,
        "trend_note": trend_note,
        "ai_recommendation": recommendation,
        "final_action": final_action,
        "overridden": overridden,
        "guardrail_status": guardrail_result,
        "recovery_probability": round(
            recovery_probability * 100,
            1,
        ),
        "recovered": recovered,
        "recovered_amount": recovered_amount,
        "confidence": round(
            confidence * 100,
            1,
        ),
        "explanation": reasoning,
        "execution_message": execution_message,
        "stage_detail": stage_detail,
        "ai_error": ai_error,
        "ai_decision_made": ai_decision_made,
        "audit_log": audit_log,
    }

# =========================================================
# SYNTHETIC DATA
# =========================================================

@st.cache_data
def generate_dataset(size):
    names = [
        "Aarav Sharma",
        "Priya Patel",
        "Rohan Gupta",
        "Ananya Singh",
        "Vikram Kumar",
        "Neha Verma",
        "Karan Malhotra",
        "Divya Iyer",
        "Arjun Rao",
        "Meera Nair",
        "Rahul Menon",
        "Sneha Reddy",
    ]

    reasons = [
        "insufficient_funds",
        "card_expired",
        "gateway_timeout",
        "fraud_flagged",
        "bank_server_down",
    ]

    reason_weights = [
        0.35,
        0.20,
        0.20,
        0.10,
        0.15,
    ]

    plans = [
        "Monthly Basic",
        "Quarterly Pro",
        "Annual Enterprise",
    ]

    channels = [
        "UPI",
        "Credit Card",
        "Debit Card",
        "NetBanking",
    ]

    data = []

    for i in range(1, size + 1):

        total_payments = random.randint(5, 50)

        failed_payments = random.randint(
            0,
            max(
                1,
                int(total_payments * 0.4),
            ),
        )

        successful_payments = (
            total_payments - failed_payments
        )

        success_rate = round(
            successful_payments /
            total_payments,
            2,
        )

        recent_success_rate = round(
            min(
                1.0,
                max(
                    0.0,
                    success_rate
                    + random.uniform(
                        -0.25,
                        0.15,
                    ),
                ),
            ),
            2,
        )

        data.append({
            "transaction_id":
                f"TXN_2026_{1000+i}",
            "customer_id":
                f"CUST_{random.randint(1000,9999)}",
            "customer_name":
                random.choice(names),
            "subscription_plan":
                random.choice(plans),
            "payment_channel":
                random.choice(channels),
            "amount":
                random.choice([
                    499,
                    999,
                    2499,
                    7999,
                    18999,
                ]),
            "failure_reason":
                random.choices(
                    reasons,
                    weights=reason_weights,
                )[0],
            "previous_payment_count":
                total_payments,
            "successful_payments":
                successful_payments,
            "failed_payments":
                failed_payments,
            "success_rate":
                success_rate,
            "recent_success_rate":
                recent_success_rate,
            "customer_tenure_months":
                random.randint(1, 36),
            "previous_recovery_attempts":
                random.randint(0, 3),
            "retry_count":
                random.randint(0, 4),
            "days_since_failure":
                random.randint(1, 7),
        })

    return pd.DataFrame(data)

# =========================================================
# GUARDRAIL TEST CASES
# =========================================================

def build_guardrail_test_cases():

    base = {
        "customer_id": "CUST_TEST",
        "customer_name": "Test Customer",
        "subscription_plan": "Quarterly Pro",
        "payment_channel": "Credit Card",
        "previous_payment_count": 20,
        "successful_payments": 16,
        "failed_payments": 4,
        "success_rate": 0.80,
        "recent_success_rate": 0.80,
        "customer_tenure_months": 18,
        "previous_recovery_attempts": 0,
        "days_since_failure": 2,
    }

    cases = []

    cases.append({
        "test_name": "TEST 1: Fraud Flagged",
        "expected_guardrail":
            "Security Guardrail",
        "force_confidence": None,
        "row": {
            **base,
            "transaction_id": "TEST_FRAUD",
            "amount": 5000,
            "failure_reason": "fraud_flagged",
            "retry_count": 0,
        },
    })

    cases.append({
        "test_name": "TEST 2: Max Retries",
        "expected_guardrail":
            "Max-Retry Guardrail",
        "force_confidence": None,
        "row": {
            **base,
            "transaction_id": "TEST_MAXRETRY",
            "amount": 999,
            "failure_reason": "gateway_timeout",
            "retry_count": 4,
        },
    })

    cases.append({
        "test_name": "TEST 3: High Value + High Risk",
        "expected_guardrail":
            "High-Value Approval Guardrail",
        "force_confidence": None,
        "row": {
            **base,
            "transaction_id": "TEST_HIGHVALUE",
            "amount": 22000,
            "failure_reason": "insufficient_funds",
            "retry_count": 1,
            "success_rate": 0.35,
            "recent_success_rate": 0.30,
            "previous_recovery_attempts": 2,
            "failed_payments": 10,
        },
    })

    cases.append({
        "test_name": "TEST 4: Low AI Confidence",
        "expected_guardrail":
            "Low-Confidence Guardrail",
        "force_confidence": 0.35,
        "row": {
            **base,
            "transaction_id": "TEST_LOWCONF",
            "amount": 2499,
            "failure_reason": "insufficient_funds",
            "retry_count": 0,
        },
    })

    cases.append({
        "test_name": "TEST 5: Normal Gateway Timeout",
        "expected_guardrail":
            "Passed Guardrails",
        "force_confidence": None,
        "row": {
            **base,
            "transaction_id": "TEST_NORMAL",
            "amount": 999,
            "failure_reason": "gateway_timeout",
            "retry_count": 0,
            "success_rate": 0.85,
            "recent_success_rate": 0.85,
        },
    })

    return cases

# =========================================================
# DATA
# =========================================================

df_raw = generate_dataset(batch_size)

# =========================================================
# HERO
# =========================================================

mode_icon = "🟢" if client else "🔵"

st.markdown(
    f"""
<div class="hero">
    <div class="hero-title">💳 RevGuard AI</div>
    <div class="hero-subtitle">
        Autonomous Revenue Recovery Command Center
    </div>
    <div class="status-pill">
        {mode_icon} {ai_mode} &nbsp;•&nbsp; Deterministic Policy Guardrails Active
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.warning(
    "⚠️ Synthetic Data: all transactions, customer history, "
    "risk scores and recovery outcomes are simulated. "
    "No real payment is attempted."
)

# =========================================================
# PIPELINE
# =========================================================

st.markdown(
    """
<div class="section-title">⚡ Recovery Intelligence Pipeline</div>
<div class="section-subtitle">
AI recommends. Deterministic policy decides. Recovery is measured.
</div>
""",
    unsafe_allow_html=True,
)

pipeline = [
    ("💳", "FAILED", "Payment"),
    ("🧠", "RISK", "Detection"),
    ("👤", "CONTEXT", "Customer"),
    ("🤖", "AI", "Decision"),
    ("🛡️", "GUARDRAIL", "Policy"),
    ("💰", "RECOVERY", "Outcome"),
]

cols = st.columns(6)

for col, (icon, title, subtitle) in zip(cols, pipeline):
    with col:
        st.markdown(
            f"""
<div class="kpi-card center-text">
    <div style="font-size:24px; margin-bottom: 4px;">{icon}</div>
    <b>{title}</b>
    <div class="kpi-note">{subtitle}</div>
</div>
""",
            unsafe_allow_html=True,
        )

# =========================================================
# INPUT STREAM
# =========================================================

st.markdown(
    """
<div class="section-title">📡 Incoming Failed Transaction Stream</div>
<div class="section-subtitle">
Synthetic failed payments waiting for bounded AI analysis.
</div>
""",
    unsafe_allow_html=True,
)

col1, col2 = st.columns([1.3, 0.7])

with col1:
    st.dataframe(
        df_raw[
            [
                "transaction_id",
                "customer_name",
                "amount",
                "failure_reason",
                "success_rate",
                "retry_count",
            ]
        ],
        use_container_width=True,
        height=400,
        hide_index=True,
    )

with col2:
    st.markdown(
        """
<div class="guardrail-box">
<h3>🤖 Agentic AI Execution Engine</h3>
<p style="color:#94a3b8; font-size:13px; margin-top:8px;">
Risk Detection → Customer Context → AI Decision →
Policy Guardrails → Recovery Simulation → Audit Trail
</p>
</div>
""",
        unsafe_allow_html=True,
    )

    st.info(f"Current mode: **{ai_mode}**")

    run_pipeline = st.button(
        "🚀 Run Full Recovery Pipeline",
        type="primary",
        use_container_width=True,
    )

# =========================================================
# GUARDRAIL TEST
# =========================================================

st.markdown(
    """
<div class="section-title">🛡️ Bounded Autonomy Verification</div>
<div class="section-subtitle">
Five deterministic cases prove that policy can override an AI recommendation.
</div>
""",
    unsafe_allow_html=True,
)

run_test_suite = st.button(
    "🧪 Run 5 Guardrail Tests",
    use_container_width=True,
)

if run_test_suite:

    test_cases = build_guardrail_test_cases()
    test_rows = []

    for case in test_cases:

        result = process_transaction(
            case["row"],
            client,
            confidence_threshold,
            high_value_threshold,
            force_confidence=case["force_confidence"],
        )

        expected = case["expected_guardrail"]
        actual = result["guardrail_status"]

        passed = (
            expected == "Passed Guardrails"
            and actual == "Passed Guardrails"
        ) or (
            expected != "Passed Guardrails"
            and expected in actual
        )

        test_rows.append({
            "Test": case["test_name"],
            "Expected": expected,
            "Actual": actual,
            "Result": "✅ PASS" if passed else "❌ FAIL",
            "Final Action": result["final_action"],
            "Confidence":
                f"{result['confidence']}%",
            "Risk":
                result["risk_score"],
        })

    test_df = pd.DataFrame(test_rows)

    if (test_df["Result"] == "✅ PASS").all():
        st.success(
            "✅ 5/5 guardrail tests passed. "
            "Bounded autonomy verified."
        )
    else:
        st.error(
            "❌ One or more guardrail tests failed."
        )

    st.dataframe(
        test_df,
        use_container_width=True,
        hide_index=True,
    )

# =========================================================
# FULL PIPELINE
# =========================================================

if run_pipeline:

    with st.spinner(
        f"Running RevGuard across {batch_size} transactions..."
    ):

        progress = st.progress(0)
        processed = []

        for idx, row in df_raw.iterrows():

            progress.progress(
                int(
                    ((idx + 1) / len(df_raw))
                    * 100
                )
            )

            processed.append(
                process_transaction(
                    row.to_dict(),
                    client,
                    confidence_threshold,
                    high_value_threshold,
                )
            )

        progress.empty()

    df_processed = pd.DataFrame(processed)

    st.success(
        "✅ Recovery intelligence pipeline completed."
    )

    # =====================================================
    # METRICS
    # =====================================================

    total_revenue_at_risk = (
        df_processed["amount"].sum()
    )

    total_recovered = (
        df_processed["recovered_amount"].sum()
    )

    recovered_count = int(
        df_processed["recovered"].sum()
    )

    failed_count = int(
        (~df_processed["recovered"]).sum()
    )

    escalated_count = int(
        (
            df_processed["final_action"]
            == "Escalate to Human"
        ).sum()
    )

    stopped_guardrail = int(
        (
            df_processed["guardrail_status"]
            != "Passed Guardrails"
        ).sum()
    )

    automated_eligible = int(
        (
            df_processed["guardrail_status"]
            == "Passed Guardrails"
        ).sum()
    )

    ai_decisions = int(
        df_processed["ai_decision_made"].sum()
    )

    ai_failures = int(
        df_processed["ai_error"].notna().sum()
    )

    overridden_count = int(
        df_processed["overridden"].sum()
    )

    revenue_recovery_rate = (
        total_recovered
        / total_revenue_at_risk
        * 100
        if total_revenue_at_risk > 0
        else 0
    )

    transaction_recovery_rate = (
        recovered_count
        / automated_eligible
        * 100
        if automated_eligible > 0
        else 0
    )

    # =====================================================
    # KPI CARDS
    # =====================================================

    st.markdown(
        """
<div class="section-title">💰 Revenue Recovery Command Center</div>
<div class="section-subtitle">
Measured business impact from the processed batch.
</div>
""",
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)

    metrics = [
        (
            "💰 REVENUE AT RISK",
            f"₹{total_revenue_at_risk:,}",
            f"{batch_size} failed transactions",
        ),
        (
            "🟢 REVENUE RECOVERED",
            f"₹{total_recovered:,}",
            f"{recovered_count} successful recoveries",
        ),
        (
            "📈 RECOVERY RATE",
            f"{revenue_recovery_rate:.1f}%",
            "Revenue recovered / revenue at risk",
        ),
        (
            "🛡️ GUARDRAIL STOPS",
            str(stopped_guardrail),
            f"{overridden_count} AI recommendations overridden",
        ),
    ]

    for col, (label, value, note) in zip(
        [k1, k2, k3, k4],
        metrics,
    ):
        with col:
            st.markdown(
                f"""
<div class="kpi-card">
<div class="kpi-label">{label}</div>
<div class="kpi-value">{value}</div>
<div class="kpi-note">{note}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    # =====================================================
    # MONEY VISUAL (ENHANCED BAR CHART)
    # =====================================================

    st.markdown(
        '<div class="section-title">💵 Revenue Recovery Performance</div>',
        unsafe_allow_html=True,
    )

    money_fig = go.Figure(
        go.Bar(
            x=[
                "Revenue at Risk",
                "Revenue Recovered",
            ],
            y=[
                total_revenue_at_risk,
                total_recovered,
            ],
            text=[
                f"₹{total_revenue_at_risk:,}",
                f"₹{total_recovered:,}",
            ],
            textposition="auto",
            marker_color=["#3b82f6", "#10b981"],
            marker_line_width=0,
            opacity=0.9,
        )
    )
    apply_plotly_theme(money_fig, height=320)
    money_fig.update_layout(yaxis_title="Amount (₹)")

    st.plotly_chart(
        money_fig,
        use_container_width=True,
    )

    # =====================================================
    # RECOVERY FUNNEL
    # =====================================================

    st.markdown(
        """
<div class="section-title">🔻 Recovery Funnel</div>
<div class="section-subtitle">
Failed payments moving through AI analysis, policy and recovery.
</div>
""",
        unsafe_allow_html=True,
    )

    funnel_fig = go.Figure(
        go.Funnel(
            y=[
                "Failed Transactions",
                "AI Analyzed",
                "Guardrail Approved",
                "Recovered",
            ],
            x=[
                batch_size,
                ai_decisions,
                automated_eligible,
                recovered_count,
            ],
            textinfo="value+percent initial",
            marker=dict(color=["#4f46e5", "#6366f1", "#818cf8", "#10b981"])
        )
    )
    apply_plotly_theme(funnel_fig, height=380)

    st.plotly_chart(
        funnel_fig,
        use_container_width=True,
    )

    # =====================================================
    # BOUNDED AUTONOMY
    # =====================================================

    st.markdown(
        """
<div class="section-title">🛡️ Bounded Autonomy Controls</div>
<div class="section-subtitle">
AI proposes. Deterministic policy decides what is actually allowed.
</div>
""",
        unsafe_allow_html=True,
    )

    ai_wanted = int(
        (
            df_processed["ai_recommendation"]
            != "Escalate to Human"
        ).sum()
    )

    policy_allowed = int(
        (
            (
                df_processed["ai_recommendation"]
                != "Escalate to Human"
            )
            &
            (
                df_processed["final_action"]
                == df_processed["ai_recommendation"]
            )
        ).sum()
    )

    policy_blocked = int(
        (
            (
                df_processed["ai_recommendation"]
                != "Escalate to Human"
            )
            &
            (
                df_processed["final_action"]
                == "Escalate to Human"
            )
        ).sum()
    )

    b1, b2, b3 = st.columns(3)
    b1.metric("🤖 AI Wanted Automation", ai_wanted)
    b2.metric("🟢 Policy Allowed", policy_allowed)
    b3.metric("🛡️ Policy Blocked", policy_blocked)

    autonomy_fig = px.bar(
        pd.DataFrame({
            "Category": [
                "AI Wanted Automation",
                "Policy Allowed",
                "Policy Blocked",
            ],
            "Transactions": [
                ai_wanted,
                policy_allowed,
                policy_blocked,
            ],
        }),
        x="Transactions",
        y="Category",
        orientation="h",
        text="Transactions",
        color="Category",
        color_discrete_map={
            "AI Wanted Automation": "#60a5fa",
            "Policy Allowed": "#34d399",
            "Policy Blocked": "#f87171"
        }
    )
    apply_plotly_theme(autonomy_fig, height=300)
    autonomy_fig.update_layout(showlegend=False, yaxis_title="")

    st.plotly_chart(
        autonomy_fig,
        use_container_width=True,
    )

    # =====================================================
    # RISK HEATMAP
    # =====================================================

    st.markdown(
        """
<div class="section-title">🔥 Risk Intelligence Heatmap</div>
<div class="section-subtitle">
Failure type versus calculated risk level distribution.
</div>
""",
        unsafe_allow_html=True,
    )

    risk_temp = df_processed.copy()

    risk_temp["risk_bucket"] = pd.cut(
        risk_temp["risk_score"],
        bins=[-1, 39, 69, 89, 101],
        labels=["Low", "Medium", "High", "Critical"],
    )

    heatmap_data = pd.crosstab(
        risk_temp["failure_reason"],
        risk_temp["risk_bucket"],
    )

    for bucket in ["Low", "Medium", "High", "Critical"]:
        if bucket not in heatmap_data.columns:
            heatmap_data[bucket] = 0

    heatmap_data = heatmap_data[["Low", "Medium", "High", "Critical"]]

    heatmap_fig = px.imshow(
        heatmap_data,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Viridis",
    )
    apply_plotly_theme(heatmap_fig, height=360)

    st.plotly_chart(
        heatmap_fig,
        use_container_width=True,
    )

    # =====================================================
    # SANKEY
    # =====================================================

    st.markdown(
        """
<div class="section-title">🔀 AI Action to Guardrail & Final Action Flow</div>
<div class="section-subtitle">
Visual proof tracking how AI recommendations transform under policies.
</div>
""",
        unsafe_allow_html=True,
    )

    labels = [
        "AI: Smart Retry",
        "AI: Payment Reminder",
        "AI: Card Update",
        "AI: Human Escalation",
        "Final: Smart Retry",
        "Final: Payment Reminder",
        "Final: Card Update",
        "Final: Human Escalation",
    ]

    action_source = {
        "Smart Retry": 0,
        "Send Payment Reminder": 1,
        "Request Card Update": 2,
        "Escalate to Human": 3,
    }

    action_target = {
        "Smart Retry": 4,
        "Send Payment Reminder": 5,
        "Request Card Update": 6,
        "Escalate to Human": 7,
    }

    grouped = (
        df_processed
        .groupby(["ai_recommendation", "final_action"])
        .size()
    )

    source, target, values = [], [], []

    for (ai_action, final_action), count in grouped.items():
        if ai_action in action_source and final_action in action_target:
            source.append(action_source[ai_action])
            target.append(action_target[final_action])
            values.append(int(count))

    sankey_fig = go.Figure(
        go.Sankey(
            node=dict(
                pad=20,
                thickness=18,
                label=labels,
                color="#6366f1"
            ),
            link=dict(
                source=source,
                target=target,
                value=values,
                color="rgba(99, 102, 241, 0.3)"
            ),
        )
    )
    apply_plotly_theme(sankey_fig, height=450)

    st.plotly_chart(
        sankey_fig,
        use_container_width=True,
    )

    # =====================================================
    # ACTION DISTRIBUTION
    # =====================================================

    st.markdown(
        '<div class="section-title">🤖 Recovery Action Distribution</div>',
        unsafe_allow_html=True,
    )

    action_counts = (
        df_processed["final_action"]
        .value_counts()
        .reset_index()
    )
    action_counts.columns = ["Action", "Transactions"]

    action_fig = px.bar(
        action_counts,
        x="Transactions",
        y="Action",
        orientation="h",
        text="Transactions",
        color="Action",
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    apply_plotly_theme(action_fig, height=320)
    action_fig.update_layout(showlegend=False, yaxis_title="")

    st.plotly_chart(
        action_fig,
        use_container_width=True,
    )

    # =====================================================
    # ACTIVITY
    # =====================================================

    st.markdown(
        """
<div class="section-title">⚡ Recovery Activity Feed</div>
<div class="section-subtitle">
Representative decisions from the processed batch.
</div>
""",
        unsafe_allow_html=True,
    )

    for _, result in df_processed.head(10).iterrows():

        if result["recovered"]:
            status = "🟢 RECOVERED"
        elif result["overridden"]:
            status = "🛡️ BLOCKED"
        elif result["final_action"] == "Escalate to Human":
            status = "🔴 HUMAN REVIEW"
        else:
            status = "⏳ NOT RECOVERED"

        st.markdown(
            f"""
<div class="activity-card">
<div class="activity-id">
{result["transaction_id"]} &nbsp;•&nbsp; ₹{result["amount"]:,} &nbsp;•&nbsp; {result["failure_reason"]}
</div>
<div class="activity-meta">
AI: <b>{result["ai_recommendation"]}</b> → Final: <b>{result["final_action"]}</b> &nbsp;|&nbsp; Status: <b>{status}</b> &nbsp;|&nbsp; Risk: <b>{result["risk_score"]}/100</b>
</div>
</div>
""",
            unsafe_allow_html=True,
        )

    # =====================================================
    # ROI & SYSTEM PERFORMANCE
    # =====================================================

    st.markdown(
        '<div class="section-title">💼 Business Impact & ROI</div>',
        unsafe_allow_html=True,
    )

    review_cost_avoided = automated_eligible * avg_human_review_cost
    automation_cost = automated_eligible * automation_cost_per_txn
    net_savings = review_cost_avoided - automation_cost
    roi_percent = (net_savings / automation_cost * 100) if automation_cost > 0 else 0

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Human Review Avoided", f"₹{review_cost_avoided:,}")
    r2.metric("Automation Cost", f"₹{automation_cost:,}")
    r3.metric("Net Operational Savings", f"₹{net_savings:,}")
    r4.metric("Estimated ROI", f"{roi_percent:,.0f}%")

    st.markdown(
        '<div class="section-title">📊 System Performance</div>',
        unsafe_allow_html=True,
    )

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("AI Decisions", ai_decisions)
    s2.metric("AI Call Failures", ai_failures)
    s3.metric("Human Escalations", escalated_count)
    s4.metric("Txn Recovery Rate", f"{transaction_recovery_rate:.1f}%")

    # =====================================================
    # RESULTS TABLE & INSPECTORS
    # =====================================================

    st.markdown(
        '<div class="section-title">📋 Processed Batch Execution</div>',
        unsafe_allow_html=True,
    )

    st.dataframe(
        df_processed[
            [
                "transaction_id",
                "customer",
                "amount",
                "failure_reason",
                "risk_score",
                "risk_level",
                "ai_recommendation",
                "final_action",
                "overridden",
                "guardrail_status",
                "recovered",
                "recovered_amount",
            ]
        ],
        use_container_width=True,
        height=450,
        hide_index=True,
    )

    # =====================================================
    # EXPORT BUTTONS
    # =====================================================

    st.markdown(
        '<div class="section-title">📥 Export Results</div>',
        unsafe_allow_html=True,
    )

    export_cols = [c for c in df_processed.columns if c != "stage_detail"]
    csv_data = df_processed[export_cols].to_csv(index=False).encode("utf-8")

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        st.download_button(
            "📊 Download Batch Results CSV",
            data=csv_data,
            file_name="revguard_recovery_results.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_exp2:
        audit_text = "\n".join(df_processed["audit_log"])
        st.download_button(
            "🔎 Download Audit Trail",
            data=audit_text.encode("utf-8"),
            file_name="revguard_audit_trail.txt",
            mime="text/plain",
            use_container_width=True,
        )
