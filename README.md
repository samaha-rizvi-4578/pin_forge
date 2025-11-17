

# Django Project Setup Guide

This repository contains a Django project. Follow the steps below to install and run it on your system.

---

## 📦 Requirements

* Python **3.9+**
* pip (Python package manager)
* Virtual environment tool (recommended)
* Git (optional)

---

## 🚀 1. Clone the Repository

```bash
git clone https://github.com/your-username/your-project.git
cd your-project
```

---

## 🧱 2. Create & Activate Virtual Environment

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

---

## 📥 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` is missing, generate it:

```bash
pip install django
pip freeze > requirements.txt
```

---

## ⚙️ 4. Environment Variables (Optional)

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
```

If using `django-environ`, ensure you load it in `settings.py`.

---

## 🗂️ 5. Apply Migrations

```bash
python manage.py migrate
```

---

## 👤 6. Create Admin User

```bash
python manage.py createsuperuser
```

---

## ▶️ 7. Start Development Server

```bash
python manage.py runserver
```

Project will be available at:

```
http://127.0.0.1:8000/
```

---

## 🧪 8. Run Tests

```bash
python manage.py test
```

---

## 📦 9. Collect Static Files (Production Only)

```bash
python manage.py collectstatic
```

---

## 🏗️ Project Structure

```
project-root/
│
├── app_name/
├── project_name/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── manage.py
├── requirements.txt
└── README.md
```

---

## 📝 Notes

* Always activate your virtual environment before running Django commands.
* Set `DEBUG=False` in production.
* Configure database, allowed hosts, and static files for deployment.


