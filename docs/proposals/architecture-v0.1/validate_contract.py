#!/usr/bin/env python3
"""Validate OpenAPI references, operation headers, examples and diagram links.
Run: python validate_contract.py
Dependencies: PyYAML, jsonschema. FastAPI enables an additional model check.
"""
from __future__ import annotations
import copy
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent
SPEC = yaml.safe_load((ROOT / 'openapi.yaml').read_text(encoding='utf-8'))
METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}


def resolve(ref: str):
    if not ref.startswith('#/'):
        raise AssertionError(f'External reference: {ref}')
    result = SPEC
    for key in ref[2:].split('/'):
        result = result[key.replace('~1', '/').replace('~0', '~')]
    return result


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def main() -> None:
    refs = [v['$ref'] for v in walk(SPEC) if '$ref' in v]
    for ref in refs:
        resolve(ref)
    identifiers = set()
    for path, item in SPEC['paths'].items():
        for method, operation in item.items():
            if method not in METHODS:
                continue
            oid = operation['operationId']
            assert oid not in identifiers, f'Duplicate operationId: {oid}'
            identifiers.add(oid)
            raw = item.get('parameters', []) + operation.get('parameters', [])
            parameters = [resolve(p['$ref']) if '$ref' in p else p for p in raw]
            path_names = {p['name'] for p in parameters if p['in'] == 'path'}
            assert path_names == set(re.findall(r'{([^}]+)}', path)), path
            assert all(p.get('required') for p in parameters if p['in'] == 'path'), path
            headers = {p['name'] for p in parameters if p['in'] == 'header' and p.get('required')}
            if method in {'post', 'put', 'patch', 'delete'}:
                assert 'X-CSRF-Token' in headers, path
            if method == 'post' and not path.startswith('/auth/'):
                assert 'Idempotency-Key' in headers, path
            if method in {'put', 'delete'} or (method == 'post' and path.endswith(('/confirm', '/publish', '/actions', '/submissions', '/feedback'))):
                assert 'If-Match' in headers, path
            assert any(str(c).startswith('2') for c in operation['responses']), path
    assert (len(SPEC['paths']), len(identifiers), len(SPEC['components']['schemas'])) == (44, 55, 64)
    profile = SPEC['paths']['/cases/{case_id}/profile']['get']['responses']['200']
    assert profile['content']['application/json']['schema'] == {'$ref': '#/components/schemas/CaseProfile'}
    assert 'ETag' not in profile.get('headers', {})
    for schema in SPEC['components']['schemas'].values():
        Draft202012Validator.check_schema(schema)
    resource = Resource.from_contents({'$schema': 'https://json-schema.org/draft/2020-12/schema', **SPEC})
    registry = Registry().with_resource('urn:job-lens:spec', resource)
    def valid(name, value):
        schema = {'$ref': 'urn:job-lens:spec#/components/schemas/' + name}
        return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker()).is_valid(value)
    uid = '00000000-0000-4000-8000-000000000001'
    prefs = dict(font_scale=1.25, volume=0.6, quiet_mode=False, speech_enabled=False, vibration_enabled=True)
    profile_value = dict(display_name='示例学员', sensory_preferences=['图文'], communication_preference='短句', work_notes='文档质检', user_id=uid, version=1)
    marker = dict(id=uid, shape='rect', x=0.1, y=0.2, width=0.3, height=0.4, text='补充日期')
    feedback = dict(outcome='changes_requested', message='补充日期后重新提交。', tags=['naming_adjustment'], redo_step_ids=[uid], annotation_ids=[])
    examples = [
        ('PreferencesWrite', prefs),
        ('CaseProfile', dict(profile=profile_value, preferences={**prefs, 'version': 2})),
        ('TaskAction', {'action': 'cancel', 'reason': '更换训练方向'}),
        ('TaskAction', {'action': 'start'}),
        ('FeedbackCreate', feedback),
        ('FeedbackCreate', {**feedback, 'outcome': 'passed', 'redo_step_ids': []}),
        ('Marker', marker),
        ('Marker', dict(id=uid, shape='point', x=0.1, y=0.2, text='标题')),
        ('MessageCreate', {'body': '', 'attachment_ids': [uid]}),
        ('AssistanceCreate', dict(case_id=uid, task_id=None, step_id=None, message='请帮我确认', attachment_ids=[], preferred_mode='text')),
        ('PublishRequest', {'due_on': None}),
        ('PublishRequest', {'due_on': '2026-09-20'}),
        ('EventBatch', {'events': [dict(event_id=uid, session_id=uid, sequence=1, step_id=uid, kind='time_sample', value=600, observed_at='2026-09-19T01:00:00Z')]}),
        ('NotificationPage', {'items': [], 'next_seq': '0', 'has_more': False}),
    ]
    negative = [
        ('PreferencesWrite', {**prefs, 'volume': 2}),
        ('PreferencesWrite', {**prefs, 'role': 'counselor'}),
        ('CaseProfile', {'profile': profile_value}),
        ('CaseProfile', {'profile': profile_value, 'preferences': prefs}),
        ('TaskAction', {'action': 'cancel'}),
        ('TaskAction', {'action': 'cancel', 'reason': '  '}),
        ('FeedbackCreate', {**feedback, 'redo_step_ids': []}),
        ('FeedbackCreate', {**feedback, 'outcome': 'passed'}),
        ('Marker', {**marker, 'width': 0}),
        ('Marker', {**marker, 'shape': 'point'}),
        ('Marker', {**marker, 'x': 1.2}),
        ('MessageCreate', {'body': ' ', 'attachment_ids': []}),
        ('PublishRequest', {'due_on': 'invalid-date'}),
        ('EventBatch', {'events': []}),
    ]
    for name, value in examples:
        assert valid(name, value), f'Positive rejected: {name} {json.dumps(value, ensure_ascii=False)}'
    for name, value in negative:
        assert not valid(name, value), f'Negative accepted: {name}'
    diagrams = []
    architecture = (ROOT / 'architecture.md').read_text(encoding='utf-8')
    for target in re.findall(r'!\[[^\]]*\]\((figures/[^)]+)\)', architecture):
        path = ROOT / target
        tree = ET.parse(path)
        assert tree.getroot().tag.endswith('svg'), target
        assert len(tree.findall('.//{http://www.w3.org/2000/svg}text')) > 5, target
        diagrams.append(target)
    assert len(set(diagrams)) == 6
    try:
        from fastapi.openapi.models import OpenAPI
        OpenAPI.model_validate(SPEC)
        model_check = 'passed'
    except ImportError:
        model_check = 'skipped (FastAPI not installed)'
    print(f'PASS: {len(SPEC["paths"])} paths, {len(identifiers)} operations, {len(SPEC["components"]["schemas"])} schemas')
    print(f'PASS: {len(refs)} references; path parameters and required headers')
    print(f'PASS: {len(examples)} positive / {len(negative)} negative schema examples')
    print(f'PASS: {len(set(diagrams))} linked SVG diagrams; CaseProfile projection')
    print(f'FastAPI OpenAPI model: {model_check}')

if __name__ == '__main__':
    main()
