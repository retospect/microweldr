# GitHub Actions Deployment Setup

This document explains how to set up the GitHub Actions workflows for publishing MicroWeldr to PyPI.

## 🔧 Required Setup Steps

### 1. Create GitHub Environments

Go to your repository settings → Environments and create:

#### **`testpypi` Environment**
- **Name**: `testpypi`
- **Protection rules**:
  - ✅ Required reviewers: Add yourself
  - ✅ Wait timer: 0 minutes
  - ✅ Restrict to selected branches: `master`, `main`

#### **`pypi` Environment**
- **Name**: `pypi`
- **Protection rules**:
  - ✅ Required reviewers: Add yourself
  - ✅ Wait timer: 5 minutes (safety buffer)
  - ✅ Restrict to selected branches: `master`, `main`

### 2. Set Up PyPI Trusted Publishing

#### **For TestPyPI:**
1. Go to https://test.pypi.org/manage/account/publishing/
2. Add a new trusted publisher:
   - **PyPI Project Name**: `microweldr`
   - **Owner**: `retospect`
   - **Repository name**: `microweldr`
   - **Workflow filename**: `pypi_publish.yml`
   - **Environment name**: `testpypi`

#### **For PyPI:**
1. Go to https://pypi.org/manage/account/publishing/
2. Add a new trusted publisher:
   - **PyPI Project Name**: `microweldr`
   - **Owner**: `retospect`
   - **Repository name**: `microweldr`
   - **Workflow filename**: `pypi_publish.yml`
   - **Environment name**: `pypi`

### 3. Initial PyPI Project Setup

**First-time setup only:**

```bash
# Build the package locally
python -m build

# Upload to TestPyPI first (using API token)
twine upload --repository testpypi dist/*

# Then upload to PyPI (using API token)
twine upload dist/*
```

After the first upload, the GitHub Actions will use trusted publishing (no tokens needed).

## 🚀 Usage Workflows

### **Publishing to TestPyPI**
```bash
# Manual trigger via GitHub UI:
# Actions → Publish to PyPI → Run workflow
# Environment: testpypi
```

### **Publishing to PyPI**
```bash
# Option 1: Create a release (automatic)
git tag v1.0.1
git push origin v1.0.1
# Then create release in GitHub UI

# Option 2: Manual trigger
# Actions → Publish to PyPI → Run workflow
# Environment: pypi
```

### **Version Bumping**
```bash
# Manual trigger via GitHub UI:
# Actions → Version Bump → Run workflow
# Version type: patch/minor/major
# Create release: true/false
```

## 🔒 Security Features

### **Trusted Publishing**
- ✅ No API tokens stored in GitHub secrets
- ✅ OpenID Connect (OIDC) authentication
- ✅ Automatic token generation per workflow run
- ✅ Scoped to specific repository and environment

### **Environment Protection**
- ✅ Manual approval required for production deployments
- ✅ Branch restrictions (only master/main)
- ✅ Wait timers for safety
- ✅ Audit trail of all deployments

### **Workflow Security**
- ✅ Minimal permissions (`contents: read`, `id-token: write`)
- ✅ Artifact isolation between jobs
- ✅ Package testing before publication
- ✅ Build verification and linting

## 📋 Workflow Overview

### **`test.yml`** - Continuous Integration
- **Triggers**: Push, PR, manual
- **Matrix testing**: Python 3.8-3.12
- **Checks**: Linting, type checking, tests, CLI functionality
- **Coverage**: Codecov integration

### **`pypi_publish.yml`** - Package Publishing
- **Triggers**: Release creation, manual dispatch
- **Jobs**: Build → Test → Publish (TestPyPI/PyPI)
- **Security**: Environment protection, trusted publishing
- **Artifacts**: Wheel and source distribution

### **`version_bump.yml`** - Version Management
- **Triggers**: Manual dispatch
- **Features**: Semantic versioning, git tagging, release creation
- **Updates**: pyproject.toml, __init__.py, git tags

## 🎯 Deployment Process

### **Development → TestPyPI**
1. Develop features on feature branches
2. Merge to master via PR (triggers tests)
3. Manual dispatch: `Publish to PyPI` → `testpypi`
4. Test installation: `pip install -i https://test.pypi.org/simple/ microweldr`

### **TestPyPI → PyPI Production**
1. Verify TestPyPI package works correctly
2. Manual dispatch: `Version Bump` → bump version → create release
3. Release creation triggers automatic PyPI publication
4. Verify: `pip install microweldr`

### **Emergency Hotfix**
1. Create hotfix branch from master
2. Fix issue, test locally
3. Manual dispatch: `Version Bump` → `patch` → create release
4. Automatic PyPI publication

## 🔍 Monitoring & Troubleshooting

### **Check Workflow Status**
- GitHub Actions tab shows all workflow runs
- Environment deployments show approval history
- PyPI/TestPyPI show upload history

### **Common Issues**
- **Trusted publishing not working**: Check PyPI publisher configuration
- **Environment protection**: Ensure correct branch and approvals
- **Version conflicts**: Ensure version is bumped before publishing
- **Build failures**: Check Python compatibility and dependencies

### **Rollback Process**
```bash
# If bad version published:
# 1. Fix the issue
# 2. Bump to new version (don't delete PyPI versions)
# 3. Publish fixed version
# 4. Update documentation
```

## ✅ Verification Checklist

Before first deployment:
- [ ] GitHub environments created (`testpypi`, `pypi`)
- [ ] PyPI trusted publishers configured
- [ ] Initial package uploaded manually (first time only)
- [ ] Test workflow runs successfully
- [ ] Version bump workflow works
- [ ] TestPyPI deployment successful
- [ ] PyPI deployment successful
- [ ] Package installs correctly: `pip install microweldr`
- [ ] CLI works: `microweldr --help`

Your MicroWeldr package is now ready for professional CI/CD! 🚀
