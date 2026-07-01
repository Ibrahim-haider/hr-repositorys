"""
JW SEZ Digital HR Prototype
Core demo flow: Employee fills onboarding form -> HR reviews -> Approved employee joins main employee database.
Run: streamlit run app.py
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "jw_sez_hr_prototype.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

PRIMARY = "#2563EB"
ACCENT = "#F59E0B"
BG = "#0F172A"
CARD = "#111827"
TEXT = "#E5E7EB"
MUTED = "#9CA3AF"
GREEN = "#22C55E"
RED = "#EF4444"


# ----------------------------- DATABASE ---------------------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL CHECK(role IN ('employee','hr','admin')),
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS onboarding_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            father_name TEXT,
            cnic TEXT,
            date_of_birth TEXT,
            gender TEXT,
            marital_status TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            education TEXT,
            institute TEXT,
            department TEXT,
            designation TEXT,
            joining_date TEXT,
            bank_name TEXT,
            account_title TEXT,
            account_number TEXT,
            signature_text TEXT,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Draft','Pending','Approved','Rejected','Changes Requested')),
            hr_notes TEXT,
            submitted_at TEXT,
            reviewed_at TEXT,
            reviewed_by INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            saved_path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY(application_id) REFERENCES onboarding_applications(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            employee_code TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            cnic TEXT,
            phone TEXT,
            email TEXT,
            department TEXT,
            designation TEXT,
            joining_date TEXT,
            status TEXT NOT NULL DEFAULT 'Active',
            added_at TEXT NOT NULL,
            FOREIGN KEY(application_id) REFERENCES onboarding_applications(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TEXT NOT NULL
        )
        """
    )

    # Seed demo users
    demo_users = [
        ("employee.demo", "employee1234", "Employee Demo", "employee.demo@jwsez.com", "employee"),
        ("hr.manager", "hr1234", "HR Manager", "hr.manager@jwsez.com", "hr"),
        ("admin", "admin1234", "System Admin", "admin@jwsez.com", "admin"),
    ]
    for username, password, full_name, email, role in demo_users:
        cur.execute("SELECT id FROM users WHERE username=?", (username,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (username,password_hash,full_name,email,role,created_at) VALUES (?,?,?,?,?,?)",
                (username, hash_password(password), full_name, email, role, now()),
            )

    # Seed realistic demo data for HR/Admin analytics
    cur.execute("SELECT COUNT(*) AS c FROM onboarding_applications WHERE cnic LIKE 'SAMPLE-%'")
    if cur.fetchone()["c"] == 0:
        sample_rows = [
            ("sample.ali", "Ali Raza", "SAMPLE-001", "IT", "Software Intern", "Approved", "2026-01-08", "2026-01-10"),
            ("sample.sara", "Sara Khan", "SAMPLE-002", "HR", "HR Assistant", "Approved", "2026-02-05", "2026-02-07"),
            ("sample.usman", "Usman Ahmed", "SAMPLE-003", "Supply Chain", "Supply Chain Officer", "Rejected", "2026-02-18", "2026-02-19"),
            ("sample.ayesha", "Ayesha Malik", "SAMPLE-004", "Finance", "Accounts Trainee", "Approved", "2026-03-03", "2026-03-05"),
            ("sample.bilal", "Bilal Hussain", "SAMPLE-005", "Processing", "Processing Supervisor", "Pending", "2026-03-19", None),
            ("sample.hina", "Hina Shah", "SAMPLE-006", "Operations", "Operations Coordinator", "Approved", "2026-04-11", "2026-04-13"),
            ("sample.omar", "Omar Farooq", "SAMPLE-007", "Admin", "Admin Officer", "Changes Requested", "2026-05-02", "2026-05-03"),
            ("sample.zain", "Zain Iqbal", "SAMPLE-008", "IT", "Data Analyst", "Approved", "2026-06-14", "2026-06-16"),
            ("sample.noor", "Noor Fatima", "SAMPLE-009", "Supply Chain", "Procurement Intern", "Rejected", "2026-06-22", "2026-06-23"),
        ]
        for username, full_name, cnic, dept, desig, status, submitted_at, reviewed_at in sample_rows:
            email = f"{username}@jwsez.com"
            cur.execute("SELECT id FROM users WHERE username=?", (username,))
            row = cur.fetchone()
            if row:
                user_id = row["id"]
            else:
                cur.execute(
                    "INSERT INTO users (username,password_hash,full_name,email,role,created_at) VALUES (?,?,?,?,?,?)",
                    (username, hash_password("employee1234"), full_name, email, "employee", now()),
                )
                user_id = cur.lastrowid
            cur.execute(
                """
                INSERT INTO onboarding_applications
                (user_id, full_name, father_name, cnic, date_of_birth, gender, marital_status, phone, email, address,
                 emergency_contact_name, emergency_contact_phone, education, institute, department, designation, joining_date,
                 bank_name, account_title, account_number, signature_text, status, hr_notes, submitted_at, reviewed_at, reviewed_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (user_id, full_name, "Demo Father", cnic, "2000-01-01", "Male", "Single", "03000000000", email, "Demo address",
                 "Emergency Contact", "03111111111", "Bachelor's", "Demo Institute", dept, desig, submitted_at,
                 "Demo Bank", full_name, "PK00DEMO0000000000", full_name, status,
                 "Demo analytics record" if status != "Pending" else "", submitted_at + " 09:00:00",
                 (reviewed_at + " 15:00:00") if reviewed_at else None, 2)
            )
            app_id = cur.lastrowid
            if status == "Approved":
                cur.execute(
                    """
                    INSERT OR IGNORE INTO employees
                    (application_id,user_id,employee_code,full_name,cnic,phone,email,department,designation,joining_date,status,added_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (app_id, user_id, f"JW-{app_id:05d}", full_name, cnic, "03000000000", email, dept, desig, submitted_at, "Active", reviewed_at + " 15:00:00"),
                )

    conn.commit()
    conn.close()


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def audit(action: str, details: str = "") -> None:
    user = st.session_state.get("user", {})
    username = user.get("username", "system")
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_log (username, action, details, timestamp) VALUES (?,?,?,?)",
        (username, action, details, now()),
    )
    conn.commit()
    conn.close()


def verify_login(username: str, password: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND is_active=1", (username.strip(),)
    ).fetchone()
    conn.close()
    if row and row["password_hash"] == hash_password(password):
        return dict(row)
    return None


def read_df(query: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_my_application(user_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM onboarding_applications WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_application(user_id: int, data: dict, status: str = "Pending") -> int:
    existing = get_my_application(user_id)
    conn = get_conn()
    cur = conn.cursor()
    fields = [
        "full_name", "father_name", "cnic", "date_of_birth", "gender", "marital_status",
        "phone", "email", "address", "emergency_contact_name", "emergency_contact_phone",
        "education", "institute", "department", "designation", "joining_date", "bank_name",
        "account_title", "account_number", "signature_text"
    ]
    values = [data.get(f, "") for f in fields]
    if existing and existing["status"] in ["Draft", "Pending", "Rejected", "Changes Requested"]:
        set_clause = ",".join([f"{f}=?" for f in fields])
        cur.execute(
            f"UPDATE onboarding_applications SET {set_clause}, status=?, submitted_at=?, hr_notes=NULL WHERE id=?",
            (*values, status, now(), existing["id"]),
        )
        app_id = existing["id"]
    else:
        cur.execute(
            f"""
            INSERT INTO onboarding_applications
            (user_id,{','.join(fields)},status,submitted_at)
            VALUES ({','.join(['?'] * (len(fields)+3))})
            """,
            (user_id, *values, status, now()),
        )
        app_id = cur.lastrowid
    conn.commit()
    conn.close()
    return app_id


def save_uploaded_documents(app_id: int, uploads: dict) -> None:
    conn = get_conn()
    for doc_type, file in uploads.items():
        if file is None:
            continue
        safe_name = file.name.replace("/", "_").replace("\\", "_")
        folder = UPLOAD_DIR / f"APP-{app_id:05d}"
        folder.mkdir(exist_ok=True)
        saved_path = folder / f"{doc_type.replace(' ', '_')}_{safe_name}"
        saved_path.write_bytes(file.getbuffer())
        conn.execute(
            "INSERT INTO documents (application_id,document_type,original_filename,saved_path,uploaded_at) VALUES (?,?,?,?,?)",
            (app_id, doc_type, safe_name, str(saved_path), now()),
        )
    conn.commit()
    conn.close()


def approve_application(app_id: int, notes: str) -> None:
    user = st.session_state.user
    conn = get_conn()
    app = conn.execute("SELECT * FROM onboarding_applications WHERE id=?", (app_id,)).fetchone()
    if not app:
        conn.close()
        raise ValueError("Application not found")

    employee_code = f"JW-{app_id:05d}"
    conn.execute(
        """
        INSERT OR IGNORE INTO employees
        (application_id,user_id,employee_code,full_name,cnic,phone,email,department,designation,joining_date,status,added_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            app_id, app["user_id"], employee_code, app["full_name"], app["cnic"], app["phone"],
            app["email"], app["department"], app["designation"], app["joining_date"], "Active", now(),
        ),
    )
    conn.execute(
        "UPDATE onboarding_applications SET status='Approved', hr_notes=?, reviewed_at=?, reviewed_by=? WHERE id=?",
        (notes, now(), user["id"], app_id),
    )
    conn.commit()
    conn.close()
    audit("APPROVED_APPLICATION", f"APP-{app_id:05d} moved to employees table")


def update_application_status(app_id: int, status: str, notes: str) -> None:
    user = st.session_state.user
    conn = get_conn()
    conn.execute(
        "UPDATE onboarding_applications SET status=?, hr_notes=?, reviewed_at=?, reviewed_by=? WHERE id=?",
        (status, notes, now(), user["id"], app_id),
    )
    conn.commit()
    conn.close()
    audit("UPDATED_APPLICATION", f"APP-{app_id:05d} -> {status}")


# ----------------------------- UI ---------------------------------------

st.set_page_config(page_title="JW SEZ Digital HR Prototype", page_icon="🏢", layout="wide")
init_db()

st.markdown(
    f"""
    <style>
    :root {{ --primary:#2563EB; --accent:#F59E0B; --bg:#0F172A; --card:#111827; --text:#E5E7EB; --muted:#9CA3AF; }}
    .stApp {{ background: radial-gradient(circle at top left, #1e3a8a 0, #0f172a 30%, #020617 100%); color: var(--text); }}
    .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1280px; }}
    h1, h2, h3, h4, h5, h6, p, label, span, div {{ color: var(--text) !important; }}
    .hero {{ background: linear-gradient(135deg, rgba(37,99,235,.25), rgba(245,158,11,.12)); border:1px solid rgba(148,163,184,.25); padding:28px; border-radius:24px; box-shadow:0 20px 50px rgba(0,0,0,.28); margin-bottom:20px; }}
    .hero-title {{ font-size:38px; line-height:1.1; font-weight:900; margin-bottom:8px; }}
    .hero-subtitle {{ color:#CBD5E1 !important; font-size:16px; max-width:760px; }}
    .topbar {{ background:rgba(15,23,42,.82); backdrop-filter:blur(10px); color:white; padding:18px 24px; border-radius:18px; margin-bottom:18px; border:1px solid rgba(148,163,184,.25); box-shadow:0 12px 35px rgba(0,0,0,.25); }}
    .brand {{ font-size:24px; font-weight:900; letter-spacing:-.02em; }}
    .subtitle {{ color:#CBD5E1 !important; font-size:14px; margin-top:4px; }}
    .card {{ background:rgba(17,24,39,.86); padding:18px; border-radius:18px; border:1px solid rgba(148,163,184,.22); box-shadow:0 14px 36px rgba(0,0,0,.24); }}
    .feature-card {{ min-height:120px; }}
    .metric-card {{ background:linear-gradient(180deg,rgba(30,41,59,.92),rgba(17,24,39,.92)); padding:18px; border-radius:18px; border:1px solid rgba(148,163,184,.22); box-shadow:0 10px 28px rgba(0,0,0,.20); }}
    .metric-title {{ color:#A7B0C3 !important; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }}
    .metric-value {{ color:#93C5FD !important; font-size:34px; font-weight:900; margin-top:4px; }}
    .muted {{ color:#94A3B8 !important; }}
    .status {{ padding:5px 12px; border-radius:999px; font-weight:800; font-size:12px; display:inline-block; }}
    .pending {{ background:#78350F; color:#FDE68A !important; }}
    .approved {{ background:#064E3B; color:#A7F3D0 !important; }}
    .rejected {{ background:#7F1D1D; color:#FECACA !important; }}
    .changes {{ background:#312E81; color:#C7D2FE !important; }}
    [data-testid="stSidebar"] {{ background-color:#0B1220; border-right:1px solid rgba(148,163,184,.16); }}
    [data-testid="stSidebar"] * {{ color:#F9FAFB !important; }}
    .stTextInput input, .stTextArea textarea, .stDateInput input, .stNumberInput input {{ background-color:#111827 !important; color:#F9FAFB !important; border:1px solid #475569 !important; border-radius:11px !important; }}
    div[data-baseweb="select"] > div {{ background-color:#111827 !important; border:1px solid #475569 !important; border-radius:11px !important; }}
    div[data-baseweb="select"] * {{ color:#F9FAFB !important; }}
    .stButton button {{ background:linear-gradient(135deg,#2563EB,#1D4ED8) !important; color:white !important; border-radius:12px !important; border:none !important; font-weight:800; box-shadow:0 8px 20px rgba(37,99,235,.25); }}
    .stButton button:hover {{ transform:translateY(-1px); filter:brightness(1.08); }}
    [data-testid="stDataFrame"], [data-testid="stMetric"] {{ background-color:#111827 !important; border-radius:14px; }}
    .stAlert {{ background-color:#111827 !important; color:#F9FAFB !important; border:1px solid rgba(148,163,184,.22); }}
    hr {{ border-color:rgba(148,163,184,.22); }}
    </style>
    """,
    unsafe_allow_html=True,
)


def header():
    u = st.session_state.user
    st.markdown(
        f"""
        <div class='topbar'>
          <div class='brand'>JW SEZ Corporation · Digital HR Prototype</div>
          <div class='subtitle'>Logged in as <b>{u['full_name']}</b> · Role: <b>{u['role'].upper()}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def login_screen():
    st.markdown("""
    <div class='hero'>
      <div class='hero-title'>JW SEZ Digital Employee Onboarding Portal</div>
      <div class='hero-subtitle'>A proof-of-concept system that converts paper-based onboarding into a secure workflow: employee form submission, HR review, approval, employee database, and analytics.</div>
    </div>
    """, unsafe_allow_html=True)

    f1, f2, f3 = st.columns(3)
    with f1:
        st.markdown("<div class='card feature-card'><h4>👤 Employee Portal</h4><p class='muted'>Employees fill onboarding forms and upload documents themselves.</p></div>", unsafe_allow_html=True)
    with f2:
        st.markdown("<div class='card feature-card'><h4>✅ HR Review</h4><p class='muted'>HR can approve, reject, or request corrections with notes.</p></div>", unsafe_allow_html=True)
    with f3:
        st.markdown("<div class='card feature-card'><h4>📊 Analytics</h4><p class='muted'>Dashboards show hiring patterns, departments, approvals, and rejections.</p></div>", unsafe_allow_html=True)

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        st.markdown("<div class='card'><h2 style='text-align:center;margin-bottom:4px'>Sign in</h2><p style='text-align:center;color:#94A3B8!important'>Prototype access for employee, HR and admin roles</p></div>", unsafe_allow_html=True)
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", type="primary", use_container_width=True):
            user = verify_login(username, password)
            if user:
                st.session_state.user = user
                audit("LOGIN")
                st.rerun()
            else:
                st.error("Invalid username or password")
        st.info("Demo logins:\n\nEmployee: `employee.demo / employee1234`\n\nHR: `hr.manager / hr1234`\n\nAdmin: `admin / admin1234`")


def employee_portal():
    st.subheader("Employee Portal")
    app = get_my_application(st.session_state.user["id"])

    if app:
        status_class = {
            "Pending": "pending", "Approved": "approved", "Rejected": "rejected", "Changes Requested": "changes", "Draft": "pending"
        }.get(app["status"], "pending")
        st.markdown(
            f"Application status: <span class='status {status_class}'>{app['status']}</span>",
            unsafe_allow_html=True,
        )
        if app.get("hr_notes"):
            st.warning(f"HR Notes: {app['hr_notes']}")
        if app["status"] == "Approved":
            st.success("Your onboarding has been approved. You are now added to the employee database.")
            return

    st.markdown("### Fill Onboarding Form")
    with st.form("employee_form"):
        st.markdown("#### Personal Information")
        c1, c2 = st.columns(2)
        full_name = c1.text_input("Full Name *", value=(app or {}).get("full_name", st.session_state.user["full_name"]))
        father_name = c2.text_input("Father's Name", value=(app or {}).get("father_name", ""))
        c1, c2, c3 = st.columns(3)
        cnic = c1.text_input("CNIC *", value=(app or {}).get("cnic", ""), placeholder="XXXXX-XXXXXXX-X")
        dob = c2.date_input("Date of Birth", value=date(2000, 1, 1))
        gender = c3.selectbox("Gender", ["Male", "Female", "Other"], index=0)
        c1, c2 = st.columns(2)
        marital_status = c1.selectbox("Marital Status", ["Single", "Married", "Divorced", "Widowed"])
        phone = c2.text_input("Phone *", value=(app or {}).get("phone", ""))
        email = st.text_input("Email", value=(app or {}).get("email", st.session_state.user.get("email", "")))
        address = st.text_area("Address", value=(app or {}).get("address", ""))

        st.markdown("#### Emergency Contact")
        c1, c2 = st.columns(2)
        emergency_name = c1.text_input("Emergency Contact Name", value=(app or {}).get("emergency_contact_name", ""))
        emergency_phone = c2.text_input("Emergency Contact Phone", value=(app or {}).get("emergency_contact_phone", ""))

        st.markdown("#### Education & Employment")
        c1, c2 = st.columns(2)
        education = c1.selectbox("Highest Education", ["Matric", "Intermediate", "Bachelor's", "Master's", "Other"])
        institute = c2.text_input("Institute", value=(app or {}).get("institute", ""))
        c1, c2, c3 = st.columns(3)
        department = c1.selectbox("Department", ["HR", "Supply Chain", "Processing", "Finance", "IT", "Operations", "Admin"])
        designation = c2.text_input("Designation", value=(app or {}).get("designation", ""), placeholder="e.g. Intern")
        joining_date = c3.date_input("Joining Date", value=date.today())

        st.markdown("#### Bank Details")
        c1, c2, c3 = st.columns(3)
        bank_name = c1.text_input("Bank Name", value=(app or {}).get("bank_name", ""))
        account_title = c2.text_input("Account Title", value=(app or {}).get("account_title", ""))
        account_number = c3.text_input("Account Number / IBAN", value=(app or {}).get("account_number", ""))

        st.markdown("#### Documents")
        c1, c2, c3 = st.columns(3)
        cnic_front = c1.file_uploader("CNIC Front", type=["png", "jpg", "jpeg", "pdf"])
        cv = c2.file_uploader("CV", type=["pdf", "docx"])
        photo = c3.file_uploader("Passport Photo", type=["png", "jpg", "jpeg"])

        st.markdown("#### Digital Signature")
        signature_text = st.text_input("Type your full name as digital signature *", value=(app or {}).get("signature_text", ""))
        agreement = st.checkbox("I confirm the information provided is correct.")
        submitted = st.form_submit_button("Submit to HR", type="primary", use_container_width=True)

    if submitted:
        missing = []
        if not full_name.strip(): missing.append("Full name")
        if not cnic.strip(): missing.append("CNIC")
        if not phone.strip(): missing.append("Phone")
        if not signature_text.strip(): missing.append("Digital signature")
        if not agreement: missing.append("Confirmation checkbox")
        if missing:
            st.error("Please complete: " + ", ".join(missing))
        else:
            data = dict(
                full_name=full_name, father_name=father_name, cnic=cnic, date_of_birth=str(dob),
                gender=gender, marital_status=marital_status, phone=phone, email=email, address=address,
                emergency_contact_name=emergency_name, emergency_contact_phone=emergency_phone,
                education=education, institute=institute, department=department, designation=designation,
                joining_date=str(joining_date), bank_name=bank_name, account_title=account_title,
                account_number=account_number, signature_text=signature_text,
            )
            app_id = upsert_application(st.session_state.user["id"], data, "Pending")
            save_uploaded_documents(app_id, {"CNIC Front": cnic_front, "CV": cv, "Passport Photo": photo})
            audit("SUBMITTED_ONBOARDING", f"APP-{app_id:05d}")
            st.success(f"Submitted to HR successfully. Reference: APP-{app_id:05d}")
            st.rerun()


def application_detail(app_id: int):
    conn = get_conn()
    app = conn.execute("SELECT * FROM onboarding_applications WHERE id=?", (app_id,)).fetchone()
    docs = conn.execute("SELECT * FROM documents WHERE application_id=? ORDER BY uploaded_at DESC", (app_id,)).fetchall()
    conn.close()
    if not app:
        st.error("Application not found")
        return
    app = dict(app)
    st.markdown(f"### APP-{app_id:05d}: {app['full_name']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", app["status"])
    c2.metric("Department", app.get("department") or "—")
    c3.metric("Designation", app.get("designation") or "—")
    c4.metric("Submitted", app.get("submitted_at") or "—")

    st.markdown("#### Application Information")
    display_fields = [
        "full_name", "father_name", "cnic", "date_of_birth", "gender", "marital_status", "phone", "email", "address",
        "emergency_contact_name", "emergency_contact_phone", "education", "institute", "department", "designation",
        "joining_date", "bank_name", "account_title", "account_number", "signature_text"
    ]
    rows = [{"Field": f.replace("_", " ").title(), "Value": app.get(f) or "—"} for f in display_fields]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("#### Uploaded Documents")
    if docs:
        for d in docs:
            st.write(f"✅ **{d['document_type']}** — {d['original_filename']} ({d['uploaded_at']})")
    else:
        st.caption("No documents uploaded yet.")

    st.markdown("#### HR Decision")
    notes = st.text_area("HR Notes", value=app.get("hr_notes") or "")
    c1, c2, c3 = st.columns(3)
    if c1.button("Approve & Add to Employee Database", type="primary", use_container_width=True):
        approve_application(app_id, notes)
        st.success("Approved. Employee added to main employee database.")
        st.rerun()
    if c2.button("Request Changes", use_container_width=True):
        update_application_status(app_id, "Changes Requested", notes or "Please correct the highlighted information.")
        st.warning("Changes requested from employee.")
        st.rerun()
    if c3.button("Reject", use_container_width=True):
        update_application_status(app_id, "Rejected", notes or "Rejected by HR.")
        st.error("Application rejected.")
        st.rerun()



def get_employee_master_df() -> pd.DataFrame:
    """Full employee/application view for HR and Admin."""
    return read_df(
        """
        SELECT
            a.id AS application_id,
            COALESCE(e.employee_code, 'Not assigned') AS employee_code,
            a.full_name,
            a.cnic,
            a.phone,
            a.email,
            a.department,
            a.designation,
            a.joining_date,
            a.status AS application_status,
            COALESCE(e.status, 'Not active employee') AS employee_status,
            a.submitted_at,
            a.reviewed_at,
            a.hr_notes
        FROM onboarding_applications a
        LEFT JOIN employees e ON e.application_id = a.id
        ORDER BY a.id DESC
        """
    )


def analytics_dashboard(apps: pd.DataFrame, employees: pd.DataFrame) -> None:
    st.markdown("### Hiring Analytics")
    if apps.empty:
        st.info("No onboarding data yet. Submit a few forms to generate analytics.")
        return

    apps2 = apps.copy()
    apps2["submitted_date"] = pd.to_datetime(apps2["submitted_at"], errors="coerce")
    apps2["month"] = apps2["submitted_date"].dt.strftime("%b %Y")

    c1, c2 = st.columns(2)
    with c1:
        status_counts = apps2["status"].fillna("Unknown").value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig = px.pie(status_counts, names="Status", values="Count", title="Application Status Mix", hole=0.35)
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        dept_counts = apps2["department"].fillna("Unknown").value_counts().reset_index()
        dept_counts.columns = ["Department", "Applications"]
        fig = px.bar(dept_counts, x="Department", y="Applications", title="Applications by Department")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        monthly = apps2.dropna(subset=["submitted_date"]).groupby("month", sort=False).size().reset_index(name="Applications")
        fig = px.line(monthly, x="month", y="Applications", markers=True, title="Monthly Hiring Pipeline")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Month")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        rejected = apps2[apps2["status"].eq("Rejected")]
        if rejected.empty:
            st.info("No rejected applications yet.")
        else:
            rej_dept = rejected["department"].fillna("Unknown").value_counts().reset_index()
            rej_dept.columns = ["Department", "Rejections"]
            fig = px.bar(rej_dept, x="Department", y="Rejections", title="Rejections by Department")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Quick Analysis")
    total = len(apps2)
    approved = int((apps2["status"] == "Approved").sum())
    rejected_count = int((apps2["status"] == "Rejected").sum())
    pending = int((apps2["status"] == "Pending").sum())
    approval_rate = round((approved / total) * 100, 1) if total else 0
    rejection_rate = round((rejected_count / total) * 100, 1) if total else 0
    st.write(f"Approval rate: **{approval_rate}%** · Rejection rate: **{rejection_rate}%** · Pending reviews: **{pending}**")



def show_employee_profile(application_id: int):
    conn = get_conn()
    app = conn.execute("SELECT * FROM onboarding_applications WHERE id=?", (application_id,)).fetchone()
    emp = conn.execute("SELECT * FROM employees WHERE application_id=?", (application_id,)).fetchone()
    docs = conn.execute("SELECT document_type, original_filename, uploaded_at FROM documents WHERE application_id=? ORDER BY uploaded_at DESC", (application_id,)).fetchall()
    conn.close()
    if not app:
        st.warning("No profile found for this record.")
        return
    app=dict(app)
    emp=dict(emp) if emp else {}
    status_class={"Pending":"pending","Approved":"approved","Rejected":"rejected","Changes Requested":"changes","Draft":"pending"}.get(app.get("status"),"pending")
    st.markdown(f"""
    <div class='card'>
      <h3>{app.get('full_name','Employee Profile')}</h3>
      <p class='muted'>Application APP-{application_id:05d} · Employee Code: <b>{emp.get('employee_code','Not assigned')}</b> · <span class='status {status_class}'>{app.get('status','Unknown')}</span></p>
    </div>
    """, unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Department", app.get("department") or "—")
    c2.metric("Designation", app.get("designation") or "—")
    c3.metric("Joining Date", app.get("joining_date") or "—")
    c4.metric("Employee Status", emp.get("status","Not active"))
    t1,t2,t3=st.tabs(["Personal Details","Documents","HR Notes"])
    with t1:
        rows=[]
        for f in ["full_name","father_name","cnic","date_of_birth","gender","marital_status","phone","email","address","emergency_contact_name","emergency_contact_phone","education","institute","bank_name","account_title","account_number"]:
            rows.append({"Field":f.replace('_',' ').title(),"Value":app.get(f) or "—"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with t2:
        if docs:
            st.dataframe(pd.DataFrame([dict(d) for d in docs]), use_container_width=True, hide_index=True)
        else:
            st.caption("No uploaded documents found for this profile.")
    with t3:
        st.write(app.get("hr_notes") or "No HR notes yet.")
        st.caption(f"Submitted: {app.get('submitted_at') or '—'} · Reviewed: {app.get('reviewed_at') or '—'}")


def employee_database_view():
    employees_full = get_employee_master_df()
    st.markdown("### Employee Database & Application Records")
    st.caption("HR and Admin can view approved employees, rejected applications, pending onboarding, and changes requested from one place.")
    if employees_full.empty:
        st.info("No employee/application records yet.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Records", len(employees_full))
    c2.metric("Approved Employees", int((employees_full["application_status"] == "Approved").sum()))
    c3.metric("Pending", int((employees_full["application_status"] == "Pending").sum()))
    c4.metric("Rejected", int((employees_full["application_status"] == "Rejected").sum()))

    col1, col2, col3 = st.columns([2,1,1])
    search = col1.text_input("Search", placeholder="Name, CNIC, department, designation, status...")
    status_options = ["All"] + sorted([x for x in employees_full["application_status"].dropna().unique().tolist()])
    dept_options = ["All"] + sorted([x for x in employees_full["department"].fillna("Unknown").unique().tolist()])
    status_filter = col2.selectbox("Status", status_options)
    dept_filter = col3.selectbox("Department", dept_options)

    filtered = employees_full.copy()
    if status_filter != "All":
        filtered = filtered[filtered["application_status"] == status_filter]
    if dept_filter != "All":
        filtered = filtered[filtered["department"].fillna("Unknown") == dept_filter]
    if search.strip():
        mask = filtered.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
        filtered = filtered[mask]

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button("Download Filtered HR Data CSV", filtered.to_csv(index=False).encode("utf-8"), "jw_sez_hr_filtered_data.csv", "text/csv")

    if not filtered.empty:
        st.markdown("### Employee / Application Profile")
        choices = [f"APP-{int(r.application_id):05d} · {r.full_name} · {r.application_status}" for _, r in filtered.iterrows()]
        selected_label = st.selectbox("Open a profile", choices)
        selected_id = int(selected_label.split("·")[0].replace("APP-", ""))
        show_employee_profile(selected_id)


def hr_portal():
    st.subheader("HR Review Portal")
    apps = read_df("SELECT id, full_name, cnic, department, designation, status, submitted_at, reviewed_at FROM onboarding_applications ORDER BY id DESC")
    employees = read_df("SELECT * FROM employees ORDER BY id DESC")
    pending_count = int((apps["status"] == "Pending").sum()) if not apps.empty else 0
    approved_count = int((apps["status"] == "Approved").sum()) if not apps.empty else 0
    rejected_count = int((apps["status"] == "Rejected").sum()) if not apps.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pending Review", pending_count)
    c2.metric("Approved", approved_count)
    c3.metric("Rejected", rejected_count)
    c4.metric("Active Employees", len(employees))

    tab1, tab2, tab3, tab4 = st.tabs(["Review Forms", "All Employees Data", "Analytics", "Audit Log"])
    with tab1:
        if apps.empty:
            st.info("No applications yet. Login as employee.demo and submit a form first.")
        else:
            status_filter = st.selectbox("Filter status", ["All", "Pending", "Changes Requested", "Approved", "Rejected"])
            filtered = apps if status_filter == "All" else apps[apps["status"] == status_filter]
            st.dataframe(filtered, use_container_width=True, hide_index=True)
            selected = st.number_input("Enter Application ID to review", min_value=1, step=1)
            if st.button("Open Application"):
                st.session_state.selected_app_id = int(selected)
            if st.session_state.get("selected_app_id"):
                application_detail(st.session_state.selected_app_id)

    with tab2:
        employee_database_view()

    with tab3:
        analytics_dashboard(apps, employees)

    with tab4:
        logs = read_df("SELECT username, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 100")
        st.dataframe(logs, use_container_width=True, hide_index=True)

def admin_portal():
    st.subheader("Admin Panel")
    apps = read_df("SELECT id, full_name, cnic, department, designation, status, submitted_at, reviewed_at FROM onboarding_applications ORDER BY id DESC")
    employees = read_df("SELECT * FROM employees ORDER BY id DESC")

    tab1, tab2, tab3, tab4 = st.tabs(["Users", "All Employees Data", "Analytics", "Audit Log"])
    with tab1:
        users = read_df("SELECT id, username, full_name, email, role, is_active, created_at FROM users ORDER BY id")
        st.dataframe(users, use_container_width=True, hide_index=True)
        st.markdown("### Create Employee / HR Account")
        with st.form("create_user"):
            c1, c2 = st.columns(2)
            username = c1.text_input("Username")
            full_name = c2.text_input("Full Name")
            c1, c2, c3 = st.columns(3)
            email = c1.text_input("Email")
            role = c2.selectbox("Role", ["employee", "hr", "admin"])
            password = c3.text_input("Temporary Password", type="password")
            submitted = st.form_submit_button("Create Account", type="primary")
        if submitted:
            if not username or not full_name or not password:
                st.error("Username, full name and password are required.")
            else:
                try:
                    conn = get_conn()
                    conn.execute(
                        "INSERT INTO users (username,password_hash,full_name,email,role,created_at) VALUES (?,?,?,?,?,?)",
                        (username, hash_password(password), full_name, email, role, now()),
                    )
                    conn.commit(); conn.close()
                    audit("CREATED_USER", f"{username} ({role})")
                    st.success(f"Created {role} account: {username}")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That username already exists.")
    with tab2:
        employee_database_view()
    with tab3:
        analytics_dashboard(apps, employees)
    with tab4:
        logs = read_df("SELECT username, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 200")
        st.dataframe(logs, use_container_width=True, hide_index=True)


if "user" not in st.session_state:
    login_screen()
    st.stop()

header()
with st.sidebar:
    st.write(f"**{st.session_state.user['full_name']}**")
    st.write(st.session_state.user["role"].upper())
    if st.button("Logout", use_container_width=True):
        audit("LOGOUT")
        st.session_state.clear()
        st.rerun()

role = st.session_state.user["role"]
if role == "employee":
    employee_portal()
elif role == "hr":
    hr_portal()
elif role == "admin":
    admin_portal()
else:
    st.error("Unknown role")
