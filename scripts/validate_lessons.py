#!/usr/bin/env python3
"""validate_lessons.py — validate lessons against schema/lesson.schema.json.

Uses the `jsonschema` library if importable; otherwise falls back to a built-in
checker covering exactly the keywords our frozen schema uses (type, required,
additionalProperties:false, pattern, min/maxLength, enum, const, array
min/maxItems/uniqueItems/items). Dependency-free so CI never silently skips.

Usage: validate_lessons.py lessons/<id>.json [...]   (schema auto-located)
Exit 0 valid · 1 invalid · 2 usage/IO.
"""
import json
import os
import re
import sys

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'schema', 'lesson.schema.json')


def _type_ok(val, t):
    return {
        'string': isinstance(val, str),
        'array': isinstance(val, list),
        'boolean': isinstance(val, bool),
        'object': isinstance(val, dict),
        'number': isinstance(val, (int, float)) and not isinstance(val, bool),
        'integer': isinstance(val, int) and not isinstance(val, bool),
        'null': val is None,
    }.get(t, False)


def _check(val, sch, path, errs):
    t = sch.get('type')
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(val, x) for x in types):
            errs.append(f'{path}: expected type {t}, got {type(val).__name__}')
            return
    if 'const' in sch and val != sch['const']:
        errs.append(f'{path}: must equal {sch["const"]!r}')
    if 'enum' in sch and val not in sch['enum']:
        errs.append(f'{path}: must be one of {sch["enum"]}')
    if isinstance(val, str):
        if 'minLength' in sch and len(val) < sch['minLength']:
            errs.append(f'{path}: shorter than minLength {sch["minLength"]}')
        if 'maxLength' in sch and len(val) > sch['maxLength']:
            errs.append(f'{path}: longer than maxLength {sch["maxLength"]}')
        if 'pattern' in sch and not re.search(sch['pattern'], val):
            errs.append(f'{path}: does not match pattern {sch["pattern"]}')
    if isinstance(val, list):
        if 'minItems' in sch and len(val) < sch['minItems']:
            errs.append(f'{path}: fewer than minItems {sch["minItems"]}')
        if 'maxItems' in sch and len(val) > sch['maxItems']:
            errs.append(f'{path}: more than maxItems {sch["maxItems"]}')
        if sch.get('uniqueItems') and len(val) != len({json.dumps(x, sort_keys=True) for x in val}):
            errs.append(f'{path}: items not unique')
        if 'items' in sch:
            for i, item in enumerate(val):
                _check(item, sch['items'], f'{path}[{i}]', errs)
    if isinstance(val, dict) and sch.get('type') == 'object' or (isinstance(val, dict) and 'properties' in sch):
        props = sch.get('properties', {})
        for req in sch.get('required', []):
            if req not in val:
                errs.append(f'{path}: missing required property "{req}"')
        if sch.get('additionalProperties') is False:
            for k in val:
                if k not in props:
                    errs.append(f'{path}: additional property "{k}" not allowed')
        for k, v in val.items():
            if k in props:
                _check(v, props[k], f'{path}.{k}', errs)


def validate_builtin(lesson, schema):
    errs = []
    _check(lesson, schema, '$', errs)
    return errs


def main(argv):
    paths = argv[1:]
    if not paths:
        print('usage: validate_lessons.py lessons/<id>.json [...]', file=sys.stderr)
        return 2
    try:
        schema = json.load(open(SCHEMA_PATH, encoding='utf-8'))
    except OSError as e:
        print(f'cannot read schema {SCHEMA_PATH}: {e}', file=sys.stderr)
        return 2

    validator = None
    try:
        import jsonschema  # type: ignore
        validator = jsonschema.Draft202012Validator(schema)
        mode = 'jsonschema'
    except Exception:
        mode = 'builtin'

    total = 0
    for p in paths:
        try:
            lesson = json.load(open(p, encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as e:
            print(f'✗ {p}: cannot read/parse: {e}', file=sys.stderr)
            total += 1
            continue
        if validator is not None:
            errs = [f'{list(e.absolute_path)}: {e.message}' for e in validator.iter_errors(lesson)]
        else:
            errs = validate_builtin(lesson, schema)
        # filename must equal <id>.json
        expect = lesson.get('id')
        if isinstance(expect, str) and os.path.basename(p) != f'{expect}.json':
            errs.append(f'filename {os.path.basename(p)} != "{expect}.json"')
        if errs:
            total += len(errs)
            print(f'✗ {p}', file=sys.stderr)
            for e in errs:
                print(f'    {e}', file=sys.stderr)
    if total:
        print(f'validate_lessons: INVALID — {total} error(s). [{mode}]', file=sys.stderr)
        return 1
    print(f'validate_lessons: valid ({len(paths)} lesson(s)). [{mode}]')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
