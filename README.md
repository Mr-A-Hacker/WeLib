# 📚 WeLib  
A lightweight, self‑hosted web library system built with **Python (Flask)** and a simple HTML interface.  
WeLib is designed to be fast, minimal, and easy to deploy — perfect for small personal libraries, LAN setups, or simple book‑tracking tools.

---

## 🚀 Features
- 🖥️ **Clean HTML interface** (`index.html`)
- 🐍 **Flask backend** (`app.py`)
- 📦 **Easy dependency setup** via `requirements.txt`
- 🐳 **Docker support** for fast deployment
- ⚡ Lightweight and beginner‑friendly codebase

---

## 📁 Project Structure
```
WeLib/
│
├── app.py               # Flask backend server
├── index.html           # Main UI page
├── requirements.txt     # Python dependencies
└── Dockerfile           # Container build instructions
```

---

## 🛠️ Installation (Local)
### 1. Clone the repository
```bash
git clone https://github.com/Mr-A-Hacker/WeLib
cd WeLib
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the server
```bash
python app.py
```

### 4. Open in your browser
```
http://localhost:5000
```

---

## 🐳 Running with Docker
### Build the image
```bash
docker build -t welib .
```

### Run the container
```bash
docker run -p 5000:5000 welib
```

### Access the app
```
http://localhost:5000
```

---

## 🧩 How It Works
### Frontend (`index.html`)
- Displays the main UI  
- Sends requests to the Flask backend  

### Backend (`app.py`)
- Hosts the web server  
- Handles routes  
- Renders the HTML interface  

---

## 📌 Future Improvements
- Add book search  
- Add database support (SQLite)  
- Add user accounts  
- Add upload system for PDFs  
- Add dark mode UI  

---

## 🤝 Contributing
Pull requests are welcome!  
Feel free to improve the UI, backend logic, or add new features.

---

## ⭐ Support the Project
If you like this project, consider starring the repo — it helps a lot!
