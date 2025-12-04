import streamlit as st, json, threading, time, smtplib, os, uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from streamlit_autorefresh import st_autorefresh
from zoneinfo import ZoneInfo

TASKS_FILE = "tasks.json"
GMT_PLUS_7 = ZoneInfo("Asia/Jakarta")

class TaskManager:
    # Sistem agar deadline sesuai timezone
    def __init__(self, tasks_file=TASKS_FILE, timezone=GMT_PLUS_7):
        self.tasks_file, self.timezone = tasks_file, timezone

    def fix_timezone_for_existing_tasks(self, all_tasks):
        for email, tasks in all_tasks.items():
            for task in tasks:
                if "deadline" in task:
                    try:
                        deadline_dt = datetime.fromisoformat(task["deadline"])
                        if deadline_dt.tzinfo is None:
                            task["deadline"] = deadline_dt.replace(tzinfo=self.timezone).isoformat()
                    except: print(f"Error fixing timezone for task {task.get('id', 'unknown')}")
        return all_tasks

    # Sistem baca file json
    def load_tasks(self):
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return self.fix_timezone_for_existing_tasks(data) if isinstance(data, dict) else {}
            return {}
        except Exception as e: st.error(f"Error loading tasks: {e}"); return {}

    # Sistem simpan data ke json
    def save_tasks(self, all_tasks):
        try:
            all_tasks = all_tasks if isinstance(all_tasks, dict) else {}
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(all_tasks, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e: st.error(f"Error saving tasks: {e}"); return False

    # Sistem input tugas baru
    def add_task(self, email, task_name, deadline_datetime):
        all_tasks = self.load_tasks()
        if email not in all_tasks: all_tasks[email] = []
        new_task = {"name": task_name.strip(), "deadline": deadline_datetime.isoformat(), "id": uuid.uuid4().hex}
        all_tasks[email].append(new_task)
        return self.save_tasks(all_tasks), new_task

    # Sistem hapus tugas
    def delete_task(self, email, task_id):
        all_tasks = self.load_tasks()
        if email in all_tasks:
            original_length = len(all_tasks[email])
            all_tasks[email] = [task for task in all_tasks[email] if task.get("id") != task_id]
            if len(all_tasks[email]) < original_length:
                return self.save_tasks(all_tasks), True
        return False, False

    # Sistem ambil tugas dari email tertentu
    def get_tasks_for_email(self, email):
        """Ambil semua tugas untuk email tertentu"""
        all_tasks = self.load_tasks()
        return all_tasks.get(email, [])


class EmailNotifier:
    # Sistem ambil config email pengirim
    def __init__(self, sender_email=None, app_password=None, timezone=GMT_PLUS_7):
        self.sender_email = sender_email or SENDER_EMAIL
        self.app_password = app_password or APP_PASSWORD
        self.timezone = timezone

    # Sistem notif ke Email
    def send_email(self, to_email, subject, body):
        if not self.sender_email or not self.app_password: print("Error: Konfigurasi email belum diatur!"); return False
        try:
            msg = MIMEText(body); msg['Subject'], msg['From'], msg['To'] = subject, self.sender_email, to_email
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.sender_email, self.app_password); server.send_message(msg)
            return True
        except Exception as e: print(f"Gagal kirim email: {e}"); return False

    # Sistem Notif H-3, H-2, H-1 Deadline
    def send_deadline_reminder(self, to_email, task_name, deadline_datetime, hours_remaining):
        """Kirim reminder untuk tugas yang mendekati deadline"""
        now = datetime.now(self.timezone)
        if hours_remaining == 1:
            subject = f"🚨 DARURAT! Tugas '{task_name}' deadline 1 jam lagi!"
        elif hours_remaining == 2:
            subject = f"⚠️ PERINGATAN! Tugas '{task_name}' deadline 2 jam lagi!"
        elif hours_remaining == 3:
            subject = f"🔔 REMINDER! Tugas '{task_name}' deadline 3 jam lagi!"
        else:
            subject = f"⚠️ Tugas '{task_name}' deadline {hours_remaining} jam lagi!"

        body = f"Reminder: Tugas '{task_name}' akan deadline pada {deadline_datetime.strftime('%d-%m-%Y %H:%M')}\n\nWaktu tersisa: {deadline_datetime - now}"
        return self.send_email(to_email, subject, body)

    # Sistem tes email
    def send_test_email(self, to_email):
        """Kirim email test"""
        return self.send_email(to_email, "Test Notifikasi Reminder", "Ini adalah email test dari DLRemindMe.")

    # SISTEM UTAMA
    def check_and_send_notifications(self, task_manager, current_email, sent_notifications):
        """Periksa dan kirim notifikasi untuk tugas yang mendekati deadline"""
        if not current_email:
            return sent_notifications

        tasks = task_manager.get_tasks_for_email(current_email)
        now = datetime.now(self.timezone)

        for task in tasks:
            try:
                deadline_dt = datetime.fromisoformat(task["deadline"])
                if deadline_dt.tzinfo is None:
                    deadline_dt = deadline_dt.replace(tzinfo=self.timezone)
                task_id = task.get("id", "")

                # Skip tasks that are already past deadline
                if deadline_dt <= now:
                    continue

                # Check for H-3 notification
                if deadline_dt - timedelta(hours=3) <= now and f"{task_id}_h3" not in sent_notifications:
                    if self.send_deadline_reminder(current_email, task['name'], deadline_dt, 3):
                        sent_notifications.add(f"{task_id}_h3")
                        print(f"Notifikasi H-3 dikirim untuk tugas: {task['name']}")

                # Check for H-2 notification
                if deadline_dt - timedelta(hours=2) <= now and f"{task_id}_h2" not in sent_notifications:
                    if self.send_deadline_reminder(current_email, task['name'], deadline_dt, 2):
                        sent_notifications.add(f"{task_id}_h2")
                        print(f"Notifikasi H-2 dikirim untuk tugas: {task['name']}")

                # Check for H-1 notification
                if deadline_dt - timedelta(hours=1) <= now and f"{task_id}_h1" not in sent_notifications:
                    if self.send_deadline_reminder(current_email, task['name'], deadline_dt, 1):
                        sent_notifications.add(f"{task_id}_h1")
                        print(f"Notifikasi H-1 dikirim untuk tugas: {task['name']}")

            except Exception as e:
                print(f"Error processing task: {e}")

        return sent_notifications


