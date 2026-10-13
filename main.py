try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ModuleNotFoundError as exc:
    if exc.name != "selenium":
        raise
    webdriver = None  # Batch previews do not need browser dependencies.
import time
import os
import json
import argparse
from claim_batches import MAX_SERVICES_PER_BATCH, prepare_claim_batches

# First, you'll need to install selenium:
# pip install selenium



# Load form data from JSON file
def load_form_data(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Helper to handle debug stepping
def debug_checkpoint(enabled, message):
    if not enabled:
        return

    command = input(
        f"\n[STEP] {message}\n"
        "Press Enter to continue, or type q to quit: "
    ).strip().lower()

    if command in {"q", "quit"}:
        raise KeyboardInterrupt("Debug session stopped by user")
    
def fill_form_1(driver, data):
    """
    Fill the form with provided data
    
    Args:
        driver: Selenium WebDriver instance
        data: Dictionary containing form field values
    """
    # Wait for forms to be present and fill them
    # Member ID
    member_id = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "QR~QID17"))
    )
    member_id.send_keys(data.get('member_id', ''))
    
    # First Name
    first_name = driver.find_element(By.ID, "QR~QID22~4")
    first_name.send_keys(data.get('first_name', ''))
    
    # Middle Initial
    middle_initial = driver.find_element(By.ID, "QR~QID22~5")
    middle_initial.send_keys(data.get('middle_initial', ''))
    
    # Last Name
    last_name = driver.find_element(By.ID, "QR~QID22~6")
    last_name.send_keys(data.get('last_name', ''))
    
    # Date of Birth
    dob = driver.find_element(By.ID, "QR~QID16")
    dob.send_keys(data.get('dob', ''))
    
    # Group Number
    group_number = driver.find_element(By.ID, "QR~QID51")
    group_number.send_keys(data.get('group_number', ''))
    
    # Employer Name
    employer = driver.find_element(By.ID, "QR~QID54")
    employer.send_keys(data.get('employer', ''))

    def click_dependent_button(driver):
        """
        Clicks the 'Dependent' radio button
        
        Args:
            driver: Selenium WebDriver instance
        """
        # Wait for the element to be present and clickable
        dependent_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "QR~QID2~3"))
        )
        
        # Try using JavaScript to click the element
        driver.execute_script("arguments[0].click();", dependent_button)
        time.sleep(1)  # Give it a moment to register the click

    click_dependent_button(driver)

def fill_form_2(driver, form_data):
    """
    Fills out the Surest claim form using the correct element IDs
    """
    # Wait for form to be loaded
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "QuestionBody"))
    )

    try:
        # Define field mappings with correct IDs
        fields = {
            # Name fields
            "first_name": "QR~QID1~4",
            "middle_initial": "QR~QID1~5",
            "last_name": "QR~QID1~6",
            
            # Member Info
            "member_id": "QR~QID8",
            "date_of_birth": "QR~QID9",
            
            # Address fields
            "street_address": "QR~QID53~4",
            "city": "QR~QID53~5",
            "state": "QR~QID53~6",
            "zip_code": "QR~QID53~7"
        }

        # Fill out each field
        for field_name, element_id in fields.items():
            if field_name in form_data:
                try:
                    field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, element_id))
                    )
                    field.clear()
                    field.send_keys(form_data[field_name])
                    print(f"Successfully filled {field_name}")
                except Exception as e:
                    print(f"Error filling {field_name}: {str(e)}")

    except Exception as e:
        print(f"General error in form filling: {str(e)}")

def click_next_button(driver):
    """
    Clicks the 'Next' button on the form
    
    Args:
        driver: Selenium WebDriver instance
    """
    next_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "NextButton"))
    )
    next_button.click()

def fill_form_3(driver, data):
    """
    Fills out the foreign services form (3rd page)
    
    Args:
        driver: Selenium WebDriver instance
        data: Dictionary containing:
            - is_foreign: boolean, whether service was in foreign country
    """
    try:
        # Wait for radio buttons to be present
        if data.get('is_foreign', False):
            button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "QR~QID55~1"))
            )
        else:
            button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "QR~QID55~2"))
            )
        
        # Use JavaScript to click the button
        driver.execute_script("arguments[0].click();", button)
        time.sleep(1)  # Give it a moment to register the click
            
        print("Successfully filled form 3")
    except Exception as e:
        print(f"Error filling form 3: {str(e)}")

