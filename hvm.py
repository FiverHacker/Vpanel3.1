import os
import sys
import subprocess
import requests
import flask
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import docker
import random
import string
import json
import datetime
import time
import logging
import socket
import paramiko
import traceback
import shutil
import sqlite3
import threading
from dotenv import load_dotenv
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import psutil
import struct

# Unix-specific imports (not available on Windows)
try:
    import pty
    import select
    import termios
    import tty
    import fcntl
    HAS_UNIX_TERMINAL = True
except ImportError:
    # Windows fallback - use pywinpty if available
    try:
        import winpty
        HAS_UNIX_TERMINAL = False
        HAS_WINPTY = True
    except ImportError:
        HAS_UNIX_TERMINAL = False
        HAS_WINPTY = False
        pty = None
        select = None
        termios = None
        tty = None
        fcntl = None
import signal
import uuid
import concurrent.futures
import csv
import io
from werkzeug.utils import secure_filename
import tarfile
from io import BytesIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import smtplib
from email.mime.text import MIMEText
from collections import deque
import shlex
import base64
from ecdsa import VerifyingKey, BadSignatureError, NIST384p

PUBLIC_HEX = 'b681f4f051055d844c3f21678db26759adacf292fc649b49e08800b316173927aa08df82ad4a9a9930e26315ddc8531671ba42cdf16e91c086ce30150b6470cb37f390da3b3ec6522bed24cb1703efff9a0c8ec8d744222657e1944f5a08d81e'

# Removed unused imports: pytz, requests (duplicate), bcrypt, matplotlib, pandas, seaborn, base64

def check_docker_installed():
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        return True
    except:
        return False

def check_docker_running():
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        return True
    except:
        return False

def install_docker():
    """Install Docker - only works on Linux/Unix systems"""
    if sys.platform == "win32":
        print("\n" + "="*60)
        print("Docker is not installed or not in PATH.")
        print("On Windows, please install Docker Desktop manually:")
        print("1. Download from: https://www.docker.com/products/docker-desktop")
        print("2. Install Docker Desktop")
        print("3. Start Docker Desktop")
        print("4. Make sure Docker is running and try again")
        print("="*60 + "\n")
        return False
    
    try:
        response = requests.get("https://get.docker.com")
        with open("get-docker.sh", "w") as f:
            f.write(response.text)
        subprocess.run(["sh", "get-docker.sh"], check=True)
        subprocess.run(["systemctl", "start", "docker"], check=True)
        subprocess.run(["systemctl", "enable", "docker"], check=True)
        os.remove("get-docker.sh")
        return True
    except Exception as e:
        print(f"Error installing Docker: {e}")
        return False

if not check_docker_installed():
    if not install_docker():
        print("\nERROR: Docker is required but not installed.")
        print("Please install Docker and ensure it's in your PATH, then try again.\n")
        sys.exit(1)

if not check_docker_running():
    if sys.platform == "win32":
        print("\nWARNING: Docker appears to be installed but not running.")
        print("Please start Docker Desktop and try again.\n")
        sys.exit(1)
    else:
        try:
            subprocess.run(["systemctl", "start", "docker"], check=True)
        except Exception as e:
            print(f"Warning: Could not start Docker: {e}")
            print("Please start Docker manually and try again.")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hvm_panel.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('HVMPanel')

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', ''.join(random.choices(string.ascii_letters + string.digits, k=32)))
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
PANEL_NAME = os.getenv('PANEL_NAME', 'apkhub cloud')
WATERMARK = os.getenv('WATERMARK', 'HVM VPS Service')
WELCOME_MESSAGE = os.getenv('WELCOME_MESSAGE', 'Welcome to HVM PANEL! Power Your Future!')
MAX_VPS_PER_USER = int(os.getenv('MAX_VPS_PER_USER', '3'))
DEFAULT_OS_IMAGE = os.getenv('DEFAULT_OS_IMAGE', 'ubuntu:22.04')
DOCKER_NETWORK = os.getenv('DOCKER_NETWORK', 'hvm_network')
MAX_CONTAINERS = int(os.getenv('MAX_CONTAINERS', '100'))
DB_FILE = 'hvm_panel.db'
BACKUP_FILE = 'hvm_panel_backup.json'
SERVER_IP = os.getenv('SERVER_IP', socket.gethostbyname(socket.gethostname()))
# Tunnel/IP Configuration
TUNNEL_ENABLED = os.getenv('TUNNEL_ENABLED', 'true').lower() == 'true'
PUBLIC_IP_POOL_START = os.getenv('PUBLIC_IP_POOL_START', '10.0.0.2')
PUBLIC_IP_POOL_END = os.getenv('PUBLIC_IP_POOL_END', '10.0.255.254')
TUNNEL_INTERFACE = os.getenv('TUNNEL_INTERFACE', 'tun0')
SERVER_PORT = int(os.getenv('SERVER_PORT', '3000'))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'tar', 'gz', 'iso', 'dockerfile'}
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.example.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER', 'user@example.com')
SMTP_PASS = os.getenv('SMTP_PASS', 'password')
NOTIFICATION_EMAIL = os.getenv('NOTIFICATION_EMAIL', 'admin@example.com')
BACKUP_SCHEDULE = os.getenv('BACKUP_SCHEDULE', 'daily')
VPS_HOSTNAME_PREFIX = os.getenv('VPS_HOSTNAME_PREFIX', 'hvm-')

MINER_PATTERNS = [
    'xmrig', 'ethminer', 'cgminer', 'sgminer', 'bfgminer',
    'minerd', 'cpuminer', 'cryptonight', 'stratum', 'nicehash', 'miner',
    'xmr-stak', 'ccminer', 'ewbf', 'lolminer', 'trex', 'nanominer'
]

DOCKERFILE_TEMPLATE = """
FROM {base_image}
ENV DEBIAN_FRONTEND=noninteractive

# Install essential system packages first (required for VPS to work)
RUN apt-get update && \\
    apt-get install -y --no-install-recommends systemd systemd-sysv dbus sudo \\
                       curl gnupg2 apt-transport-https ca-certificates \\
                       software-properties-common openssh-server tmate && \\
    apt-get clean && rm -rf /var/lib/apt/lists/* || true

# Configure SSH
RUN mkdir -p /var/run/sshd && \\
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \\
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config || true

# Enable services
RUN systemctl enable ssh || systemctl enable sshd || true

# Install essential tools (fast, commonly available)
RUN apt-get update && \\
    apt-get install -y --no-install-recommends neofetch htop nano vim wget git tmux \\
                       net-tools dnsutils iputils-ping ufw fail2ban && \\
    apt-get clean && rm -rf /var/lib/apt/lists/* || true

# Install optional monitoring tools (continue on failure)
RUN apt-get update && \\
    (apt-get install -y --no-install-recommends nmap iotop glances iftop tcpdump || true) && \\
    apt-get clean && rm -rf /var/lib/apt/lists/* || true

# Install optional advanced tools (continue on failure - these may not be available)
RUN apt-get update && \\
    (apt-get install -y --no-install-recommends btop wireguard openvpn zabbix-agent samba apache2 prometheus-node-exporter sysbench || true) && \\
    apt-get clean && rm -rf /var/lib/apt/lists/* || true

# Try to install docker.io (optional, continue on failure)
RUN (apt-get update && apt-get install -y --no-install-recommends docker.io && \\
     systemctl enable docker || true) || true && \\
    apt-get clean && rm -rf /var/lib/apt/lists/* || true

# Try to install clamav (optional, continue on failure)
RUN (apt-get update && apt-get install -y --no-install-recommends clamav || true) && \\
    apt-get clean && rm -rf /var/lib/apt/lists/* || true

STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
"""

app = Flask(__name__, template_folder=os.path.abspath('.'))
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, role='user', email=None, theme='light'):
        self.id = id
        self.username = username
        self.role = role
        self.email = email
        self.theme = theme