class UIManager:
    # Sistem Notifikasi Sukses Input
    def set_success_message(self, message, duration=3):
        st.session_state["success_message"], st.session_state["success_timestamp"], st.session_state["success_duration"] = message, time.time(), duration

    def show_success_message(self):
        if st.session_state.get("success_message", ""):
            elapsed = time.time() - st.session_state.get("success_timestamp", 0)
            if elapsed < st.session_state.get("success_duration", 3): st.success(st.session_state["success_message"])
            else: st.session_state["success_message"], st.session_state["success_timestamp"] = "", 0

    # Sistem Countdown 
    def show_task_countdown(self, task, timezone):
        try:
            deadline_dt = datetime.fromisoformat(task["deadline"])
            if deadline_dt.tzinfo is None: deadline_dt = deadline_dt.replace(tzinfo=timezone)
            remaining = deadline_dt - datetime.now(timezone)
            if remaining.total_seconds() > 0:
                days, hours, minutes, seconds = remaining.days, remaining.seconds // 3600, (remaining.seconds // 60) % 60, remaining.seconds % 60
                return f"{days}d {hours}h {minutes}m {seconds}s"
            return "Expired"
        except: return "Error"

# Configurasi email pengirim
SENDER_EMAIL, APP_PASSWORD = "bayhaqinaryo13@gmail.com", "auaq lvhj qihk ulem"

# Aktifin class
task_manager, email_notifier, ui_manager = TaskManager(), EmailNotifier(), UIManager()

# Wrapper functions
def set_success_message(message, duration=3): ui_manager.set_success_message(message, duration)
def show_success_message(): ui_manager.show_success_message()
def load_tasks(): return task_manager.load_tasks()
def save_tasks(all_tasks): return task_manager.save_tasks(all_tasks)
def send_email(to_email, subject, body): return email_notifier.send_email(to_email, subject, body)

# Sistem Thread
def check_notifications():
    sent_notifications = set()
    while True:
        try:
            time.sleep(60); current_email = st.session_state.get("current_email", "")
            sent_notifications = email_notifier.check_and_send_notifications(task_manager, current_email, sent_notifications)
        except Exception as e: print(f"Error in notification thread: {e}"); time.sleep(5)


st.set_page_config(page_title="DLRemindMe", layout="wide")
# HEADER UTAMA
st.markdown("""
<div style='background-color: #9370DB; padding: 20px; border-radius: 10px; margin-bottom: 20px; color: white;'>
    <h1 style='text-align: center; margin: 0; color: white;'>DLRemindMe</h1>
    <p style='text-align: center; margin: 5px 0 0 0; color: #e6f3ff;'>Reminder Tugas Sebelum Deadline</p>
</div>
""", unsafe_allow_html=True)

st_autorefresh(interval=1000, key="auto_refresh")

# Session state init
for key, default in [("current_email", ""), ("current_page", "email"), ("thread_started", False), ("success_message", ""), ("success_timestamp", 0)]:
    if key not in st.session_state: st.session_state[key] = default

# Tampilkan pesan sukses input
show_success_message()

# Load tugas dari json
all_tasks = task_manager.load_tasks()
current_email = st.session_state.get("current_email", "")

# ===== NAVIGASI HALAMAN =====
current_page = st.session_state["current_page"]

