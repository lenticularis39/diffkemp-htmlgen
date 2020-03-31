from diffkemp_htmlgen.htmlgen import ExternalSymbol
import yaml


def test_kind___str__():
    kind = ExternalSymbol.Kind.FUNCTION
    assert str(kind) == "function"


def test_kind_from_yaml():
    kind = ExternalSymbol.Kind.from_yaml("function")
    assert kind == ExternalSymbol.Kind.FUNCTION


def test_from_yaml():
    yaml_dict = yaml.safe_load(("name:  __alloc_pages_nodemask\n"
                                "kind: function\n"))
    symbol = ExternalSymbol.from_yaml(yaml_dict)

    assert symbol.name == "__alloc_pages_nodemask"
    assert symbol.kind == ExternalSymbol.Kind.FUNCTION