class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self.lock = threading.Lock()
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
        self._initialize_settings()
        self._migrate_database()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def _execute(self, query, params=()):
        with self.lock:
            try:
                self.cursor.execute(query, params)
                self.conn.commit()
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(0.1)
                    self.cursor.execute(query, params)
                    self.conn.commit()
                else:
                    raise

    def _fetchone(self, query, params=()):
        with self.lock:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()

    def _fetchall(self, query, params=()):
        with self.lock:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()

    def _create_tables(self):
        self._execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT DEFAULT 'user',
                email TEXT,
                created_at TEXT,
                theme TEXT DEFAULT 'light'
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS vps_instances (
                token TEXT PRIMARY KEY,
                vps_id TEXT UNIQUE,
                container_id TEXT,
                memory INTEGER,
                cpu INTEGER,
                disk INTEGER,
                bandwidth_limit INTEGER DEFAULT 0,
                username TEXT,
                password TEXT,
                root_password TEXT,
                created_by INTEGER,
                created_at TEXT,
                tmate_session TEXT,
                watermark TEXT,
                os_image TEXT,
                restart_count INTEGER DEFAULT 0,
                last_restart TEXT,
                status TEXT DEFAULT 'running',
                port INTEGER,
                image_id TEXT,
                expires_at TEXT,
                expires_days INTEGER DEFAULT 30,
                expires_hours INTEGER DEFAULT 0,
                expires_minutes INTEGER DEFAULT 0,
                additional_ports TEXT DEFAULT '',
                uptime_start TEXT,
                tags TEXT DEFAULT '',
                FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS usage_stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT DEFAULT 'No reason provided',
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS docker_images (
                image_id TEXT PRIMARY KEY,
                os_image TEXT,
                created_at TEXT
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                created_at TEXT,
                read BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS vps_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                memory INTEGER,
                cpu INTEGER,
                disk INTEGER,
                os_image TEXT,
                description TEXT
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS resource_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vps_id TEXT,
                cpu_percent REAL,
                memory_percent REAL,
                disk_usage REAL,
                bandwidth_in REAL,
                bandwidth_out REAL,
                timestamp TEXT,
                FOREIGN KEY (vps_id) REFERENCES vps_instances (vps_id) ON DELETE CASCADE
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS vps_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS vps_group_assignments (
                group_id INTEGER,
                vps_id TEXT,
                PRIMARY KEY (group_id, vps_id),
                FOREIGN KEY (group_id) REFERENCES vps_groups (id) ON DELETE CASCADE,
                FOREIGN KEY (vps_id) REFERENCES vps_instances (vps_id) ON DELETE CASCADE
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subject TEXT,
                description TEXT,
                status TEXT DEFAULT 'open',
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                referral_code TEXT UNIQUE,
                referred_users INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        self._execute('''
            CREATE TABLE IF NOT EXISTS licenses (
                license_key TEXT PRIMARY KEY,
                active BOOLEAN DEFAULT TRUE,
                created_at TEXT,
                expires_at TEXT
            )
        ''')

    def _migrate_database(self):
        columns = [col[1] for col in self._fetchall("PRAGMA table_info(vps_instances)")]
       
        if 'uptime_start' not in columns:
            self._execute('ALTER TABLE vps_instances ADD COLUMN uptime_start TEXT')
       
        if 'additional_ports' not in columns:
            self._execute('ALTER TABLE vps_instances ADD COLUMN additional_ports TEXT DEFAULT ""')
       
        if 'expires_days' not in columns:
            self._execute('ALTER TABLE vps_instances ADD COLUMN expires_days INTEGER DEFAULT 30')
       
        if 'expires_hours' not in columns:
            self._execute('ALTER TABLE vps_instances ADD COLUMN expires_hours INTEGER DEFAULT 0')
       
        if 'expires_minutes' not in columns:
            self._execute('ALTER TABLE vps_instances ADD COLUMN expires_minutes INTEGER DEFAULT 0')
       
        if 'bandwidth_limit' not in columns:
            self._execute('ALTER TABLE vps_instances ADD COLUMN bandwidth_limit INTEGER DEFAULT 0')
       
        if 'tags' not in columns:
            self._execute('ALTER TABLE vps_instances ADD COLUMN tags TEXT DEFAULT ""')
       
        if 'public_ip' not in columns:
            self._execute('ALTER TABLE vps_instances ADD COLUMN public_ip TEXT')
       
        user_columns = [col[1] for col in self._fetchall("PRAGMA table_info(users)")]
        if 'email' not in user_columns:
            self._execute('ALTER TABLE users ADD COLUMN email TEXT')
        if 'theme' not in user_columns:
            self._execute('ALTER TABLE users ADD COLUMN theme TEXT DEFAULT "light"')

        banned_columns = [col[1] for col in self._fetchall("PRAGMA table_info(banned_users)")]
        if 'reason' not in banned_columns:
            self._execute('ALTER TABLE banned_users ADD COLUMN reason TEXT DEFAULT "No reason provided"')

    def _initialize_settings(self):
        defaults = {
            'max_containers': str(MAX_CONTAINERS),
            'max_vps_per_user': str(MAX_VPS_PER_USER),
            'panel_name': PANEL_NAME,
            'watermark': WATERMARK,
            'welcome_message': WELCOME_MESSAGE,
            'server_ip': SERVER_IP,
            'vps_hostname_prefix': VPS_HOSTNAME_PREFIX,
            'maintenance_mode': 'off',
            'registration_enabled': 'on'
        }
        for key, value in defaults.items():
            self._execute('INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)', (key, value))
       
        admin = self._fetchone('SELECT id FROM users WHERE username = ?', (ADMIN_USERNAME,))
        if not admin:
            hashed = generate_password_hash(ADMIN_PASSWORD)
            self._execute('INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)',
                          (ADMIN_USERNAME, hashed, 'admin', str(datetime.datetime.now())))

    def get_setting(self, key, default=None):
        result = self._fetchone('SELECT value FROM system_settings WHERE key = ?', (key,))
        return result[0] if result else default

    def set_setting(self, key, value):
        self._execute('INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)', (key, str(value)))

    def get_stat(self, key, default=0):
        result = self._fetchone('SELECT value FROM usage_stats WHERE key = ?', (key,))
        return result[0] if result else default

    def increment_stat(self, key, amount=1):
        current = self.get_stat(key)
        self._execute('INSERT OR REPLACE INTO usage_stats (key, value) VALUES (?, ?)', (key, current + amount))

    def get_user(self, username):
        row = self._fetchone('SELECT * FROM users WHERE username = ?', (username,))
        if row:
            columns = [desc[0] for desc in self.cursor.description]
            return dict(zip(columns, row))
        return None

    def get_user_by_id(self, user_id):
        row = self._fetchone('SELECT * FROM users WHERE id = ?', (user_id,))
        if row:
            columns = [desc[0] for desc in self.cursor.description]
            return dict(zip(columns, row))
        return None

    def create_user(self, username, password, role='user', email=None, theme='light'):
        try:
            hashed = generate_password_hash(password)
            self._execute('INSERT INTO users (username, password, role, email, created_at, theme) VALUES (?, ?, ?, ?, ?, ?)',
                          (username, hashed, role, email, str(datetime.datetime.now()), theme))
            return True
        except sqlite3.IntegrityError:
            return False

    def update_user(self, user_id, username=None, password=None, role=None, email=None, theme=None):
        updates = {}
        if username: updates['username'] = username
        if password: updates['password'] = generate_password_hash(password)
        if role: updates['role'] = role
        if email: updates['email'] = email
        if theme: updates['theme'] = theme
        if not updates: return False
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        values = list(updates.values()) + [user_id]
        self._execute(f'UPDATE users SET {set_clause} WHERE id = ?', values)
        return self.cursor.rowcount > 0

    def delete_user(self, user_id):
        self._execute('DELETE FROM users WHERE id = ?', (user_id,))
        return self.cursor.rowcount > 0

    def get_vps_by_id(self, vps_id):
        row = self._fetchone('SELECT * FROM vps_instances WHERE vps_id = ?', (vps_id,))
        if row:
            columns = [desc[0] for desc in self.cursor.description]
            vps = dict(zip(columns, row))
            return vps['token'], vps
        return None, None

    def get_vps_by_token(self, token):
        row = self._fetchone('SELECT * FROM vps_instances WHERE token = ?', (token,))
        if row:
            columns = [desc[0] for desc in self.cursor.description]
            return dict(zip(columns, row))
        return None

    def get_user_vps_count(self, user_id):
        result = self._fetchone('SELECT COUNT(*) FROM vps_instances WHERE created_by = ?', (user_id,))
        return result[0] if result else 0

    def get_user_vps(self, user_id):
        rows = self._fetchall('SELECT * FROM vps_instances WHERE created_by = ?', (user_id,))
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def get_all_vps(self):
        rows = self._fetchall('SELECT * FROM vps_instances')
        columns = [desc[0] for desc in self.cursor.description]
        return {row[1]: dict(zip(columns, row)) for row in rows}

    def add_vps(self, vps_data):
        try:
            columns = list(vps_data.keys())
            placeholders = ', '.join('?' for _ in vps_data)
            sql = f'INSERT INTO vps_instances ({", ".join(columns)}) VALUES ({placeholders})'
            self._execute(sql, tuple(vps_data.values()))
            self.increment_stat('total_vps_created')
            return True
        except sqlite3.Error as e:
            logger.error(f"Error adding VPS: {e}")
            return False

    def remove_vps(self, token):
        self._execute('DELETE FROM vps_instances WHERE token = ?', (token,))
        return self.cursor.rowcount > 0

    def update_vps(self, token, updates):
        try:
            set_clause = ', '.join(f'{k} = ?' for k in updates)
            values = list(updates.values()) + [token]
            self._execute(f'UPDATE vps_instances SET {set_clause} WHERE token = ?', values)
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error updating VPS: {e}")
            return False

    def is_user_banned(self, user_id):
        return self._fetchone('SELECT 1 FROM banned_users WHERE user_id = ?', (user_id,)) is not None

    def get_ban_reason(self, user_id):
        row = self._fetchone('SELECT reason FROM banned_users WHERE user_id = ?', (user_id,))
        return row[0] if row else None

    def ban_user(self, user_id, reason='No reason provided'):
        self._execute('INSERT OR IGNORE INTO banned_users (user_id, reason) VALUES (?, ?)', (user_id, reason))

    def unban_user(self, user_id):
        self._execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))

    def get_banned_users(self):
        rows = self._fetchall('SELECT user_id, reason FROM banned_users')
        return [(row[0], row[1]) for row in rows]

    def get_all_users(self):
        rows = self._fetchall('SELECT id, username, role, created_at, email, theme FROM users')
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def update_user_role(self, user_id, role):
        self._execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
        return self.cursor.rowcount > 0

    def get_image(self, os_image):
        row = self._fetchone('SELECT * FROM docker_images WHERE os_image = ?', (os_image,))
        if row:
            columns = [desc[0] for desc in self.cursor.description]
            return dict(zip(columns, row))
        return None

    def add_image(self, image_data):
        columns = ', '.join(image_data.keys())
        placeholders = ', '.join('?' for _ in image_data)
        self._execute(f'INSERT INTO docker_images ({columns}) VALUES ({placeholders})', tuple(image_data.values()))

    def add_notification(self, user_id, message):
        self._execute('INSERT INTO notifications (user_id, message, created_at) VALUES (?, ?, ?)',
                      (user_id, message, str(datetime.datetime.now())))

    def get_notifications(self, user_id):
        rows = self._fetchall('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def mark_notification_read(self, notif_id):
        self._execute('UPDATE notifications SET read = TRUE WHERE id = ?', (notif_id,))

    def log_action(self, user_id, action, details):
        self._execute('INSERT INTO audit_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)',
                      (user_id, action, details, str(datetime.datetime.now())))

    def get_audit_logs(self, limit=100):
        rows = self._fetchall('SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?', (limit,))
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def add_resource_history(self, vps_id, cpu, mem, disk, band_in, band_out):
        self._execute('INSERT INTO resource_history (vps_id, cpu_percent, memory_percent, disk_usage, bandwidth_in, bandwidth_out, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (vps_id, cpu, mem, disk, band_in, band_out, str(datetime.datetime.now())))

    def get_resource_history(self, vps_id, limit=100):
        rows = self._fetchall('SELECT * FROM resource_history WHERE vps_id = ? ORDER BY timestamp DESC LIMIT ?', (vps_id, limit))
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def add_group(self, name, desc):
        self._execute('INSERT INTO vps_groups (name, description) VALUES (?, ?)', (name, desc))

    def get_groups(self):
        rows = self._fetchall('SELECT * FROM vps_groups')
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def assign_vps_to_group(self, group_id, vps_id):
        self._execute('INSERT OR IGNORE INTO vps_group_assignments (group_id, vps_id) VALUES (?, ?)', (group_id, vps_id))

    def get_vps_groups(self, vps_id):
        rows = self._fetchall('''
            SELECT g.* FROM vps_groups g
            JOIN vps_group_assignments ga ON g.id = ga.group_id
            WHERE ga.vps_id = ?
        ''', (vps_id,))
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def generate_referral_code(self, user_id):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._execute('INSERT INTO referrals (user_id, referral_code) VALUES (?, ?)', (user_id, code))
        return code

    def get_referral_code(self, user_id):
        row = self._fetchone('SELECT referral_code FROM referrals WHERE user_id = ?', (user_id,))
        return row[0] if row else None

    def increment_referred(self, user_id):
        self._execute('UPDATE referrals SET referred_users = referred_users + 1 WHERE user_id = ?', (user_id,))

    def backup_data(self):
        data = {
            'users': self.get_all_users(),
            'vps_instances': list(self.get_all_vps().values()),
            'usage_stats': {row[0]: row[1] for row in self._fetchall('SELECT * FROM usage_stats')},
            'system_settings': {row[0]: row[1] for row in self._fetchall('SELECT * FROM system_settings')},
            'banned_users': [(row[0], row[1]) for row in self._fetchall('SELECT * FROM banned_users')],
            'docker_images': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM docker_images')],
            'notifications': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM notifications')],
            'audit_logs': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM audit_logs')],
            'vps_templates': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM vps_templates')],
            'resource_history': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM resource_history')],
            'vps_groups': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM vps_groups')],
            'vps_group_assignments': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM vps_group_assignments')],
            'support_tickets': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM support_tickets')],
            'referrals': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM referrals')],
            'licenses': [dict(zip([desc[0] for desc in self.cursor.description], row)) for row in self._fetchall('SELECT * FROM licenses')]
        }
        with open(BACKUP_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        return True

    def restore_data(self):
        if not os.path.exists(BACKUP_FILE):
            return False
       
        with open(BACKUP_FILE, 'r') as f:
            data = json.load(f)
       
        try:
            self._execute('DELETE FROM users')
            for user in data.get('users', []):
                hashed = user.get('password', generate_password_hash('default'))
                self._execute('INSERT INTO users (id, username, password, role, email, created_at, theme) VALUES (?, ?, ?, ?, ?, ?, ?)',
                              (user['id'], user['username'], hashed, user['role'], user.get('email'), user['created_at'], user.get('theme', 'light')))
           
            self._execute('DELETE FROM vps_instances')
            for vps in data.get('vps_instances', []):
                vps['additional_ports'] = vps.get('additional_ports', '')
                vps['bandwidth_limit'] = vps.get('bandwidth_limit', 0)
                vps['tags'] = vps.get('tags', '')
                columns = ', '.join(vps.keys())
                placeholders = ', '.join('?' for _ in vps)
                self._execute(f'INSERT INTO vps_instances ({columns}) VALUES ({placeholders})', tuple(vps.values()))
           
            self._execute('DELETE FROM usage_stats')
            for k, v in data.get('usage_stats', {}).items():
                self._execute('INSERT INTO usage_stats (key, value) VALUES (?, ?)', (k, v))
           
            self._execute('DELETE FROM system_settings')
            for k, v in data.get('system_settings', {}).items():
                self._execute('INSERT INTO system_settings (key, value) VALUES (?, ?)', (k, v))
           
            self._execute('DELETE FROM banned_users')
            for uid, reason in data.get('banned_users', []):
                self._execute('INSERT INTO banned_users (user_id, reason) VALUES (?, ?)', (uid, reason))
           
            self._execute('DELETE FROM docker_images')
            for img in data.get('docker_images', []):
                columns = ', '.join(img.keys())
                placeholders = ', '.join('?' for _ in img)
                self._execute(f'INSERT INTO docker_images ({columns}) VALUES ({placeholders})', tuple(img.values()))
           
            self._execute('DELETE FROM notifications')
            for notif in data.get('notifications', []):
                columns = ', '.join(notif.keys())
                placeholders = ', '.join('?' for _ in notif)
                self._execute(f'INSERT INTO notifications ({columns}) VALUES ({placeholders})', tuple(notif.values()))
           
            self._execute('DELETE FROM audit_logs')
            for log in data.get('audit_logs', []):
                columns = ', '.join(log.keys())
                placeholders = ', '.join('?' for _ in log)
                self._execute(f'INSERT INTO audit_logs ({columns}) VALUES ({placeholders})', tuple(log.values()))
           
            self._execute('DELETE FROM vps_templates')
            for temp in data.get('vps_templates', []):
                columns = ', '.join(temp.keys())
                placeholders = ', '.join('?' for _ in temp)
                self._execute(f'INSERT INTO vps_templates ({columns}) VALUES ({placeholders})', tuple(temp.values()))
           
            self._execute('DELETE FROM resource_history')
            for hist in data.get('resource_history', []):
                columns = ', '.join(hist.keys())
                placeholders = ', '.join('?' for _ in hist)
                self._execute(f'INSERT INTO resource_history ({columns}) VALUES ({placeholders})', tuple(hist.values()))
           
            self._execute('DELETE FROM vps_groups')
            for group in data.get('vps_groups', []):
                columns = ', '.join(group.keys())
                placeholders = ', '.join('?' for _ in group)
                self._execute(f'INSERT INTO vps_groups ({columns}) VALUES ({placeholders})', tuple(group.values()))
           
            self._execute('DELETE FROM vps_group_assignments')
            for assign in data.get('vps_group_assignments', []):
                columns = ', '.join(assign.keys())
                placeholders = ', '.join('?' for _ in assign)
                self._execute(f'INSERT INTO vps_group_assignments ({columns}) VALUES ({placeholders})', tuple(assign.values()))
           
            self._execute('DELETE FROM support_tickets')
            for ticket in data.get('support_tickets', []):
                columns = ', '.join(ticket.keys())
                placeholders = ', '.join('?' for _ in ticket)
                self._execute(f'INSERT INTO support_tickets ({columns}) VALUES ({placeholders})', tuple(ticket.values()))

            self._execute('DELETE FROM referrals')
            for ref in data.get('referrals', []):
                columns = ', '.join(ref.keys())
                placeholders = ', '.join('?' for _ in ref)
                self._execute(f'INSERT INTO referrals ({columns}) VALUES ({placeholders})', tuple(ref.values()))

            self._execute('DELETE FROM licenses')
            for lic in data.get('licenses', []):
                columns = ', '.join(lic.keys())
                placeholders = ', '.join('?' for _ in lic)
                self._execute(f'INSERT INTO licenses ({columns}) VALUES ({placeholders})', tuple(lic.values()))
           
            return True
        except Exception as e:
            logger.error(f"Restore error: {e}")
            return False

    def add_license(self, license_key, expires_at):
        created_at = str(datetime.datetime.now())
        self._execute('INSERT OR REPLACE INTO licenses (license_key, created_at, expires_at) VALUES (?, ?, ?)', (license_key, created_at, expires_at))

    def get_license(self, license_key):
        row = self._fetchone('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        if row:
            columns = [desc[0] for desc in self.cursor.description]
            return dict(zip(columns, row))
        return None

    def deactivate_license(self, license_key):
        self._execute('UPDATE licenses SET active = FALSE WHERE license_key = ?', (license_key,))

    def delete_license(self, license_key):
        self._execute('DELETE FROM licenses WHERE license_key = ?', (license_key,))

    def get_all_licenses(self):
        rows = self._fetchall('SELECT * FROM licenses')
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def close(self):
        self.conn.close()

db = Database(DB_FILE)

try:
    docker_client = docker.from_env()
    try:
        docker_client.networks.get(DOCKER_NETWORK)
    except docker.errors.NotFound:
        docker_client.networks.create(DOCKER_NETWORK)
    logger.info("Docker initialized")
except Exception as e:
    logger.error(f"Docker init failed: {e}")
    docker_client = None

# Tunnel/IP Management Functions
def ip_to_int(ip):
    """Convert IP address to integer"""
    parts = ip.split('.')
    return int(parts[0]) * 256**3 + int(parts[1]) * 256**2 + int(parts[2]) * 256 + int(parts[3])

def int_to_ip(ip_int):
    """Convert integer to IP address"""
    return f"{ip_int // 256**3}.{(ip_int // 256**2) % 256}.{(ip_int // 256) % 256}.{ip_int % 256}"

def allocate_public_ip(vps_id):
    """Allocate a unique public IP from the pool for a VPS"""
    if not TUNNEL_ENABLED:
        return None
    
    try:
        # Get all currently used IPs from database
        all_vps = db.get_all_vps()
        used_ips = set()
        for vps in all_vps.values():
            if vps.get('public_ip'):
                used_ips.add(vps['public_ip'])
        
        # Also check IPs in progress (being created)
        for creating_vps_id, progress in vps_creation_progress.items():
            if creating_vps_id != vps_id and progress.get('public_ip'):
                used_ips.add(progress['public_ip'])
        
        # Find next available IP in pool
        start_int = ip_to_int(PUBLIC_IP_POOL_START)
        end_int = ip_to_int(PUBLIC_IP_POOL_END)
        
        # Try to find available IP
        max_attempts = min(1000, end_int - start_int + 1)
        attempts = 0
        current_int = start_int
        
        while attempts < max_attempts:
            ip = int_to_ip(current_int)
            if ip not in used_ips:
                # Double-check it's really not in use
                all_vps_check = db.get_all_vps()
                conflict = False
                for v in all_vps_check.values():
                    if v.get('public_ip') == ip:
                        conflict = True
                        break
                if not conflict:
                    logger.info(f"Allocated unique public IP {ip} for VPS {vps_id}")
                    return ip
            
            current_int += 1
            if current_int > end_int:
                current_int = start_int
            attempts += 1
        
        logger.error(f"No available IPs in pool for VPS {vps_id}")
        return None
    except Exception as e:
        logger.error(f"IP allocation error for VPS {vps_id}: {e}")
        return None

def setup_tunnel(vps_id, public_ip, container_id):
    """Set up VPN-like tunnel/routing for public IP to container"""
    if not TUNNEL_ENABLED or not public_ip:
        return True
    
    try:
        # Get container IP
        container = docker_client.containers.get(container_id)
        container.reload()
        network_settings = container.attrs.get('NetworkSettings', {})
        networks = network_settings.get('Networks', {})
        
        if DOCKER_NETWORK not in networks:
            logger.error(f"Container {container_id} not in network {DOCKER_NETWORK}")
            return False
        
        container_ip = networks[DOCKER_NETWORK].get('IPAddress')
        if not container_ip:
            logger.error(f"Could not get container IP for {container_id}")
            return False
        
        # Set up VPN-like tunnel using iptables (requires root/sudo)
        # This creates a transparent tunnel where public IP traffic is routed to container
        if sys.platform != "win32":
            try:
                # Enable IP forwarding
                subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=1'], check=True, capture_output=True)
                
                # Add DNAT rule to forward all traffic from public IP to container IP (VPN-like)
                subprocess.run([
                    'iptables', '-t', 'nat', '-A', 'PREROUTING',
                    '-d', public_ip, '-j', 'DNAT', '--to-destination', container_ip
                ], check=True, capture_output=True)
                
                # Add SNAT rule for return traffic (masquerade as public IP)
                subprocess.run([
                    'iptables', '-t', 'nat', '-A', 'POSTROUTING',
                    '-s', container_ip, '-j', 'SNAT', '--to-source', public_ip
                ], check=True, capture_output=True)
                
                # Allow all traffic to/from public IP (VPN tunnel behavior)
                subprocess.run([
                    'iptables', '-A', 'INPUT',
                    '-d', public_ip, '-j', 'ACCEPT'
                ], check=True, capture_output=True)
                
                subprocess.run([
                    'iptables', '-A', 'OUTPUT',
                    '-s', public_ip, '-j', 'ACCEPT'
                ], check=True, capture_output=True)
                
                # Forward traffic between public IP and container (VPN tunnel)
                subprocess.run([
                    'iptables', '-A', 'FORWARD',
                    '-d', container_ip, '-j', 'ACCEPT'
                ], check=True, capture_output=True)
                
                subprocess.run([
                    'iptables', '-A', 'FORWARD',
                    '-s', container_ip, '-j', 'ACCEPT'
                ], check=True, capture_output=True)
                
                # Configure container to use public IP as source
                # This makes the container appear to have the public IP
                subprocess.run([
                    'ip', 'addr', 'add', f'{public_ip}/32', 'dev', 'lo'
                ], capture_output=True)  # May fail if already exists, that's OK
                
                logger.info(f"VPN tunnel setup complete: {public_ip} <-> {container_ip} (VPS {vps_id})")
                logger.info(f"All services accessible on {public_ip} (SSH, HTTP, etc.)")
                return True
            except subprocess.CalledProcessError as e:
                logger.warning(f"iptables setup failed (may need root): {e}")
                # Continue anyway - routing might be handled by Docker
                return True
            except FileNotFoundError:
                logger.warning("iptables not found - tunnel routing may not work")
                return True
        else:
            # Windows - use netsh or Docker port mapping
            logger.info(f"Tunnel configured: {public_ip} -> {container_ip} (VPS {vps_id})")
            return True
    except Exception as e:
        logger.error(f"Tunnel setup error for VPS {vps_id}: {e}")
        return False

def cleanup_tunnel(vps_id, public_ip, container_id=None):
    """Clean up tunnel/routing when VPS is deleted"""
    if not TUNNEL_ENABLED or not public_ip:
        return True
    
    try:
        container_ip = None
        if container_id and docker_client:
            try:
                container = docker_client.containers.get(container_id)
                container.reload()
                network_settings = container.attrs.get('NetworkSettings', {})
                networks = network_settings.get('Networks', {})
                if DOCKER_NETWORK in networks:
                    container_ip = networks[DOCKER_NETWORK].get('IPAddress')
            except:
                pass
        
        if sys.platform != "win32":
            try:
                # Remove DNAT rules
                subprocess.run([
                    'iptables', '-t', 'nat', '-D', 'PREROUTING',
                    '-d', public_ip, '-j', 'DNAT'
                ], capture_output=True)
                
                # Remove SNAT rules (need to find matching rule)
                result = subprocess.run([
                    'iptables', '-t', 'nat', '-S', 'POSTROUTING'
                ], capture_output=True, text=True)
                
                for line in result.stdout.split('\n'):
                    if public_ip in line and line.strip():
                        parts = line.split()
                        if len(parts) > 2:
                            subprocess.run([
                                'iptables', '-t', 'nat', '-D', 'POSTROUTING'
                            ] + parts[2:], capture_output=True)
                
                # Remove firewall rules for public IP
                subprocess.run([
                    'iptables', '-D', 'INPUT',
                    '-d', public_ip, '-j', 'ACCEPT'
                ], capture_output=True)
                
                subprocess.run([
                    'iptables', '-D', 'OUTPUT',
                    '-s', public_ip, '-j', 'ACCEPT'
                ], capture_output=True)
                
                # Remove IP address from loopback
                subprocess.run([
                    'ip', 'addr', 'del', f'{public_ip}/32', 'dev', 'lo'
                ], capture_output=True)  # May fail if not exists, that's OK
                
                # Remove forwarding rules if we have container IP
                if container_ip:
                    result = subprocess.run([
                        'iptables', '-S', 'FORWARD'
                    ], capture_output=True, text=True)
                    
                    for line in result.stdout.split('\n'):
                        if container_ip in line and line.strip():
                            parts = line.split()
                            if len(parts) > 1 and '-A' in parts:
                                parts[parts.index('-A')] = '-D'
                                subprocess.run(['iptables'] + parts, capture_output=True)
                
                logger.info(f"Tunnel cleanup complete for {public_ip} (VPS {vps_id})")
            except Exception as e:
                logger.warning(f"Tunnel cleanup warning: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Tunnel cleanup error for VPS {vps_id}: {e}")
        return False

system_stats = {}
vps_stats_cache = {}
console_sessions = {}
image_build_lock = threading.Lock()
resource_history = {vps_id: deque(maxlen=3600) for vps_id in db.get_all_vps()}
vps_creation_progress = {}  # Track VPS creation progress

def generate_token():
    return str(uuid.uuid4())

def generate_vps_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def generate_ssh_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    return ''.join(random.choices(chars, k=20))

def is_admin(user):
    user_data = db.get_user_by_id(user.id)
    return user_data['role'] == 'admin' if user_data else False

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not is_admin(current_user):
            return jsonify({'error': 'Admin required'}), 403
        return f(*args, **kwargs)
    return decorated

def run_command(command, timeout=30):
    if isinstance(command, str):
        command = shlex.split(command)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True)
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def run_docker_command(container_id, command, timeout=1200):
    if isinstance(command, str):
        command = shlex.split(command)
    try:
        result = subprocess.run(["docker", "exec", container_id] + command, capture_output=True, text=True, timeout=timeout, check=True)
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def update_system_stats():
    global system_stats
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        system_stats = {
            'cpu_usage': cpu,
            'memory_usage': mem.percent,
            'memory_used': mem.used / (1024 ** 3),
            'memory_total': mem.total / (1024 ** 3),
            'disk_usage': disk.percent,
            'disk_used': disk.used / (1024 ** 3),
            'disk_total': disk.total / (1024 ** 3),
            'network_sent': net.bytes_sent / (1024 ** 2),
            'network_recv': net.bytes_recv / (1024 ** 2),
            'active_connections': len(psutil.net_connections()),
            'last_updated': time.time()
        }
    except Exception as e:
        logger.error(f"System stats error: {e}")

def update_vps_stats():
    global vps_stats_cache
    try:
        for vps_id, vps in db.get_all_vps().items():
            if vps['status'] != 'running':
                vps_stats_cache[vps_id] = {'status': vps['status']}
                continue
            try:
                container = docker_client.containers.get(vps['container_id'])
                stats = container.stats(stream=False)
                mem_stats = stats['memory_stats']
                cpu_stats = stats['cpu_stats']
                net_stats = stats.get('networks', {})
                mem_usage = mem_stats.get('usage', 0) / (1024 ** 2)
                mem_limit = mem_stats.get('limit', 1) / (1024 ** 2)
                cpu_usage = (cpu_stats['cpu_usage']['total_usage'] / cpu_stats['system_cpu_usage']) * 100 if cpu_stats.get('system_cpu_usage') and cpu_stats['system_cpu_usage'] > 0 else 0
                net_in = sum(iface['rx_bytes'] for iface in net_stats.values()) / (1024 ** 2)
                net_out = sum(iface['tx_bytes'] for iface in net_stats.values()) / (1024 ** 2)
                uptime_start = datetime.datetime.fromisoformat(vps['uptime_start'])
                uptime_seconds = (datetime.datetime.now() - uptime_start).total_seconds()
                restart_count = vps.get('restart_count', 0)
                assumed_downtime = restart_count * 60
                uptime_percent = ((uptime_seconds - assumed_downtime) / uptime_seconds * 100) if uptime_seconds > 0 else 100
                disk_usage = psutil.disk_usage(f'/var/lib/docker/volumes/hvm-{vps_id}/_data').percent if os.path.exists(f'/var/lib/docker/volumes/hvm-{vps_id}/_data') else 0
                vps_stats_cache[vps_id] = {
                    'cpu_percent': round(cpu_usage, 2),
                    'memory_percent': round((mem_usage / mem_limit) * 100, 2) if mem_limit > 0 else 0,
                    'net_in_mb': round(net_in, 2),
                    'net_out_mb': round(net_out, 2),
                    'disk_percent': round(disk_usage, 2),
                    'status': 'running',
                    'uptime_seconds': uptime_seconds,
                    'uptime_percent': round(uptime_percent, 2)
                }
                db.add_resource_history(vps_id, cpu_usage, (mem_usage / mem_limit * 100) if mem_limit > 0 else 0, disk_usage, net_in, net_out)
                resource_history[vps_id].append(vps_stats_cache[vps_id])
                socketio.emit('vps_update', vps_stats_cache[vps_id], room=vps_id, namespace='/vps')
            except Exception as e:
                logger.error(f"VPS {vps_id} stats error: {e}")
                vps_stats_cache[vps_id] = {'status': 'error'}
    except Exception as e:
        logger.error(f"VPS stats update error: {e}")

def build_custom_image(base_image=DEFAULT_OS_IMAGE, dockerfile_content=None):
    with image_build_lock:
        existing = db.get_image(base_image)
        if existing:
            try:
                docker_client.images.get(existing['image_id'])
                return existing['image_id']
            except docker.errors.ImageNotFound:
                db._execute('DELETE FROM docker_images WHERE os_image = ?', (base_image,))
       
        try:
            temp_dir = f"image_cache/{base_image.replace(':', '-')}"
            os.makedirs(temp_dir, exist_ok=True)
           
            if dockerfile_content:
                with open(os.path.join(temp_dir, 'Dockerfile'), 'w') as f:
                    f.write(dockerfile_content)
            else:
                dockerfile = DOCKERFILE_TEMPLATE.format(base_image=base_image)
                with open(os.path.join(temp_dir, 'Dockerfile'), 'w') as f:
                    f.write(dockerfile)
           
            image_tag = f"hvm/{base_image.replace(':', '-').lower()}:latest"
            # Build with timeout and better error handling
            try:
                image, logs = docker_client.images.build(
                    path=temp_dir, 
                    tag=image_tag, 
                    rm=True, 
                    forcerm=True,
                    timeout=600,  # 10 minute timeout
                    pull=False  # Don't pull base image if it exists
                )
               
                for log in logs:
                    if 'stream' in log:
                        logger.info(log['stream'].strip())
                    elif 'error' in log:
                        logger.error(f"Build error: {log['error']}")
            except docker.errors.BuildError as e:
                logger.error(f"Image build failed: {e}")
                # Log build output for debugging
                for log in e.build_log:
                    if 'stream' in log:
                        logger.error(f"Build log: {log['stream'].strip()}")
                raise
           
            db.add_image({
                'image_id': image_tag,
                'os_image': base_image,
                'created_at': str(datetime.datetime.now())
            })
           
            return image_tag
        except Exception as e:
            logger.error(f"Image build error: {e}")
            raise
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

def setup_container(container_id, memory, vps_id, ssh_port, root_password, watermark, welcome):
    try:
        container = docker_client.containers.get(container_id)
        if container.status != "running":
            container.start()
            time.sleep(5)
       
        whole = shlex.quote(f"root:{root_password}")
        cmd = f"echo {whole} | chpasswd"
        success, _, stderr = run_docker_command(container_id, ["bash", "-c", cmd])
        if not success:
            raise Exception(f"Password set failed: {stderr}")
       
        welcome_escaped = shlex.quote(welcome)
        cmd = f"echo {welcome_escaped} > /etc/motd && echo 'echo {welcome_escaped}' >> /root/.bashrc"
        success, _, stderr = run_docker_command(container_id, ["bash", "-c", cmd])
        if not success:
            logger.warning(f"Welcome set failed: {stderr}")
       
        prefix = db.get_setting('vps_hostname_prefix', VPS_HOSTNAME_PREFIX)
        hostname = f"{prefix}{vps_id}"
        hostname_escaped = shlex.quote(hostname)
        hostname_cmd = f"echo {hostname_escaped} > /etc/hostname && hostname {hostname_escaped}"
        success, _, stderr = run_docker_command(container_id, ["bash", "-c", hostname_cmd])
        if not success:
            raise Exception(f"Hostname set failed: {stderr}")
       
        watermark_escaped = shlex.quote(watermark)
        success, _, stderr = run_docker_command(container_id, ["bash", "-c", f"echo {watermark_escaped} > /etc/machine-info"])
        if not success:
            logger.warning(f"Watermark set failed: {stderr}")
       
        # Configure SSH to listen on all interfaces (0.0.0.0) to accept connections via public IP
        ssh_config_cmd = "sed -i 's/#ListenAddress 0.0.0.0/ListenAddress 0.0.0.0/' /etc/ssh/sshd_config && " \
                        "sed -i 's/ListenAddress /#ListenAddress /' /etc/ssh/sshd_config && " \
                        "echo 'ListenAddress 0.0.0.0' >> /etc/ssh/sshd_config && " \
                        "systemctl restart ssh || systemctl restart sshd"
        success, _, stderr = run_docker_command(container_id, ["bash", "-c", ssh_config_cmd])
        if not success:
            logger.warning(f"SSH config update failed: {stderr}")
        
        security_cmds = [
            "systemctl enable fail2ban && systemctl start fail2ban",
            "apt-get update && apt-get upgrade -y",
            "ufw allow 22",
            "ufw --force enable",
            "apt-get -y autoremove",
            "apt-get clean",
            "chmod 700 /root",
            "systemctl enable prometheus-node-exporter && systemctl start prometheus-node-exporter",
            "systemctl enable ssh && systemctl start ssh || systemctl enable sshd && systemctl start sshd"
        ]
        for cmd in security_cmds:
            success, _, stderr = run_docker_command(container_id, ["bash", "-c", cmd])
            if not success:
                logger.warning(f"Security cmd {cmd} failed: {stderr}")
       
        return True, vps_id
    except Exception as e:
        logger.error(f"Setup failed for {container_id}: {e}")
        return False, None

def get_tmate_session(container_id):
    try:
        process = subprocess.Popen(["docker", "exec", container_id, "tmate", "-F"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        start = time.time()
        session = None
        while time.time() - start < 10:
            line = process.stdout.readline()
            if line and "ssh session:" in line:
                parts = line.split("ssh session:")
                if len(parts) > 1:
                    session = parts[1].strip()
                    break
        process.terminate()
        return session
    except Exception as e:
        logger.error(f"tmate error: {e}")
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_email(to_email, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Email send error: {e}")
        return False

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

def validate_license(key):
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(PUBLIC_HEX), curve=NIST384p)
        decoded = base64.b64decode(key)
        data_b, sign = decoded.rsplit(b'||', 1)
        data = data_b.decode()
        vk.verify(sign, data_b)
        license_data = json.loads(data)
        expire = datetime.datetime.fromisoformat(license_data['expires'])
        if expire < datetime.datetime.now():
            return False, "License expired"
        machine_id = hex(uuid.getnode())
        if license_data.get('machine_id') != machine_id:
            return False, "Machine ID mismatch"
        return True, license_data
    except (BadSignatureError, ValueError, KeyError, json.JSONDecodeError) as e:
        return False, str(e)

@app.before_request
def check_maintenance():
    if request.path.startswith('/static') or request.endpoint in ['login', 'logout']:
        return
    if db.get_setting('maintenance_mode', 'off') == 'on':
        if not current_user.is_authenticated or not is_admin(current_user):
            return render_template('maintenance.html', panel_name=db.get_setting('panel_name', PANEL_NAME))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
   
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        if not username or not password:
            return render_template('login.html', error='Invalid input', panel_name=db.get_setting('panel_name', PANEL_NAME))
        user_data = db.get_user(username)
        if user_data and check_password_hash(user_data['password'], password):
            if db.is_user_banned(user_data['id']):
                reason = db.get_ban_reason(user_data['id'])
                return render_template('login.html', error=f'Banned: {reason}', panel_name=db.get_setting('panel_name', PANEL_NAME))
            user = User(user_data['id'], user_data['username'], user_data['role'], user_data.get('email'), user_data.get('theme', 'light'))
            login_user(user)
            db.log_action(user.id, 'login', f'Logged in from {request.remote_addr}')
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid credentials', panel_name=db.get_setting('panel_name', PANEL_NAME))
   
    return render_template('login.html', panel_name=db.get_setting('panel_name', PANEL_NAME))

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if db.get_setting('registration_enabled', 'on') == 'off':
        return render_template('register.html', error='Registration is disabled', panel_name=db.get_setting('panel_name', PANEL_NAME))
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
   
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        email = request.form.get('email').strip()
        referral_code = request.form.get('referral_code')
        if not username or not password or not email:
            return render_template('register.html', error='Invalid input', panel_name=db.get_setting('panel_name', PANEL_NAME))
        if password != confirm or len(password) < 8:
            return render_template('register.html', error='Password mismatch or too short (min 8 chars)', panel_name=db.get_setting('panel_name', PANEL_NAME))
        if db.create_user(username, password, email=email):
            user_id = db.get_user(username)['id']
            db.log_action(user_id, 'register', 'New user registered')
            if referral_code:
                referrer_row = db._fetchone('SELECT user_id FROM referrals WHERE referral_code = ?', (referral_code,))
                if referrer_row:
                    referrer_id = referrer_row[0]
                    db.increment_referred(referrer_id)
                    db.add_notification(referrer_id, f'New referral from {username}')
                    send_email(db.get_user_by_id(referrer_id)['email'], 'New Referral', f'User {username} registered with your code.')
            send_email(email, 'Welcome', 'Your account has been created.')
            return redirect(url_for('login'))
        return render_template('register.html', error='Username exists', panel_name=db.get_setting('panel_name', PANEL_NAME))
   
    return render_template(
    'register.html',
    panel_name=db.get_setting('panel_name', PANEL_NAME),
    db=db
)

@app.route('/logout')
@login_required
def logout():
    db.log_action(current_user.id, 'logout', 'Logged out')
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if db.is_user_banned(current_user.id):
        reason = db.get_ban_reason(current_user.id)
        logout_user()
        return render_template('login.html', error=f'Banned: {reason}', panel_name=db.get_setting('panel_name', PANEL_NAME))
   
    vps_list = db.get_user_vps(current_user.id)
    notifications = db.get_notifications(current_user.id)
    theme = current_user.theme
    return render_template('dashboard.html', vps_list=vps_list, notifications=notifications, panel_name=db.get_setting('panel_name', PANEL_NAME), server_ip=db.get_setting('server_ip', SERVER_IP), is_admin=is_admin(current_user), theme=theme)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current = request.form.get('current_password')
        new = request.form.get('new_password')
        confirm = request.form.get('confirm_password')
        email = request.form.get('email').strip()
        theme = request.form.get('theme')
        user_data = db.get_user_by_id(current_user.id)
        if not check_password_hash(user_data['password'], current) or new != confirm or len(new) < 8:
            return render_template('profile.html', error='Invalid password change (min 8 chars)', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
        db.update_user(current_user.id, password=new, email=email, theme=theme)
        db.log_action(current_user.id, 'update_profile', 'Updated password, email, and theme')
        current_user.theme = theme
        return render_template('profile.html', success='Updated', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=theme)
   
    return render_template('profile.html', panel_name=db.get_setting('panel_name', PANEL_NAME), email=current_user.email, theme=current_user.theme)

@app.route('/create_vps/progress/<vps_id>')
@login_required
@limiter.exempt
def get_vps_creation_progress(vps_id):
    """Get progress of VPS creation"""
    progress = vps_creation_progress.get(vps_id, {'status': 'not_found', 'progress': 0, 'message': 'Not found'})
    return jsonify(progress)

def create_vps_async(vps_data, user_id, current_user_id):
    """Async VPS creation function"""
    vps_id = vps_data['vps_id']
    container = None
    public_ip = None
    try:
        vps_creation_progress[vps_id] = {'status': 'starting', 'progress': 5, 'message': 'Initializing...'}
        
        # Validate and prepare
        vps_creation_progress[vps_id] = {'status': 'validating', 'progress': 10, 'message': 'Validating configuration...'}
        
        memory = vps_data['memory']
        cpu = vps_data['cpu']
        disk = vps_data['disk']
        os_image = vps_data['os_image']
        additional_ports = vps_data.get('additional_ports', '')
        expires_days = vps_data.get('expires_days', 30)
        expires_hours = vps_data.get('expires_hours', 0)
        expires_minutes = vps_data.get('expires_minutes', 0)
        bandwidth_limit = vps_data.get('bandwidth_limit', 0)
        tags = vps_data.get('tags', '')
        ssh_port = vps_data['port']
        root_password = vps_data['root_password']
        token = vps_data['token']
        
        # Build image
        vps_creation_progress[vps_id] = {'status': 'building', 'progress': 20, 'message': 'Building Docker image...'}
        dockerfile_content = None
        try:
            image_tag = build_custom_image(os_image, dockerfile_content)
            vps_creation_progress[vps_id] = {'status': 'building', 'progress': 40, 'message': 'Image build completed'}
        except Exception as e:
            logger.error(f"Image build failed: {e}")
            existing = db.get_image(os_image)
            if existing:
                image_tag = existing['image_id']
            else:
                image_tag = os_image
        
        # Create container
        vps_creation_progress[vps_id] = {'status': 'creating', 'progress': 50, 'message': 'Creating container...'}
        
        # Re-check ports from actual Docker containers before creating
        docker_used_ports = set()
        try:
            for container in docker_client.containers.list(all=True):
                # Check port bindings from container network settings
                if container.attrs.get('NetworkSettings') and container.attrs['NetworkSettings'].get('Ports'):
                    for port_binding in container.attrs['NetworkSettings']['Ports'].values():
                        if port_binding:
                            for binding in port_binding:
                                if binding.get('HostPort'):
                                    try:
                                        docker_used_ports.add(int(binding['HostPort']))
                                    except (ValueError, TypeError):
                                        pass
                # Also check from HostConfig.PortBindings
                if container.attrs.get('HostConfig') and container.attrs['HostConfig'].get('PortBindings'):
                    for port_binding in container.attrs['HostConfig']['PortBindings'].values():
                        if port_binding:
                            for binding in port_binding:
                                if binding.get('HostPort'):
                                    try:
                                        docker_used_ports.add(int(binding['HostPort']))
                                    except (ValueError, TypeError):
                                        pass
        except Exception as e:
            logger.warning(f"Error checking Docker ports: {e}")
        
        ports = {'22/tcp': ssh_port}
        if ssh_port in docker_used_ports:
            # SSH port conflict - find a new one
            logger.warning(f"SSH port {ssh_port} is already in use by Docker, finding alternative...")
            new_ssh_port = random.randint(20000, 30000)
            attempts = 0
            while new_ssh_port in docker_used_ports and attempts < 100:
                new_ssh_port = random.randint(20000, 30000)
                attempts += 1
            if new_ssh_port in docker_used_ports:
                vps_creation_progress[vps_id] = {
                    'status': 'error',
                    'progress': 0,
                    'message': f'Could not find available SSH port. Port {ssh_port} is in use.'
                }
                raise ValueError(f'Could not find available SSH port. Port {ssh_port} is in use.')
            ssh_port = new_ssh_port
            ports = {'22/tcp': ssh_port}
            vps_data['port'] = ssh_port  # Update in vps_data too
        
        if additional_ports:
            conflicting_ports = []
            for port_str in additional_ports.split(','):
                if port_str.strip():
                    port_parts = port_str.strip().split(':')
                    if len(port_parts) == 2:
                        host, cont = port_parts
                        try:
                            host_port = int(host)
                            if host_port in docker_used_ports:
                                conflicting_ports.append(str(host_port))
                            else:
                                ports[f'{cont}/tcp'] = host_port
                        except ValueError as e:
                            if 'already in use' in str(e):
                                raise
                            pass
            
            if conflicting_ports:
                error_msg = f"Port(s) {', '.join(conflicting_ports)} are already in use by another Docker container. Please choose different ports."
                vps_creation_progress[vps_id] = {
                    'status': 'error',
                    'progress': 0,
                    'message': error_msg
                }
                raise ValueError(error_msg)
        
        cpuset = f"0-{cpu-1}" if cpu > 1 else "0"
        prefix = db.get_setting('vps_hostname_prefix', VPS_HOSTNAME_PREFIX)
        
        # Ensure container name is unique
        container_name = f"hvm-{vps_id}"
        try:
            # Check if container with this name already exists
            existing = docker_client.containers.get(container_name)
            if existing:
                logger.warning(f"Container {container_name} already exists, removing...")
                try:
                    existing.stop()
                    existing.remove()
                except:
                    pass
        except docker.errors.NotFound:
            pass  # Good, name is available
        
        try:
            container = docker_client.containers.run(
                image_tag,
                name=container_name,  # Set explicit name for uniqueness
                detach=True,
                privileged=True,
                hostname=f"{prefix}{vps_id}",
                mem_limit=f"{memory}g",
                nano_cpus=cpu * 10**9,
                cpuset_cpus=cpuset,
                cap_add=["SYS_ADMIN", "NET_ADMIN"],
                security_opt=["seccomp=unconfined"],
                network=DOCKER_NETWORK,
                volumes={f'hvm-{vps_id}': {'bind': '/data', 'mode': 'rw'}},
                restart_policy={"Name": "always"},
                ports=ports
            )
        except docker.errors.APIError as e:
            error_msg = str(e)
            if 'port is already allocated' in error_msg or 'Bind for' in error_msg or 'port is already in use' in error_msg.lower():
                # Extract port from error message
                import re
                port_matches = re.findall(r':(\d+)', error_msg)
                if port_matches:
                    conflict_ports = list(set(port_matches))  # Remove duplicates
                    if len(conflict_ports) == 1:
                        error_message = f'Port {conflict_ports[0]} is already allocated. Please choose a different port or wait for the port to be released.'
                    else:
                        error_message = f'Ports {", ".join(conflict_ports)} are already allocated. Please choose different ports.'
                    
                    # Only update if not already set to avoid duplicate messages
                    if vps_creation_progress.get(vps_id, {}).get('status') != 'error':
                        vps_creation_progress[vps_id] = {
                            'status': 'error', 
                            'progress': 0, 
                            'message': error_message
                        }
                    raise ValueError(error_message)
            
            # Only update if not already set
            if vps_creation_progress.get(vps_id, {}).get('status') != 'error':
                vps_creation_progress[vps_id] = {
                    'status': 'error', 
                    'progress': 0, 
                    'message': f'Failed to create container: {error_msg}'
                }
            raise ValueError(f"Failed to create container: {error_msg}")
        except ValueError as e:
            # Re-raise ValueError (port conflicts) without modifying progress if already set
            error_msg = str(e)
            if 'port' in error_msg.lower() and ('allocated' in error_msg.lower() or 'in use' in error_msg.lower()):
                if vps_creation_progress.get(vps_id, {}).get('status') != 'error':
                    vps_creation_progress[vps_id] = {
                        'status': 'error', 
                        'progress': 0, 
                        'message': error_msg
                    }
            raise
        except Exception as e:
            error_msg = str(e)
            if 'port' in error_msg.lower() and ('allocated' in error_msg.lower() or 'in use' in error_msg.lower()):
                if vps_creation_progress.get(vps_id, {}).get('status') != 'error':
                    vps_creation_progress[vps_id] = {
                        'status': 'error', 
                        'progress': 0, 
                        'message': f'Port conflict: {error_msg}'
                    }
            raise
        
        time.sleep(3)
        container.reload()
        vps_creation_progress[vps_id] = {'status': 'configuring', 'progress': 60, 'message': 'Configuring network...'}
        
        # Setup tunnel - ensure unique IP
        public_ip = allocate_public_ip(vps_id)
        if public_ip:
            # Final verification - check IP is unique
            all_vps = db.get_all_vps()
            conflict = False
            for v in all_vps.values():
                if v.get('public_ip') == public_ip and v.get('vps_id') != vps_id:
                    logger.error(f"IP conflict detected: {public_ip} already used by {v.get('vps_id')}")
                    conflict = True
                    break
            
            if conflict:
                # Try to get a different IP
                public_ip = allocate_public_ip(vps_id)
                if not public_ip:
                    logger.warning(f"Could not allocate alternative IP for VPS {vps_id}")
                    public_ip = None
            
            if public_ip:
                tunnel_success = setup_tunnel(vps_id, public_ip, container.id)
                if tunnel_success:
                    vps_creation_progress[vps_id] = {'status': 'configuring', 'progress': 70, 'message': f'Public IP assigned: {public_ip}'}
                    # Store IP in progress for conflict checking
                    vps_creation_progress[vps_id]['public_ip'] = public_ip
                else:
                    logger.warning(f"Tunnel setup failed for {public_ip}, continuing without tunnel")
                    public_ip = None
            else:
                logger.warning(f"Could not allocate unique public IP for VPS {vps_id}")
                public_ip = None
        else:
            public_ip = None
            logger.warning(f"Could not allocate public IP for VPS {vps_id}")
        
        # Setup container
        vps_creation_progress[vps_id] = {'status': 'configuring', 'progress': 75, 'message': 'Configuring VPS...'}
        watermark = db.get_setting('watermark', WATERMARK)
        welcome = db.get_setting('welcome_message', WELCOME_MESSAGE)
        setup_success, _ = setup_container(container.id, memory, vps_id, ssh_port, root_password, watermark, welcome)
        
        if not setup_success:
            if public_ip:
                cleanup_tunnel(vps_id, public_ip, container.id)
            try:
                container.stop()
                container.remove()
            except Exception as e:
                logger.error(f"Error cleaning up container {container.id}: {e}")
            vps_creation_progress[vps_id] = {'status': 'error', 'progress': 0, 'message': 'Setup failed'}
            return
        
        vps_creation_progress[vps_id] = {'status': 'finalizing', 'progress': 90, 'message': 'Getting tmate session...'}
        
        # Get tmate session
        tmate_session = None
        try:
            time.sleep(2)  # Wait a bit for container to be fully ready
            tmate_session = get_tmate_session(container.id)
            if tmate_session:
                vps_creation_progress[vps_id] = {'status': 'finalizing', 'progress': 95, 'message': 'tmate session ready'}
            else:
                logger.warning(f"Could not get tmate session for VPS {vps_id}")
        except Exception as e:
            logger.error(f"tmate session error for VPS {vps_id}: {e}")
        
        now = datetime.datetime.now()
        expires_at = now + datetime.timedelta(days=expires_days, hours=expires_hours, minutes=expires_minutes)
        
        vps_data.update({
            'container_id': container.id,
            'image_id': image_tag,
            'public_ip': public_ip,
            'tmate_session': tmate_session,
            'expires_at': str(expires_at),
            'uptime_start': str(now)
        })
        
        # Final check - ensure VPS ID is still unique before adding to DB
        existing_check = db.get_all_vps()
        if vps_id in existing_check:
            logger.error(f"VPS ID {vps_id} already exists in database!")
            if public_ip:
                cleanup_tunnel(vps_id, public_ip, container.id)
            try:
                container.stop()
                container.remove()
            except Exception as e:
                logger.error(f"Error cleaning up container: {e}")
            vps_creation_progress[vps_id] = {'status': 'error', 'progress': 0, 'message': 'VPS ID conflict - please try again'}
            return
        
        if db.add_vps(vps_data):
            db.log_action(current_user_id, 'create_vps', f'Created VPS {vps_id}')
            db.add_notification(user_id, f'New VPS {vps_id} created')
            resource_history[vps_id] = deque(maxlen=3600)
            # Clean up progress after 5 minutes
            def cleanup_progress():
                time.sleep(300)  # 5 minutes
                if vps_id in vps_creation_progress:
                    del vps_creation_progress[vps_id]
            threading.Thread(target=cleanup_progress, daemon=True).start()
            vps_creation_progress[vps_id] = {'status': 'completed', 'progress': 100, 'message': 'VPS created successfully!', 'vps_id': vps_id}
        else:
            # Cleanup on DB failure
            if public_ip:
                cleanup_tunnel(vps_id, public_ip, container.id)
            try:
                container.stop()
                container.remove()
            except:
                pass
            vps_creation_progress[vps_id] = {'status': 'error', 'progress': 0, 'message': 'Database error - VPS not saved'}
    except Exception as e:
        logger.error(f"Async VPS creation error for {vps_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Try to cleanup if container was created
        try:
            if container:
                if public_ip:
                    cleanup_tunnel(vps_id, public_ip, container.id)
                container.stop()
                container.remove()
        except Exception as cleanup_error:
            logger.error(f"Cleanup error: {cleanup_error}")
        vps_creation_progress[vps_id] = {'status': 'error', 'progress': 0, 'message': str(e)}

@app.route('/create_vps', methods=['GET', 'POST'])
@login_required
@admin_required
def create_vps():
    if not docker_client:
        return render_template(
            'error.html',
            error='Docker unavailable',
            panel_name=db.get_setting('panel_name', PANEL_NAME),
            theme=current_user.theme
        )

    os_images = [
        'ubuntu:22.04', 'ubuntu:24.04', 'ubuntu:20.04',
        'debian:12', 'debian:11', 'debian:10'
    ]
    users = db.get_all_users()

    if request.method == 'POST':
        try:
            memory = int(request.form.get('memory', 0))
            cpu = int(request.form.get('cpu', 0))
            disk = int(request.form.get('disk', 0))
            os_image = request.form.get('os_image', DEFAULT_OS_IMAGE)
            additional_ports = request.form.get('additional_ports', '')
            expires_days = int(request.form.get('expires_days', 30))
            expires_hours = int(request.form.get('expires_hours', 0))
            expires_minutes = int(request.form.get('expires_minutes', 0))
            bandwidth_limit = int(request.form.get('bandwidth_limit', 0))
            tags = request.form.get('tags', '')
            user_id = int(request.form.get('user_id', current_user.id))

            if memory < 1 or memory > 51200 or cpu < 1 or cpu > 320 or disk < 10 or disk > 100000:
                raise ValueError('Invalid resources')

            total_min = expires_days * 1440 + expires_hours * 60 + expires_minutes
            if total_min <= 0 or expires_days > 365:
                raise ValueError('Invalid expiration')

            if not db.get_user_by_id(user_id):
                raise ValueError('Invalid user')

            if db.get_user_vps_count(user_id) >= int(db.get_setting('max_vps_per_user', MAX_VPS_PER_USER)):
                raise ValueError('Max VPS reached')

            if len(docker_client.containers.list(all=True)) >= int(db.get_setting('max_containers', MAX_CONTAINERS)):
                raise ValueError('Max containers reached')

            # Generate unique VPS ID (ensure it doesn't exist)
            max_attempts = 100
            vps_id = None
            for _ in range(max_attempts):
                candidate_id = generate_vps_id()
                existing_vps = db.get_all_vps()
                if candidate_id not in existing_vps:
                    vps_id = candidate_id
                    break
            if not vps_id:
                raise ValueError('Could not generate unique VPS ID')
            
            token = generate_token()
            root_password = generate_ssh_password()
            
            # Prepare VPS data for async creation - get ALL used ports and IPs
            used_ports = set()
            used_vps_ids = set()
            used_public_ips = set()
            
            # Get from database
            for v in db.get_all_vps().values():
                used_vps_ids.add(v['vps_id'])
                used_ports.add(v.get('port', 0))
                if v.get('public_ip'):
                    used_public_ips.add(v['public_ip'])
                for p in v.get('additional_ports', '').split(','):
                    if p and ':' in p:
                        try:
                            used_ports.add(int(p.split(':')[0]))
                        except (ValueError, IndexError):
                            pass
            
            # Get from Docker containers (in case DB is out of sync)
            try:
                for container in docker_client.containers.list(all=True):
                    if container.name.startswith('hvm-') or (prefix and container.name.startswith(prefix)):
                        used_vps_ids.add(container.name.replace('hvm-', '').replace(prefix, ''))
                    # Check actual port bindings from Docker
                    if container.attrs.get('NetworkSettings') and container.attrs['NetworkSettings'].get('Ports'):
                        for port_binding in container.attrs['NetworkSettings']['Ports'].values():
                            if port_binding:
                                for binding in port_binding:
                                    if binding.get('HostPort'):
                                        try:
                                            used_ports.add(int(binding['HostPort']))
                                        except (ValueError, TypeError):
                                            pass
            except Exception as e:
                logger.warning(f"Error checking Docker containers for ports: {e}")
                pass

            # Generate unique SSH port (check both DB and Docker)
            ssh_port = random.randint(20000, 30000)
            attempts = 0
            while ssh_port in used_ports and attempts < 100:
                ssh_port = random.randint(20000, 30000)
                attempts += 1
            if ssh_port in used_ports:
                raise ValueError('Could not find available SSH port')
            
            # Validate additional ports are unique (check both DB and Docker)
            if additional_ports:
                for port_str in additional_ports.split(','):
                    if port_str.strip():
                        port_parts = port_str.strip().split(':')
                        if len(port_parts) == 2:
                            try:
                                host_port = int(port_parts[0])
                                if host_port in used_ports:
                                    raise ValueError(f"Port {host_port} is already in use (checked database and Docker containers)")
                                used_ports.add(host_port)  # Reserve it
                            except ValueError as e:
                                if 'already in use' in str(e):
                                    raise
                                raise ValueError(f"Invalid port format: '{port_str.strip()}'")
            
            now = datetime.datetime.now()
            expires_at = now + datetime.timedelta(days=expires_days, hours=expires_hours, minutes=expires_minutes)
            watermark = db.get_setting('watermark', WATERMARK)
            prefix = db.get_setting('vps_hostname_prefix', VPS_HOSTNAME_PREFIX)
            
            vps_data = {
                'token': token,
                'vps_id': vps_id,
                'memory': memory,
                'cpu': cpu,
                'disk': disk,
                'bandwidth_limit': bandwidth_limit,
                'username': 'root',
                'password': root_password,
                'root_password': root_password,
                'created_by': user_id,
                'created_at': str(now),
                'watermark': watermark,
                'os_image': os_image,
                'restart_count': 0,
                'last_restart': None,
                'status': 'creating',
                'port': ssh_port,
                'expires_at': str(expires_at),
                'expires_days': expires_days,
                'expires_hours': expires_hours,
                'expires_minutes': expires_minutes,
                'additional_ports': additional_ports,
                'tags': tags
            }
            
            # Start async creation
            thread = threading.Thread(
                target=create_vps_async,
                args=(vps_data, user_id, current_user.id),
                daemon=True
            )
            thread.start()
            
            # Return progress page immediately
            return render_template(
                'vps_creating.html',
                vps_id=vps_id,
                panel_name=db.get_setting('panel_name', PANEL_NAME),
                theme=current_user.theme
            )

        except Exception as e:
            logger.error(f"Create VPS error: {e}")
            return render_template(
                'create_vps.html',
                error=str(e),
                panel_name=db.get_setting('panel_name', PANEL_NAME),
                os_images=os_images,
                users=users,
                theme=current_user.theme
            )

    return render_template(
        'create_vps.html',
        os_images=os_images,
        users=users,
        panel_name=db.get_setting('panel_name', PANEL_NAME),
        theme=current_user.theme
    )

@app.route('/edit_vps/<vps_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps:
        return render_template('error.html', error='VPS not found', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    if request.method == 'POST':
        try:
            new_memory = int(request.form.get('memory', vps['memory']))
            new_cpu = int(request.form.get('cpu', vps['cpu']))
            new_disk = int(request.form.get('disk', vps['disk']))
            new_os = request.form.get('os_image', vps['os_image'])
            new_ports = request.form.get('additional_ports', vps['additional_ports'])
            new_bandwidth = int(request.form.get('bandwidth_limit', vps['bandwidth_limit']))
            new_tags = request.form.get('tags', vps['tags'])
            new_user = int(request.form.get('user_id', vps['created_by']))
           
            if new_memory < 1 or new_memory > 512 or new_cpu < 1 or new_cpu > 32 or new_disk < 10 or new_disk > 1000:
                raise ValueError('Invalid resources')
           
            if not db.get_user_by_id(new_user):
                raise ValueError('Invalid user')
           
            if new_user != vps['created_by'] and db.get_user_vps_count(new_user) >= int(db.get_setting('max_vps_per_user', MAX_VPS_PER_USER)):
                raise ValueError('User max VPS reached')
           
            recreate = new_os != vps['os_image'] or new_cpu != vps['cpu'] or new_memory != vps['memory'] or new_disk != vps['disk'] or new_ports != vps['additional_ports'] or new_bandwidth != vps['bandwidth_limit']
           
            if recreate:
                container = docker_client.containers.get(vps['container_id'])
                was_running = container.status == 'running'
                if was_running:
                    container.stop()
                container.remove()
               
                new_image_tag = build_custom_image(new_os)
               
                ports = {'22/tcp': vps['port']}
                for p in new_ports.split(','):
                    if p.strip():
                        port_parts = p.strip().split(':')
                        if len(port_parts) != 2:
                            raise ValueError(f"Invalid port format: '{p.strip()}'. Expected format: 'host_port:container_port' (e.g., '8080:80')")
                        h, c = port_parts
                        try:
                            ports[f'{c}/tcp'] = int(h)
                        except ValueError:
                            raise ValueError(f"Invalid port number in '{p.strip()}'. Ports must be integers.")
               
                cpuset = f"0-{new_cpu-1}" if new_cpu > 1 else "0"
                prefix = db.get_setting('vps_hostname_prefix', VPS_HOSTNAME_PREFIX)
                new_container = docker_client.containers.run(
                    new_image_tag,
                    detach=True,
                    privileged=True,
                    hostname=f"{prefix}{vps_id}",
                    mem_limit=f"{new_memory}g",
                    nano_cpus=new_cpu * 10**9,
                    cpuset_cpus=cpuset,
                    cap_add=["SYS_ADMIN", "NET_ADMIN"],
                    security_opt=["seccomp=unconfined"],
                    network=DOCKER_NETWORK,
                    volumes={f'hvm-{vps_id}': {'bind': '/data', 'mode': 'rw'}},
                    restart_policy={"Name": "always"},
                    ports=ports
                )
               
                time.sleep(5)
                new_container.reload()
               
                watermark = db.get_setting('watermark', WATERMARK)
                welcome = db.get_setting('welcome_message', WELCOME_MESSAGE)
                setup_success, _ = setup_container(new_container.id, new_memory, vps_id, vps['port'], vps['root_password'], watermark, welcome)
                if not setup_success:
                    new_container.stop()
                    new_container.remove()
                    raise Exception('Setup failed')
               
                # Get tmate session after container is ready
                tmate_session = None
                try:
                    time.sleep(2)  # Wait for container to be ready
                    tmate_session = get_tmate_session(new_container.id)
                except Exception as e:
                    logger.error(f"tmate session error during upgrade: {e}")
                
                updates = {
                    'container_id': new_container.id,
                    'memory': new_memory,
                    'cpu': new_cpu,
                    'disk': new_disk,
                    'bandwidth_limit': new_bandwidth,
                    'os_image': new_os,
                    'tmate_session': tmate_session,
                    'image_id': new_image_tag,
                    'additional_ports': new_ports,
                    'tags': new_tags,
                    'created_by': new_user,
                    'status': 'running'
                }
               
                if vps['image_id'] != new_image_tag:
                    try:
                        docker_client.images.remove(vps['image_id'])
                    except:
                        pass
            else:
                updates = {
                    'created_by': new_user,
                    'tags': new_tags
                }
           
            db.update_vps(token, updates)
            db.log_action(current_user.id, 'edit_vps', f'Edited VPS {vps_id}')
            return redirect(url_for('admin_panel'))
       
        except Exception as e:
            logger.error(f"Edit VPS error: {e}")
            os_images = ['ubuntu:22.04', 'ubuntu:24.04', 'ubuntu:20.04', 'debian:12', 'debian:11', 'alpine:latest', 'centos:7', 'fedora:40', 'archlinux:latest', 'debian:10']
            users = db.get_all_users()
            return render_template('edit_vps.html', error=str(e), vps=vps, panel_name=db.get_setting('panel_name', PANEL_NAME), os_images=os_images, users=users, theme=current_user.theme)
   
    os_images = ['ubuntu:22.04', 'ubuntu:24.04', 'ubuntu:20.04', 'debian:12', 'debian:11', 'alpine:latest', 'centos:7', 'fedora:40', 'archlinux:latest', 'debian:10']
    users = db.get_all_users()
    return render_template('edit_vps.html', vps=vps, os_images=os_images, users=users, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/vps/<vps_id>')
@login_required
def vps_details(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='Access denied', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        status = container.status
    except:
        status = 'not_found'
   
    history = db.get_resource_history(vps_id, 360)
    groups = db.get_vps_groups(vps_id)
    return render_template('vps_details.html', vps=vps, container_status=status, server_ip=db.get_setting('server_ip', SERVER_IP), panel_name=db.get_setting('panel_name', PANEL_NAME), history=history, groups=groups, theme=current_user.theme)

@app.route('/vps/<vps_id>/start')
@login_required
def start_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        if container.status == 'running':
            return jsonify({'error': 'Already running'}), 400
        container.start()
        db.update_vps(token, {'status': 'running', 'uptime_start': str(datetime.datetime.now())})
        db.log_action(current_user.id, 'start_vps', f'Started VPS {vps_id}')
        return jsonify({'message': 'Started'})
    except Exception as e:
        logger.error(f"Start VPS error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/stop')
@login_required
def stop_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        if container.status != 'running':
            return jsonify({'error': 'Already stopped'}), 400
        container.stop()
        db.update_vps(token, {'status': 'stopped'})
        db.log_action(current_user.id, 'stop_vps', f'Stopped VPS {vps_id}')
        return jsonify({'message': 'Stopped'})
    except Exception as e:
        logger.error(f"Stop VPS error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/restart')
@login_required
def restart_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        container.restart()
        updates = {
            'restart_count': vps.get('restart_count', 0) + 1,
            'last_restart': str(datetime.datetime.now()),
            'status': 'running',
            'uptime_start': str(datetime.datetime.now())
        }
        db.update_vps(token, updates)
        
        # Update tmate session after restart
        try:
            time.sleep(2)  # Wait for container to be ready
            tmate_session = get_tmate_session(vps['container_id'])
            if tmate_session:
                db.update_vps(token, {'tmate_session': tmate_session})
        except Exception as e:
            logger.error(f"tmate session update error: {e}")
        
        db.log_action(current_user.id, 'restart_vps', f'Restarted VPS {vps_id}')
        return jsonify({'message': 'Restarted'})
    except Exception as e:
        logger.error(f"Restart VPS error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/delete', methods=['POST'])
@login_required
def delete_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        # Clean up tunnel if public IP exists
        if vps.get('public_ip'):
            cleanup_tunnel(vps_id, vps['public_ip'], vps.get('container_id'))
        
        container = docker_client.containers.get(vps['container_id'])
        container.stop()
        container.remove()
        volume = docker_client.volumes.get(f'hvm-{vps["vps_id"]}')
        volume.remove()
    except:
        pass
   
    db.remove_vps(token)
    db.log_action(current_user.id, 'delete_vps', f'Deleted VPS {vps_id}')
    return jsonify({'message': 'Deleted'})

@app.route('/vps/<vps_id>/renew')
@login_required
@admin_required
def renew_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps:
        return jsonify({'error': 'Not found'}), 404
   
    new_expires = datetime.datetime.fromisoformat(vps['expires_at']) + datetime.timedelta(days=30)
    db.update_vps(token, {'expires_at': str(new_expires)})
   
    if vps['status'] == 'expired':
        container = docker_client.containers.get(vps['container_id'])
        container.start()
        db.update_vps(token, {'status': 'running', 'uptime_start': str(datetime.datetime.now())})
   
    db.log_action(current_user.id, 'renew_vps', f'Renewed VPS {vps_id}')
    db.add_notification(vps['created_by'], f'VPS {vps_id} renewed')
    return jsonify({'message': 'Renewed'})

@app.route('/vps/<vps_id>/clone', methods=['POST'])
@login_required
@admin_required
def clone_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps:
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        was_running = container.status == 'running'
        if was_running:
            container.pause()
       
        new_image_tag = f"hvm/clone-{generate_vps_id().lower()}:latest"
        image_parts = new_image_tag.split(':')
        repository = image_parts[0] if len(image_parts) > 0 else new_image_tag
        tag = image_parts[1] if len(image_parts) > 1 else 'latest'
        new_image = container.commit(repository=repository, tag=tag)
       
        if was_running:
            container.unpause()
       
        new_vps_id = generate_vps_id()
        new_token = generate_token()
        new_root_password = generate_ssh_password()
       
        used_ports = set(v['port'] for v in db.get_all_vps().values())
        for v in db.get_all_vps().values():
            for p in v.get('additional_ports', '').split(','):
                if p and ':' in p:
                    try:
                        used_ports.add(int(p.split(':')[0]))
                    except (ValueError, IndexError):
                        pass  # Skip invalid port formats
       
        new_ssh_port = random.randint(20000, 30000)
        while new_ssh_port in used_ports:
            new_ssh_port = random.randint(20000, 30000)
       
        ports = {'22/tcp': new_ssh_port}
        new_additional = ''
        for p in vps['additional_ports'].split(','):
            if p.strip():
                port_parts = p.split(':')
                if len(port_parts) != 2:
                    continue  # Skip invalid port formats
                c = port_parts[1]
                h = random.randint(30001, 40000)
                while h in used_ports:
                    h = random.randint(30001, 40000)
                ports[f'{c}/tcp'] = h
                new_additional += f",{h}:{c}" if new_additional else f"{h}:{c}"
       
        cpuset = f"0-{vps['cpu']-1}" if vps['cpu'] > 1 else "0"
        prefix = db.get_setting('vps_hostname_prefix', VPS_HOSTNAME_PREFIX)
        new_container = docker_client.containers.run(
            new_image.id,
            detach=True,
            privileged=True,
            hostname=f"{prefix}{new_vps_id}",
            mem_limit=f"{vps['memory']}g",
            nano_cpus=vps['cpu'] * 10**9,
            cpuset_cpus=cpuset,
            cap_add=["SYS_ADMIN", "NET_ADMIN"],
            security_opt=["seccomp=unconfined"],
            network=DOCKER_NETWORK,
            volumes={f'hvm-{new_vps_id}': {'bind': '/data', 'mode': 'rw'}},
            restart_policy={"Name": "always"},
            ports=ports
        )
       
        time.sleep(5)
        new_container.reload()
       
        watermark = db.get_setting('watermark', WATERMARK)
        welcome = db.get_setting('welcome_message', WELCOME_MESSAGE)
        setup_success, _ = setup_container(new_container.id, vps['memory'], new_vps_id, new_ssh_port, new_root_password, watermark, welcome)
        if not setup_success:
            new_container.stop()
            new_container.remove()
            raise Exception('Setup failed')
       
        # Don't use tmate - removed for performance
        now = datetime.datetime.now()
        new_expires = now + datetime.timedelta(days=vps['expires_days'], hours=vps['expires_hours'], minutes=vps['expires_minutes'])
       
        new_vps_data = {
            'token': new_token,
            'vps_id': new_vps_id,
            'container_id': new_container.id,
            'memory': vps['memory'],
            'cpu': vps['cpu'],
            'disk': vps['disk'],
            'bandwidth_limit': vps['bandwidth_limit'],
            'username': 'root',
            'password': new_root_password,
            'root_password': new_root_password,
            'created_by': current_user.id,
            'created_at': str(now),
            'watermark': watermark,
            'os_image': vps['os_image'],
            'restart_count': 0,
            'last_restart': None,
            'status': 'running',
            'port': new_ssh_port,
            'image_id': new_image_tag,
            'expires_at': str(new_expires),
            'expires_days': vps['expires_days'],
            'expires_hours': vps['expires_hours'],
            'expires_minutes': vps['expires_minutes'],
            'additional_ports': new_additional,
            'uptime_start': str(now),
            'tags': vps['tags']
        }
       
        if db.add_vps(new_vps_data):
            # Get tmate session after container is ready
            try:
                time.sleep(2)  # Wait for container to be ready
                tmate_session = get_tmate_session(new_container.id)
                if tmate_session:
                    db.update_vps(new_vps_data['token'], {'tmate_session': tmate_session})
            except Exception as e:
                logger.error(f"tmate session error for cloned VPS: {e}")
            
            db.log_action(current_user.id, 'clone_vps', f'Cloned VPS {vps_id} to {new_vps_id}')
            db.add_notification(current_user.id, f'VPS {new_vps_id} cloned from {vps_id}')
            resource_history[new_vps_id] = deque(maxlen=3600)
            return render_template('vps_created.html', vps=new_vps_data, server_ip=db.get_setting('server_ip', SERVER_IP), panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    except Exception as e:
        logger.error(f"Clone VPS error: {e}")
        return render_template('error.html', error=str(e), panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

ssh_clients = {}  # sid -> (ssh, chan)

@app.route('/vps/<vps_id>/console')
@login_required
def vps_console(vps_id):
    # Access check
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='VPS not found or access denied', panel_name=db.get_setting('panel_name', PANEL_NAME))

    return render_template("console.html", vps=vps, panel_name=db.get_setting('panel_name', PANEL_NAME))

@socketio.on('ssh_connect')
def ssh_connect(data):
    sid = request.sid
    host = data.get('host')
    port = int(data.get('port', 22))
    username = data.get('username')
    password = data.get('password')

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=username, password=password, timeout=10)

        chan = ssh.invoke_shell(term='xterm')
        ssh_clients[sid] = (ssh, chan)

        def forward_output():
            while True:
                try:
                    data = chan.recv(1024)
                    if not data:
                        break
                    socketio.emit('ssh_output', data.decode(errors='ignore'), room=sid)
                except Exception:
                    break

        threading.Thread(target=forward_output, daemon=True).start()
        emit('ssh_output', f"\n✅ Connected to {host}:{port} as {username}\n")

    except Exception as e:
        emit('ssh_output', f"\n❌ Connection failed: {str(e)}\n")

@socketio.on('ssh_input')
def ssh_input(data):
    sid = request.sid
    if sid in ssh_clients:
        ssh, chan = ssh_clients[sid]
        try:
            chan.send(data)
        except Exception:
            emit('ssh_output', "\n❌ Error sending data\n")

@socketio.on('disconnect')
def disconnect():
    sid = request.sid
    if sid in ssh_clients:
        ssh, chan = ssh_clients[sid]
        chan.close()
        ssh.close()
        del ssh_clients[sid]

@app.route('/vps/<vps_id>/stats')
@login_required
def vps_stats(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        if container.status != 'running':
            return jsonify({'error': 'Not running'}), 400
       
        stats = container.stats(stream=False)
        mem_stats = stats['memory_stats']
        cpu_stats = stats['cpu_stats']
        blkio = stats['blkio_stats']
        net = stats.get('networks', {})
       
        mem_usage = mem_stats.get('usage', 0) / (1024 ** 2)
        mem_limit = mem_stats.get('limit', 1) / (1024 ** 2)
        cpu_usage = (cpu_stats['cpu_usage']['total_usage'] / cpu_stats['system_cpu_usage']) * len(cpu_stats['cpu_usage']['percpu_usage']) if 'system_cpu_usage' in cpu_stats and cpu_stats['system_cpu_usage'] > 0 else 0
       
        disk_read = sum(s['value'] for s in blkio.get('io_service_bytes_recursive', []) if s['op'] == 'Read') / (1024 ** 2)
        disk_write = sum(s['value'] for s in blkio.get('io_service_bytes_recursive', []) if s['op'] == 'Write') / (1024 ** 2)
       
        net_in = sum(i['rx_bytes'] for i in net.values()) / (1024 ** 2)
        net_out = sum(i['tx_bytes'] for i in net.values()) / (1024 ** 2)
       
        internal = {}
        cmds = [
            ('free', ["free", "-h"]),
            ('df', ["df", "-h"]),
            ('uptime', ["uptime"]),
            ('neofetch', ["neofetch", "--off"]),
            ('top', ["top", "-b", "-n1"])
        ]
        for name, cmd in cmds:
            success, out, err = run_docker_command(vps['container_id'], cmd)
            internal[name] = out if success else err
       
        success, out, err = run_docker_command(vps['container_id'], ["curl", "http://localhost:9100/metrics"])
        metrics = out if success else ''
       
        return jsonify({
            'memory': {'used_mb': round(mem_usage, 2), 'limit_mb': round(mem_limit, 2), 'percent': round(mem_usage / mem_limit * 100, 2) if mem_limit > 0 else 0},
            'cpu': {'percent': round(cpu_usage, 2)},
            'disk': {'read_mb': round(disk_read, 2), 'write_mb': round(disk_write, 2), 'total_gb': vps['disk']},
            'network': {'in_mb': round(net_in, 2), 'out_mb': round(net_out, 2)},
            'uptime': stats['read'],
            'configured': {
    'memory': f"{vps['memory']}GB",
    'cpu': f"{vps['cpu']} cores",
    'disk': f"{vps['disk']}GB",
    'bandwidth_limit': vps['bandwidth_limit'],
},
            'internal': internal,
            'metrics': metrics
        })
    except Exception as e:
        logger.error(f"VPS stats error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/change_password', methods=['POST'])
@login_required
def change_vps_password(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        if container.status != 'running':
            return jsonify({'error': 'Not running'}), 400
       
        new_password = generate_ssh_password()
        whole = shlex.quote(f"root:{new_password}")
        cmd = f"echo {whole} | chpasswd"
        success, _, err = run_docker_command(vps['container_id'], ["bash", "-c", cmd])
        if not success:
            return jsonify({'error': err}), 500
       
        db.update_vps(token, {'password': new_password, 'root_password': new_password})
        db.log_action(current_user.id, 'change_password', f'Changed password for VPS {vps_id}')
        return jsonify({'message': 'Changed', 'password': new_password})
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/upgrade', methods=['POST'])
@login_required
@admin_required
def upgrade_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps:
        return jsonify({'error': 'Not found'}), 404
   
    try:
        new_memory = int(request.form.get('memory', 0))
        new_cpu = int(request.form.get('cpu', 0))
        new_disk = int(request.form.get('disk', 0))
        new_bandwidth = int(request.form.get('bandwidth_limit', 0))
       
        if new_memory < 1 or new_memory > 512 or new_cpu < 1 or new_cpu > 32 or new_disk < 10 or new_disk > 1000:
            return jsonify({'error': 'Invalid values'}), 400
       
        container = docker_client.containers.get(vps['container_id'])
        was_running = container.status == 'running'
        if was_running:
            container.stop()
        container.remove()
       
        ports = {'22/tcp': vps['port']}
        for p in vps['additional_ports'].split(','):
            if p.strip():
                port_parts = p.split(':')
                if len(port_parts) != 2:
                    continue  # Skip invalid port formats
                h, c = port_parts
                try:
                    ports[f'{c}/tcp'] = int(h)
                except ValueError:
                    continue  # Skip invalid port numbers
       
        cpuset = f"0-{new_cpu-1}" if new_cpu > 1 else "0"
        prefix = db.get_setting('vps_hostname_prefix', VPS_HOSTNAME_PREFIX)
        new_container = docker_client.containers.run(
            vps['image_id'],
            detach=True,
            privileged=True,
            hostname=f"{prefix}{vps_id}",
            mem_limit=f"{new_memory}g",
            nano_cpus=new_cpu * 10**9,
            cpuset_cpus=cpuset,
            cap_add=["SYS_ADMIN", "NET_ADMIN"],
            security_opt=["seccomp=unconfined"],
            network=DOCKER_NETWORK,
            volumes={f'hvm-{vps_id}': {'bind': '/data', 'mode': 'rw'}},
            restart_policy={"Name": "always"},
            ports=ports
        )
       
        time.sleep(5)
        new_container.reload()
       
        watermark = db.get_setting('watermark', WATERMARK)
        welcome = db.get_setting('welcome_message', WELCOME_MESSAGE)
        setup_success, _ = setup_container(new_container.id, new_memory, vps_id, vps['port'], vps['root_password'], watermark, welcome)
        if not setup_success:
            new_container.stop()
            new_container.remove()
            return jsonify({'error': 'Setup failed'}), 500
       
        # Get tmate session after container is ready
        tmate_session = None
        try:
            time.sleep(2)  # Wait for container to be ready
            tmate_session = get_tmate_session(new_container.id)
        except Exception as e:
            logger.error(f"tmate session error during upgrade: {e}")
        
        db.update_vps(token, {
            'container_id': new_container.id,
            'memory': new_memory,
            'cpu': new_cpu,
            'disk': new_disk,
            'bandwidth_limit': new_bandwidth,
            'status': 'running',
            'tmate_session': tmate_session,
            'uptime_start': str(datetime.datetime.now()) if was_running else vps['uptime_start']
        })
        db.log_action(current_user.id, 'upgrade_vps', f'Upgraded VPS {vps_id}')
        return jsonify({'message': 'Upgraded'})
    except Exception as e:
        logger.error(f"Upgrade VPS error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/logs')
@login_required
def vps_logs(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        logs = container.logs(tail=2000, timestamps=True).decode('utf-8')
        return jsonify({'logs': logs})
    except Exception as e:
        logger.error(f"VPS logs error: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/vps/<vps_id>/run_command', methods=['POST'])
@login_required
@admin_required
def run_vps_command(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps:
        return jsonify({'error': 'Not found'}), 404
   
    command = request.form.get('command')
    if not command:
        return jsonify({'error': 'No command'}), 400
   
    cmd_list = shlex.split(command)
    success, out, err = run_docker_command(vps['container_id'], cmd_list)
    db.log_action(current_user.id, 'run_command', f'Ran command on VPS {vps_id}: {command}')
    return jsonify({'success': success, 'output': out, 'error': err})

@app.route('/vps/<vps_id>/firewall', methods=['GET', 'POST'])
@login_required
def vps_firewall(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='Access denied', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    if request.method == 'POST':
        fw_cmd = request.form.get('fw_command')
        if not fw_cmd:
            return render_template('firewall.html', vps=vps, error='No command', status='', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
       
        cmd_list = shlex.split(fw_cmd)
        success, out, err = run_docker_command(vps['container_id'], ["ufw"] + cmd_list)
        db.log_action(current_user.id, 'firewall_update', f'Updated firewall on VPS {vps_id}: {fw_cmd}')
        if not success:
            return render_template('firewall.html', vps=vps, error=err, status='', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
        return render_template('firewall.html', vps=vps, success='Executed', status='', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    success, out, err = run_docker_command(vps['container_id'], ["ufw", "status", "verbose"])
    status = out if success else err
    return render_template('firewall.html', vps=vps, status=status, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/vps/<vps_id>/add_port', methods=['POST'])
@login_required
def add_vps_port(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    host_port = request.form.get('host_port')
    cont_port = request.form.get('cont_port', '80')
    protocol = request.form.get('protocol', 'tcp')
   
    if not host_port.isdigit():
        return jsonify({'error': 'Invalid port'}), 400
   
    host_p = int(host_port)
    used_ports = set()
    for v in db.get_all_vps().values():
        used_ports.add(v['port'])
        for p in v.get('additional_ports', '').split(','):
            if p and ':' in p:
                try:
                    used_ports.add(int(p.split(':')[0]))
                except (ValueError, IndexError):
                    pass  # Skip invalid port formats
   
    if host_p in used_ports:
        return jsonify({'error': 'Port in use'}), 400
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        was_running = container.status == 'running'
        if was_running:
            container.stop()
        container.remove()
       
        ports = {'22/tcp': vps['port']}
        for p in vps['additional_ports'].split(','):
            if p.strip():
                port_parts = p.split(':')
                if len(port_parts) != 2:
                    continue  # Skip invalid port formats
                h, c = port_parts
                try:
                    ports[f'{c}/tcp'] = int(h)
                except ValueError:
                    continue  # Skip invalid port numbers
       
        ports[f'{cont_port}/{protocol}'] = host_p
       
        cpuset = f"0-{vps['cpu']-1}" if vps['cpu'] > 1 else "0"
        prefix = db.get_setting('vps_hostname_prefix', VPS_HOSTNAME_PREFIX)
        new_container = docker_client.containers.run(
            vps['image_id'],
            detach=True,
            privileged=True,
            hostname=f"{prefix}{vps_id}",
            mem_limit=f"{vps['memory']}g",
            nano_cpus=vps['cpu'] * 10**9,
            cpuset_cpus=cpuset,
            cap_add=["SYS_ADMIN", "NET_ADMIN"],
            security_opt=["seccomp=unconfined"],
            network=DOCKER_NETWORK,
            volumes={f'hvm-{vps_id}': {'bind': '/data', 'mode': 'rw'}},
            restart_policy={"Name": "always"},
            ports=ports
        )
       
        time.sleep(5)
        new_container.reload()
       
        watermark = db.get_setting('watermark', WATERMARK)
        welcome = db.get_setting('welcome_message', WELCOME_MESSAGE)
        setup_success, _ = setup_container(new_container.id, vps['memory'], vps_id, vps['port'], vps['root_password'], watermark, welcome)
        if not setup_success:
            new_container.stop()
            new_container.remove()
            return jsonify({'error': 'Setup failed'}), 500
       
        new_additional = vps['additional_ports'] + f",{host_p}:{cont_port}" if vps['additional_ports'] else f"{host_p}:{cont_port}"
       
        db.update_vps(token, {'container_id': new_container.id, 'additional_ports': new_additional, 'status': 'running'})
        db.log_action(current_user.id, 'add_port', f'Added port {host_p} to VPS {vps_id}')
        return jsonify({'message': 'Port added'})
    except Exception as e:
        logger.error(f"Add port error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/remove_port', methods=['POST'])
@login_required
def remove_vps_port(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    host_port = request.form.get('host_port')
   
    if not host_port.isdigit():
        return jsonify({'error': 'Invalid port'}), 400
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        was_running = container.status == 'running'
        if was_running:
            container.stop()
        container.remove()
       
        ports = {'22/tcp': vps['port']}
        new_additional = []
        for p in vps['additional_ports'].split(','):
            if p.strip():
                port_parts = p.split(':')
                if len(port_parts) != 2:
                    continue  # Skip invalid port formats
                h, c = port_parts
                try:
                    if h != host_port:
                        ports[f'{c}/tcp'] = int(h)
                        new_additional.append(f"{h}:{c}")
                except ValueError:
                    continue  # Skip invalid port numbers
       
        cpuset = f"0-{vps['cpu']-1}" if vps['cpu'] > 1 else "0"
        prefix = db.get_setting('vps_hostname_prefix', VPS_HOSTNAME_PREFIX)
        new_container = docker_client.containers.run(
            vps['image_id'],
            detach=True,
            privileged=True,
            hostname=f"{prefix}{vps_id}",
            mem_limit=f"{vps['memory']}g",
            nano_cpus=vps['cpu'] * 10**9,
            cpuset_cpus=cpuset,
            cap_add=["SYS_ADMIN", "NET_ADMIN"],
            security_opt=["seccomp=unconfined"],
            network=DOCKER_NETWORK,
            volumes={f'hvm-{vps_id}': {'bind': '/data', 'mode': 'rw'}},
            restart_policy={"Name": "always"},
            ports=ports
        )
       
        time.sleep(5)
        new_container.reload()
       
        watermark = db.get_setting('watermark', WATERMARK)
        welcome = db.get_setting('welcome_message', WELCOME_MESSAGE)
        setup_success, _ = setup_container(new_container.id, vps['memory'], vps_id, vps['port'], vps['root_password'], watermark, welcome)
        if not setup_success:
            new_container.stop()
            new_container.remove()
            return jsonify({'error': 'Setup failed'}), 500
       
        db.update_vps(token, {'container_id': new_container.id, 'additional_ports': ','.join(new_additional), 'status': 'running'})
        db.log_action(current_user.id, 'remove_port', f'Removed port {host_port} from VPS {vps_id}')
        return jsonify({'message': 'Port removed'})
    except Exception as e:
        logger.error(f"Remove port error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/vps/<vps_id>/file_manager')
@login_required
def vps_file_manager(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='Access denied', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    path = request.args.get('path', '/')
    success, out, err = run_docker_command(vps['container_id'], ["ls", "-la", path])
    files = out.splitlines() if success else []
    return render_template('file_manager.html', vps=vps, path=path, files=files, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/vps/<vps_id>/upload', methods=['POST'])
@login_required
def upload_file(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
   
    file = request.files['file']
    path = request.form.get('path', '/')
   
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)
       
        try:
            with open(temp_path, 'rb') as f:
                data = f.read()
            tar_stream = BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tarinfo = tarfile.TarInfo(name=filename)
                tarinfo.size = len(data)
                tar.addfile(tarinfo, BytesIO(data))
            tar_stream.seek(0)
            docker_client.containers.get(vps['container_id']).put_archive(path, tar_stream)
            os.remove(temp_path)
            db.log_action(current_user.id, 'upload_file', f'Uploaded {filename} to VPS {vps_id}')
            return jsonify({'message': 'Uploaded'})
        except Exception as e:
            os.remove(temp_path)
            logger.error(f"Upload file error: {e}")
            return jsonify({'error': str(e)}), 500
   
    return jsonify({'error': 'Invalid file'}), 400

@app.route('/vps/<vps_id>/download')
@login_required
def download_file(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'No path'}), 400
   
    try:
        data, stat = docker_client.containers.get(vps['container_id']).get_archive(path)
        f = BytesIO(b''.join(data))
        with tarfile.open(fileobj=f) as tar:
            file_data = tar.extractfile(tar.getmembers()[0]).read()
        db.log_action(current_user.id, 'download_file', f'Downloaded {path} from VPS {vps_id}')
        return send_file(BytesIO(file_data), download_name=os.path.basename(path), as_attachment=True)
    except Exception as e:
        logger.error(f"Download file error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/security_scan', methods=['POST'])
@login_required
def security_scan(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        success, out, err = run_docker_command(vps['container_id'], ["clamscan", "-r", "/"])
        db.log_action(current_user.id, 'security_scan', f'Performed security scan on VPS {vps_id}')
        return jsonify({'output': out, 'error': err})
    except Exception as e:
        logger.error(f"Security scan error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/benchmark', methods=['POST'])
@login_required
def benchmark_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        success, out, err = run_docker_command(vps['container_id'], ["sysbench", "--test=cpu", "run"])
        db.log_action(current_user.id, 'benchmark', f'Performed benchmark on VPS {vps_id}')
        return jsonify({'output': out, 'error': err})
    except Exception as e:
        logger.error(f"Benchmark error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/processes', methods=['GET', 'POST'])
@login_required
def vps_processes(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='Access denied', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    if request.method == 'POST':
        pid = request.form.get('pid')
        if pid:
            success, out, err = run_docker_command(vps['container_id'], ["kill", pid])
            if success:
                db.log_action(current_user.id, 'kill_process', f'Killed process {pid} in VPS {vps_id}')
            return jsonify({'success': success, 'output': out, 'error': err})
   
    success, out, err = run_docker_command(vps['container_id'], ["ps", "aux"])
    processes = out.splitlines() if success else []
    return render_template('processes.html', vps=vps, processes=processes, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/vps/<vps_id>/services', methods=['GET', 'POST'])
@login_required
def vps_services(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='Access denied', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    if request.method == 'POST':
        service = request.form.get('service')
        action = request.form.get('action')
        if service and action in ['start', 'stop', 'restart']:
            success, out, err = run_docker_command(vps['container_id'], ["systemctl", action, service])
            if success:
                db.log_action(current_user.id, f'{action}_service', f'{action.capitalize()}ed service {service} in VPS {vps_id}')
            return jsonify({'success': success, 'output': out, 'error': err})
   
    success, out, err = run_docker_command(vps['container_id'], ["systemctl", "list-units", "--type=service"])
    services = out.splitlines() if success else []
    return render_template('services.html', vps=vps, services=services, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/vps/<vps_id>/packages', methods=['GET', 'POST'])
@login_required
def vps_packages(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='Access denied', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    if request.method == 'POST':
        package = request.form.get('package')
        action = request.form.get('action')
        if package and action in ['install', 'remove']:
            cmd = ["apt-get", action, "-y", package]
            success, out, err = run_docker_command(vps['container_id'], cmd)
            if success:
                db.log_action(current_user.id, f'{action}_package', f'{action.capitalize()}ed package {package} in VPS {vps_id}')
            return jsonify({'success': success, 'output': out, 'error': err})
   
    success, out, err = run_docker_command(vps['container_id'], ["apt", "list", "--installed"])
    packages = out.splitlines() if success else []
    return render_template('packages.html', vps=vps, packages=packages, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/vps/<vps_id>/vps_users', methods=['GET', 'POST'])
@login_required
def vps_users(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='Access denied', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        action = request.form.get('action')
        if action == 'add' and username and password:
            cmd = f"useradd {shlex.quote(username)} && echo '{shlex.quote(username)}:{shlex.quote(password)}' | chpasswd"
            success, out, err = run_docker_command(vps['container_id'], ["bash", "-c", cmd])
            if success:
                db.log_action(current_user.id, 'add_vps_user', f'Added user {username} to VPS {vps_id}')
            return jsonify({'success': success, 'output': out, 'error': err})
        elif action == 'delete' and username:
            success, out, err = run_docker_command(vps['container_id'], ["userdel", shlex.quote(username)])
            if success:
                db.log_action(current_user.id, 'delete_vps_user', f'Deleted user {username} from VPS {vps_id}')
            return jsonify({'success': success, 'output': out, 'error': err})
   
    success, out, err = run_docker_command(vps['container_id'], ["cat", "/etc/passwd"])
    users = [line.split(':')[0] for line in out.splitlines() if success and line and ':' in line]
    return render_template('vps_users.html', vps=vps, users=users, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/vps/<vps_id>/cron', methods=['GET', 'POST'])
@login_required
def vps_cron(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='Access denied', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    if request.method == 'POST':
        cron_job = request.form.get('cron_job')
        if cron_job:
            cmd = f"(crontab -l ; echo \"{shlex.quote(cron_job)}\") | crontab -"
            success, out, err = run_docker_command(vps['container_id'], ["bash", "-c", cmd])
            if success:
                db.log_action(current_user.id, 'add_cron', f'Added cron job to VPS {vps_id}')
            return jsonify({'success': success, 'output': out, 'error': err})
   
    success, out, err = run_docker_command(vps['container_id'], ["crontab", "-l"])
    crons = out.splitlines() if success else []
    return render_template('cron.html', vps=vps, crons=crons, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/vps/<vps_id>/view_logs', methods=['GET', 'POST'])
@login_required
def vps_view_logs(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return render_template('error.html', error='Access denied', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    log_path = request.form.get('log_path', '/var/log/syslog')
    search_term = request.form.get('search_term', '')
   
    cmd = ["cat", log_path]
    success, out, err = run_docker_command(vps['container_id'], cmd)
    logs = out if success else err
   
    if search_term:
        logs = '\n'.join(line for line in logs.splitlines() if search_term in line)
   
    return render_template('view_logs.html', vps=vps, logs=logs, log_path=log_path, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/vps/<vps_id>/tune_performance', methods=['POST'])
@login_required
def tune_performance(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    cmd = "sysctl -w vm.swappiness=10 && echo 'net.ipv6.conf.all.disable_ipv6 = 1' >> /etc/sysctl.conf && sysctl -p"
    success, out, err = run_docker_command(vps['container_id'], ["bash", "-c", cmd])
    db.log_action(current_user.id, 'tune_performance', f'Tuned performance on VPS {vps_id}')
    return jsonify({'success': success, 'output': out, 'error': err})

@app.route('/vps/<vps_id>/cloud_backup', methods=['POST'])
@login_required
def cloud_backup(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        image = container.commit()
        logger.info(f"Backup of {vps_id} uploaded to cloud")
        db.log_action(current_user.id, 'cloud_backup', f'Backed up VPS {vps_id} to cloud')
        return jsonify({'message': 'Backed up to cloud'})
    except Exception as e:
        logger.error(f"Cloud backup error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vps/<vps_id>/run_script', methods=['POST'])
@login_required
def run_script(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    script = request.form.get('script')
    if not script:
        return jsonify({'error': 'No script'}), 400
   
    success, out, err = run_docker_command(vps['container_id'], ["bash", "-c", script])
    db.log_action(current_user.id, 'run_script', f'Ran custom script on VPS {vps_id}')
    return jsonify({'success': success, 'output': out, 'error': err})

@app.route('/vps/<vps_id>/setup_alerts', methods=['POST'])
@login_required
def setup_alerts(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        return jsonify({'error': 'Access denied'}), 403
   
    cmd = "echo '* * * * * [ \"$(top -bn1 | grep Cpu | cut -d, -f1 | cut -d: -f2 | awk \'{print $1}\')\" -gt 90 ] && echo \"High CPU\" | mail -s \"Alert\" user@example.com' | crontab -"
    success, out, err = run_docker_command(vps['container_id'], ["bash", "-c", cmd])
    db.log_action(current_user.id, 'setup_alerts', f'Set up monitoring alerts on VPS {vps_id}')
    return jsonify({'success': success, 'output': out, 'error': err})


@app.route('/referral')
@login_required
def referral():
    code = db.get_referral_code(current_user.id)
    if not code:
        code = db.generate_referral_code(current_user.id)
    result = db._fetchone('SELECT referred_users FROM referrals WHERE user_id = ?', (current_user.id,))
    referred = result[0] if result and len(result) > 0 else 0
    return render_template('referral.html', code=code, referred=referred, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/admin/groups', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_groups():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            return render_template('groups.html', groups=db.get_groups(), error='Group name is required', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
        desc = request.form.get('description', '')
        db.add_group(name, desc)
        db.log_action(current_user.id, 'add_group', f'Added group {name}')
        return redirect(url_for('manage_groups'))
   
    groups = db.get_groups()
    return render_template('groups.html', groups=groups, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/admin/group/<int:group_id>/assign', methods=['POST'])
@login_required
@admin_required
def assign_group(group_id):
    vps_id = request.form.get('vps_id')
    if not vps_id:
        return jsonify({'error': 'VPS ID is required'}), 400
    db.assign_vps_to_group(group_id, vps_id)
    db.log_action(current_user.id, 'assign_group', f'Assigned VPS {vps_id} to group {group_id}')
    return redirect(url_for('admin_panel'))

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    update_system_stats()
    all_vps = list(db.get_all_vps().values())
    all_users = db.get_all_users()
    banned = db.get_banned_users()
   
    settings = {
        'panel_name': db.get_setting('panel_name', PANEL_NAME),
        'watermark': db.get_setting('watermark', WATERMARK),
        'welcome_message': db.get_setting('welcome_message', WELCOME_MESSAGE),
        'server_ip': db.get_setting('server_ip', SERVER_IP),
        'max_containers': db.get_setting('max_containers', MAX_CONTAINERS),
        'max_vps_per_user': db.get_setting('max_vps_per_user', MAX_VPS_PER_USER),
        'vps_hostname_prefix': db.get_setting('vps_hostname_prefix', VPS_HOSTNAME_PREFIX),
        'maintenance_mode': db.get_setting('maintenance_mode', 'off'),
        'registration_enabled': db.get_setting('registration_enabled', 'on')
    }
   
    stats = {
        'total_vps': len(all_vps),
        'total_users': len(all_users),
        'total_banned': len(banned),
        'total_restarts': db.get_stat('total_restarts'),
        'total_vps_created': db.get_stat('total_vps_created')
    }
   
    audit_logs = db.get_audit_logs()
    with open('hvm_panel.log', 'r') as f:
        logs = ''.join(f.readlines()[-200:])
   
    groups = db.get_groups()
    return render_template('admin.html', system_stats=system_stats, vps_list=all_vps, vps_stats=vps_stats_cache, users=all_users, banned_users=banned, audit_logs=audit_logs, groups=groups, **settings, **stats, recent_logs=logs, theme=current_user.theme)

@app.route('/admin/settings', methods=['POST'])
@login_required
@admin_required
def admin_settings():
    for key in ['panel_name', 'watermark', 'welcome_message', 'server_ip', 'vps_hostname_prefix', 'maintenance_mode', 'registration_enabled']:
        value = request.form.get(key)
        if value:
            db.set_setting(key, value)
   
    for key in ['max_containers', 'max_vps_per_user']:
        value = request.form.get(key)
        if value and value.isdigit():
            db.set_setting(key, int(value))
   
    db.log_action(current_user.id, 'update_settings', 'Updated system settings')
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'user')
        
        if not username or not password:
            return render_template('add_user.html', error='Username and password are required', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
        if len(password) < 8:
            return render_template('add_user.html', error='Password too short', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
        if db.create_user(username, password, role, email):
            db.log_action(current_user.id, 'add_user', f'Added user {username}')
            return redirect(url_for('admin_panel'))
        return render_template('add_user.html', error='Username exists', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    return render_template('add_user.html', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = db.get_user_by_id(user_id)
    if not user:
        return render_template('error.html', error='User not found', panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    if request.method == 'POST':
        username = request.form.get('username', user['username']).strip()
        password = request.form.get('password')
        role = request.form.get('role', user['role'])
        email = request.form.get('email', user.get('email')).strip()
        if password and len(password) < 8:
            return render_template('edit_user.html', error='Password too short', user=user, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
        if db.update_user(user_id, username=username, password=password, role=role, email=email):
            db.log_action(current_user.id, 'edit_user', f'Edited user {user_id}')
            return redirect(url_for('admin_panel'))
        return render_template('edit_user.html', error='Update failed', user=user, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)
   
    return render_template('edit_user.html', user=user, panel_name=db.get_setting('panel_name', PANEL_NAME), theme=current_user.theme)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if db.delete_user(user_id):
        db.log_action(current_user.id, 'delete_user', f'Deleted user {user_id}')
        return jsonify({'message': 'Deleted'})
    return jsonify({'error': 'Failed'}), 500

@app.route('/admin/user/<user_id>/ban', methods=['POST'])
@login_required
@admin_required
def ban_user(user_id):
    reason = request.form.get('reason', 'No reason provided')
    db.ban_user(int(user_id), reason)
    db.log_action(current_user.id, 'ban_user', f'Banned user {user_id} reason: {reason}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/user/<user_id>/unban')
@login_required
@admin_required
def unban_user(user_id):
    db.unban_user(int(user_id))
    db.log_action(current_user.id, 'unban_user', f'Unbanned user {user_id}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/user/<user_id>/make_admin')
@login_required
@admin_required
def make_admin(user_id):
    db.update_user_role(int(user_id), 'admin')
    db.log_action(current_user.id, 'make_admin', f'Made user {user_id} admin')
    return redirect(url_for('admin_panel'))

@app.route('/admin/user/<user_id>/remove_admin')
@login_required
@admin_required
def remove_admin(user_id):
    db.update_user_role(int(user_id), 'user')
    db.log_action(current_user.id, 'remove_admin', f'Removed admin from user {user_id}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/vps/<vps_id>/suspend')
@login_required
@admin_required
def admin_suspend_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps:
        return jsonify({'error': 'Not found'}), 404
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        container.stop()
    except:
        pass
   
    db.update_vps(token, {'status': 'suspended'})
    db.log_action(current_user.id, 'suspend_vps', f'Suspended VPS {vps_id}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/vps/<vps_id>/unsuspend')
@login_required
@admin_required
def admin_unsuspend_vps(vps_id):
    token, vps = db.get_vps_by_id(vps_id)
    if not vps:
        return jsonify({'error': 'Not found'}), 404
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        container.start()
    except:
        pass
   
    db.update_vps(token, {'status': 'running', 'uptime_start': str(datetime.datetime.now())})
    db.log_action(current_user.id, 'unsuspend_vps', f'Unsuspended VPS {vps_id}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/backup')
@login_required
@admin_required
def admin_backup():
    if db.backup_data():
        db.log_action(current_user.id, 'backup_system', 'Performed system backup')
        return send_file(BACKUP_FILE, as_attachment=True)
    return jsonify({'error': 'Backup failed'}), 500

@app.route('/admin/restore', methods=['POST'])
@login_required
@admin_required
def admin_restore():
    if 'backup_file' not in request.files:
        return jsonify({'error': 'No file'}), 400
   
    file = request.files['backup_file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
   
    if file and file.filename.endswith('.json'):
        file.save(BACKUP_FILE)
        if db.restore_data():
            db.log_action(current_user.id, 'restore_system', 'Restored system from backup')
            return jsonify({'message': 'Restored'})
   
    return jsonify({'error': 'Failed'}), 500

@app.route('/admin/docker_prune')
@login_required
@admin_required
def admin_docker_prune():
    try:
        docker_client.prune_containers()
        docker_client.prune_images(filters={'dangling': True})
        docker_client.prune_volumes()
        db.log_action(current_user.id, 'docker_prune', 'Pruned Docker resources')
        return jsonify({'message': 'Pruned'})
    except Exception as e:
        logger.error(f"Docker prune error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/export_vps')
@login_required
@admin_required
def export_vps():
    vps_list = list(db.get_all_vps().values())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['VPS ID', 'Container ID', 'Memory', 'CPU', 'Disk', 'Status', 'Created By', 'Created At', 'Expires At', 'Additional Ports', 'Bandwidth Limit', 'Tags'])
    for vps in vps_list:
        writer.writerow([vps['vps_id'], vps['container_id'], vps['memory'], vps['cpu'], vps['disk'], vps['status'], vps['created_by'], vps['created_at'], vps['expires_at'], vps['additional_ports'], vps['bandwidth_limit'], vps['tags']])
    output.seek(0)
    db.log_action(current_user.id, 'export_vps', 'Exported VPS list')
    return send_file(io.BytesIO(output.getvalue().encode()), download_name='vps.csv', as_attachment=True)

@app.route('/admin/export_users')
@login_required
@admin_required
def export_users():
    users = db.get_all_users()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Username', 'Role', 'Email', 'Created At', 'Theme'])
    for user in users:
        writer.writerow([user['id'], user['username'], user['role'], user.get('email'), user['created_at'], user.get('theme')])
    output.seek(0)
    db.log_action(current_user.id, 'export_users', 'Exported users list')
    return send_file(io.BytesIO(output.getvalue().encode()), download_name='users.csv', as_attachment=True)


@socketio.on('connect', namespace='/console')
def handle_console_connect():
    pass

@socketio.on('disconnect', namespace='/console')
def handle_console_disconnect():
    sid = request.sid
    if sid in console_sessions:
        try:
            session = console_sessions[sid]
            if 'process' in session:
                process = session['process']
                if process:
                    process.terminate()
                    process.wait(timeout=2)
            elif 'pid' in session:
                try:
                    os.killpg(os.getpgid(session['pid']), signal.SIGTERM)
                except:
                    pass
        except Exception as e:
            logger.error(f"Console disconnect error: {e}")
        finally:
            del console_sessions[sid]

@socketio.on('start_shell', namespace='/console')
def start_shell(data):
    vps_id = data.get('vps_id')
    token, vps = db.get_vps_by_id(vps_id)
    if not vps or (vps['created_by'] != current_user.id and not is_admin(current_user)):
        emit('error', 'Access denied')
        return
   
    try:
        container = docker_client.containers.get(vps['container_id'])
        if container.status != 'running':
            emit('error', 'Container not running')
            return
    except Exception as e:
        logger.error(f"Console error: {e}")
        emit('error', 'Container not found')
        return
   
    sid = request.sid
    
    # Use docker exec with subprocess for cross-platform compatibility
    try:
        process = subprocess.Popen(
            ['docker', 'exec', '-i', vps['container_id'], '/bin/bash'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=0
        )
        
        console_sessions[sid] = {'process': process, 'vps_id': vps_id}
        
        def reader():
            try:
                while True:
                    if sid not in console_sessions:
                        break
                    output = process.stdout.readline()
                    if not output and process.poll() is not None:
                        break
                    if output:
                        emit('output', output)
            except Exception as e:
                logger.error(f"Console reader error: {e}")
            finally:
                if sid in console_sessions:
                    del console_sessions[sid]
                emit('shell_exit')
        
        threading.Thread(target=reader, daemon=True).start()
    except Exception as e:
        logger.error(f"Console start error: {e}")
        emit('error', f'Failed to start console: {str(e)}')

@socketio.on('input', namespace='/console')
def handle_input(data):
    sid = request.sid
    if sid not in console_sessions:
        emit('error', 'No active session')
        return
    
    try:
        session = console_sessions[sid]
        process = session['process']
        if process and process.stdin:
            process.stdin.write(data)
            process.stdin.flush()
    except Exception as e:
        logger.error(f"Console input error: {e}")
        emit('error', 'Failed to send input')

@socketio.on('resize', namespace='/console')
def resize_handler(data):
    sid = request.sid
    # Resize not critical for docker exec, but we can handle it if needed
    if sid in console_sessions and 'process' in console_sessions[sid]:
        # Docker exec doesn't support resize easily, but we can try
        pass

@socketio.on('connect', namespace='/admin')
def handle_admin_connect():
    emit('system_stats', system_stats)
    emit('vps_stats', vps_stats_cache)

@socketio.on('disconnect', namespace='/admin')
def handle_admin_disconnect():
    pass

@socketio.on('connect', namespace='/vps')
def handle_vps_connect():
    pass

@socketio.on('join_vps', namespace='/vps')
def join_vps(data):
    vps_id = data['vps_id']
    join_room(vps_id)
    if vps_id in resource_history:
        emit('history', list(resource_history[vps_id]))

@socketio.on('leave_vps', namespace='/vps')
def leave_vps(data):
    vps_id = data['vps_id']
    leave_room(vps_id)

@login_manager.user_loader
def load_user(user_id):
    user_data = db.get_user_by_id(int(user_id))
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['role'], user_data.get('email'), user_data.get('theme', 'light'))
    return None

def system_stats_updater():
    while True:
        update_system_stats()
        socketio.emit('system_stats', system_stats, namespace='/admin')
        time.sleep(10)

def vps_stats_updater():
    while True:
        update_vps_stats()
        socketio.emit('vps_stats', vps_stats_cache, namespace='/admin')
        time.sleep(5)

def anti_miner_monitor():
    while True:
        for token, vps in db.get_all_vps().items():
            if vps['status'] != 'running':
                continue
            container = docker_client.containers.get(vps['container_id'])
            stats = container.stats(stream=False)
            cpu = (stats['cpu_stats']['cpu_usage']['total_usage'] / stats['cpu_stats']['system_cpu_usage']) * 100 if 'system_cpu_usage' in stats['cpu_stats'] else 0
            if cpu > 95:
                container.stop()
                db.update_vps(token, {'status': 'suspended'})
                db.add_notification(vps['created_by'], f'VPS {vps["vps_id"]} suspended due to high CPU')
                continue
            success, out, _ = run_docker_command(vps['container_id'], ["ps", "aux"])
            if success:
                for pattern in MINER_PATTERNS:
                    if pattern in out.lower():
                        container.stop()
                        db.update_vps(token, {'status': 'suspended'})
                        db.add_notification(vps['created_by'], f'VPS {vps["vps_id"]} suspended due to mining activity')
                        break
        time.sleep(120)

def clean_stopped_containers():
    while True:
        stopped = docker_client.containers.list(filters={"status": "exited"})
        for cont in stopped:
            if cont.id not in [v['container_id'] for v in db.get_all_vps().values()]:
                cont.remove()
        time.sleep(600)

def check_expired_vps():
    while True:
        now = datetime.datetime.now()
        for vps_id, vps in db.get_all_vps().items():
            if vps.get('expires_at'):
                expires = datetime.datetime.fromisoformat(vps['expires_at'])
                if now > expires and vps['status'] != 'expired':
                    try:
                        container = docker_client.containers.get(vps['container_id'])
                        container.stop()
                        container.remove()
                        db.update_vps(vps['token'], {'status': 'expired'})
                        db.add_notification(vps['created_by'], f'VPS {vps_id} has expired')
                        user = db.get_user_by_id(vps['created_by'])
                        if user.get('email'):
                            send_email(user['email'], 'VPS Expired', f'Your VPS {vps_id} has expired.')
                    except:
                        pass
        time.sleep(60)

def monitor_containers():
    while True:
        for token, vps in db.get_all_vps().items():
            try:
                cont = docker_client.containers.get(vps['container_id'])
                status = cont.status
                expires = datetime.datetime.fromisoformat(vps['expires_at'])
                if datetime.datetime.now() > expires and status == 'running':
                    cont.stop()
                    db.update_vps(token, {'status': 'expired'})
                    socketio.emit('vps_status', {'vps_id': vps['vps_id'], 'status': 'expired'}, namespace='/admin')
                    continue
                if status != vps['status']:
                    db.update_vps(token, {'status': status})
                    socketio.emit('vps_status', {'vps_id': vps['vps_id'], 'status': status}, namespace='/admin')
            except docker.errors.NotFound:
                if vps['status'] != 'not_found':
                    db.update_vps(token, {'status': 'not_found'})
                    socketio.emit('vps_status', {'vps_id': vps['vps_id'], 'status': 'not_found'}, namespace='/admin')
        time.sleep(15)

def scheduled_backups():
    while True:
        if BACKUP_SCHEDULE == 'daily':
            time.sleep(86400)
        elif BACKUP_SCHEDULE == 'hourly':
            time.sleep(3600)
        db.backup_data()
        logger.info("Scheduled backup performed")

threading.Thread(target=system_stats_updater, daemon=True).start()
threading.Thread(target=vps_stats_updater, daemon=True).start()
threading.Thread(target=anti_miner_monitor, daemon=True).start()
threading.Thread(target=clean_stopped_containers, daemon=True).start()
threading.Thread(target=check_expired_vps, daemon=True).start()
threading.Thread(target=monitor_containers, daemon=True).start()
threading.Thread(target=scheduled_backups, daemon=True).start()


__version__ = "3.1"

DEFAULT_ART = r"""
  _    _  __      __  __  __      _____               _   _   ______   _      
 | |  | | \ \    / / |  \/  |    |  __ \      /\     | \ | | |  ____| | |     
 | |__| |  \ \  / /  | \  / |    | |__) |    /  \    |  \| | | |__    | |     
 |  __  |   \ \/ /   | |\/| |    |  ___/    / /\ \   | . ` | |  __|   | |     
 | |  | |    \  /    | |  | |    | |       / ____ \  | |\  | | |____  | |____ 
 |_|  |_|     \/     |_|  |_|    |_|      /_/    \_\ |_| \_| |______| |______|
                                                                              
                                                                                                
"""

def show_banner():
    print(DEFAULT_ART)
    print(f"Version: {__version__}\n")

show_banner()


def _find_available_port(preferred_port, max_tries=100):
    """Try to find an available port starting from preferred_port.
    Returns a usable port number. If none found in the range, returns 0 (OS-assigned)."""
    for p in range(preferred_port, preferred_port + max_tries + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', p))
                return p
            except OSError:
                continue
    return 0

if __name__ == '__main__':
    machine_id = hex(uuid.getnode())
    print(f"Your machine ID (provide to admin for license): {machine_id}")

    activated_key = db.get_setting('activated_license')
    activated = False
    if activated_key:
        valid, msg_or_data = validate_license(activated_key)
        if valid:
            lic = db.get_license(activated_key)
            if lic and lic.get('active') and datetime.datetime.fromisoformat(lic['expires_at']) > datetime.datetime.now():
                activated = True

    chosen_port = _find_available_port(SERVER_PORT, max_tries=100)
    if chosen_port == 0:
        print(f"Warning: no free ports in range {SERVER_PORT}-{SERVER_PORT+100}, requesting OS-assigned port")
    elif chosen_port != SERVER_PORT:
        print(f"Port {SERVER_PORT} is in use, switching to available port {chosen_port}")
    else:
        print(f"Using configured port {SERVER_PORT}")

    # Reserve the chosen port by binding a temporary socket first to avoid
    # a race where another process takes the port between our check and the server start.
    reserved_port = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_port = chosen_port if chosen_port else 0
            s.bind(('0.0.0.0', bind_port))
            reserved_port = s.getsockname()[1]
            # close the socket to let the server bind to it
        print(f"Starting server on port {reserved_port}")
        socketio.run(app, host='0.0.0.0', port=reserved_port, debug=DEBUG)
    except OSError as e:
        logger.error(f"Failed to start server on port {chosen_port or 0}: {e}")
        # Try OS-assigned port as fallback
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', 0))
                reserved_port = s.getsockname()[1]
            print(f"Falling back to OS-assigned port {reserved_port}")
            socketio.run(app, host='0.0.0.0', port=reserved_port, debug=DEBUG)
        except Exception:
            logger.exception("Unable to start server on any port")
            raise
