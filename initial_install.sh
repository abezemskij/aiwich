#!/bin/bash
set -euo pipefail

# =============================================================
#  Initial Install Script — University of AI-Wich
#  Tested on: Ubuntu 22.04 / Debian 12
#  Usage:     sudo bash initial_install.sh
# =============================================================

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[✔]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✘]${NC} $*"; exit 1; }
step()  { echo -e "\n${YELLOW}──── $* ────${NC}"; }

[ "$EUID" -eq 0 ] || error "Run as root: sudo bash initial_install.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─────────────────────────────────────────
# 1. SYSTEM UPDATE & PREREQUISITES
# ─────────────────────────────────────────
step "Updating system and installing prerequisites"
apt-get update -y
apt-get install -y curl python3 python3-pip
log "Prerequisites ready"


# ─────────────────────────────────────────
# 2. MYSQL / MARIADB — INSTALL IF MISSING
# ─────────────────────────────────────────
step "Checking MySQL / MariaDB"
if dpkg -l mysql-server 2>/dev/null | grep -q '^ii'; then
    log "MySQL already installed"
    DB_SERVICE="mysql"
elif dpkg -l mariadb-server 2>/dev/null | grep -q '^ii'; then
    log "MariaDB already installed"
    DB_SERVICE="mariadb"
else
    log "No MySQL/MariaDB found — attempting mysql-server..."
    if apt-get install -y mysql-server 2>/dev/null; then
        log "MySQL installed"
        DB_SERVICE="mysql"
    else
        warn "mysql-server not available — falling back to mariadb-server"
        apt-get install -y mariadb-server
        log "MariaDB installed"
        DB_SERVICE="mariadb"
    fi
fi

systemctl enable "$DB_SERVICE"
systemctl start  "$DB_SERVICE"
log "$DB_SERVICE service is running"


# ─────────────────────────────────────────
# 3. MYSQL — DATABASE, USER & DATA SETUP
# ─────────────────────────────────────────
step "Configuring MySQL database"
mysql <<'SQL'
-- University user
CREATE USER IF NOT EXISTS 'university'@'localhost' IDENTIFIED BY 'university';

-- Database
CREATE DATABASE IF NOT EXISTS students;

-- Permissions
GRANT ALL PRIVILEGES ON students.* TO 'university'@'localhost';
FLUSH PRIVILEGES;

-- Table
USE students;
CREATE TABLE IF NOT EXISTS student_info (
    student_id     VARCHAR(10)  PRIMARY KEY,
    student_name   VARCHAR(100) NOT NULL,
    student_course VARCHAR(20)  NOT NULL,
    student_grade  VARCHAR(10)  NOT NULL
);

-- Sample data (INSERT IGNORE skips duplicates on re-runs)
INSERT IGNORE INTO student_info (student_id, student_name, student_course, student_grade) VALUES
('S1001', 'Alice Johnson',  'COMP1671', '72'),
('S1002', 'Ben Carter',     'COMP1671', '85'),
('S1003', 'Clara Smith',    'COMP1671', '61'),
('S1004', 'Daniel Brown',   'COMP1671', '90'),
('S1005', 'Emma Wilson',    'COMP1671', '55'),
('S1006', 'Finn Murphy',    'COMP1671', '78'),
('S1007', 'Grace Lee',      'COMP1671', '68'),
('S1008', 'Harry Davis',    'COMP1671', '83'),
('S1009', 'Isla Thompson',  'COMP1671', '47'),
('S1010', 'Jack Martin',    'COMP1671', '91');
SQL
log "Database, user, and sample data ready"


# ─────────────────────────────────────────
# 4. OLLAMA — INSTALL IF MISSING
# ─────────────────────────────────────────
step "Installing Ollama"
if command -v ollama &>/dev/null; then
    log "Ollama already installed — skipping"
else
    bash "$SCRIPT_DIR/install.sh"
    log "Ollama installed"
fi

systemctl enable ollama 2>/dev/null || true
systemctl start  ollama 2>/dev/null || true

# Wait up to 30 s for the Ollama API to become ready
log "Waiting for Ollama API..."
for i in $(seq 1 15); do
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
curl -s http://localhost:11434/api/tags >/dev/null 2>&1 || error "Ollama API did not respond — check: systemctl status ollama"
log "Ollama API is ready"


# ─────────────────────────────────────────
# 5. PULL phi3:mini
# ─────────────────────────────────────────
step "Pulling phi3:mini model"
if ollama list 2>/dev/null | grep -q "phi3:mini"; then
    log "phi3:mini already present — skipping pull"
else
    log "Downloading phi3:mini (this may take several minutes)..."
    ollama pull phi3:mini
fi
log "phi3:mini ready"


# ─────────────────────────────────────────
# 6. PYTHON DEPENDENCIES
# ─────────────────────────────────────────
step "Installing Python dependencies"
pip3 install -r "$SCRIPT_DIR/requirements.txt"
log "Python dependencies installed"


# ─────────────────────────────────────────
# DONE
# ─────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       Installation complete!             ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
echo -e "${GREEN}║  Start the app:                          ║${NC}"
echo -e "${GREEN}║  gunicorn --bind 0.0.0.0:5000 app:app    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
