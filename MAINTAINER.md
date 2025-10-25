# MicroWeldr Maintainer Guide

This document provides instructions for maintainers on how to manage releases, publish to PyPI, and maintain the MicroWeldr package.

## 🚀 Publishing Workflow

### **PyPI Environment Names**
- **TestPyPI Environment**: `testpypi`
- **Production PyPI Environment**: `pypi`

### **Automated Publishing Process**

#### **Method 1: Version Bump + Automatic Release (Recommended)**
```bash
# 1. Go to GitHub Actions
# 2. Select "Version Bump" workflow
# 3. Click "Run workflow"
# 4. Choose version type: patch/minor/major
# 5. Set "Create release": true
# 6. The workflow will:
#    - Bump version in pyproject.toml and __init__.py
#    - Create git tag and push
#    - Create GitHub release
#    - Automatically trigger PyPI publishing
```

#### **Method 2: Manual Release Creation**
```bash
# 1. Manually bump version
poetry version patch  # or minor/major

# 2. Update __init__.py
sed -i 's/__version__ = ".*"/__version__ = "NEW_VERSION"/' microweldr/__init__.py

# 3. Commit and tag
git add pyproject.toml microweldr/__init__.py
git commit -m "🔖 Bump version: OLD_VERSION → NEW_VERSION"
git tag -a "vNEW_VERSION" -m "Version NEW_VERSION"
git push origin master
git push origin "vNEW_VERSION"

# 4. Create release in GitHub UI
# This automatically triggers PyPI publishing
```

#### **Method 3: Manual Dispatch (Testing)**
```bash
# For TestPyPI testing:
# Actions → "Publish to PyPI" → Run workflow → Environment: testpypi

# For production PyPI:
# Actions → "Publish to PyPI" → Run workflow → Environment: pypi
```

## 🔒 Security Setup (One-time)

### **1. GitHub Environments**
Go to Repository Settings → Environments and create:

**`testpypi` Environment:**
- Protection rules: ✅ Required reviewers (yourself)
- Branch restrictions: ✅ `master` only
- Wait timer: 0 minutes

**`pypi` Environment:**
- Protection rules: ✅ Required reviewers (yourself)  
- Branch restrictions: ✅ `master` only
- Wait timer: 5 minutes (safety buffer)

### **2. PyPI Trusted Publishing Setup**

**TestPyPI Configuration:**
- URL: https://test.pypi.org/manage/account/publishing/
- PyPI Project Name: `microweldr`
- Owner: `retospect`
- Repository name: `microweldr`
- Workflow filename: `pypi_publish.yml`
- Environment name: `testpypi`

**PyPI Configuration:**
- URL: https://pypi.org/manage/account/publishing/
- PyPI Project Name: `microweldr`
- Owner: `retospect`
- Repository name: `microweldr`
- Workflow filename: `pypi_publish.yml`
- Environment name: `pypi`

### **3. First-Time Package Upload**
```bash
# Only needed once to create the PyPI project
python scripts/setup_pypi.py
# Choose option 5: Full setup
```

## 📋 Release Checklist

### **Pre-Release**
- [ ] All tests passing (`pytest`)
- [ ] Code quality checks pass (`black`, `isort`, `flake8`, `mypy`)
- [ ] Version bumped appropriately
- [ ] CHANGELOG.md updated (if exists)
- [ ] Examples tested with new version
- [ ] Documentation updated

### **Release Process**
- [ ] Use GitHub Actions "Version Bump" workflow
- [ ] Verify GitHub release created
- [ ] Check PyPI upload successful
- [ ] Test installation: `pip install microweldr==NEW_VERSION`
- [ ] Verify CLI works: `microweldr --help`
- [ ] Test example: `microweldr examples/example.svg`

### **Post-Release**
- [ ] Update any dependent projects
- [ ] Announce release (if applicable)
- [ ] Monitor for issues

## 🔧 Development Workflow

### **Branch Strategy**
- `master` - Production releases
- `develop` - Development integration (optional)
- `feature/*` - Feature branches
- `hotfix/*` - Emergency fixes

### **Version Strategy**
- **Patch** (1.0.1): Bug fixes, small improvements
- **Minor** (1.1.0): New features, backward compatible
- **Major** (2.0.0): Breaking changes

### **Testing Before Release**
```bash
# Run full test suite
pytest --cov=microweldr

# Test package build
python -m build
twine check dist/*

# Test CLI installation
pip install -e .
microweldr examples/example.svg --no-validation

# Test with real printer (if available)
microweldr examples/calibration_test.svg --submit-to-printer --queue-only
```

## 🚨 Emergency Procedures

### **Hotfix Release**
```bash
# 1. Create hotfix branch from master
git checkout master
git checkout -b hotfix/critical-fix

# 2. Fix the issue
# ... make changes ...

# 3. Test thoroughly
pytest
microweldr examples/example.svg

# 4. Merge to master
git checkout master
git merge hotfix/critical-fix

# 5. Use GitHub Actions for immediate release
# Actions → Version Bump → patch → create release
```

### **Rollback (if needed)**
```bash
# PyPI doesn't allow deleting versions
# Instead, release a new fixed version
# Update documentation to recommend new version
```

## 📊 Monitoring

### **Check Release Status**
- GitHub Actions: Monitor workflow runs
- PyPI: https://pypi.org/project/microweldr/
- TestPyPI: https://test.pypi.org/project/microweldr/

### **Download Statistics**
- PyPI Stats: https://pypistats.org/packages/microweldr
- GitHub Insights: Repository traffic and clones

### **Issue Tracking**
- GitHub Issues: Bug reports and feature requests
- GitHub Discussions: Community questions
- Dependabot: Security vulnerability alerts

## 🛠️ Development Environment

### **Poetry Setup (Maintainers)**
For maintainers working on the codebase, use Poetry for dependency management:

```bash
# Clone repository
git clone https://github.com/retospect/microweldr.git
cd microweldr

# Install with Poetry
poetry install

# Activate virtual environment
poetry shell

# Run development commands
poetry run pytest
poetry run black .
poetry run mypy microweldr/
```

### **Poetry Commands**
```bash
# Add dependencies
poetry add requests

# Add development dependencies  
poetry add --group dev pytest

# Update dependencies
poetry update

# Build package
poetry build

# Publish to PyPI (use GitHub Actions instead)
poetry publish
```

## 🛠️ Maintenance Tasks

### **Regular Updates**
- [ ] Dependency updates (monthly): `poetry update`
- [ ] Security patches (as needed)
- [ ] Python version compatibility (annually)
- [ ] Documentation updates (as needed)

### **Quality Assurance**
- [ ] Run calibration tests periodically
- [ ] Verify printer compatibility
- [ ] Update example files
- [ ] Performance benchmarking

## 📞 Support

### **User Support**
- GitHub Issues for bug reports
- GitHub Discussions for questions
- Examples directory for documentation

### **Maintainer Resources**
- `.github/DEPLOYMENT_SETUP.md` - Detailed setup guide
- `scripts/setup_pypi.py` - Interactive setup tool
- GitHub Actions workflows - Automated CI/CD

## 🎯 Best Practices Summary

1. **Always use GitHub Actions** for releases (no manual PyPI uploads)
2. **Test on TestPyPI first** for major changes
3. **Use semantic versioning** consistently
4. **Require PR reviews** for master branch
5. **Monitor security alerts** and update dependencies
6. **Keep examples updated** and tested
7. **Document breaking changes** clearly
8. **Use environment protection** for production releases

---

**Happy maintaining! 🔬🚀**

For questions or issues with this process, check the GitHub Actions logs or create an issue in the repository.
