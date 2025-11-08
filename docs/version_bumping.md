# DRY Version Bumping Guide

MicroWeldr now uses `bump-my-version` for automated, DRY version management. This eliminates the need to manually update version strings across multiple files.

## 🎯 Benefits

- **DRY Principle**: Single source of truth for version numbers
- **Automated Updates**: All files updated simultaneously
- **Git Integration**: Automatic commits and tags
- **Error Prevention**: No more missed version updates
- **Consistent Workflow**: Standardized release process

## 📁 Files Automatically Updated

When you bump the version, these files are automatically updated:

- `pyproject.toml` - Poetry package version
- `microweldr/__init__.py` - Main package version
- `microweldr/api/__init__.py` - API version
- `microweldr/api/monitoring.py` - System monitoring version
- `microweldr/api/core.py` - Core API version
- `microweldr/cli/enhanced_main.py` - CLI version display
- `CHANGELOG.md` - Changelog header

## 🚀 Usage Methods

### Method 1: Make Commands (Recommended)

```bash
# Bump patch version (4.0.0 -> 4.0.1)
make bump-patch

# Bump minor version (4.0.0 -> 4.1.0)
make bump-minor

# Bump major version (4.0.0 -> 5.0.0)
make bump-major

# Show current version
make version

# Complete release workflow (bump + publish)
make release-patch
make release-minor
make release-major
```

### Method 2: Python Script

```bash
# Direct script usage
python scripts/bump_version.py patch
python scripts/bump_version.py minor
python scripts/bump_version.py major
```

### Method 3: Direct bump-my-version

```bash
# Raw bump-my-version commands
bump-my-version bump patch
bump-my-version bump minor
bump-my-version bump major
```

## 📋 Complete Release Workflow

### Quick Release (Automated)
```bash
# For patch releases (bug fixes)
make release-patch

# For minor releases (new features)
make release-minor

# For major releases (breaking changes)
make release-major
```

### Manual Release (Step by Step)
```bash
# 1. Bump version
make bump-patch  # or bump-minor/bump-major

# 2. Review changes
git show

# 3. Push to remote
git push && git push --tags

# 4. Build and publish
make publish
```

## ⚙️ Configuration

The version bumping behavior is configured in `.bumpversion.toml`:

```toml
[tool.bumpversion]
current_version = "4.0.0"
parse = "(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)"
serialize = ["{major}.{minor}.{patch}"]
search = "{current_version}"
replace = "{new_version}"
tag = true
tag_name = "v{new_version}"
tag_message = "MicroWeldr v{new_version}"
commit = true
commit_args = "--no-verify"
message = "🚀 Bump version: {current_version} → {new_version}"

# File-specific configurations...
```

## 🔍 What Happens During Version Bump

1. **Version Detection**: Reads current version from configuration
2. **File Updates**: Updates all configured files with new version
3. **Git Commit**: Creates commit with standardized message
4. **Git Tag**: Creates annotated tag (e.g., `v4.0.1`)
5. **Changelog**: Updates CHANGELOG.md with new version header

## 🎨 Semantic Versioning

MicroWeldr follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes, incompatible API changes
- **MINOR** (0.X.0): New features, backward-compatible additions
- **PATCH** (0.0.X): Bug fixes, backward-compatible fixes

### When to Use Each Type

**Patch Version (4.0.0 → 4.0.1):**
- Bug fixes
- Security patches
- Documentation updates
- Test improvements
- Performance optimizations (no API changes)

**Minor Version (4.0.0 → 4.1.0):**
- New features
- New CLI commands
- New API endpoints
- Enhanced functionality
- Deprecations (with backward compatibility)

**Major Version (4.0.0 → 5.0.0):**
- Breaking API changes
- Removed deprecated features
- Architectural changes
- Incompatible changes

## 🛠️ Troubleshooting

### Version Mismatch Issues
If you encounter version mismatches:

```bash
# Reset to current version in all files
bump-my-version bump --current-version 4.0.0 patch --dry-run
```

### Rollback Version
If you need to rollback:

```bash
# Reset to previous commit
git reset --hard HEAD~1

# Remove the tag
git tag -d v4.0.1
```

### Manual Version Fix
If files get out of sync:

1. Edit `.bumpversion.toml` to set correct `current_version`
2. Run `bump-my-version bump patch --dry-run` to preview changes
3. Run actual bump command to sync all files

## 📚 Examples

### Example 1: Bug Fix Release
```bash
# Current: v4.0.0
# Fix critical bug in SVG parser
make bump-patch
# Result: v4.0.1, all files updated, committed, tagged
```

### Example 2: Feature Release
```bash
# Current: v4.0.1
# Add new temperature control commands
make bump-minor
# Result: v4.1.0, all files updated, committed, tagged
```

### Example 3: Major Refactor
```bash
# Current: v4.1.0
# Complete API overhaul with breaking changes
make bump-major
# Result: v5.0.0, all files updated, committed, tagged
```

## 🔗 Integration with CI/CD

The version bumping system integrates well with CI/CD:

```yaml
# GitHub Actions example
- name: Bump version and publish
  run: |
    make release-patch

# Or for manual control:
- name: Bump version
  run: make bump-patch

- name: Build and publish
  run: make publish
```

## 📖 Best Practices

1. **Always use the automated tools** - Don't manually edit version numbers
2. **Review changes before pushing** - Use `git show` to verify updates
3. **Use semantic versioning** - Choose appropriate bump type
4. **Update CHANGELOG.md** - Add release notes before bumping
5. **Test before releasing** - Run tests before version bump
6. **Push tags** - Don't forget `git push --tags`

## 🎉 Benefits Over Manual Versioning

**Before (Manual):**
- Edit 6+ files individually
- Risk of missing files
- Inconsistent version numbers
- Manual git commits and tags
- Error-prone process

**After (DRY with bump-my-version):**
- Single command updates everything
- Guaranteed consistency
- Automated git operations
- Standardized commit messages
- Zero human error

This DRY approach ensures version management is reliable, consistent, and effortless! 🚀
