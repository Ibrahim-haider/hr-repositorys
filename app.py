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
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "jw_sez_hr_prototype.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

PRIMARY = "#23395B"
ACCENT = "#B88A44"
BG = "#F6F8FB"
GREEN = "#1F7A4D"
RED = "#B23B3B"


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
    .stApp {{ background: {BG}; }}
    .block-container {{ padding-top: 1.3rem; }}
    h1, h2, h3 {{ color: {PRIMARY}; }}
    .topbar {{ background:{PRIMARY}; color:white; padding:18px 24px; border-radius:16px; margin-bottom:18px; }}
    .brand {{ font-size:24px; font-weight:800; }}
    .subtitle {{ color:#DDE6F3; font-size:14px; margin-top:4px; }}
    .card {{ background:white; padding:18px; border-radius:16px; border:1px solid #E6EAF0; box-shadow:0 8px 24px rgba(31,45,61,.06); }}
    .metric-title {{ color:#6B7280; font-size:13px; }}
    .metric-value {{ color:{PRIMARY}; font-size:30px; font-weight:800; }}
    .status {{ padding:4px 10px; border-radius:999px; font-weight:700; font-size:12px; }}
    .pending {{ background:#FFF2CC; color:#7A5A00; }}
    .approved {{ background:#DCFCE7; color:#166534; }}
    .rejected {{ background:#FEE2E2; color:#991B1B; }}
    .changes {{ background:#E0E7FF; color:#3730A3; }}
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
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown(
            f"""
            <div class='card'>
              <h2 style='text-align:center;margin-bottom:0'>JW SEZ Digital HR Prototype</h2>
              <p style='text-align:center;color:#6B7280'>Employee onboarding → HR review → employee database</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### Sign in")
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
        st.info(
            "Demo logins:\n\n"
            "Employee: `employee.demo / employee1234`\n\n"
            "HR: `hr.manager / hr1234`\n\n"
            "Admin: `admin / admin1234`"
        )


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


def hr_portal():
    st.subheader("HR Review Portal")
    apps = read_df("SELECT id, full_name, cnic, department, designation, status, submitted_at FROM onboarding_applications ORDER BY id DESC")
    employees = read_df("SELECT * FROM employees ORDER BY id DESC")
    pending_count = int((apps["status"] == "Pending").sum()) if not apps.empty else 0
    approved_count = int((apps["status"] == "Approved").sum()) if not apps.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Pending Review", pending_count)
    c2.metric("Approved Applications", approved_count)
    c3.metric("Existing Employees", len(employees))

    tab1, tab2, tab3 = st.tabs(["Pending / Submitted Forms", "Existing Employees Database", "Audit Log"])
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
        st.markdown("These are only the employees whose onboarding forms were approved by HR.")
        if employees.empty:
            st.info("No approved employees yet.")
        else:
            st.dataframe(employees, use_container_width=True, hide_index=True)
            st.download_button(
                "Download Employees CSV",
                employees.to_csv(index=False).encode("utf-8"),
                "jw_sez_employees.csv",
                "text/csv",
            )

    with tab3:
        logs = read_df("SELECT username, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 100")
        st.dataframe(logs, use_container_width=True, hide_index=True)


def admin_portal():
    st.subheader("Admin Panel")
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
