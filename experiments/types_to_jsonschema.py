"""Can we generate a json schema from python 3 type hints?

Run the tests/examples (below) using::

    py.test experiments/types_to_jsonschema.py

"""
import inspect
import json

from decimal import Decimal

from typing import Union, Optional, Tuple

import itertools

import logging

EMPTY = inspect.Signature.empty
NoneType = type(None)


def wrap_with_one_of(schemas):
    if len(schemas) == 1:
        return schemas[0]
    else:
        return {'oneOf': schemas}


def make_custom_object_schema(type_):
    property_names = list(set(list(type_.__annotations__.keys()) + dir(type_)))
    properties = {}
    required = []
    for property_name in property_names:
        if not property_name.startswith('_'):
            properties[property_name] = wrap_with_one_of(
                python_type_to_json_schemas(
                    type_.__annotations__.get(property_name, None)
                )
            )
            default = getattr(type_, property_name, EMPTY)
            if default is not EMPTY:
                properties[property_name]['default'] = default
            else:
                required.append(property_name)
    return {
        'type': 'object',
        'title': type_.__name__,
        'properties': properties,
        'required': required,
        'additionalProperties': False,
    }


def python_type_to_json_schemas(type_):
    if type(type_) == type(Union):
        sub_types = type_._subs_tree()[1:]
        return list(itertools.chain(*map(python_type_to_json_schemas, sub_types)))
    elif issubclass(type_, (str, bytes, Decimal, complex)):
        return [{'type': 'string'}]
    elif issubclass(type_, (bool, )):
        return [{'type': 'boolean'}]
    elif issubclass(type_, (int, float)):
        return [{'type': 'number'}]
    elif issubclass(type_, (dict, )):
        return [{'type': 'object'}]
    elif type(type_) == type(Tuple) and len(type_._subs_tree()) > 1:
        sub_types = type_._subs_tree()[1:]
        return [{
            'type': 'array',
            'maxItems': len(sub_types),
            'minItems': len(sub_types),
            'items': [wrap_with_one_of(python_type_to_json_schemas(sub_type)) for sub_type in sub_types]
        }]
    elif issubclass(type_, (list, tuple)):
        return [{'type': 'array'}]
    elif issubclass(type_, NoneType):
        return [{'type': 'null'}]
    elif inspect.isclass(type_):
        # This is somewhat dicey as too many things are classes for this to be
        # reliable.
        return [make_custom_object_schema(type_)]
    else:
        return [{'type': 'string'}]


def parameter_to_json_schemas(parameter):
    if parameter.annotation is not EMPTY:
        return python_type_to_json_schemas(parameter.annotation)
    elif parameter.default is not EMPTY:
        return python_type_to_json_schemas(type(parameter.default))
    else:
        return None


def parameter_to_schema(parameter):
    type_schemas = parameter_to_json_schemas(parameter)
    if not type_schemas:
        return {}

    schemas = []
    for type_schema in type_schemas:
        if parameter.default is not EMPTY:
            type_schema['default'] = parameter.default
        schemas.append(type_schema)

    return wrap_with_one_of(schemas)


def return_type_to_schema(type_):
    if type_ is EMPTY:
        return {}

    type_schemas = python_type_to_json_schemas(type_)
    if not type_schemas:
        return {}

    return wrap_with_one_of(type_schemas)


def make_parameter_schema(f):
    parameter_schema = {
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': '{}() parameters'.format(f.__name__),
        'type': 'object',
        'additionalProperties': False,
        'properties': {},
        'required': [],
    }
    sig = inspect.signature(f)
    for parameter in sig.parameters.values():
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.VAR_POSITIONAL):
            logging.warning('Positional-only arguments are not supported: {}'.format(parameter))
            continue

        if parameter.kind == parameter.VAR_KEYWORD:
            parameter_schema['additionalProperties'] = True
            continue

        parameter_schema['properties'][parameter.name] = parameter_to_schema(parameter)
        if parameter.default is EMPTY:
            parameter_schema['required'].append(parameter.name)

    logging.info(json.dumps(parameter_schema, indent=4))
    return parameter_schema


def make_response_schema(f):
    response_schema = {
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': '{}() parameters'.format(f.__name__),
    }
    sig = inspect.signature(f)
    response_schema.update(
        **return_type_to_schema(sig.return_annotation)
    )
    logging.info(json.dumps(response_schema, indent=4))
    return response_schema


