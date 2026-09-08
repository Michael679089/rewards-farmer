import json
import logging
import os
import re
import sys
from typing import NamedTuple

import log_utils
import mimic_typing
import mouse_trajectory
import rewards_tasks
from constants import PROFILE_NAME, REWARDS_HEADLESS, USER_DATA_DIR
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException

logger = logging.getLogger(__name__)


def build_options(profile_directory: str = None) -> webdriver.EdgeOptions:
    """Builds Selenium options for Edge, keeping bot detection flags clean."""
    options = webdriver.EdgeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")

    if profile_directory:
        options.add_argument(f"--profile-directory={profile_directory}")

    if REWARDS_HEADLESS:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    return options


def get_info_cache_from_local_state() -> dict:
    """Reads profile info cache directly from Edge's Local State file."""
    local_state_path = os.path.join(USER_DATA_DIR, "Local State")
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("profile", {}).get("info_cache", {})
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.error("Could not read Local State: %s", exc)
        return {}


def is_local_state_updated(profile_children: list) -> bool:
    """Verifies that Local State contains non-empty gaia IDs and valid profiles."""
    profiles = get_info_cache_from_local_state()
    if not profiles or not profiles.get("Default", {}).get("gaia_id"):
        return False

    for profile in profiles:
        if profile not in profile_children:
            logger.error(
                "Profile '%s' in Local State does not exist in data-dir folder.",
                profile,
            )
            return False
    return True


def call_the_bot():
    """Initializes the data directory and prompts the user to sign in manually."""
    logger.info("Opening Edge to create/update user data directory...")
    driver = None
    try:
        driver = webdriver.Edge(options=build_options(PROFILE_NAME))
        driver.get("https://rewards.bing.com/dashboard")
        print("\nPlease sign in to your Microsoft Edge browser if you haven't already.")
        input("Press Enter to continue after signing in...")
    except Exception as exc:
        logger.error("Failed during manual sign-in initialization: %s", exc)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def ensure_data_dir_ready():
    """Ensures data-dir exists and Local State is valid before entering the menu."""
    while True:
        if not os.path.exists(USER_DATA_DIR):
            logger.warning("data-dir folder missing. Launching initial setup...")
            call_the_bot()
            continue

        children = os.listdir(USER_DATA_DIR)
        profile_children = [c for c in children if re.search(r"Default|Profile", c)]

        if not is_local_state_updated(profile_children):
            logger.warning("Local State is not updated. Launching Edge for sign-in...")
            call_the_bot()
        else:
            logger.info("data-dir and Local State are verified and ready.")
            break


class ProfileTask(NamedTuple):
    profile_name: str
    gaia_name: str
    user_name: str
    IsDoneInThisCurrentSession: bool


def run_profile(task: ProfileTask) -> bool:
    """Safely runs automation tasks for a selected profile with full cleanup."""
    driver = None
    try:
        driver = webdriver.Edge(options=build_options(task.profile_name))
    except SessionNotCreatedException as exc:
        logger.error("[FAIL] %s: Could not start Edge.", task.profile_name)
        logger.error(
            "       The profile might already be open in another Edge window."
        )
        logger.error("       Driver output: %s", log_utils.exception_summary(exc))
        return False
    except Exception as exc:
        logger.error("[FAIL] %s: %s", task.profile_name, log_utils.exception_summary(exc))
        return False

    try:
        mouse = mouse_trajectory.MouseUtils(driver)
        keyboard = mimic_typing.KeyboardUtils(driver)
        rewards = rewards_tasks.RewardsTaskUtils(driver)
        rewards.complete_all_tasks()
        return True
    except Exception as exc:
        logger.error(
            "[FAIL] %s: Task execution failed: %s",
            task.profile_name,
            log_utils.exception_summary(exc),
        )
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as exc:
                logger.warning(
                    "%s: Driver did not shut down cleanly: %s",
                    task.profile_name,
                    log_utils.exception_summary(exc),
                )


def main() -> int:
    log_utils.setup_logging()
    ensure_data_dir_ready()

    profiles = get_info_cache_from_local_state()
    print(json.dumps(profiles, indent=4))

    profile_tasks = [
        ProfileTask(
            profile_name=prof,
            gaia_name=data.get("gaia_name", ""),
            user_name=data.get("user_name", ""),
            IsDoneInThisCurrentSession=False,
        )
        for prof, data in profiles.items()
    ]

    if not profile_tasks:
        logger.error("No valid profiles detected.")
        return 1

    is_all_tasks_done = False
    while not is_all_tasks_done:
        print("\nPlease choose a profile to run the script for:")
        for i, task in enumerate(profile_tasks):
            status = "✅" if task.IsDoneInThisCurrentSession else "❌"
            print(
                f"({i}) [{task.profile_name}] | Profile Name: {task.gaia_name} | "
                f"User Name: {task.user_name} | Done?: {status}"
            )

        input_number = input("Input_Number (No Symbols, No Letters): ").strip()
        if re.match(r"^\d+$", input_number):
            idx = int(input_number)
            if 0 <= idx < len(profile_tasks):
                selected_task = profile_tasks[idx]
                logger.info("Executing profile: %s", selected_task.profile_name)

                success = run_profile(selected_task)
                if success:
                    profile_tasks[idx] = selected_task._replace(
                        IsDoneInThisCurrentSession=True
                    )

                if not REWARDS_HEADLESS:
                    input("Press Enter to return to menu...")
            else:
                print(f"Out of range. Pick between 0 and {len(profile_tasks) - 1}.")
        else:
            print("Invalid input. NUMBERS ONLY.")

        is_all_tasks_done = all(t.IsDoneInThisCurrentSession for t in profile_tasks)

    logger.info("All profile tasks completed for this session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())