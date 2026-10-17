#!/usr/bin/env bash
set -euo pipefail
: "${AWS_REGION:?Set AWS_REGION}" "${OPS_CONTACT:?Set OPS_CONTACT to your contact address}"
aws eks update-kubeconfig --region "$AWS_REGION" --name cluster-1 --alias cluster-1
printf '\nCluster: cluster-1 | Environment: assessment | Region: %s\nAuthorized use only. Activity may be audited.\nContact: %s\n\n' "$AWS_REGION" "$OPS_CONTACT"
kubectl get nodes