if current_page == "email":
    # ===== HALAMAN 1: EMAIL SETUP =====

    # ===== NAVIGASI =====
    col1, col2, col3 = st.columns([2, 3, 2])

    with col1:
        if st.button("📧 Email Setup"):
            st.session_state["current_page"] = "email"
            st.rerun()

    with col3:
        if st.button("📋 Task Manager"):
            st.session_state["current_page"] = "tasks"
            st.rerun()

    st.header("📧 Setup Email Penerima")

    # ===== Email Penerima =====
    st.subheader("Email Penerima Notifikasi")
    with st.form("email_form"):
        email_input = st.text_input("Email Penerima", value=st.session_state.get("current_email", ""), placeholder="penerima@gmail.com")
        submitted = st.form_submit_button("Pilih Email")
        if submitted:
            if email_input.strip():
                st.session_state["current_email"] = email_input.strip()
                set_success_message("✅ Email penerima berhasil disimpan!", 3)
                st.session_state["current_page"] = "tasks"; st.rerun()
            else: st.error("❌ Email tidak boleh kosong!")

    # ===== Test Email =====
    st.subheader("📤 Test Kirim Email")

    if current_email:
        st.info(f"📧 Email penerima saat ini: **{current_email}**")
    else:
        st.warning("⚠️ Belum ada email penerima yang dipilih!")

    if st.button("📨 Kirim Test Email ke Penerima"):
        if not current_email:
            st.error("❌ Pilih email penerima terlebih dahulu!")
        else:
            st.info(f"📤 Mengirim test email ke: {current_email}...")
            if send_email(current_email, "Test Notifikasi Reminder", "Ini adalah email test dari DLRemindMe."):
                set_success_message(f"✅ Test email berhasil dikirim ke {current_email}! Cek inbox email kamu.", duration=8)
            else:
                st.error("❌ Gagal mengirim test email. Pastikan konfigurasi email pengirim sudah benar di kode.")

if current_page == "tasks":
    # ===== HALAMAN 2: TASK MANAGER =====

    # ===== NAVIGASI =====
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("📧 Email Setup"):
            st.session_state["current_page"] = "email"
            st.rerun()

    with col3:
        if st.button("📋 Task Manager"):
            st.session_state["current_page"] = "tasks"
            st.rerun()

    st.header("📋 Task Manager")

    # ===== Tambah Tugas =====
    tasks = task_manager.get_tasks_for_email(current_email) if current_email else []

    if not current_email:
        st.warning("⚠️ Silakan setup email penerima terlebih dahulu di halaman Email Setup!")
        if st.button("⬅️ Kembali ke Email Setup"):
            st.session_state["current_page"] = "email"
            st.rerun()
    else:
        # input tugas baru
        st.subheader("Tambah Tugas Baru")
        with st.form("task_form"):
            name = st.text_input("Nama Tugas", placeholder="Masukkan nama tugas...")
            deadline_input = st.date_input("Deadline", format="DD-MM-YYYY")
            submitted = st.form_submit_button("➕ Tambah Tugas")

        if submitted:
            if not current_email:
                st.error("❌ Pilih email penerima terlebih dahulu!")
            elif not name.strip():
                st.error("❌ Nama tugas tidak boleh kosong!")
            elif SENDER_EMAIL == "your-email@gmail.com" or APP_PASSWORD == "your-app-password":
                st.error("❌ Konfigurasi email pengirim belum diatur di kode! Edit file DLRemindMe.py")
            else:

                deadline_dt = datetime.combine(deadline_input, datetime.min.time()).replace(tzinfo=GMT_PLUS_7)
                success, new_task = task_manager.add_task(current_email, name.strip(), deadline_dt)
                if success:
                    set_success_message(f"✅ Tugas '{name.strip()}' berhasil ditambahkan!")
                    all_tasks = task_manager.load_tasks()
                else:
                    st.error("❌ Gagal menyimpan tugas. Silakan coba lagi.")

        # ===== Daftar Tugas =====
        st.subheader(f"📌 Daftar Tugas ({current_email})")

        if not tasks: st.info("📝 Belum ada tugas. Tambahkan tugas baru di atas!")
        else:
            for task in tasks:
                try:
                    # Tampilkan deadline
                    deadline_dt = datetime.fromisoformat(task["deadline"])
                    if deadline_dt.tzinfo is None:
                        deadline_dt = deadline_dt.replace(tzinfo=GMT_PLUS_7)

                    # Countdown deadline
                    countdown = ui_manager.show_task_countdown(task, GMT_PLUS_7)

                    # Tampilkan daftar tugas
                    cols = st.columns([8, 2])
                    task_name = task.get("name", "Unknown")
                    deadline_str = deadline_dt.strftime("%d-%m-%Y")
                    cols[0].markdown(f'<div style="font-size: 20px; line-height: 1.5;">📝 {task_name} | 📅 {deadline_str} | ⏱️ {countdown}</div>', unsafe_allow_html=True)
                   
                    # Tombol hapus tugas
                    if cols[1].button("🗑️ Hapus", key=f"del_{task.get('id', 'unknown')}"):
                        success, deleted = task_manager.delete_task(current_email, task.get("id"))
                        if success and deleted:
                            set_success_message(f"✅ Tugas '{task_name}' dihapus!")
                            tasks = task_manager.get_tasks_for_email(current_email)
                        else: st.error("❌ Gagal menghapus tugas.")
                except Exception as e:
                    st.error(f"Error menampilkan tugas: {e}")


if not st.session_state["thread_started"]:
    threading.Thread(target=check_notifications, daemon=True).start()
    st.session_state["thread_started"] = True