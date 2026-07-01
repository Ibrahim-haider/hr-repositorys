JW SEZ Digital HR Prototype
===========================

Purpose:
This is a lightweight prototype for demonstrating the core HR onboarding workflow:

1. Employee logs in and fills the onboarding form.
2. Employee uploads basic documents and submits to HR.
3. HR logs in and reviews the submitted form.
4. HR approves, rejects, or requests changes.
5. When HR approves, the employee is automatically added to the main employees database.

How to run on Windows:
1. Extract the ZIP file.
2. Double-click 1_INSTALL_FIRST_TIME.bat once.
3. Double-click 2_RUN_DEMO.bat whenever you want to run the system.
4. The browser should open automatically. If not, open http://localhost:8501

Demo logins:
Employee: employee.demo / employee1234
HR:       hr.manager    / hr1234
Admin:    admin         / admin1234

Recommended demo script:
1. Login as employee.demo.
2. Fill and submit the onboarding form.
3. Logout.
4. Login as hr.manager.
5. Open the pending application.
6. Click Approve & Add to Employee Database.
7. Open Existing Employees Database and show that the employee has been added.

Files created by the app:
- jw_sez_hr_prototype.db: local SQLite database
- uploads/: uploaded documents folder

This is a prototype, not the final production HRMS.
