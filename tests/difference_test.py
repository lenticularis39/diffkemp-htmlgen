from diffkemp_htmlgen.htmlgen import Difference, InternalSymbol, ExternalSymbol
import yaml


def test_from_yaml():
    yaml_dict = yaml.safe_load("""
symbol: kmalloc_node
diff-kind: function

location-old:
  file: include/linux/slab.h
  line: 541
location-new:
  file: include/linux/slab.h
  line: 578

diff: difference

affected-symbols:
  - symbol:
        name:  __alloc_pages_nodemask
        kind: function
    callstack-old:
      - symbol: kmalloc_node
        file: include/linux/slab.h
        line: 718
    callstack-new:
      - symbol: kmalloc_node
        file: include/linux/slab.h
        line: 760
    """)
    difference = Difference.from_yaml(yaml_dict)

    for symbol in [difference.symbol_old, difference.symbol_new]:
        assert symbol.name == "kmalloc_node"
        assert symbol.kind == InternalSymbol.Kind.FUNCTION
        assert symbol.location.filename == "include/linux/slab.h"
    assert difference.symbol_old.location.line == 541
    assert difference.symbol_new.location.line == 578
    assert difference.diff == "difference"
    assert len(difference.affected_symbols) == 1

    affected_symbol = difference.affected_symbols[0]
    assert isinstance(affected_symbol.symbol, ExternalSymbol)
    assert affected_symbol.symbol.name == "__alloc_pages_nodemask"
    assert affected_symbol.symbol.kind == ExternalSymbol.Kind.FUNCTION
    assert len(affected_symbol.callstack_old) == 1
    assert len(affected_symbol.callstack_new) == 1

    call_old = affected_symbol.callstack_old[0]
    assert call_old.symbol_name == "kmalloc_node"
    assert call_old.location.filename == "include/linux/slab.h"
    assert call_old.location.line == 718

    call_new = affected_symbol.callstack_new[0]
    assert call_new.symbol_name == "kmalloc_node"
    assert call_new.location.filename == "include/linux/slab.h"
    assert call_new.location.line == 760