def fill_form_4(driver, data):
    """
    Fills out the service type and location form (4th page)
    
    Args:
        driver: Selenium WebDriver instance
        data: Dictionary containing:
            - service_type: string matching one of the dropdown options
            - place_of_service: string matching one of the dropdown options
    """
    try:
        # Wait for dropdowns to be present
        service_type_select = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "QR~QID66"))
        )
        place_of_service_select = driver.find_element(By.ID, "QR~QID67")
        
        # Create Select objects for the dropdowns
        from selenium.webdriver.support.ui import Select
        service_select = Select(service_type_select)
        place_select = Select(place_of_service_select)
        
        # Select the options
        if data.get('service_type'):
            service_select.select_by_visible_text(data['service_type'])
        if data.get('place_of_service'):
            place_select.select_by_visible_text(data['place_of_service'])
            
        print("Successfully filled form 4")
    except Exception as e:
        print(f"Error filling form 4: {str(e)}")

def fill_form_5(driver, data):
    """
    Fills out the provider information form (5th page)
    
    Args:
        driver: Selenium WebDriver instance
        data: Dictionary containing:
            - provider_name: string
            - provider_npi: string
            - provider_facility: string
            - provider_tin: string (9 digits, default 777777777)
            - provider_address: string
            - provider_city: string
            - provider_state: string (2-letter state code)
            - provider_zip: string
    """
    try:
        # Wait for form to be loaded
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "QuestionBody"))
        )

        # Define field mappings with correct IDs
        fields = {
            "provider_name": "QR~QID71~1",
            "provider_npi": "QR~QID71~2",
            "provider_facility": "QR~QID71~3",
            "provider_tin": "QR~QID71~4",
            "provider_address": "QR~QID71~5",
            "provider_city": "QR~QID71~6",
            "provider_state": "QR~QID71~7",
            "provider_zip": "QR~QID71~8"
        }

        # Fill out each field
        for field_name, element_id in fields.items():
            if field_name in data:
                try:
                    field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, element_id))
                    )
                    field.clear()
                    field.send_keys(data[field_name])
                    print(f"Successfully filled {field_name}")
                except Exception as e:
                    print(f"Error filling {field_name}: {str(e)}")

    except Exception as e:
        print(f"General error in form filling: {str(e)}")

def discover_service_fields(driver):
    """Find a complete visible service row by its headers, without guessing IDs."""
    required = {"date_of_service", "procedure_code", "diagnosis_code", "charges"}
    matches = []
    for table in driver.find_elements(By.CSS_SELECTOR, "table"):
        if not table.is_displayed():
            continue
        columns = {}
        for row in table.find_elements(By.CSS_SELECTOR, "thead tr"):
            column = 0
            for cell in row.find_elements(By.XPATH, "./th | ./td"):
                label = " ".join(cell.text.lower().split())
                if "date of service" in label:
                    columns["date_of_service"] = column
                elif "procedure" in label and "code" in label:
                    columns["procedure_code"] = column
                elif "diagnosis" in label and "code" in label:
                    columns["diagnosis_code"] = column
                elif label == "charges":
                    columns["charges"] = column
                column += int(cell.get_attribute("colspan") or 1)
        if set(columns) != required:
            continue
        for row in table.find_elements(By.CSS_SELECTOR, "tbody tr"):
            fields = {}
            column = 0
            for cell in row.find_elements(By.XPATH, "./th | ./td"):
                width = int(cell.get_attribute("colspan") or 1)
                for name, position in columns.items():
                    if column <= position < column + width:
                        inputs = [field for field in cell.find_elements(
                            By.CSS_SELECTOR, "input:not([type='hidden']), textarea"
                        ) if field.is_displayed() and field.is_enabled()]
                        if len(inputs) == 1:
                            fields[name] = inputs[0]
                column += width
            if set(fields) == required:
                matches.append(fields)
    return matches[0] if len(matches) == 1 else False


