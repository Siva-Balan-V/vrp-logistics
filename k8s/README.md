# Kubernetes Deployment — VRP Logistics

## Quick Start

```bash
# Create namespace
kubectl create ns vrp

# Create secrets from .env
kubectl create secret generic vrp-env --from-env-file=.env.production -n vrp

# Deploy infrastructure (Redis, PostgreSQL)
kubectl apply -f k8s/infrastructure.yaml -n vrp

# Wait for infra pods to be ready
kubectl wait --for=condition=ready pod -l app=redis -n vrp --timeout=120s
kubectl wait --for=condition=ready pod -l app=postgres -n vrp --timeout=120s

# Deploy backend
kubectl apply -f k8s/backend.yaml -n vrp

# Deploy frontend
kubectl apply -f k8s/frontend.yaml -n vrp

# Check status
kubectl get all -n vrp
```

## Access

- Frontend: port-forward `kubectl port-forward svc/vrp-frontend 8080:80 -n vrp`
- Backend API: port-forward `kubectl port-forward svc/vrp-backend 8000:8000 -n vrp`
- Metrics: `kubectl port-forward svc/vrp-backend 8000:8000 -n vrp` then `curl http://localhost:8000/metrics`

## Production

For production, replace `vrp-env` with proper secrets management (SealedSecrets, External Secrets Operator, or Vault).
