#!/usr/bin/env python3
"""Validate proposal structure and examples; this is not a running-service test.
Requires Python 3.11+, PyYAML and jsonschema. Optional: FastAPI OpenAPI model.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'}
BASE = 'https://job-lens.invalid/proposed-openapi'
UID = '00000000-0000-4000-8000-000000000101'

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def pointer(doc: dict[str, Any], reference: str) -> Any:
    require(reference.startswith('#/'), f'External reference not expected: {reference}')
    node: Any = doc
    for part in reference[2:].split('/'):
        node = node[part.replace('~1', '/').replace('~0', '~')]
    return node

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('spec', nargs='?', default=str(Path(__file__).with_name('openapi.yaml')))
    parser.add_argument('--json-out')
    args = parser.parse_args()
    path = Path(args.spec)
    raw = path.read_bytes()
    doc = yaml.safe_load(raw)
    require(doc['openapi'] == '3.1.1', 'Expected chosen OAS version 3.1.1')
    require(doc['security'] == [{'WebSession': []}], 'Expected shared Web session boundary')
    refs = 0
    def walk(node: Any) -> None:
        nonlocal refs
        if isinstance(node, dict):
            if '$ref' in node:
                pointer(doc, node['$ref'])
                refs += 1
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(doc)
    operations: dict[str, tuple[str, str]] = {}
    schema_count = len(doc['components']['schemas'])
    for name, schema in doc['components']['schemas'].items():
        Draft202012Validator.check_schema(schema)
        if schema.get('type') == 'object':
            require(schema.get('additionalProperties') is False, f'{name}: open object')
            require(set(schema.get('required', [])) <= set(schema['properties']), f'{name}: missing property')
    for route, item in doc['paths'].items():
        placeholders = set(re.findall(r'\{([^}]+)\}', route))
        for method, op in item.items():
            if method not in METHODS:
                continue
            oid = op['operationId']
            require(oid not in operations, f'Duplicate operationId: {oid}')
            operations[oid] = (method, route)
            params = item.get('parameters', []) + op.get('parameters', [])
            params = [pointer(doc, p['$ref']) if '$ref' in p else p for p in params]
            actual = {p['name'] for p in params if p['in'] == 'path' and p.get('required')}
            require(actual == placeholders, f'{oid}: path parameters mismatch')
            headers = {p['name'] for p in params if p['in'] == 'header' and p.get('required')}
            require('default' in op['responses'], f'{oid}: missing Problem fallback')
            require(any(str(code).startswith('2') for code in op['responses']), f'{oid}: no success response')
            if method in {'post', 'put', 'patch', 'delete'}:
                require('X-CSRF-Token' in headers, f'{oid}: missing CSRF')
            if method == 'post' and route not in {'/auth/login', '/auth/logout'}:
                require('Idempotency-Key' in headers, f'{oid}: missing idempotency')
            if method in {'put', 'delete'} or route.endswith(('/publish', '/confirm', '/actions', '/feedback')) or (route.endswith('/submissions') and method == 'post'):
                require('If-Match' in headers, f'{oid}: missing optimistic concurrency')
            if 'If-Match' in headers:
                require({'412', '428'} <= set(op['responses']), f'{oid}: missing precondition errors')
    require(len(operations) == 55, 'Endpoint catalog should contain 55 operations')
    require(len(doc['paths']) == 44 and schema_count == 63, 'Unexpected contract counts')
    registry = Registry().with_resource(BASE, Resource.from_contents(doc, default_specification=DRAFT202012))
    checker = FormatChecker()
    positive = negative = 0
    def example(name: str, value: Any, valid: bool = True) -> None:
        nonlocal positive, negative
        validator = Draft202012Validator({'$ref': BASE + '#/components/schemas/' + name}, registry=registry, format_checker=checker)
        errors = list(validator.iter_errors(value))
        require(bool(errors) != valid, f'{name}: unexpected example result: {[e.message for e in errors]}')
        if valid:
            positive += 1
        else:
            negative += 1
    example('LoginRequest', {'login_name': 'demo_learner', 'password': 'synthetic-example-only'})
    example('LoginRequest', {'login_name': 'demo', 'password': 'x', 'role': 'counselor'}, False)
    preferences = dict(font_scale=1.25, volume=0.5, quiet_mode=True, speech_enabled=False, vibration_enabled=False)
    example('PreferencesWrite', preferences)
    example('PreferencesWrite', dict(preferences, volume=2), False)
    example('PublishRequest', {'due_on': None})
    example('PublishRequest', {'due_on': '2026-09-20'})
    example('PublishRequest', {'due_on': '2026-99-20'}, False)
    step = dict(id=UID, position=1, instruction='检查标题', media_ids=[], estimated_seconds=720, evidence_required=True)
    example('RevisionWrite', dict(goal='核验文档', steps=[step], reminder=dict(speech_enabled=False, vibration_enabled=False, prompt_level=1)))
    example('ProgressWrite', {'status': 'completed', 'attachment_ids': [UID]})
    example('ProgressWrite', {'status': 'passed', 'attachment_ids': []}, False)
    feedback = dict(outcome='changes_requested', message='补充日期后重新提交', tags=['naming_adjustment'], redo_step_ids=[UID], annotation_ids=[])
    example('FeedbackCreate', feedback)
    example('FeedbackCreate', dict(feedback, redo_step_ids=[]), False)
    example('FeedbackCreate', dict(feedback, outcome='passed'), False)
    example('FeedbackCreate', dict(feedback, outcome='passed', redo_step_ids=[]))
    point = dict(id=UID, shape='point', x=0.2, y=0.5, text='检查此处')
    example('Marker', point)
    example('Marker', dict(point, x=1.2), False)
    rect = dict(point, shape='rect', width=0.3, height=0.1)
    example('Marker', rect)
    example('Marker', dict(point, width=0.3), False)
    example('TaskAction', {'action': 'cancel', 'reason': '重新制定计划'})
    example('TaskAction', {'action': 'cancel'}, False)
    example('TaskAction', {'action': 'start'})
    example('MessageCreate', {'body': '请帮助查看', 'attachment_ids': []})
    example('MessageCreate', {'body': '', 'attachment_ids': [UID]})
    example('MessageCreate', {'body': '  ', 'attachment_ids': []}, False)
    example('AssistanceCreate', dict(case_id=UID, task_id=None, step_id=None, message='需要帮助', attachment_ids=[], preferred_mode='text'))
    example('NotificationPage', {'items': [], 'next_seq': '42', 'has_more': False})
    example('NotificationPage', {'items': [], 'next_seq': 42, 'has_more': False}, False)
    example('Problem', dict(type='urn:job-lens:problem:version-conflict', title='资源已更新', status=412, code='VERSION_CONFLICT', trace_id='example_001'))
    # Geometry sum bounds require application logic; demonstrate this limitation, not a fake API test.
    out_of_bounds = dict(rect, x=0.9)
    example('Marker', out_of_bounds)
    require(out_of_bounds['x'] + out_of_bounds['width'] > 1, 'Geometry limitation example changed')
    fastapi_result = 'not installed (optional model check skipped)'
    try:
        from fastapi.openapi.models import OpenAPI
        OpenAPI.model_validate(doc)
        fastapi_result = 'PASS'
    except ImportError:
        pass
    report = {
        'status': 'PASS', 'scope': 'Static design contract only; no service, security or performance tests',
        'paths': len(doc['paths']), 'operations': len(operations), 'schemas': schema_count,
        'resolved_ref_occurrences': refs, 'positive_schema_examples': positive,
        'negative_schema_examples': negative, 'fastapi_openapi_model': fastapi_result,
        'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'limitations': ['Object authorization and state transitions need runtime tests', 'Rectangle sum bounds and immutable history need service tests', 'No full external OpenAPI conformance validator was installed'],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

if __name__ == '__main__':
    main()
