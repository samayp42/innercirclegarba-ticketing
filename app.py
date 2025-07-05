import streamlit as st
from supabase import create_client, Client
from email.message import EmailMessage
import smtplib
import tempfile
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="🎟️ Ticket Booking", layout="centered")

# 🔐 Access code gate
auth = st.text_input("Enter access code", type="password")
if auth != "innercircle":
    st.warning("Access denied. Please enter the correct code.")
    st.stop()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
STORAGE_BUCKET = "tickets"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🎨 Stylish Branding for Inner Circle Garba
st.image("logo.jpeg", width=120)
st.markdown(
    """
    <div style="text-align: center; margin-top: -30px;">
        <h1 style="color: #e63946; margin-bottom: 0px; font-size: 48px;">Inner Circle Garba 2025</h1>
        <p style="color: #aaa; font-size: 20px;">✨ Request Your Garba Passes Below</p>
    </div>
    <hr style="margin-top: 0px; border: 1px solid #e63946;" />
    """,
    unsafe_allow_html=True
)

with st.form("ticket_form"):
    name = st.text_input("Full Name")
    email = st.text_input("Email")
    phone = st.text_input("Phone")
    tickets = st.number_input("Number of Tickets", min_value=1, max_value=10, step=1)
    submitted = st.form_submit_button("Submit")

if submitted:
    with st.spinner("Processing your request..."):
        # Step 1: Insert user
        user_resp = supabase.table("users").insert({
            "name": name,
            "email": email,
            "phone": phone,
            "tickets_count": tickets
        }).execute()
        user_id = user_resp.data[0]["id"]

        # Step 2: Get unused tickets
        ticket_resp = supabase.table("tickets").select("*").eq("used", False).limit(tickets).execute()
        available = ticket_resp.data

        if len(available) < tickets:
            st.error("Not enough tickets available. Please try fewer.")
            st.stop()

        # Step 3: Download PDFs
        downloaded = []
        for t in available:
            file_bytes = supabase.storage.from_(STORAGE_BUCKET).download(t["storage_path"])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.write(file_bytes)
            tmp.close()
            downloaded.append((t, tmp.name))

        # Step 4: Send email
        msg = EmailMessage()
        msg["Subject"] = "🎫 Your Tickets"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = email
        msg.set_content(f"Hi {name},\n\nAttached are your {tickets} ticket(s). Enjoy!")

        for ticket, path in downloaded:
            with open(path, "rb") as f:
                msg.add_attachment(
                    f.read(),
                    maintype="application",
                    subtype="pdf",
                    filename=ticket["file_name"]  # ✅ FIXED FIELD NAME
                )

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)
        except Exception as e:
            st.error(f"Failed to send email: {str(e)}")
            st.stop()

        # Step 5: Mark tickets as used
        for ticket, _ in downloaded:
            supabase.table("tickets").update({
                "used": True,
                "assigned_to_user": user_id,  # ✅ FIXED FK COLUMN
                "assigned_at": datetime.utcnow().isoformat()
            }).eq("id", ticket["id"]).execute()

        st.success("✅ Tickets sent successfully to your email!")
        
st.markdown("<hr style='margin-top: 40px; border: 1px solid #333;'/>", unsafe_allow_html=True)
st.subheader("🔧 Admin Controls")

if st.button("🔁 Reset All Tickets"):
    try:
        supabase.table("tickets").update({
            "used": False,
            "assigned_to_user": None,
            "assigned_at": None
        }).neq("used", False).execute()
        st.success("✅ All tickets have been reset successfully.")
    except Exception as e:
        st.error(f"Failed to reset tickets: {str(e)}")