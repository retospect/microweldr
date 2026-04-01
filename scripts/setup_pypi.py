#!/usr/bin/env python3
"""
Setup script for MicroWeldr PyPI publishing.
This script helps configure the initial PyPI uploads and trusted publishing.
"""

import shlex
import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f"🔧 Running: {cmd}")
    result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)  # nosec B603

    if check and result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        print(f"Error: {result.stderr}")
        sys.exit(1)

    return result


def check_dependencies():
    """Check if required tools are installed."""
    print("🔍 Checking dependencies...")

    try:
        import build
        import twine

        print("✅ build and twine are installed")
    except ImportError:
        print("❌ Missing dependencies. Installing...")
        run_command("pip install build twine")


def build_package():
    """Build the package distributions."""
    print("📦 Building package...")

    # Clean previous builds
    dist_dir = Path("dist")
    if dist_dir.exists():
        print("🧹 Cleaning previous builds...")
        run_command("rm -rf dist/")

    # Build package
    run_command("python -m build")

    # Check distributions
    run_command("twine check dist/*")
    print("✅ Package built and verified")


def upload_to_testpypi():
    """Upload package to TestPyPI."""
    print("🚀 Uploading to TestPyPI...")
    print("📝 You'll need your TestPyPI API token")
    print("   Get it from: https://test.pypi.org/manage/account/token/")

    result = run_command("twine upload --repository testpypi dist/*", check=False)

    if result.returncode == 0:
        print("✅ Successfully uploaded to TestPyPI!")
        print("🔗 Check: https://test.pypi.org/project/microweldr/")
        print(
            "📦 Test install: pip install -i https://test.pypi.org/simple/ microweldr"
        )
        return True
    else:
        print("❌ TestPyPI upload failed")
        print(f"Error: {result.stderr}")
        return False


def upload_to_pypi():
    """Upload package to PyPI."""
    print("🚀 Uploading to PyPI...")
    print("📝 You'll need your PyPI API token")
    print("   Get it from: https://pypi.org/manage/account/token/")

    confirm = input("⚠️  This will publish to production PyPI. Continue? (y/N): ")
    if confirm.lower() != "y":
        print("❌ Cancelled PyPI upload")
        return False

    result = run_command("twine upload dist/*", check=False)

    if result.returncode == 0:
        print("✅ Successfully uploaded to PyPI!")
        print("🔗 Check: https://pypi.org/project/microweldr/")
        print("📦 Install: pip install microweldr")
        return True
    else:
        print("❌ PyPI upload failed")
        print(f"Error: {result.stderr}")
        return False


def setup_trusted_publishing():
    """Display instructions for setting up trusted publishing."""
    print("\n🔒 Setting up Trusted Publishing")
    print("=" * 50)

    print("\n📋 TestPyPI Trusted Publisher:")
    print("   URL: https://test.pypi.org/manage/account/publishing/")
    print("   PyPI Project Name: microweldr")
    print("   Owner: retospect")
    print("   Repository name: microweldr")
    print("   Workflow filename: pypi_publish.yml")
    print("   Environment name: testpypi")

    print("\n📋 PyPI Trusted Publisher:")
    print("   URL: https://pypi.org/manage/account/publishing/")
    print("   PyPI Project Name: microweldr")
    print("   Owner: retospect")
    print("   Repository name: microweldr")
    print("   Workflow filename: pypi_publish.yml")
    print("   Environment name: pypi")

    print("\n🔧 GitHub Environments:")
    print("   Go to: Settings → Environments")
    print("   Create: 'testpypi' and 'pypi' environments")
    print("   Add protection rules and required reviewers")

    print("\n📖 Full setup guide: .github/DEPLOYMENT_SETUP.md")


def main():
    """Main setup function."""
    print("🔧 MicroWeldr PyPI Setup")
    print("=" * 30)

    # Check we're in the right directory
    if not Path("pyproject.toml").exists():
        print("❌ Run this script from the project root directory")
        sys.exit(1)

    print("\nWhat would you like to do?")
    print("1. Check dependencies and build package")
    print("2. Upload to TestPyPI (first time)")
    print("3. Upload to PyPI (first time)")
    print("4. Show trusted publishing setup")
    print("5. Full setup (build + TestPyPI + instructions)")

    choice = input("\nEnter choice (1-5): ").strip()

    if choice == "1":
        check_dependencies()
        build_package()

    elif choice == "2":
        check_dependencies()
        build_package()
        upload_to_testpypi()

    elif choice == "3":
        check_dependencies()
        build_package()
        if upload_to_testpypi():
            print("\n✅ TestPyPI upload successful. Now uploading to PyPI...")
            upload_to_pypi()

    elif choice == "4":
        setup_trusted_publishing()

    elif choice == "5":
        check_dependencies()
        build_package()
        if upload_to_testpypi():
            setup_trusted_publishing()
            print("\n🎉 Setup complete!")
            print("Next steps:")
            print("1. Set up trusted publishing (see instructions above)")
            print("2. Create GitHub environments")
            print("3. Use GitHub Actions for future releases")

    else:
        print("❌ Invalid choice")
        sys.exit(1)


if __name__ == "__main__":
    main()
