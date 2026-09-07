# Kubernetes Deployment Guide

Deploys the VRP stack (backend, frontend, redis, postgres) into the
`vrp-production` namespace.

## Prerequisites

- A Kubernetes cluster with an nginx ingress controller.
- `vrp-env` Secret populated (see `secret.example.yaml`).

## 1. Create the Secret

```sh
cp secret.example.yaml secret.yaml
# edit secret.yaml and set real values (they are read as plain strings via stringData)
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
```

## 2. Applies (order matters)

```sh
kubectl apply -f infrastructure.yaml   # redis + postgres
kubectl apply -f backend.yaml          # backend + service + HPA
kubectl apply -f frontend.yaml         # frontend + service + ingress
```

## 3. Rollout / rollback

```sh
# pin the running image to a specific CI build (Jenkins pushes :latest and :<BUILD_NUMBER>)
kubectl -n vrp-production set image deployment/vrp-backend  backend  =ghcr.io/siva-balan-v/vrp-backend:<BUILD_NUMBER>
kubectl -n vrp-production set image deployment/vrp-frontend frontend =ghcr.io/siva-balan-v/vrp-frontend:<BUILD_NUMBER>
```

## Notes

- The backend runs `alembic upgrade head` automatically at startup, so no
  separate migration job is needed.
- Migrations are tracked by the `vrp-env` Secret; re-adding the Secret requires
  `kubectl delete secret vrp-env --ignore-not-found && kubectl apply -f secret.yaml`.
- Prometheus scrape annotations on the backend deployment pair it with the
  `docker-compose.monitoring.yml` stack if deployed in-cluster.
- **Persistence:** redis/postgres currently mount `emptyDir` volumes, so data is
  lost on pod restart. For real persistence, replace the emptyDir blocks in
  `infrastructure.yaml` with `PersistentVolumeClaim` volumes backed by a
  StorageClass appropriate for your cluster (e.g. managed disks / EBS).
