"""Offline regression checks for the skill's read-only configuration helpers."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("params_check", ROOT / "scripts/check-model-params.py")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def parameters():
    field = {
        "name": "quality", "type": "radios", "required": False, "default": "medium",
        "options": [{"label": "低", "value": "low"},
                    {"label": "中", "value": "medium", "select": True}],
    }
    result = {locale: {"field_map": {"quality": copy.deepcopy(field)}}
              for locale in ("zh-CN", "en-US")}
    result["en-US"]["field_map"]["quality"]["options"][0]["label"] = "Low"
    return result


class ParameterChecks(unittest.TestCase):
    def test_translated_labels_do_not_change_parameter_contract(self):
        errors, _ = CHECKER.check(parameters())
        self.assertEqual(errors, [])

    def test_unknown_radio_default_is_rejected(self):
        data = parameters()
        data["zh-CN"]["field_map"]["quality"]["default"] = "unsupported"
        self.assertTrue(CHECKER.check(data)[0])

    def test_multiple_selected_radios_are_rejected(self):
        data = parameters()
        data["zh-CN"]["field_map"]["quality"]["options"][0]["select"] = True
        self.assertTrue(CHECKER.check(data)[0])

    def test_required_string_is_not_a_boolean(self):
        data = parameters()
        data["zh-CN"]["field_map"]["quality"]["required"] = "false"
        self.assertTrue(CHECKER.check(data)[0])

    def test_locale_field_map_does_not_deep_merge_root(self):
        data = {"field_map": parameters()["zh-CN"]["field_map"],
                "en-US": {"field_map": {}}}
        self.assertTrue(CHECKER.check(data)[0])

    def test_optional_canvas_absence_is_not_auto_enabled(self):
        data = parameters()
        self.assertEqual(CHECKER.check(data)[0], [])
        self.assertEqual(CHECKER.canvas_visibility(data),
                         {"zh-CN": "missing", "en-US": "missing"})

    def test_required_canvas_absence_fails(self):
        self.assertTrue(CHECKER.check(parameters(), require_canvas=True)[0])

    def test_chinese_only_canvas_does_not_cover_english(self):
        data = parameters()
        data["zh-CN"]["canvas_show"] = True
        self.assertTrue(CHECKER.check(data, require_canvas=True)[0])
        self.assertEqual(CHECKER.canvas_visibility(data)["en-US"], "missing")

    def test_root_canvas_inherits_into_both_locales(self):
        data = parameters()
        data["canvas_show"] = True
        self.assertEqual(CHECKER.check(data, require_canvas=True)[0], [])
        self.assertEqual(set(CHECKER.canvas_visibility(data).values()), {"visible"})

    def test_locale_false_overrides_root_true(self):
        data = parameters()
        data["canvas_show"] = True
        data["en-US"]["canvas_show"] = False
        self.assertTrue(CHECKER.check(data, require_canvas=True)[0])
        self.assertEqual(CHECKER.canvas_visibility(data)["en-US"], "hidden")

    def test_canvas_string_and_number_are_not_booleans(self):
        for value in ("true", 1, None):
            with self.subTest(value=value):
                data = parameters()
                data["canvas_show"] = value
                self.assertTrue(CHECKER.check(data)[0])

    def test_valid_intentional_locale_difference_is_reported(self):
        data = parameters()
        data["zh-CN"]["canvas_show"] = True
        data["en-US"]["canvas_show"] = False
        errors, warnings = CHECKER.check(data)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)

    def test_invalid_json_does_not_echo_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text('{PRIVATE_TEST_VALUE', encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/check-model-params.py"),
                                     str(path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("PRIVATE_TEST_VALUE", result.stdout + result.stderr)


@unittest.skipUnless(shutil.which("ruby"), "Ruby is required for the YAML helper")
class ModelInspection(unittest.TestCase):
    def run_helper(self, source, model_id="fixture"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(source, encoding="utf-8")
            return subprocess.run(["ruby", str(ROOT / "scripts/inspect-model.rb"), str(path), model_id],
                                  text=True, capture_output=True)

    def test_at_and_zero_weight_are_retained_but_secrets_are_not(self):
        result = self.run_helper('''vendor:
  access_key: PRIVATE_TEST_VALUE
models:
  - model_id: fixture
    model_name: fixture-image
    modality: image
    custom_secret: PRIVATE_TEST_VALUE
    at:
      enabled: true
      token: PRIVATE_TEST_VALUE
    clients:
      default:
        - client_name: fallback
          weight: 0
          token: PRIVATE_TEST_VALUE
''')
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["at"], {"enabled": True})
        self.assertEqual(data["clients"]["default"], [{"client_name": "fallback", "weight": 0}])
        self.assertNotIn("PRIVATE_TEST_VALUE", result.stdout + result.stderr)

    def test_missing_at_remains_absent(self):
        result = self.run_helper('models:\n  - {model_id: fixture, model_name: image, modality: image}\n')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("at", json.loads(result.stdout))

    def test_duplicate_model_id_is_rejected(self):
        result = self.run_helper('''models:
  - {model_id: fixture, model_name: a, modality: image}
  - {model_id: fixture, model_name: b, modality: image}
''')
        self.assertEqual(result.returncode, 1)

    def test_string_at_flag_is_rejected(self):
        result = self.run_helper('''models:
  - model_id: fixture
    model_name: image
    modality: image
    at: {enabled: "true"}
''')
        self.assertEqual(result.returncode, 1)

    def test_malformed_yaml_does_not_echo_source(self):
        result = self.run_helper('vendor: [PRIVATE_TEST_VALUE\n')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("PRIVATE_TEST_VALUE", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
