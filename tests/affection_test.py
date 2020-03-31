from diffkemp_htmlgen.htmlgen import Affection, ExternalSymbol
import yaml


def test_from_yaml():
    # Note: the symbol in affections generated from YAML is always an
    # ExternalSymbol.
    yaml_dict = yaml.safe_load(("symbol:\n"
                                "    name:  __alloc_pages_nodemask\n"
                                "    kind: function\n"
                                "callstack-old:\n"
                                "    - symbol: kmalloc_node\n"
                                "      file: include/linux/slab.h\n"
                                "      line: 718\n"
                                "callstack-new:\n"
                                "    - symbol: kmalloc_node\n"
                                "      file: include/linux/slab.h\n"
                                "      line: 760\n"))
    affection = Affection.from_yaml(yaml_dict)

    assert isinstance(affection.symbol, ExternalSymbol)
    assert affection.symbol.name == "__alloc_pages_nodemask"
    assert affection.symbol.kind == ExternalSymbol.Kind.FUNCTION
    assert len(affection.callstack_old) == 1
    assert len(affection.callstack_new) == 1

    call_old = affection.callstack_old[0]
    assert call_old.symbol_name == "kmalloc_node"
    assert call_old.location.filename == "include/linux/slab.h"
    assert call_old.location.line == 718

    call_new = affection.callstack_new[0]
    assert call_new.symbol_name == "kmalloc_node"
    assert call_new.location.filename == "include/linux/slab.h"
    assert call_new.location.line == 760
