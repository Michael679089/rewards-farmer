import rewards_tasks
import mouse_trajectory
import mimic_typing
from selenium import webdriver
from constants import USER_DATA_DIR, PROFILE_NAME
from typing import NamedTuple
import json


def getNoBotDetectedEdgeDriverDefault(): # To run the Edge Browser without bot detection.
    options = webdriver.EdgeOptions() # this prevents bot detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--profile-directory={PROFILE_NAME}")
    driver = webdriver.Edge(options=options)
    return driver

def getNoBotDetectedEdgeDriverWithProfile(profile_name): # To run the Edge Browser without bot detection.
    options = webdriver.EdgeOptions() # this prevents bot detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--profile-directory={profile_name}")
    driver = webdriver.Edge(options=options)
    return driver


def getInfoCacheFromLocalState():
    fd = os.open(USER_DATA_DIR + "/Local State", os.O_RDONLY)
    rd = os.read(fd, os.path.getsize(USER_DATA_DIR + "/Local State"))
    os.close(fd)
    rd_as_json = json.loads(rd.decode("utf-8"))
    profiles = rd_as_json["profile"]["info_cache"]
    return profiles

def isLocalStateUpdated(profile_children):
    profiles = getInfoCacheFromLocalState()
    # check first if gaia_id is not blank
    try:
        if profiles["Default"]["gaia_id"] == "":
            return False
    except KeyError:
        return False

    # next, compare against profile_children
    keyExist = False
    for x in profiles:
        if x in profile_children:
            keyExist = True
        else:
            raise Exception(x + " Profile in Local State does not exist physically in data-dir folder. Please delete data-dir and run the script again!")
            return False
    return keyExist
    

        
    



    



# LOOP-GATE: We need to check if datadir exists + and local state exists and updated.
import os
import re
does_data_dir_exist = False
is_local_state_updated = False  # Changed name here
profile_children = []
while (does_data_dir_exist == False or is_local_state_updated == False):
    def callTheBot():
        driver = getNoBotDetectedEdgeDriverDefault() 
        driver.get("https://rewards.bing.com/dashboard") # this will create a data-dir folder if it doesn't exist
        print("Waiting for 10 seconds to let the browser create the data-dir folder...")
        print("Please sign in to your Microsoft Edge browser if you haven't already.")
        input("Press Enter to continue...")
        driver.quit()

    try:
        os.listdir(USER_DATA_DIR)
        does_data_dir_exist = True
        print("data-dir folder exists.")
    except FileNotFoundError:
        does_data_dir_exist = False
        # then create one.
        callTheBot()

    if (does_data_dir_exist == True):
        # then we look for folders that have "DEFAULT" or "PROFILE" in its name.
        children = os.listdir(USER_DATA_DIR)
        onlydefaultorprofileregex="Default|Profile"
        profile_children = [child for child in children if re.search(onlydefaultorprofileregex, child)]

        is_local_state_updated = isLocalStateUpdated(profile_children)
        if is_local_state_updated == False:
            print("Local State is not updated. Please sign in to your Microsoft Edge browser and run the script again.")
            callTheBot()
        else:
            print("Local State is updated.")

print("All set! Proceeding to open the browser...")
class ProfileTask(NamedTuple):
    profile_name: str
    gaia_name: str
    user_name: str
    IsDoneInThisCurrentSession: bool
profile_tasks=[]
profiles = getInfoCacheFromLocalState()
# print profiles as json indents
print(json.dumps(profiles, indent=4))
for profile in profiles:
    gaia_name = profiles[profile]["gaia_name"]
    user_name = profiles[profile]["user_name"]
    profile_tasks.append(ProfileTask(profile, gaia_name, user_name, False))
if len(profile_tasks) > 0:
    print("we got some tasks to do!")
    is_all_tasks_done = False
    while not is_all_tasks_done:
        print("Please choose a profile to run the script for:")
        for i, profile_task in enumerate(profile_tasks):
            print(f"({i + 1}) [{profile_task.profile_name}] | Profile Name: {profile_task.gaia_name} | User Name: {profile_task.user_name} | IsDoneInThisCurrentSession?: {profile_task.IsDoneInThisCurrentSession and '✅' or '❌'}")
        input_number = input("Input_Number (No Symbols, No Letters):")
        isInputNumberValid = re.match(r"^(\d+(,\d+)*)?$", input_number)
        if isInputNumberValid:
            if (input_number == ""):
                print("Please select something")
            else:
                input_number_as_int = int(input_number) - 1
                print("Choosing: ", input_number_as_int + 1)
                print(">", profile_tasks[input_number_as_int])
                try:
                    driver = getNoBotDetectedEdgeDriverWithProfile(profile_tasks[input_number_as_int].profile_name)
                    mouse = mouse_trajectory.MouseUtils(driver)
                    keyboard = mimic_typing.KeyboardUtils(driver)
                    rewards = rewards_tasks.RewardsTaskUtils(driver)
                    rewards.complete_all_tasks()
                    input("Press Enter to exit...")
                    driver.quit()
                    profile_tasks[input_number_as_int] = profile_tasks[input_number_as_int]._replace(is_done=True)
                except Exception as e:
                    print("Error: ", e)
                    print("Please make sure you have Microsoft Edge installed and the profile exists.")
        else:
            print("Invalid input. NUMBERS ONLY")
        is_all_tasks_done = all(task.is_done for task in profile_tasks)
    print("Task completed for all selected profiles.")
else:
    print('its like nothing was added')