def test_no_types():
    def func(username): pass
    schema = make_parameter_schema(func)
    assert schema['description'] == 'func() parameters'
    assert schema['properties']['username'] == {}
    assert schema['required'] == ['username']
    assert schema['additionalProperties'] is False


def test_default():
    def func(field=123): pass
    schema = make_parameter_schema(func)
    assert schema['description'] == 'func() parameters'
    assert schema['properties']['field'] == {'type': 'number', 'default': 123}
    assert schema['required'] == []


def test_type():
    def func(field: dict): pass
    schema = make_parameter_schema(func)
    assert schema['description'] == 'func() parameters'
    assert schema['properties']['field'] == {'type': 'object'}
    assert schema['required'] == ['field']


def test_type_with_default():
    def func(field: float=3.142): pass
    schema = make_parameter_schema(func)
    assert schema['description'] == 'func() parameters'
    assert schema['properties']['field'] == {'type': 'number', 'default': 3.142}
    assert schema['required'] == []


def test_kwargs():
    def func(field: dict, **kwargs): pass
    schema = make_parameter_schema(func)
    assert schema['description'] == 'func() parameters'
    # **kwargs isn't a property, but additionalProperties is now set to true
    assert list(schema['properties'].keys()) == ['field']
    assert schema['required'] == ['field']
    assert schema['additionalProperties'] is True


def test_positional_args():
    def func(field: dict, *args): pass
    schema = make_parameter_schema(func)
    assert schema['description'] == 'func() parameters'
    assert list(schema['properties'].keys()) == ['field']  # *args is ignored
    assert schema['required'] == ['field']
    assert schema['additionalProperties'] is False


def test_python_type_to_json_types_union():
    json_types = python_type_to_json_schemas(Union[str, int])
    assert json_types == [
        {'type': 'string'},
        {'type': 'number'},
    ]


def test_union():
    def func(field: Union[str, int]): pass
    schema = make_parameter_schema(func)
    assert schema['description'] == 'func() parameters'
    assert schema['properties']['field'] == {
        'oneOf': [
            {'type': 'string'},
            {'type': 'number'},
        ]
    }
    assert schema['required'] == ['field']


def test_union_default():
    def func(field: Union[str, int] = 123): pass
    schema = make_parameter_schema(func)
    assert schema['description'] == 'func() parameters'
    assert schema['properties']['field'] == {
        'oneOf': [
            {'type': 'string', 'default': 123},  # Technically an invalid default value
            {'type': 'number', 'default': 123},
        ]
    }
    assert schema['required'] == []


def test_optional():
    def func(username: Optional[str]): pass
    schema = make_parameter_schema(func)
    assert schema['description'] == 'func() parameters'
    assert schema['properties']['username'] == {
        'oneOf': [
            {'type': 'string'},
            {'type': 'null'},
        ]
    }
    assert schema['required'] == ['username']


def test_custom_class():

    class User(object):
        username: str
        password: str
        is_admin: bool = False

    def func(user: User): pass
    schema = make_parameter_schema(func)

    assert schema['properties']['user']['title'] == 'User'
    assert schema['properties']['user']['type'] == 'object'
    assert schema['properties']['user']['properties'] == {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'is_admin': {'type': 'boolean', 'default': False},
        }
    assert set(schema['properties']['user']['required']) == {'password', 'username'}


def test_response_no_types():
    def func(username): pass
    schema = make_response_schema(func)
    assert 'type' not in schema


def test_response_bool():
    def func(username) -> bool: pass
    schema = make_response_schema(func)
    assert schema['type'] == 'boolean'


def test_response_typed_tuple():
    def func(username) -> Tuple[str, int, bool]: pass
    schema = make_response_schema(func)
    assert schema['type'] == 'array'
    assert schema['items'] == [
        {'type': 'string'},
        {'type': 'number'},
        {'type': 'boolean'},
    ]


def test_response_custom_object():

    class User(object):
        username: str
        password: str
        is_admin: bool = False

    def func(username) -> User: pass
    schema = make_response_schema(func)
    assert schema['type'] == 'object'
    assert schema['title'] == 'User'
    assert schema['properties'] == {
        'username': {'type': 'string'},
        'password': {'type': 'string'},
        'is_admin': {'type': 'boolean', 'default': False},
    }
    assert set(schema['required']) == {'username', 'password'}
    assert schema['additionalProperties'] == False

