# Publishing Guide

This guide explains how to publish `autobots-devtools-shared-lib` to PyPI.

## Prerequisites

### 1. Create PyPI Account

1. **Production PyPI**: Sign up at https://pypi.org/account/register/
2. **TestPyPI** (optional but recommended): Sign up at https://test.pypi.org/account/register/
3. **Enable 2FA** on both accounts (required for publishing)

### 2. Generate API Tokens

#### For Production PyPI:
1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Token name: `autobots-devtools-shared-lib-github-actions`
4. Scope: "Entire account" (initially) or "Project: autobots-devtools-shared-lib" (after first publish)
5. **Copy the token immediately** - it's only shown once

#### For TestPyPI (optional):
1. Go to https://test.pypi.org/manage/account/token/
2. Follow the same steps as above

### 3. Configure GitHub Secret

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `PYPI_API_TOKEN`
5. Value: Paste your PyPI API token (starts with `pypi-`)
6. Click **Add secret**

### 4. Configure Local Poetry (for manual publishing)

```bash
# Configure PyPI token for local publishing
poetry config pypi-token.pypi <your-pypi-token>

# Optional: Configure TestPyPI for testing
poetry config repositories.testpypi https://test.pypi.org/legacy/
poetry config pypi-token.testpypi <your-test-pypi-token>
```

## Publishing Methods

### Method 1: Automated via GitHub Release (Recommended)

This method automatically publishes to PyPI when you create a GitHub release.

#### Step 1: Bump Version

```bash
cd autobots-devtools-shared-lib/

# Bump version (choose one)
poetry version patch   # 0.1.0 → 0.1.1 (bug fixes)
poetry version minor   # 0.1.0 → 0.2.0 (new features)
poetry version major   # 0.1.0 → 1.0.0 (breaking changes)
```

#### Step 2: Commit and Push

```bash
git add pyproject.toml
git commit -m "Bump version to $(poetry version -s)"
git push origin main
```

#### Step 3: Create GitHub Release

1. Go to your repository's releases page
2. Click **Draft a new release**
3. Click **Choose a tag** → Type new tag (e.g., `v0.1.1`) → **Create new tag**
4. Release title: `v0.1.1` (or your version)
5. Describe changes in the release notes
6. Click **Publish release**

The GitHub Action will automatically:
- Build the package
- Publish to PyPI
- You can monitor progress in the **Actions** tab

### Method 2: Manual Publishing

Use this for testing or when you want manual control.

#### Test on TestPyPI First (Recommended)

```bash
cd autobots-devtools-shared-lib/

# Build the package
poetry build

# Publish to TestPyPI
poetry publish -r testpypi

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ autobots-devtools-shared-lib
```

#### Publish to Production PyPI

```bash
cd autobots-devtools-shared-lib/

# Build the package
poetry build

# Publish to PyPI
poetry publish
```

## Verification

After publishing, verify the package:

### Check PyPI Page
- Visit: https://pypi.org/project/autobots-devtools-shared-lib/
- Verify version, description, and metadata

### Test Installation

```bash
# Create a test environment
python -m venv test-env
source test-env/bin/activate  # On Windows: test-env\Scripts\activate

# Install from PyPI
pip install autobots-devtools-shared-lib

# Test import
python -c "import autobots_devtools_shared_lib; print(autobots_devtools_shared_lib.__version__)"

# Cleanup
deactivate
rm -rf test-env
```

## Version Management

### Semantic Versioning

Follow [SemVer](https://semver.org/):
- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, backward compatible

### Pre-release Versions

```bash
# Alpha release
poetry version prerelease --prerelease=alpha  # 0.1.0 → 0.1.0a1

# Beta release
poetry version prerelease --prerelease=beta   # 0.1.0 → 0.1.0b1

# Release candidate
poetry version prerelease --prerelease=rc     # 0.1.0 → 0.1.0rc1
```

## Troubleshooting

### Package Name Already Exists

If `autobots-devtools-shared-lib` is taken on PyPI:
1. Change the name in `pyproject.toml`
2. Update all references in documentation
3. Ensure the name is available: https://pypi.org/project/your-new-name/

### Version Already Published

You **cannot** delete or re-upload the same version. Solutions:
1. Bump to a new version: `poetry version patch`
2. Use a post-release: `poetry version 0.1.0.post1`

### Authentication Failed

```bash
# Verify token is configured
poetry config --list | grep pypi-token

# Re-configure token
poetry config pypi-token.pypi <your-token>
```

### Build Fails

```bash
# Clean build artifacts
make clean

# Rebuild
poetry build

# Check for issues
poetry check
```

### GitHub Action Fails

1. Check the **Actions** tab for error logs
2. Verify `PYPI_API_TOKEN` secret is set correctly
3. Ensure the token has correct permissions
4. Check if package name conflicts with existing PyPI package

## Best Practices

### Before Publishing

1. **Run all checks**:
   ```bash
   make all-checks
   ```

2. **Update changelog/release notes**

3. **Test locally**:
   ```bash
   poetry build
   # Test the built package
   ```

4. **Test on TestPyPI first** (for major releases)

### Checklist

- [ ] Version bumped in `pyproject.toml`
- [ ] All tests passing
- [ ] Code formatted and linted
- [ ] Type checking passes
- [ ] Changelog updated
- [ ] README.md is current
- [ ] GitHub secret `PYPI_API_TOKEN` configured
- [ ] Package name available on PyPI

## Resources

- [PyPI Help](https://pypi.org/help/)
- [Poetry Publishing Docs](https://python-poetry.org/docs/cli/#publish)
- [Python Packaging Guide](https://packaging.python.org/)
- [Semantic Versioning](https://semver.org/)
