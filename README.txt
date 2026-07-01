JW SEZ Digital HR Onboarding Prototype - Presentation Ready

Purpose:
This Streamlit prototype demonstrates a digital onboarding process:
Employee fills onboarding form -> HR reviews -> Approved employee is added to the employee database -> HR/Admin view analytics.

Demo Logins:
Employee: employee.demo / employee1234
HR:       hr.manager / hr1234
Admin:    admin / admin1234

Run Locally:
1. Extract this ZIP.
2. Double-click 1_INSTALL_FIRST_TIME.bat.
3. Double-click 2_RUN_DEMO.bat.
4. Browser will open at http://localhost:8501.

Deploy on Streamlit Cloud:
1. Upload this folder contents to a GitHub repository.
2. Include app.py, requirements.txt and .streamlit/config.toml.
3. Go to https://share.streamlit.io.
4. Create a new app and select app.py as the main file.
5. Deploy and share the Streamlit link with HR.

Important Demo Note:
Streamlit Community Cloud local SQLite storage can reset after reboot/redeploy.
For a production version, use PostgreSQL/Supabase instead of local SQLite.