def fill_form_6(driver, data, index=0, has_more_services=False):
    """
    Fills out the services and charges form, handling multiple instances
    
    Args:
        driver: Selenium WebDriver instance
        data: Dictionary containing service info
        index: Integer (0 for first form, 1 for second, etc.)
        has_more_services: Whether another service remains in the current batch
    """
    # List of form QIDs and their corresponding "add another" QIDs
    FORM_IDS = [
        {"form": "QID25", "add_another": "QID69"},  # First form
        {"form": "QID68", "add_another": "QID74"},  # Second form
        {"form": "QID75", "add_another": "QID76"},  # Third form
        {"form": "QID77", "add_another": "QID78"},  # Fourth form
        {"form": "QID79", "add_another": "QID80"},  # Fifth form
        {"form": "QID81", "add_another": "QID82"},  # Sixth form
        {"form": "QID83", "add_another": "QID84"},  # Seventh form
        {"form": "QID85", "add_another": "QID86"},  # Eighth form
    ]

    if not 0 <= index < MAX_SERVICES_PER_BATCH:
        raise ValueError(f"No service entry supported for index {index}")

    try:
        # Get the correct IDs for this form index
        if index < len(FORM_IDS):
            form_qid = FORM_IDS[index]["form"]
            add_another_qid = FORM_IDS[index]["add_another"]
            fields = {
                "date_of_service": f"QR~{form_qid}#4~1~1~TEXT",
                "procedure_code": f"QR~{form_qid}#1~1~1~TEXT",
                "diagnosis_code": f"QR~{form_qid}#3~1~1~TEXT",
                "charges": f"QR~{form_qid}#2~1~1~TEXT"
            }
            discovered_fields = None
        else:
            discovered_fields = WebDriverWait(driver, 10).until(discover_service_fields)
            fields = dict.fromkeys(("date_of_service", "procedure_code", "diagnosis_code", "charges"))
            add_another_qid = None

        # Fill out each field
        date_field = None
        for field_name, element_id in fields.items():
            if field_name in data:
                try:
                    field = discovered_fields[field_name] if discovered_fields else WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, element_id))
                    )
                    driver.execute_script("arguments[0].scrollIntoView(true);", field)
                    field.clear()
                    field.send_keys(data[field_name])
                    WebDriverWait(driver, 10).until(
                        lambda browser: field.get_attribute("value") == str(data[field_name])
                    )
                    if field_name == "date_of_service":
                        date_field = field
                    print(f"Successfully filled {field_name}")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Error filling {field_name}: {str(e)}")
                    raise

        # Handle "Do you have another service to add?" radio buttons
        try:
            if add_another_qid is None:
                # At the limit the page may omit this question altogether.
                buttons = driver.find_elements(
                    By.XPATH,
                    "//div[contains(@class, 'QuestionOuter')]"
                    "[.//*[contains(@class, 'QuestionText') and "
                    "contains(., 'Do you have another service to add?')]]"
                    f"//input[@type='radio' and @value='{1 if has_more_services else 2}']"
                )
                if not buttons and not has_more_services:
                    return date_field
                if len(buttons) != 1:
                    raise ValueError("Could not identify the ninth service's add-another question.")
                button = buttons[0]
            else:
                button_id = f"QR~{add_another_qid}~{1 if has_more_services else 2}"
                button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, button_id))
                )
            driver.execute_script("arguments[0].click();", button)
            print("Successfully selected add_another option")
        except Exception as e:
            print(f"Error selecting add_another option: {str(e)}")
            raise

        return date_field

    except Exception as e:
        print(f"General error in form filling: {str(e)}")
        raise

def fill_form_7(driver, data):
    """
    Fills out the charges summary form (7th page)
    
    Args:
        driver: Selenium WebDriver instance
        data: Dictionary containing:
            - total_charge: string (dollar amount)
            - amount_paid: string (dollar amount)
    """
    try:
        # Wait for form to be loaded
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "QuestionBody"))
        )

        # Define field mappings
        fields = {
            "total_charge": "QR~QID48~1",
            "amount_paid": "QR~QID48~2"
        }

        # Fill out each field
        for field_name, element_id in fields.items():
            if field_name in data:
                try:
                    field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, element_id))
                    )
                    field.clear()
                    field.send_keys(data[field_name])
                    print(f"Successfully filled {field_name}")
                except Exception as e:
                    print(f"Error filling {field_name}: {str(e)}")

    except Exception as e:
        print(f"General error in form filling: {str(e)}")

def fill_form_11(driver, pdf_path):
    """
    Uploads a PDF file to the form
    
    Args:
        driver: Selenium WebDriver instance
        pdf_path: String path to the PDF file to upload
    """
    try:
        # Wait for the upload input element to be present
        # The file input is typically hidden, so we need to find it and send_keys to it
        file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        
        # Convert the path to absolute path
        absolute_path = os.path.abspath(pdf_path)
        
        # Send the file path to the input element
        file_input.send_keys(absolute_path)
        
        # Wait for upload to complete (look for the filename display or success message)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "FileUploadName"))
        )
        
        print(f"Successfully uploaded PDF: {pdf_path}")
        
    except Exception as e:
        print(f"Error uploading PDF: {str(e)}")
        raise

