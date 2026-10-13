from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from claim_batches import prepare_claim_batches
import main


class ClaimBatchTests(unittest.TestCase):
    def config(self, date_count=15):
        return {
            "service_dates": [f"10/{day:02d}/2026" for day in range(1, date_count + 1)],
            "form_6_entries": [
                {"procedure_code": code, "diagnosis_code": "EXAMPLE", "charges": charge}
                for code, charge in [("A", "100.10"), ("B", "50.20"), ("C", "25.30")]
            ],
            "form_7": {"total_charge": "9999.00", "amount_paid": "0.00"},
            "form_11": {"pdf_path": "Invoice.pdf"},
        }

    def test_month_covers_every_service_once_and_handles_final_date(self):
        data = self.config(16)
        original = deepcopy(data)
        batches = prepare_claim_batches(data)
        self.assertEqual(len(batches), 6)
        self.assertEqual([len(b["form_6_entries"]) for b in batches], [9] * 5 + [3])
        actual = [(e["date_of_service"], e["procedure_code"])
                  for batch in batches for e in batch["form_6_entries"]]
        expected = [(date, service["procedure_code"])
                    for date in data["service_dates"] for service in data["form_6_entries"]]
        self.assertEqual(actual, expected)
        for batch in batches:
            entries = batch["form_6_entries"]
            self.assertTrue(all("add_another" not in entry for entry in entries))
            self.assertEqual(batch["form_11"]["pdf_path"], "Invoice.pdf")
        self.assertEqual(batches[0]["form_7"]["total_charge"], "526.80")
        self.assertEqual(batches[-1]["form_7"]["total_charge"], "175.60")
        self.assertEqual(data, original)
        batches[0]["form_6_entries"][0]["charges"] = "0.00"
        self.assertEqual(batches[1]["form_6_entries"][0]["charges"], "100.10")

    def test_amount_paid_is_per_service_date(self):
        data = self.config(4)
        data["form_7"]["amount_paid"] = "150.00"
        original = deepcopy(data)
        self.assertEqual([b["form_7"]["amount_paid"] for b in prepare_claim_batches(data)],
                         ["450.00", "150.00"])
        self.assertEqual(data, original)

    def test_fully_paid_services_match_batch_charges(self):
        data = self.config()
        data["form_7"]["amount_paid"] = "175.60"
        for batch in prepare_claim_batches(data):
            self.assertEqual(batch["form_7"]["amount_paid"], batch["form_7"]["total_charge"])

    def test_single_date_and_missing_payment(self):
        data = self.config(1)
        data["form_7"]["amount_paid"] = "125.50"
        self.assertEqual(prepare_claim_batches(data)[0]["form_7"]["amount_paid"], "125.50")
        del data["form_7"]["amount_paid"]
        self.assertEqual(prepare_claim_batches(data)[0]["form_7"]["amount_paid"], "0.00")

    def test_batch_payment_overrides(self):
        data = self.config(4)
        data["form_7"]["amount_paid"] = "400.00"
        data["batch_amounts_paid"] = ["300.00", "100.00"]
        self.assertEqual([b["form_7"]["amount_paid"] for b in prepare_claim_batches(data)],
                         ["300.00", "100.00"])
        data["batch_amounts_paid"] = ["400.00"]
        with self.assertRaises(ValueError):
            prepare_claim_batches(data)

    def test_rejects_invalid_per_date_payment(self):
        for value in ("-1.00", "invalid", "NaN", "0.001"):
            with self.subTest(value=value):
                data = self.config(3)
                data["form_7"]["amount_paid"] = value
                with self.assertRaises(ValueError):
                    prepare_claim_batches(data)

    def test_rejects_bad_dates_templates_and_charges(self):
        for change in ("duplicates", "invalid_date", "empty_dates", "too_many_services", "invalid_charge"):
            with self.subTest(change=change):
                data = self.config(2)
                if change == "duplicates":
                    data["service_dates"] = ["10/01/2026", "10/1/2026"]
                elif change == "invalid_date":
                    data["service_dates"][0] = "02/30/2026"
                elif change == "empty_dates":
                    data["service_dates"] = []
                elif change == "too_many_services":
                    data["form_6_entries"].append(deepcopy(data["form_6_entries"][0]))
                else:
                    data["form_6_entries"][0]["charges"] = "NaN"
                with self.assertRaises(ValueError):
                    prepare_claim_batches(data)

    def test_existing_format_remains_available(self):
        data = self.config(1)
        del data["service_dates"]
        data["form_6_entries"] = [
            {**entry, "date_of_service": "10/01/2026"}
            for entry in data["form_6_entries"]
        ]
        batches = prepare_claim_batches(data)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["form_7"], data["form_7"])
        data["form_7"]["amount_paid"] = "150.00"
        self.assertEqual(prepare_claim_batches(data)[0]["form_7"]["amount_paid"], "150.00")
        self.assertTrue(all("add_another" not in entry for entry in batches[0]["form_6_entries"]))

    def test_browser_selection_follows_each_batch_without_json_flags(self):
        # Mock browser calls; verify the actual radio-button choice for every service.
        batches = prepare_claim_batches(self.config(5))
        for batch in batches:
            services = batch["form_6_entries"]
            for index, entry in enumerate(services):
                with self.subTest(date=entry["date_of_service"], index=index):
                    has_more = index < len(services) - 1
                    if index == 8:
                        continue  # Dynamic ninth-entry discovery has dedicated checks below.
                    question_id = ["QID69", "QID74", "QID76", "QID78", "QID80", "QID82", "QID84", "QID86"][index]
                    with patch.object(main, "By", SimpleNamespace(ID="id"), create=True), \
                         patch.object(main, "EC", create=True) as conditions, \
                         patch.object(main, "WebDriverWait", create=True), \
                         patch.object(main.time, "sleep"), patch("builtins.print"):
                        main.fill_form_6(MagicMock(), entry, index, has_more_services=has_more)
                        conditions.presence_of_element_located.assert_called_with(
                            ("id", f"QR~{question_id}~{1 if has_more else 2}")
                        )

    def test_old_json_flags_are_discarded(self):
        data = self.config(3)
        for entry in data["form_6_entries"]:
            entry["add_another"] = False
        for batch in prepare_claim_batches(data):
            self.assertTrue(all("add_another" not in entry for entry in batch["form_6_entries"]))
        del data["service_dates"]
        self.assertTrue(all("add_another" not in entry
                            for entry in prepare_claim_batches(data)[0]["form_6_entries"]))

    def test_fifteen_dates_make_five_claims(self):
        self.assertEqual([len(b["form_6_entries"]) for b in prepare_claim_batches(self.config())],
                         [9] * 5)

    def test_final_two_date_batch_totals_and_payments(self):
        data = self.config(5)
        data["form_7"]["amount_paid"] = "150.00"
        batches = prepare_claim_batches(data)
        self.assertEqual([len(b["form_6_entries"]) for b in batches], [9, 6])
        self.assertEqual([b["form_7"]["total_charge"] for b in batches], ["526.80", "351.20"])
        self.assertEqual([b["form_7"]["amount_paid"] for b in batches], ["450.00", "300.00"])

    def test_explicit_format_accepts_nine_and_rejects_ten(self):
        data = self.config()
        del data["service_dates"]
        data["form_6_entries"] *= 3
        self.assertEqual(len(prepare_claim_batches(data)[0]["form_6_entries"]), 9)
        data["form_6_entries"].append(deepcopy(data["form_6_entries"][0]))
        with self.assertRaises(ValueError):
            prepare_claim_batches(data)

    def test_ninth_service_uses_actual_page_ids(self):
        entry = prepare_claim_batches(self.config(3))[0]["form_6_entries"][8]
        for has_prompt in (True, False):
            with self.subTest(has_prompt=has_prompt):
                driver = MagicMock()
                table, fields = self.service_table()
                button = MagicMock()
                driver.find_elements.side_effect = lambda by, selector: (
                    [table] if selector == "table" else [button] if has_prompt else []
                )
                with patch.object(main, "By", SimpleNamespace(ID="id", CSS_SELECTOR="css", XPATH="xpath"), create=True), \
                     patch.object(main, "WebDriverWait", create=True) as wait, \
                     patch.object(main.time, "sleep"), patch("builtins.print"):
                    wait.return_value.until.side_effect = lambda condition: condition(driver)
                    self.assertIs(main.fill_form_6(driver, entry, 8, has_more_services=False),
                                  fields["date_of_service"])
                    for name, field in fields.items():
                        field.send_keys.assert_called_once_with(entry[name])
                        self.assertEqual(field.get_attribute("value"), entry[name])
                    if has_prompt:
                        driver.execute_script.assert_any_call("arguments[0].click();", button)
                    else:
                        self.assertEqual(driver.execute_script.call_count, 4)

    def service_table(self):
        """A reordered service row with IDs unrelated to the old #1/#2/#3/#4 scheme."""
        headings = [("procedure_code", "Procedure, service or supplies code"),
                    ("charges", "Charges"), ("date_of_service", "Date of service"),
                    ("diagnosis_code", "Diagnosis code")]
        header_cells, body_cells, fields = [], [], {}
        # Include a two-column spacer to exercise colspan-aware header alignment.
        for cells in (header_cells, body_cells):
            spacer = MagicMock()
            spacer.text = ""
            spacer.get_attribute.return_value = "2"
            spacer.find_elements.return_value = []
            cells.append(spacer)
        for name, label in headings:
            header = MagicMock()
            header.text = label
            header.get_attribute.return_value = "1"
            header_cells.append(header)
            field = MagicMock()
            state = {"value": "", "id": f"unrelated_{name}"}
            field.get_attribute.side_effect = lambda attr, state=state: state.get(attr)
            field.clear.side_effect = lambda state=state: state.update(value="")
            field.send_keys.side_effect = lambda value, state=state: state.update(value=value)
            field.is_displayed.return_value = True
            field.is_enabled.return_value = True
            fields[name] = field
            cell = MagicMock()
            cell.get_attribute.return_value = "1"
            cell.find_elements.return_value = [field]
            body_cells.append(cell)
        header_row, body_row = MagicMock(), MagicMock()
        header_row.find_elements.return_value = header_cells
        body_row.find_elements.return_value = body_cells
        table = MagicMock()
        table.is_displayed.return_value = True
        table.find_elements.side_effect = lambda by, selector: (
            [header_row] if selector == "thead tr" else [body_row]
        )
        return table, fields

    def test_discovery_requires_one_complete_visible_service_row(self):
        table, fields = self.service_table()
        hidden_table, _ = self.service_table()
        hidden_table.is_displayed.return_value = False
        driver = MagicMock()
        with patch.object(main, "By", SimpleNamespace(CSS_SELECTOR="css", XPATH="xpath"), create=True):
            driver.find_elements.return_value = [hidden_table, table]
            self.assertEqual(main.discover_service_fields(driver), fields)
            fields["procedure_code"].is_enabled.return_value = False
            self.assertFalse(main.discover_service_fields(driver))
            fields["procedure_code"].is_enabled.return_value = True
            other_table, _ = self.service_table()
            driver.find_elements.return_value = [table, other_table]
            self.assertFalse(main.discover_service_fields(driver))

    def test_rejected_date_is_not_reported_as_success(self):
        driver = MagicMock()
        table, fields = self.service_table()
        driver.find_elements.return_value = [table]
        fields["date_of_service"].send_keys.side_effect = None  # Simulate rejected input.
        with patch.object(main, "By", SimpleNamespace(CSS_SELECTOR="css", XPATH="xpath"), create=True), \
             patch.object(main, "WebDriverWait", create=True) as wait, patch("builtins.print") as output:
            def until(condition):
                result = condition(driver)
                if not result:
                    raise RuntimeError("Input value was not accepted")
                return result
            wait.return_value.until.side_effect = until
            with self.assertRaisesRegex(RuntimeError, "not accepted"):
                main.fill_form_6(driver, {"date_of_service": "10/03/2026"}, 8)
            self.assertNotIn(unittest.mock.call("Successfully filled date_of_service"), output.call_args_list)

    def test_next_service_waits_for_previous_page_to_leave(self):
        data = prepare_claim_batches(self.config(3))[0]
        for number in range(1, 6):
            data[f"form_{number}"] = {}
        fields = [object() for _ in range(9)]
        events = []
        def fill(driver, entry, index, has_more_services):
            events.append(("fill", index))
            return fields[index]
        with patch.object(main, "webdriver", MagicMock()), \
             patch.object(main.os.path, "isfile", return_value=True), \
             patch.multiple(main, **{name: MagicMock() for name in (
                 "fill_form_1", "fill_form_2", "fill_form_3", "fill_form_4", "fill_form_5",
                 "fill_form_7", "fill_form_11", "debug_checkpoint")}), \
             patch.object(main, "fill_form_6", side_effect=fill), \
             patch.object(main, "click_next_button", side_effect=lambda driver: events.append(("next", None))), \
             patch.object(main, "EC", create=True) as conditions, \
             patch.object(main, "finish_claim") as submitted, \
             patch.object(main, "By", SimpleNamespace(CLASS_NAME="class"), create=True), \
             patch.object(main, "WebDriverWait", create=True) as wait, patch("builtins.input", return_value=""):
            conditions.staleness_of.side_effect = lambda field: events.append(("stale", fields.index(field)))
            main.click_button_on_website(data)
            self.assertEqual(conditions.staleness_of.call_count, 9)
            self.assertEqual(wait.return_value.until.call_count, 9)
            submitted.assert_called_once()
            self.assertEqual(events.count(("next", None)), 17)
            first_fill = events.index(("fill", 0))
            self.assertEqual(events[first_fill:first_fill + 27],
                             [event for index in range(9)
                              for event in (("fill", index), ("next", None), ("stale", index))])

    def test_ninth_service_missing_field_stops_instead_of_skipping(self):
        with patch.object(main, "WebDriverWait", create=True) as wait, patch("builtins.print"):
            wait.return_value.until.side_effect = RuntimeError("Missing ninth service")
            with self.assertRaisesRegex(RuntimeError, "Missing ninth service"):
                main.fill_form_6(MagicMock(), {}, 8)

    def test_all_batches_use_one_browser_without_normal_mode_prompts(self):
        batches = prepare_claim_batches(self.config(7))
        with patch.object(main, "webdriver", MagicMock()) as browser, \
             patch.object(main.os.path, "isfile", return_value=True), \
             patch.object(main, "fill_claim") as fill, patch.object(main, "debug_checkpoint"), \
             patch("builtins.input") as prompt, patch("builtins.print"):
            main.click_button_on_website(batches)
            browser.Firefox.assert_called_once()
            driver = browser.Firefox.return_value
            self.assertEqual(driver.get.call_count, 3)
            self.assertEqual(fill.call_args_list, [
                unittest.mock.call(driver, batch, step_mode=False) for batch in batches
            ])
            driver.quit.assert_called_once()
            prompt.assert_not_called()

    def test_start_batch_and_single_batch(self):
        batches = prepare_claim_batches(self.config(7))
        for single, expected in ((False, batches[1:]), (True, batches[1:2])):
            with self.subTest(single=single), \
                 patch.object(main, "webdriver", MagicMock()) as browser, \
                 patch.object(main.os.path, "isfile", return_value=True), \
                 patch.object(main, "fill_claim") as fill, patch.object(main, "debug_checkpoint"), \
                 patch("builtins.input") as prompt, patch("builtins.print"):
                main.click_button_on_website(batches, start_batch=2, single_batch=single, step_mode=True)
                driver = browser.Firefox.return_value
                self.assertEqual(fill.call_args_list, [
                    unittest.mock.call(driver, batch, step_mode=True) for batch in expected
                ])
                self.assertEqual(driver.get.call_count, len(expected))
                prompt.assert_not_called()

    def test_failed_submission_stops_before_next_batch_and_keeps_browser_for_review(self):
        batches = prepare_claim_batches(self.config(7))
        with patch.object(main, "webdriver", MagicMock()) as browser, \
             patch.object(main.os.path, "isfile", return_value=True), \
             patch.object(main, "fill_claim", side_effect=[None, RuntimeError("No confirmation")]) as fill, \
             patch("builtins.input", return_value="") as prompt, patch("builtins.print") as output:
            driver = browser.Firefox.return_value
            prompt.side_effect = lambda message: self.assertEqual(driver.quit.call_count, 0)
            with self.assertRaisesRegex(RuntimeError, "No confirmation"):
                main.click_button_on_website(batches)
            self.assertEqual(fill.call_count, 2)
            self.assertEqual(driver.get.call_count, 2)
            prompt.assert_called_once()
            driver.quit.assert_called_once()
            self.assertIn(unittest.mock.call("Submission confirmed for batch 1/3."), output.call_args_list)
            self.assertNotIn(unittest.mock.call("Submission confirmed for batch 2/3."), output.call_args_list)

    def test_confirmation_detection_rejects_review_and_error_pages(self):
        for text, expected in (("Please review your responses and submit your claim.", False),
                               ("Unable to submit your claim.", False),
                               ("Your response has been recorded.", True),
                               ("Your claim has been submitted.", True),
                               ("Thank you for submitting your claim.\nPlease allow up to 30 days for processing.", True)):
            with self.subTest(text=text):
                driver = MagicMock()
                driver.find_element.return_value.text = text
                driver.find_elements.return_value = []
                with patch.object(main, "By", SimpleNamespace(TAG_NAME="tag", CSS_SELECTOR="css"), create=True), \
                     patch.object(main, "WebDriverWait", create=True) as wait:
                    wait.return_value.until.side_effect = lambda condition: self.assertEqual(condition(driver), expected)
                    main.wait_for_submission(driver)

    def test_confirmed_claim_with_download_pdf_never_clicks_next(self):
        driver = MagicMock()
        driver.find_element.return_value.text = (
            "Thank you for submitting your claim.\n\n"
            "Please allow up to 30 days for processing.\n\n"
            "If you have questions, please contact member services using the phone number on your ID card."
        )
        download = MagicMock()
        download.is_displayed.return_value = True
        driver.find_elements.side_effect = lambda by, selector: (
            [download] if selector == "DownloadResponsesPDF" else []
        )
        with patch.object(main, "By", SimpleNamespace(TAG_NAME="tag", CSS_SELECTOR="css", CLASS_NAME="class"), create=True), \
             patch.object(main, "WebDriverWait", create=True) as wait, \
             patch.object(main, "debug_checkpoint") as checkpoint, \
             patch.object(main, "click_next_button") as next_button:
            wait.return_value.until.side_effect = lambda condition: condition(driver)
            main.finish_claim(driver, step_mode=True)
            next_button.assert_not_called()
            checkpoint.assert_not_called()
            driver.find_elements.assert_called_once_with("css", "#EndOfSurvey, .EndOfSurvey")

    def review_driver(self):
        driver = MagicMock()
        driver.find_element.return_value.text = "Please review your responses and submit your claim."
        download, button = MagicMock(), MagicMock()
        download.is_displayed.return_value = True
        button.is_displayed.return_value = True
        button.is_enabled.return_value = True
        def elements(by, selector):
            if selector == "DownloadResponsesPDF":
                return [download]
            if selector.startswith("#NextButton"):
                return [button]
            return []
        driver.find_elements.side_effect = elements
        return driver, button

    def test_real_review_page_submits_once_then_waits_for_confirmation(self):
        driver, button = self.review_driver()
        with patch.object(main, "By", SimpleNamespace(TAG_NAME="tag", CSS_SELECTOR="css", CLASS_NAME="class"), create=True), \
             patch.object(main, "WebDriverWait", create=True) as wait, \
             patch.object(main, "debug_checkpoint"), patch.object(main, "wait_for_submission") as confirmation:
            wait.return_value.until.side_effect = lambda condition: condition(driver)
            main.finish_claim(driver)
            button.click.assert_called_once()
            confirmation.assert_called_once_with(driver)

    def test_manual_submission_during_step_pause_does_not_submit_twice(self):
        driver, button = self.review_driver()
        with patch.object(main, "By", SimpleNamespace(TAG_NAME="tag", CSS_SELECTOR="css", CLASS_NAME="class"), create=True), \
             patch.object(main, "WebDriverWait", create=True) as wait, \
             patch.object(main, "debug_checkpoint") as checkpoint, \
             patch.object(main, "wait_for_submission") as confirmation:
            wait.return_value.until.side_effect = lambda condition: condition(driver)
            checkpoint.side_effect = lambda enabled, message: setattr(
                driver.find_element.return_value, "text", "Thank you for submitting your claim."
            )
            main.finish_claim(driver, step_mode=True)
            button.click.assert_not_called()
            confirmation.assert_not_called()

    def test_missing_submission_state_gives_actionable_error(self):
        with patch.object(main, "WebDriverWait", create=True) as wait:
            wait.return_value.until.side_effect = RuntimeError("Timeout")
            with self.assertRaisesRegex(RuntimeError, "No submission confirmation or available submit button"):
                main.finish_claim(MagicMock())

    def test_upload_failure_is_not_swallowed(self):
        with patch.object(main, "By", SimpleNamespace(CSS_SELECTOR="css"), create=True), \
             patch.object(main, "EC", create=True), \
             patch.object(main, "WebDriverWait", create=True) as wait, patch("builtins.print"):
            wait.return_value.until.side_effect = RuntimeError("Upload failed")
            with self.assertRaisesRegex(RuntimeError, "Upload failed"):
                main.fill_form_11(MagicMock(), "Invoice.pdf")


if __name__ == "__main__":
    unittest.main()
