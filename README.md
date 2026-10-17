# Ops Tasks: Kubernetes assessment application

A Flask/PostgreSQL task tracker with a browser UI, CRUD API, Docker Compose,
EKS manifests, Argo CD Application, namespace policy and S3 backup CronJob.

## 1. Run locally first
Requires Docker Engine with Docker Compose v2.

```bash
cp .env.example .env
# Edit .env: replace the example password with a random password.
docker compose up --build -d
docker compose logs migrate web
```
Open http://localhost:8080. Add a task, refresh, mark complete, delete.
Database is not exposed on a host port. Web is bound to loopback.

```bash
curl -fsS http://localhost:8080/health/ready
curl -fsS -H 'Content-Type: application/json' -d '{"title":"Verify persistent storage"}' http://localhost:8080/api/tasks
curl -fsS http://localhost:8080/api/tasks
docker compose restart db
# Wait for /health/ready to return 200, then verify the same task remains.
curl -fsS http://localhost:8080/api/tasks
```
`docker compose down` preserves the named volume; `down -v` deletes it.

## 2. EKS deployment prerequisites
Provision EKS named cluster-1 with managed nodes. This package does NOT provision
AWS infrastructure, install Argo CD/Kyverno, or grant cloud access automatically.
Install the EBS CSI add-on and its IAM permissions; the included gp3 StorageClass
uses standard EKS EBS CSI, not EKS Auto Mode. Ensure nodes can pull the ECR images.
Install Argo CD and Kyverno using their supported, pinned installation versions.

Build and push two images to private ECR repositories (authenticate Docker to ECR
first), replacing REGISTRY and TAG below with real values:

```bash
docker build -t "$REGISTRY/tasks:$TAG" .
docker push "$REGISTRY/tasks:$TAG"
docker build -t "$REGISTRY/tasks-backup:$TAG" backup
docker push "$REGISTRY/tasks-backup:$TAG"
```
Replace ALL `REPLACE_...` values in k8s/kustomization.yaml, k8s/backup.yaml and
gitops/application.yaml. Use unique commit tags or image digests, not latest.
Create namespace and an out-of-band Secret before Argo sync. Use a password manager
or a cloud secret manager; never commit generated Secret YAML or credentials.

```bash
kubectl create namespace tasks
read -rsp 'Database password: ' DB_PASSWORD; echo
SECRET_DIR=$(mktemp -d)
chmod 700 "$SECRET_DIR"
printf %s "$DB_PASSWORD" > "$SECRET_DIR/password"
chmod 600 "$SECRET_DIR/password"
kubectl -n tasks create secret generic database --from-file=password="$SECRET_DIR/password"
rm -rf "$SECRET_DIR"
unset DB_PASSWORD
```
This example's PostgreSQL bootstrap role owns the database and is a superuser;
use separate least-privilege application and backup roles for production.
Changing the Secret does not rotate the password inside an existing database.

