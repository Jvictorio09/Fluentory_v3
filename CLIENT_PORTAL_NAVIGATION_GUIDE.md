# Fluentory Client Navigation Guide

This guide explains how to use the platform from a client perspective across the four main roles:

- Admin
- Teacher
- Student
- Partner

All links below use the production domain:

- `https://www.fluentory.me`

---

## 1) Quick Access and Login

### Main public pages

- Home (EN): [https://www.fluentory.me/](https://www.fluentory.me/)
- Home (AR): [https://www.fluentory.me/ar/](https://www.fluentory.me/ar/)
- Courses: [https://www.fluentory.me/courses/](https://www.fluentory.me/courses/)
- Login: [https://www.fluentory.me/login/](https://www.fluentory.me/login/)
- Register (Student): [https://www.fluentory.me/register/](https://www.fluentory.me/register/)
- Register (Teacher): [https://www.fluentory.me/register/teacher/](https://www.fluentory.me/register/teacher/)

### Default admin credentials (as requested)

- Username: `admin`
- Password: `admin`

Recommended first action after login: change the password immediately.

---

## 2) Role-Based Entry Points

- **Admin Dashboard**: [https://www.fluentory.me/dashboard/](https://www.fluentory.me/dashboard/)
- **Teacher Dashboard**: [https://www.fluentory.me/teacher/](https://www.fluentory.me/teacher/)
- **Student Dashboard**: [https://www.fluentory.me/my-dashboard/](https://www.fluentory.me/my-dashboard/)
- **Partner Dashboard**: [https://www.fluentory.me/partner/](https://www.fluentory.me/partner/)
- **Django Admin (technical/backoffice)**: [https://www.fluentory.me/admin/](https://www.fluentory.me/admin/)

---

## 3) Admin Dashboard Navigation

Admin handles platform setup, courses, lessons, learners, bundles, CRM, and monitoring.

### Core pages

- Dashboard Home: [https://www.fluentory.me/dashboard/](https://www.fluentory.me/dashboard/)
- Analytics: [https://www.fluentory.me/dashboard/analytics/](https://www.fluentory.me/dashboard/analytics/)
- Site Settings: [https://www.fluentory.me/dashboard/settings/](https://www.fluentory.me/dashboard/settings/)

### Course management

- Courses list: [https://www.fluentory.me/dashboard/courses/](https://www.fluentory.me/dashboard/courses/)
- Add course: [https://www.fluentory.me/dashboard/courses/add/](https://www.fluentory.me/dashboard/courses/add/)
- Lessons list (all): [https://www.fluentory.me/dashboard/lessons/](https://www.fluentory.me/dashboard/lessons/)
- Add lesson: [https://www.fluentory.me/dashboard/lessons/add/](https://www.fluentory.me/dashboard/lessons/add/)
- Quizzes: [https://www.fluentory.me/dashboard/quizzes/](https://www.fluentory.me/dashboard/quizzes/)

### Student operations

- Students list: [https://www.fluentory.me/dashboard/students/](https://www.fluentory.me/dashboard/students/)
- Student progress view: [https://www.fluentory.me/dashboard/students/progress/](https://www.fluentory.me/dashboard/students/progress/)
- Bulk access manager: [https://www.fluentory.me/dashboard/access/bulk/](https://www.fluentory.me/dashboard/access/bulk/)

### Bundles

- Bundles list: [https://www.fluentory.me/dashboard/bundles/](https://www.fluentory.me/dashboard/bundles/)
- Add bundle: [https://www.fluentory.me/dashboard/bundles/add/](https://www.fluentory.me/dashboard/bundles/add/)

### CRM and teacher applications

- CRM leads: [https://www.fluentory.me/dashboard/crm/leads/](https://www.fluentory.me/dashboard/crm/leads/)
- CRM analytics: [https://www.fluentory.me/dashboard/crm/analytics/](https://www.fluentory.me/dashboard/crm/analytics/)
- Teacher requests: [https://www.fluentory.me/dashboard/teacher-requests/](https://www.fluentory.me/dashboard/teacher-requests/)

### Typical admin workflow

1. Create a course at `/dashboard/courses/add/`.
2. Configure course visibility and ordering (including V3 landing settings if needed).
3. Add lessons and quizzes.
4. Grant student access manually or through purchase flow.
5. Track analytics and student progress.
6. Review partner and CRM data for growth insights.

---

## 4) Teacher Portal Navigation

Teachers manage their profile, courses, lessons, and live sessions.

### Main pages

- Teacher home: [https://www.fluentory.me/teacher/](https://www.fluentory.me/teacher/)
- Profile: [https://www.fluentory.me/teacher/profile/](https://www.fluentory.me/teacher/profile/)
- My courses: [https://www.fluentory.me/teacher/courses/](https://www.fluentory.me/teacher/courses/)
- Add course: [https://www.fluentory.me/teacher/courses/add/](https://www.fluentory.me/teacher/courses/add/)

### Live sessions

- Live sessions list: [https://www.fluentory.me/teacher/sessions/](https://www.fluentory.me/teacher/sessions/)

From a course page, teachers can create a live session using the "Create Live Session" action for that course.

### Typical teacher workflow

1. Open `/teacher/courses/`.
2. Create or edit a course.
3. Add lessons and supporting content.
4. Schedule live sessions.
5. Check bookings and mark attendance.

---

## 5) Student Portal Navigation

Students browse courses, purchase/enroll, learn, take quizzes, and track progress.

### Main pages

- Student dashboard: [https://www.fluentory.me/my-dashboard/](https://www.fluentory.me/my-dashboard/)
- Certifications list: [https://www.fluentory.me/my-certifications/](https://www.fluentory.me/my-certifications/)
- Courses catalog: [https://www.fluentory.me/courses/](https://www.fluentory.me/courses/)

### Learning flow

1. Student opens courses page.
2. Selects a course detail page.
3. Purchases paid course or enrolls in free course.
4. Accesses lessons and quizzes.
5. Progress is saved in dashboard automatically.
6. Certificate becomes available after completion requirements.

### Useful public pages

- Login: [https://www.fluentory.me/login/](https://www.fluentory.me/login/)
- Register: [https://www.fluentory.me/register/](https://www.fluentory.me/register/)

---

## 6) Partner Portal Navigation

Partners monitor attributed sales and conversion performance.

### Main pages

- Partner dashboard: [https://www.fluentory.me/partner/](https://www.fluentory.me/partner/)

### What partners see

- Total attributed revenue (all-time)
- Recent paid orders
- Course-level performance (sales, revenue, commission)
- Conversion and trend data

### Attribution note

Partner metrics depend on attributed purchases. If a sale is not attributed to the partner, it will not appear in partner totals.

---

## 7) Creator Lesson Pages (Internal Content Team)

If your team uses the creator workflow:

- Creator home: [https://www.fluentory.me/creator/](https://www.fluentory.me/creator/)

Current behavior:

- AI lesson generation/regeneration is shown as "coming soon".
- Manual lesson creation and editing are active.
- AI Coach training and testing tools are still available where enabled.

---

## 8) Link Patterns for Dynamic Pages

Some links depend on slugs or IDs. Use these patterns:

- Course detail: `https://www.fluentory.me/courses/<course-slug>/`
- Lesson page: `https://www.fluentory.me/courses/<course-slug>/<lesson-slug>/`
- Teacher profile: `https://www.fluentory.me/teachers/<username>/`
- Student certificate verify: `https://www.fluentory.me/verify-certificate/<certificate-id>/`

Replace placeholders with real values from the dashboard URLs.

---

## 9) Recommended Client Onboarding Sequence

1. Login with admin account.
2. Update admin password.
3. Review site settings and currencies.
4. Add at least 3 public courses and verify V3 landing placement.
5. Create teacher accounts and assign ownership.
6. Test student purchase and lesson access end-to-end.
7. Verify partner attribution on test links.
8. Share role-specific links from this guide with operations staff.

---

## 10) Troubleshooting Basics

- If a page opens but data is empty, verify the user role has access and that records exist.
- If partner dashboard seems low, validate attribution setup and paid purchase status.
- If a student cannot open a lesson, check enrollment/access grant first.
- If links redirect to login, authenticate and retry with the same account type.