def click_download_pdf(driver):
    """
    Clicks the download PDF button at the end of the form
    
    Args:
        driver: Selenium WebDriver instance
    """
    try:
        # Wait for the download button to be present and clickable
        download_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "DownloadResponsesPDF"))
        )
        
        # Scroll the button into view
        driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
        
        # Click the button
        download_button.click()
        
        print("Successfully clicked download PDF button")
        
    except Exception as e:
        print(f"Error clicking download PDF button: {str(e)}")

def submission_confirmed(driver):
    texts = [driver.find_element(By.TAG_NAME, "body").text]
    for element in driver.find_elements(By.CSS_SELECTOR, "#EndOfSurvey, .EndOfSurvey"):
        if element.is_displayed() and element.text.strip():
            texts.append(element.text)
    text = " ".join(" ".join(texts).lower().split())
    return any(message in text for message in (
        "your response has been recorded", "your response has been submitted",
        "your claim has been submitted", "your claim was submitted",
        "your claim has been received", "your claim has been successfully submitted",
        "your submission has been received", "thank you for submitting",
        "thank you for completing", "thank you for your submission",
    ))


def wait_for_submission(driver):
    """Do not leave a claim until the website reports that it was submitted."""
    WebDriverWait(driver, 30).until(submission_confirmed)


def claim_finish_state(driver):
    # A confirmation page may still have a Download PDF button. Check it first.
    if submission_confirmed(driver):
        return "submitted", None
    reviews = driver.find_elements(By.CLASS_NAME, "DownloadResponsesPDF")
    if not any(element.is_displayed() for element in reviews):
        return False
    buttons = driver.find_elements(
        By.CSS_SELECTOR,
        "#NextButton, #SubmitButton, #submitButton, input[type='submit'], button[type='submit']"
    )
    if not buttons:
        buttons = driver.find_elements(
            By.XPATH,
            "//*[self::button or self::input or self::a]"
            "[translate(normalize-space(string(.)), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz') = 'submit' or "
            "translate(normalize-space(string(.)), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz') = 'submit claim' or "
            "translate(normalize-space(string(.)), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz') = 'finish' or @value='Submit' or @value='Finish']"
        )
    ready = [button for button in buttons if button.is_displayed() and button.is_enabled()]
    return ("review", ready[0]) if len(ready) == 1 else False


def finish_claim(driver, step_mode=False):
    try:
        state = WebDriverWait(driver, 30).until(claim_finish_state)
    except Exception as exc:
        raise RuntimeError("No submission confirmation or available submit button was found after the PDF upload. "
                           "Inspect this claim before restarting.") from exc
    if state[0] == "submitted":
        return
    debug_checkpoint(step_mode, "Review the completed claim. Continuing will submit this batch.")
    # In step mode the user may have submitted it manually during the pause.
    state = WebDriverWait(driver, 30).until(claim_finish_state)
    if state[0] == "submitted":
        return
    state[1].click()
    try:
        wait_for_submission(driver)
    except Exception as exc:
        raise RuntimeError("The submit button was clicked, but submission could not be confirmed. "
                           "Check the claim status before restarting this batch.") from exc


def fill_claim(driver, form_data, step_mode=False):
    # Click Next button first to get to the form
    click_next_button(driver)

    fill_form_1(driver, form_data["form_1"])
    debug_checkpoint(step_mode, "Subscriber information filled. Review the page.")
    click_next_button(driver)

    fill_form_2(driver, form_data["form_2"])
    debug_checkpoint(step_mode, "Patient information filled. Review the page.")
    click_next_button(driver)

    fill_form_3(driver, form_data["form_3"])
    debug_checkpoint(step_mode, "Foreign-service selection completed.")
    click_next_button(driver)

    fill_form_4(driver, form_data["form_4"])
    debug_checkpoint(step_mode, "Service type and location form completed.")
    click_next_button(driver)

    fill_form_5(driver, form_data["form_5"])
    debug_checkpoint(step_mode, "Provider information filled. Review the page.")
    click_next_button(driver)

    services = form_data["form_6_entries"]
    for index, entry in enumerate(services):
        date_field = fill_form_6(driver, entry, index, has_more_services=index < len(services) - 1)
        debug_checkpoint(step_mode, f"Service entry {index + 1} of {len(services)} filled. Review the page.")
        click_next_button(driver)
        if date_field is not None:
            WebDriverWait(driver, 10).until(EC.staleness_of(date_field))

    fill_form_7(driver, form_data["form_7"])
    debug_checkpoint(step_mode, "Charges summary form filled. Review the page.")
    click_next_button(driver)

    fill_form_11(driver, form_data["form_11"]["pdf_path"])
    debug_checkpoint(step_mode, "PDF file selected. Review the attachment.")
    click_next_button(driver)

    # Some flows require review submission; others have already submitted here.
    finish_claim(driver, step_mode=step_mode)