Create an S3 bucket with block-public-access, encryption, lifecycle and versioning.
Configure an EKS Pod Identity association for service account database-backup in
namespace tasks, including the Pod Identity Agent and required IAM trust policy.
The backup role needs s3:PutObject and s3:GetObject on BUCKET/tasks/* (head-object
uses GetObject). Give restore operators separate read access; avoid static keys.
Configure lifecycle expiration after 7 days for prefix tasks/, and expiration of
noncurrent versions after 7 days if versioning is enabled. Job history retention
is separate from S3 retention. A 7-day object policy is not exact version retention.
The job uses S3 SSE-S3 (AES256); S3 manages encryption keys. SSE-KMS instead needs
an explicitly retained KMS key and appropriate encrypt/decrypt permissions.

Push the repository, configure Argo CD repository access, and apply the Application:

```bash
kubectl apply -f gitops/application.yaml
kubectl apply -f policies/namespace.yaml
kubectl -n tasks get pods,pvc,jobs,cronjobs
kubectl -n tasks port-forward svc/web 8080:8080
```
The namespace policy is a bootstrap operation here. To make it GitOps managed,
create a separate Argo Application pointing to policies/ after Kyverno is healthy.
Sync ordering is database (wave 0), schema Job (wave 1), app (wave 2).

## 3. Backups and restoration
Daily at 02:00 UTC; logical pg_dump custom-format snapshots of the tasks database.
Each dump is consistent at its snapshot time. Writes after the snapshot are not
included. Daily backups imply up to roughly 24 hours of data loss if jobs succeed;
monitor failures. No WAL archiving/PITR is configured. RTO must be measured.

The backup image includes matching PostgreSQL 17 client tools and AWS CLI.
pg_restore --list checks archive readability, not restore success. Actual restore
verification below is necessary. Backup failures return a nonzero exit code.

```bash
kubectl -n tasks get cronjob database-backup -o yaml
kubectl -n tasks get jobs --sort-by=.metadata.creationTimestamp
kubectl -n tasks logs job/ACTUAL_SCHEDULED_JOB_NAME
aws s3 ls "s3://$BACKUP_BUCKET/tasks/" --recursive
```
Wait for a genuinely scheduled execution. Temporarily set schedule to */5 * * * *
in Git to collect evidence, then commit the daily schedule again. Manually created
Jobs help debug but are not evidence of scheduler execution.

Restore into a NEW empty PostgreSQL 17 database/server. Keep the original intact.
Obtain the database credentials through the approved secret store, read permission
for S3, network access, and matching PostgreSQL client tools. The dump omits owners,
ACLs, cluster roles and global objects: recreate necessary roles separately.

Example using your local Compose database as an isolated restore target:

```bash
aws s3 cp "s3://$BACKUP_BUCKET/tasks/EXACT_BACKUP_KEY.dump" restore.dump
docker compose exec -T db createdb -U tasks tasks_restore
docker compose exec -T db pg_restore -U tasks -d tasks_restore --no-owner --no-acl --exit-on-error < restore.dump
docker compose exec -T db psql -U tasks -d tasks_restore -c 'SELECT * FROM tasks ORDER BY id;'
```
Verify known records from before the snapshot. For application-level recovery,
point a separate app deployment at the restored database, verify reads/writes,
and only then plan a controlled cutover. Do not restore over the running original.
Remove local dump files after verification; they contain application data.

## 4. Evidence checklist
- Banner: AWS_REGION=... OPS_CONTACT=... bash scripts/cluster-login.sh
- Policy: kubectl create ns test-demo must fail; kubectl create ns demo must pass.
- Argo Synced/Healthy; manually scale web to 1, then show self-heal returns to 2.
- App POST/GET output; Bound PVC; delete db-0 pod, wait Ready, repeat GET.
- Scheduled Job creation/logs; S3 listing; daily schedule and lifecycle configuration.
- Restore known records and show query/API evidence, recording backup timestamp.
- Reviewer access: temporary IAM access plus suitable RBAC; kubeconfig alone is not
  an AWS credential. Agree review duration and revoke access after review.

## Design and limitations
Browser -> ClusterIP web service -> Flask Deployment -> db headless service ->
PostgreSQL StatefulSet -> gp3 EBS PVC. CronJob reads PostgreSQL and uploads to S3.
Argo reconciles the remote Git manifests into this cluster.

Single database replica: persistent but not highly available. The application is
unauthenticated and intended for loopback/port-forward demo access. Add authentication,
TLS ingress, network policies and distinct database roles before exposing it publicly.
No full monitoring stack is bundled; use pod logs, readiness/liveness and Job status
for assessment evidence and add backup-failure alerts for production.
Schema init is idempotent for this first schema; use versioned migrations for changes.
Argo bootstrap, AWS setup, Secret injection and IAM association remain explicit
prerequisites. All cloud evidence must come from real execution, not these templates.

## Checks
```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```
Unit checks cover input validation and HTTP routing. They do not prove database
integration, Docker builds, cluster deployment, scheduled backup or recovery.
