#!/usr/bin/env python3
"""Integration test runner script.

This script:
1. Starts fresh Docker containers using compose.yml
2. Waits for services to be ready
3. Runs integration tests
4. Cleans up containers afterward
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from rich.console import Console

PROJECT_ROOT = Path(__file__).parent.parent
COMPOSE_FILE = PROJECT_ROOT / "compose.testing.yml"

console = Console()


def log(message: str, style: str = "") -> None:
    """Print styled log message."""
    console.print(message, style=style)


def run_command(
    cmd: list[str], check: bool = True, capture_output: bool = False
) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    log(f"Running: {' '.join(cmd)}", "cyan")
    return subprocess.run(
        cmd, check=check, capture_output=capture_output, text=True, cwd=PROJECT_ROOT
    )


async def wait_for_mint(url: str, timeout: int = 60) -> bool:
    """Wait for mint to be ready."""
    log(f"Waiting for mint at {url}...", "yellow")

    start_time = time.time()
    async with httpx.AsyncClient() as client:
        while time.time() - start_time < timeout:
            try:
                response = await client.get(f"{url}/v1/info", timeout=5.0)
                if response.status_code == 200:
                    info = response.json()
                    if info.get("name"):
                        log(f"✅ Mint ready: {info.get('name')}", "green")
                        return True
            except Exception:
                pass

            await asyncio.sleep(2)

    log(f"❌ Mint at {url} not ready after {timeout}s", "red")
    return False


def cleanup_docker() -> None:
    """Clean up Docker containers and volumes."""
    log("🧹 Cleaning up Docker containers and volumes...", "yellow")

    try:
        # Stop and remove containers
        run_command(
            ["docker-compose", "-f", str(COMPOSE_FILE), "down", "-v"], check=False
        )

        # Remove any orphaned containers
        run_command(["docker", "container", "prune", "-f"], check=False)

        # Remove unused volumes (be careful with this)
        run_command(["docker", "volume", "prune", "-f"], check=False)

        log("✅ Docker cleanup completed", "green")
    except Exception as e:
        log(f"⚠️  Docker cleanup failed: {e}", "yellow")


def start_services() -> None:
    """Start Docker services with fresh state."""
    log("🚀 Starting Docker services...", "blue")

    # Ensure we start with clean state
    cleanup_docker()

    # Start services
    run_command(
        [
            "docker-compose",
            "-f",
            str(COMPOSE_FILE),
            "up",
            "-d",
            "--force-recreate",  # Recreate containers even if config hasn't changed
            "--renew-anon-volumes",  # Recreate anonymous volumes
        ]
    )

    log("✅ Docker services started", "green")


def run_tests() -> bool:
    """Run the integration tests."""
    log("🧪 Running integration tests...", "blue")

    env = os.environ.copy()
    env["RUN_INTEGRATION_TESTS"] = "1"
    env["USE_LOCAL_SERVICES"] = "1"  # Use local Docker services

    # Run only integration tests
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/",
        "-v",
        "--tb=short",
        "--color=yes",
    ]

    try:
        result = subprocess.run(cmd, env=env, cwd=PROJECT_ROOT)
        if result.returncode == 0:
            log("✅ Integration tests passed", "green")
            return True
        else:
            log("❌ Integration tests failed", "red")
            return False
    except Exception as e:
        log(f"❌ Failed to run tests: {e}", "red")
        return False


def check_dependencies() -> bool:
    """Check that required dependencies are available."""
    log("🔍 Checking dependencies...", "blue")

    # Check Docker
    try:
        run_command(["docker", "--version"], capture_output=True)
        log("✅ Docker found", "green")
    except (subprocess.CalledProcessError, FileNotFoundError):
        log("❌ Docker not found. Please install Docker.", "red")
        return False

    # Check Docker Compose
    try:
        run_command(["docker-compose", "--version"], capture_output=True)
        log("✅ Docker Compose found", "green")
    except (subprocess.CalledProcessError, FileNotFoundError):
        log("❌ Docker Compose not found. Please install Docker Compose.", "red")
        return False

    # Check pytest
    try:
        run_command([sys.executable, "-m", "pytest", "--version"], capture_output=True)
        log("✅ pytest found", "green")
    except (subprocess.CalledProcessError, FileNotFoundError):
        log("❌ pytest not found. Please install pytest.", "red")
        return False

    # Check compose file exists
    if not COMPOSE_FILE.exists():
        log(f"❌ Compose file not found: {COMPOSE_FILE}", "red")
        return False
    else:
        log("✅ Compose file found", "green")

    return True


async def main() -> int:
    """Main function."""
    log("🎯 Starting integration test runner", "bold blue")

    try:
        # Check dependencies
        if not check_dependencies():
            sys.exit(1)

        # Start services
        start_services()

        # Wait for services to be ready
        if not await wait_for_mint("http://localhost:3338"):
            raise RuntimeError("Mint failed to start properly")

        # Run tests
        success = run_tests()

        if success:
            log(
                "🎉 Integration tests completed successfully!",
                "bold green",
            )
            return 0
        else:
            log("💥 Integration tests failed!", "bold red")
            return 1

    except KeyboardInterrupt:
        log("⏹️  Interrupted by user", "yellow")
        return 1

    except Exception as e:
        log(f"💥 Unexpected error: {e}", "red")
        return 1

    finally:
        # Always cleanup
        cleanup_docker()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
