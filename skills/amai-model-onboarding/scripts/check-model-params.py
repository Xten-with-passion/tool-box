#!/usr/bin/env python3
"""Read llm_model.config_detail JSON; check known UI metadata, never mutate it."""
import argparse
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def canvas_visibility(document):
    """Mirror the observed shallow locale override and strict bool visibility check."""
    if not isinstance(document, dict):
        return {}

    result = {}
    for locale in ("zh-CN", "en-US"):
        scope = document[locale] if isinstance(document.get(locale), dict) else {}
        owner = scope if "canvas_show" in scope else document
        if "canvas_show" not in owner:
            result[locale] = "missing"
        elif not isinstance(owner["canvas_show"], bool):
            result[locale] = "invalid"
        else:
            result[locale] = "visible" if owner["canvas_show"] else "hidden"
    return result


def check(document, require_canvas=False):
    errors, warnings = [], []
    if not isinstance(document, dict):
        return ["config_detail must be an object"], warnings

    field_maps = {}
    if "field_map" in document:
        field_maps["root"] = document["field_map"]

    locales = ("zh-CN", "en-US")
    scopes = {"root": document}
    for locale in locales:
        if locale not in document:
            continue
        body = document[locale]
        if not isinstance(body, dict):
            errors.append(f"{locale} must be an object")
        else:
            scopes[locale] = body
            if "field_map" in body:
                field_maps[locale] = body["field_map"]
            elif "field_map" not in document:
                warnings.append(f"{locale} has no field_map; verify the model's UI contract")

    for name, body in scopes.items():
        if "canvas_show" in body and not isinstance(body["canvas_show"], bool):
            errors.append(f"{name}.canvas_show must be boolean")

    visibility = canvas_visibility(document)
    if require_canvas:
        for locale, state in visibility.items():
            if state != "visible":
                errors.append(f"{locale}.canvas_show must resolve to true for the requested canvas contract")
    elif len(set(visibility.values())) > 1:
        warnings.append("Effective canvas visibility differs by locale; review against the contract")

    if not field_maps:
        warnings.append("No known field_map found; no parameter semantics were checked")

    signatures = {}
    for scope, fields in field_maps.items():
        if not isinstance(fields, dict):
            errors.append(f"{scope}.field_map must be an object")
            continue
        signatures[scope] = {}
        for name, field in fields.items():
            path = f"{scope}.field_map.{name}"
            if not isinstance(field, dict):
                errors.append(f"{path} must be an object")
                continue
            for key in ("name", "type"):
                if key in field and not isinstance(field[key], str):
                    errors.append(f"{path}.{key} must be a string")
            if "required" in field and not isinstance(field["required"], bool):
                errors.append(f"{path}.required must be boolean")

            values, selected = [], []
            if "options" in field:
                options = field["options"]
                if not isinstance(options, list):
                    errors.append(f"{path}.options must be an array")
                else:
                    for index, option in enumerate(options):
                        option_path = f"{path}.options[{index}]"
                        if not isinstance(option, dict) or "value" not in option:
                            errors.append(f"{option_path} must be an object with value")
                            continue
                        token = canonical(option["value"])
                        values.append(token)
                        if "select" in option and not isinstance(option["select"], bool):
                            errors.append(f"{option_path}.select must be boolean")
                        if option.get("select") is True:
                            selected.append(token)
                    if len(values) != len(set(values)):
                        errors.append(f"{path}.options contains duplicate values")

            # Only enforce single-choice semantics for the observed radios control.
            if field.get("type") == "radios":
                if "default" in field and "options" in field:
                    default = canonical(field["default"])
                    if default not in values:
                        errors.append(f"{path}.default is absent from options")
                    if selected and selected != [default]:
                        errors.append(f"{path}.default and selected option disagree")
                if len(selected) > 1:
                    errors.append(f"{path} has multiple selected radio options")

            semantic = {key: field[key] for key in
                        ("name", "type", "required", "default", "min", "max") if key in field}
            if "options" in field:
                semantic["option_values"] = sorted(values)
                semantic["selected_values"] = sorted(selected)
            signatures[scope][name] = canonical(semantic)

    # Locale override is shallow; a locale field_map replaces the whole root map.
    effective = {}
    for locale in locales:
        if locale in signatures:
            effective[locale] = signatures[locale]
        elif "root" in signatures:
            effective[locale] = signatures["root"]
    if len(effective) == 2:
        left, right = (effective[locale] for locale in locales)
        if left.keys() != right.keys():
            errors.append("Locale field_map keys differ; locale override does not deep-merge fields")
        for name in sorted(left.keys() & right.keys()):
            if left[name] != right[name]:
                errors.append(f"Locale parameter semantics differ for {name}; review against the contract")
    elif field_maps:
        warnings.append("Both effective locales could not be compared")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_detail", type=Path)
    parser.add_argument("--require-canvas", action="store_true",
                        help="Require effective canvas_show=true in both zh-CN and en-US")
    args = parser.parse_args()
    visibility = {}
    try:
        document = json.loads(args.config_detail.read_text(encoding="utf-8"))
        errors, warnings = check(document, require_canvas=args.require_canvas)
        visibility = canvas_visibility(document)
    except (OSError, UnicodeError, ValueError):
        errors, warnings = ["Cannot read config_detail as UTF-8 JSON; source contents suppressed"], []
    print(json.dumps({"valid": not errors, "errors": errors, "warnings": warnings,
                      "effective_canvas_visibility": visibility}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
