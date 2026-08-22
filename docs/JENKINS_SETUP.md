# Jenkins CI/CD Setup Guide — Linux (Ubuntu/Debian)

## Prerequisites

- Ubuntu 22.04/24.04 or Debian 12 (adjust package names for RHEL/CentOS)
- sudo/root access
- Docker installed and running
- Git, Python 3.11+, Node.js 20+

---

## Step 1: Install Java 17 (Jenkins prerequisite)

```bash
sudo apt update
sudo apt install -y openjdk-17-jre-headless
java -version
```

## Step 2: Install Jenkins

```bash
# Add Jenkins GPG key
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key | sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null

# Add Jenkins repository
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null

# Install Jenkins
sudo apt update
sudo apt install -y jenkins

# Start and enable Jenkins
sudo systemctl start jenkins
sudo systemctl enable jenkins

# Get initial admin password
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

## Step 3: Access Jenkins UI

1. Open `http://<YOUR_SERVER_IP>:8080` in your browser
2. Enter the admin password from Step 2
3. Click **Install suggested plugins**
4. Create an admin user when prompted

## Step 4: Install Required Plugins

From Jenkins dashboard:
1. Go to **Manage Jenkins** → **Plugins** → **Available plugins**
2. Search and install:
   - `Pipeline`
   - `Docker Pipeline`
   - `Git`
   - `Pipeline: Stage View` (optional, for visual pipeline)
3. Restart Jenkins after installing plugins

## Step 5: Configure Docker Registry Credentials (GHCR)

1. Go to **Manage Jenkins** → **Credentials** → **System** → **Global credentials**
2. Click **Add Credentials**
3. Fill in:
   - **Kind**: `Username with password`
   - **Scope**: Global
   - **Username**: Your GitHub username (e.g., `siva-balan-v`)
   - **Password**: GitHub Personal Access Token (see below)
   - **ID**: `docker-registry`
   - **Description**: `GitHub Container Registry`
4. Click **Create**

### How to get a GitHub Personal Access Token:

1. Go to [github.com](https://github.com) → Click your profile → **Settings**
2. Left sidebar → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. Click **Generate new token (classic)**
   - Note: `jenkins-ghcr`
   - Expiration: 90 days (or no expiration)
   - Scopes: check **`write:packages`** and **`read:packages`**
4. Click **Generate token** → **Copy it immediately** (you won't see it again)

## Step 6: Create Jenkins Pipeline Job

1. From Jenkins dashboard, click **New Item**
2. Enter item name: `vrp-logistics`
3. Select **Pipeline** → Click **OK**
4. Under **Pipeline** section:
   - **Definition**: `Pipeline script from SCM`
   - **SCM**: `Git`
   - **Repository URL**: `https://github.com/siva-balan-v/vrp-logistics.git`
   - **Branch**: `*/main` (or `*/develop`)
   - **Script Path**: `Jenkinsfile`
5. Click **Save**

## Step 7: First Build

1. Click **Build Now** on the pipeline page
2. Watch the build progress in **Stage View**
3. Each stage will show success/failure with logs

---

## Pipeline Stages

| Stage | What it does |
|---|---|
| **Checkout** | Pulls code from GitHub |
| **Backend Lint** | Runs `ruff check .` on Python code |
| **Backend Tests** | Runs `pytest -v` |
| **Frontend Lint** | Runs `npm run lint` (ESLint) |
| **Frontend Tests** | Runs `npm test` |
| **Frontend Build** | Runs `npm run build` |
| **Docker Build & Push** | Builds Docker images, pushes to GHCR |
| **Deploy** | Runs `docker compose pull && docker compose up -d` |

---

## Troubleshooting

### Jenkins can't find docker command
```bash
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins
```

### Jenkins permission denied on files
```bash
sudo chown -R jenkins:jenkins /var/lib/jenkins/workspace/
```

### Port 8080 already in use
Edit `/etc/default/jenkins` and change `HTTP_PORT=8080` to another port.

### View Jenkins logs
```bash
sudo journalctl -u jenkins -f
```

### Restart Jenkins
```bash
sudo systemctl restart jenkins
```

---

## Environment Variables

The pipeline uses these environment variables (defined in `Jenkinsfile`):
- `DOCKER_REGISTRY` = `ghcr.io/siva-balan-v`
- `BACKEND_IMAGE` = `ghcr.io/siva-balan-v/vrp-backend`
- `FRONTEND_IMAGE` = `ghcr.io/siva-balan-v/vrp-frontend`

---

## Manual Deployment (without Jenkins)

If you just want to deploy manually on your server:

```bash
cd /path/to/vrp-logistics

# Pull latest images
docker compose pull

# Restart with new images
docker compose up -d --force-recreate

# Check status
docker compose ps

# View logs
docker compose logs -f backend
```
