# Deployment Structure Planning

## Overview

This document outlines the proposed directory structure for supporting multiple deployment targets:
- **Docker Compose**: Local development and simple deployments
- **Kubernetes (kind)**: Local Kubernetes testing and development
- **AWS EKS**: Production Kubernetes deployments on AWS

## Proposed Directory Structure

```
deploy/
├── README.md                          # Overview and quick start guide
├── compose/                           # Docker Compose configurations
│   ├── docker-compose.yml             # Main compose file (moved from root)
│   ├── docker-compose.embedded.yml   # With embedded MongoDB (moved from root)
│   └── .env.example                   # Example environment variables
│
├── kubernetes/                        # Kubernetes manifests
│   ├── base/                          # Base Kustomize configuration
│   │   ├── kustomization.yaml         # Base kustomization
│   │   ├── namespace.yaml             # Namespace definition
│   │   ├── configmap.yaml             # Shared ConfigMaps
│   │   ├── secrets.yaml               # Secrets template (gitignored)
│   │   │
│   │   ├── frontend/                  # Frontend service
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   └── ingress.yaml
│   │   │
│   │   ├── backend/                   # Backend API service
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   └── hpa.yaml               # Horizontal Pod Autoscaler
│   │   │
│   │   ├── worker/                    # Worker service
│   │   │   ├── deployment.yaml
│   │   │   └── service.yaml
│   │   │
│   │   └── mongodb/                   # MongoDB (optional, for kind)
│   │       ├── statefulset.yaml
│   │       ├── service.yaml
│   │       └── pvc.yaml               # Persistent Volume Claim
│   │
│   ├── overlays/                      # Environment-specific overlays
│   │   ├── kind/                      # Kubernetes in Docker
│   │   │   ├── kustomization.yaml
│   │   │   ├── configmap-patch.yaml   # kind-specific config
│   │   │   ├── ingress-patch.yaml     # kind ingress configuration
│   │   │   └── mongodb-patch.yaml     # Enable MongoDB for kind
│   │   │
│   │   └── eks/                       # AWS EKS
│   │       ├── kustomization.yaml
│   │       ├── configmap-patch.yaml   # EKS-specific config
│   │       ├── ingress-patch.yaml     # AWS ALB Ingress
│   │       ├── serviceaccount.yaml    # IAM roles for service accounts
│   │       ├── mongodb-patch.yaml     # Disable embedded MongoDB (use external)
│   │       └── README.md              # EKS deployment guide
│   │
│   └── scripts/                       # Helper scripts
│       ├── deploy-kind.sh             # Deploy to kind
│       ├── deploy-eks.sh              # Deploy to EKS
│       ├── setup-kind.sh              # Setup kind cluster
│       └── cleanup.sh                 # Cleanup resources
│
└── shared/                            # Shared resources
    ├── docker/                        # Docker-related files
    │   └── Dockerfile                 # Main Dockerfile (moved from root)
    │
    ├── config/                        # Configuration templates
    │   ├── env.template               # Environment variables template
    │   └── nginx.conf                 # Nginx config (for reference)
    │
    └── docs/                          # Deployment documentation
        ├── compose.md                 # Docker Compose guide
        ├── kind.md                    # kind deployment guide
        └── eks.md                     # EKS deployment guide
```

## Key Design Decisions

### 1. Kustomize for Kubernetes
- **Why**: Industry standard for managing Kubernetes configurations across environments
- **Benefits**: 
  - DRY principle (Don't Repeat Yourself)
  - Easy environment-specific overrides
  - Native Kubernetes tooling support

### 2. Base + Overlays Pattern
- **Base**: Common Kubernetes resources shared across all environments
- **Overlays**: Environment-specific patches and configurations
  - `kind`: Local development with embedded MongoDB
  - `eks`: Production with AWS services (RDS/DocumentDB, ALB, etc.)

### 3. Separation of Concerns
- **compose/**: Docker Compose files (simple, single-machine deployments)
- **kubernetes/**: Kubernetes manifests (orchestrated, scalable deployments)
- **shared/**: Common resources (Dockerfiles, configs, docs)

### 4. Backward Compatibility
- Existing `docker-compose.yml` files moved to `deploy/compose/`
- Root-level symlinks or documentation pointing to new location
- Or keep at root for convenience (both options viable)

## Environment-Specific Considerations

### Docker Compose
- **Use Case**: Local development, single-node deployments
- **Features**: 
  - Simple networking
  - Volume mounts for development
  - Embedded MongoDB option

### Kubernetes (kind)
- **Use Case**: Local Kubernetes testing, CI/CD validation
- **Why kind over k3s**: 
  - **Production parity**: Runs standard Kubernetes (same as EKS), ensuring local testing matches production behavior
  - **EKS alignment**: What works in kind will work in EKS without surprises
  - **CI/CD standard**: Widely used in CI/CD pipelines for Kubernetes validation
  - **Docker integration**: Leverages existing Docker setup
- **Features**:
  - Full Kubernetes API
  - Embedded MongoDB StatefulSet
  - NodePort/LoadBalancer services
  - Local image registry support
- **Note**: k3s/k3d could be considered for resource-constrained environments, but kind is recommended for EKS alignment

### AWS EKS
- **Use Case**: Production deployments
- **Features**:
  - AWS Load Balancer Controller
  - IAM Roles for Service Accounts (IRSA)
  - External MongoDB (DocumentDB or self-managed)
  - Auto-scaling groups
  - CloudWatch integration
  - Secrets Manager integration

## Migration Strategy

1. **Phase 1**: Create new structure alongside existing files
2. **Phase 2**: Move compose files to `deploy/compose/`
3. **Phase 3**: Create base Kubernetes manifests
4. **Phase 4**: Create kind overlay
5. **Phase 5**: Create EKS overlay
6. **Phase 6**: Update documentation and scripts

## Next Steps

1. Review and approve this structure
2. Create the directory structure
3. Migrate existing Docker Compose files
4. Create base Kubernetes manifests
5. Implement kind overlay
6. Implement EKS overlay
7. Create deployment scripts
8. Update documentation