def click_button_on_website(form_data, step_mode=False, start_batch=1, single_batch=False):
    batches = [form_data] if isinstance(form_data, dict) else form_data
    if not 1 <= start_batch <= len(batches):
        raise ValueError(f"start_batch must be between 1 and {len(batches)}.")
    if webdriver is None:
        raise RuntimeError("Install Selenium before filling forms: pip install selenium")
    # Set up the LibreWolf (Firefox) driver
    librewolf_path = os.environ.get(
        "LIBREWOLF_BINARY",
        r"C:\Program Files\LibreWolf\librewolf.exe"
    )

    if not os.path.isfile(librewolf_path):
        raise FileNotFoundError(
            f"LibreWolf was not found at: {librewolf_path}\n"
            "Set LIBREWOLF_BINARY to the location of librewolf.exe."
        )

    options = webdriver.FirefoxOptions()
    options.binary_location = librewolf_path

    # Uncomment to run without showing the browser:
    # options.add_argument("-headless")

    # Selenium Manager obtains and starts GeckoDriver automatically.
    driver = webdriver.Firefox(options=options)
    
    current_batch = start_batch
    completed = []
    try:
        stop = start_batch if single_batch else len(batches)
        for current_batch in range(start_batch, stop + 1):
            batch = batches[current_batch - 1]
            dates = list(dict.fromkeys(entry["date_of_service"] for entry in batch["form_6_entries"]))
            print(f"Starting batch {current_batch}/{len(batches)}: {', '.join(dates)} "
                  f"({len(batch['form_6_entries'])} services).")
            # The form's own reset link uses this URL. Start a fresh claim in this tab.
            driver.get("https://survey.surest.com/jfe/form/SV_3VIAsFFJdsZZbDL")
            fill_claim(driver, batch, step_mode=step_mode)
            completed.append(current_batch)
            print(f"Submission confirmed for batch {current_batch}/{len(batches)}.")
        print(f"Finished submitting {len(completed)} batch(es).")
        debug_checkpoint(step_mode, "All selected batches submitted. Continuing closes the browser.")
    except Exception as exc:
        reason = str(exc).split("Stacktrace:", 1)[0].strip() or type(exc).__name__
        print(f"Reason: {reason}")
        print(f"Stopped at batch {current_batch}. Confirmed batches in this run: {completed or 'none'}.")
        print("Check whether this claim was submitted before restarting with --batch. "
              "No further batches will be started.")
        input("Review the browser. Press Enter to close it...")
        raise
    finally:
        # Close the browser
        driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fill the Surest claim form."
    )
    parser.add_argument(
        "--step",
        action="store_true",
        help="Pause for confirmation before advancing each page."
    )
    parser.add_argument("--data", default="form_data.json", help="Path to the JSON configuration.")
    parser.add_argument("--batch", type=int, default=1, help="First batch to submit; continues through all remaining batches.")
    parser.add_argument("--single-batch", action="store_true", help="Submit only the batch selected by --batch.")
    parser.add_argument("--preview", action="store_true", help="Show batch dates and totals without opening a browser.")
    args = parser.parse_args()

    try:
        batches = prepare_claim_batches(load_form_data(args.data))
        if not 1 <= args.batch <= len(batches):
            raise ValueError(f"--batch must be between 1 and {len(batches)}.")
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    for number, batch in enumerate(batches, start=1):
        dates = list(dict.fromkeys(entry["date_of_service"] for entry in batch["form_6_entries"]))
        print(f"Batch {number}/{len(batches)}: {', '.join(dates)} | "
              f"{len(batch['form_6_entries'])} services | "
              f"total ${batch['form_7']['total_charge']} | paid ${batch['form_7']['amount_paid']}")
    if not args.preview:
        if webdriver is None:
            parser.error("Install Selenium before filling forms: pip install selenium")
        try:
            click_button_on_website(batches, step_mode=args.step, start_batch=args.batch,
                                   single_batch=args.single_batch)
        except KeyboardInterrupt:
            parser.exit(130, "Run stopped by user.\n")
        except Exception as exc:
            reason = str(exc).split("Stacktrace:", 1)[0].strip() or type(exc).__name__
            parser.exit(1, f"Run stopped: {reason}\n")
