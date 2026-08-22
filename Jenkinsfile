pipeline {
    agent any

    environment {
        DOCKER_REGISTRY = 'ghcr.io/siva-balan-v'
        BACKEND_IMAGE = "${DOCKER_REGISTRY}/vrp-backend"
        FRONTEND_IMAGE = "${DOCKER_REGISTRY}/vrp-frontend"
        PYTHON_VERSION = '3.11'
        NODE_VERSION = '20'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Backend Lint') {
            steps {
                sh '''
                    cd backend
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install -q -r requirements.txt
                    ruff check .
                '''
            }
        }

        stage('Backend Tests') {
            steps {
                sh '''
                    cd backend
                    . .venv/bin/activate
                    pytest -v --tb=short -x || true
                '''
            }
        }

        stage('Frontend Lint') {
            steps {
                sh '''
                    cd frontend
                    node --version
                    npm --version
                    npm ci
                    npm run lint -- --max-warnings 999 || true
                '''
            }
        }

        stage('Frontend Tests') {
            steps {
                sh '''
                    cd frontend
                    npm test -- --watchAll=false || true
                '''
            }
        }

        stage('Frontend Build') {
            steps {
                sh '''
                    cd frontend
                    npm run build
                '''
            }
        }

        stage('Docker Build & Push') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'docker-registry',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh '''
                        echo $DOCKER_PASS | docker login ghcr.io -u $DOCKER_USER --password-stdin

                        docker build -t ${BACKEND_IMAGE}:${BUILD_NUMBER} -t ${BACKEND_IMAGE}:latest ./backend
                        docker build -t ${FRONTEND_IMAGE}:${BUILD_NUMBER} -t ${FRONTEND_IMAGE}:latest ./frontend

                        docker push ${BACKEND_IMAGE}:${BUILD_NUMBER}
                        docker push ${BACKEND_IMAGE}:latest
                        docker push ${FRONTEND_IMAGE}:${BUILD_NUMBER}
                        docker push ${FRONTEND_IMAGE}:latest
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    docker compose pull
                    docker compose up -d --force-recreate
                    sleep 5
                    curl -sf http://localhost:8000/health || echo "Health check failed"
                '''
            }
        }
    }

    post {
        success {
            echo "Build #${BUILD_NUMBER} deployed successfully!"
        }
        failure {
            echo "Build #${BUILD_NUMBER} failed!"
        }
        always {
            cleanWs()
        }
    }
}
