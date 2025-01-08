from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
import time
import random
import logging

# Set up logging to file
logging.basicConfig(filename='booking_errors.log', level=logging.INFO)

# Random delay function
def random_delay(min_delay=1, max_delay=3):
    time.sleep(random.uniform(min_delay, max_delay))

# Logging function for errors
def log_error(message):
    logging.info(f"{datetime.now()}: {message}")
    print(message)

# Function to load emails from a text file
def load_emails(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        emails = file.read().splitlines()
    return emails

# Function to click element with retries
def safe_click(driver, xpath, max_retries=3):
    attempt = 0
    while attempt < max_retries:
        try:
            element = WebDriverWait(driver, 60).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            driver.execute_script("arguments[0].scrollIntoView();", element)
            element.click()
            return True
        except (ElementClickInterceptedException, TimeoutException, NoSuchElementException) as e:
            log_error(f"Click attempt {attempt + 1} failed: {str(e)}")
            attempt += 1
            random_delay(1, 2)
    log_error(f"Failed to click on element: {xpath}")
    return False

# Function to send keys with retries
def safe_send_keys(driver, xpath, keys, max_retries=3):
    attempt = 0
    while attempt < max_retries:
        try:
            field = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            driver.execute_script("arguments[0].scrollIntoView();", field)
            field.clear()
            field.send_keys(keys)
            return True
        except (NoSuchElementException, TimeoutException) as e:
            log_error(f"Error sending keys to {xpath}, attempt {attempt + 1}: {e}")
            attempt += 1
            random_delay(1, 2)
    log_error(f"Failed to send keys to element: {xpath}")
    return False

# Function to prepare booking and pause before the final click
def prepare_booking_for_debug(email, retry_attempts=3, timeout_duration=120):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("user-agent=Mozilla/5.0")
    chrome_options.add_argument("--start-maximized")

    attempt = 0

    while attempt < retry_attempts:
        attempt += 1
        driver = webdriver.Chrome(options=chrome_options)
        try:
            driver.get('https://egy.almaviva-visa.it/appointment')

            start_time = time.time()  # Track the time at the start of the process

            # Log in
            if not safe_send_keys(driver, '//*[@id="username"]', email):
                raise TimeoutException("Failed to log in")

            if not safe_send_keys(driver, '//*[@id="password"]', "Amr2060$"):
                raise TimeoutException("Failed to send password")

            driver.find_element(By.ID, 'password').send_keys("\n")

            # Check if timeout has occurred and refresh the page if it has
            if time.time() - start_time > timeout_duration:
                log_error(f"Timeout exceeded {timeout_duration} seconds for {email}. Refreshing the page and retrying.")
                driver.refresh()
                continue  # Retry from the start

            # Wait for the booking page to load
            if not safe_click(driver, '/html/body/app-root/div/app-homepage/app-base-info-page/div[2]/div[1]/div[3]/a'):
                raise TimeoutException("Failed to load booking page")

            # Select booking options
            if not safe_click(driver, '//*[@id="mat-select-0"]') or not safe_click(driver, '//mat-option//span[contains(text(), "Cairo")]'):
                raise TimeoutException("Failed to select center")

            if not safe_click(driver, '//*[@id="mat-select-4"]') or not safe_click(driver, '//mat-option//span[contains(text(), "Standard - EGP 1750")]'):
                raise TimeoutException("Failed to select service level")

            if not safe_click(driver, '//*[@id="mat-select-2"]') or not safe_click(driver, '//mat-option//span[contains(text(), "Employment Visa (D)")]'):
                raise TimeoutException("Failed to select visa type")

            # Skip automatic date setting for now
            if not safe_send_keys(driver, '//*[@id="cdk-step-content-0-0"]/app-memebers-number/form/div/div[7]/div/input', "Milano"):
                raise TimeoutException("Failed to set destination")

            # JavaScript to click checkboxes
            checkbox1 = driver.find_element(By.XPATH, '//*[@id="mat-mdc-checkbox-1-input"]')
            checkbox2 = driver.find_element(By.XPATH, '//*[@id="mat-mdc-checkbox-2-input"]')
            js_click(driver, checkbox1)
            js_click(driver, checkbox2)

            # If everything is successful
            print(f"Booking setup completed for {email}. The window is now open and ready.")
            return driver

        except TimeoutException as e:
            log_error(f"TimeoutException for {email} (Attempt {attempt}/{retry_attempts}): {e}")
            driver.quit()

    log_error(f"Failed to complete booking setup for {email} after {retry_attempts} attempts.")
    return None


# JavaScript-based checkbox clicker for element interception
def js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)

# Function to synchronize all sessions to click at the exact target time
def synchronized_click(drivers, click_xpath, target_time):
    print(f"Waiting for synchronized click at {target_time.strftime('%H:%M:%S:%f')}")
    
    while datetime.now() < target_time:
        time.sleep(0.001)  # Sleep in small increments to avoid missing the target
    
    click_time_log = []  # To store the actual click times for each session
    for driver in drivers:
        try:
            button = driver.find_element(By.XPATH, click_xpath)
            button.click()
            actual_click_time = datetime.now()
            click_time_log.append(f"Clicked at: {actual_click_time.strftime('%H:%M:%S:%f')}")
        except Exception as e:
            click_time_log.append(f"Click failed: {str(e)}")
    
    return click_time_log

# Function to calculate the best time for next attempt
def recommend_next_click_time(click_logs, appointments_speed=2.0):
    times = [datetime.strptime(log.split("Clicked at: ")[1], '%H:%M:%S:%f') for log in click_logs if "Clicked at:" in log]
    if not times:
        print("No successful clicks were logged.")
        return None
    
    average_time = sum([t.microsecond for t in times]) / len(times)
    next_target = times[0] + timedelta(seconds=appointments_speed, microseconds=average_time)
    
    print(f"Recommended next click time: {next_target.strftime('%H:%M:%S:%f')}")
    return next_target

# Main function to handle multiple setups
def main():
    emails = load_emails(r'D:\WOrk\Eslam bot\Clients\1\محمود شواده.txt')
    click_xpath = '//*[@id="cdk-step-content-0-0"]/app-memebers-number/div[2]/div/button'

    drivers = []
    failed_emails = []

    for email in emails:
        driver_instance = prepare_booking_for_debug(email)
        if driver_instance:
            drivers.append(driver_instance)
        else:
            failed_emails.append(email)

    # Retry failed emails
    if failed_emails:
        print("Retrying failed emails...")
        for email in failed_emails[:]:
            driver_instance = prepare_booking_for_debug(email)
            if driver_instance:
                drivers.append(driver_instance)
                failed_emails.remove(email)

    # Set the target time for the synchronized click to exactly 9:00:00
    target_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    # Wait for 9:00:00 and perform the synchronized clicks
    click_logs = synchronized_click(drivers, click_xpath, target_time)

    print("Click logs:")
    for log in click_logs:
        print(log)

    recommend_next_click_time(click_logs)

    input("Press Enter to close all browsers and exit...")
    for driver in drivers:
        driver.quit()

if __name__ == "__main__":
    main()
