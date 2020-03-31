from diffkemp_htmlgen.htmlgen import InternalSymbol
import yaml


def test_kind___str__():
    kind = InternalSymbol.Kind.FUNCTION
    assert str(kind) == "function"


def test_kind_from_yaml():
    kind = InternalSymbol.Kind.from_yaml("function")
    assert kind == InternalSymbol.Kind.FUNCTION


def test_from_yaml():
    yaml_dict = yaml.safe_load(("name: __alloc_pages_nodemask\n"
                                "kind: function\n"
                                "location:\n"
                                "    file: mm/page_alloc.c\n"
                                "    line: 3083\n"))
    symbol = InternalSymbol.from_yaml(yaml_dict)

    assert symbol.name == "__alloc_pages_nodemask"
    assert symbol.kind == InternalSymbol.Kind.FUNCTION
    assert symbol.location.filename == "mm/page_alloc.c"
    assert symbol.location.line == 3083
