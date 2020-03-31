from diffkemp_htmlgen.htmlgen import Call
import yaml


def test_from_yaml():
    yaml_dict = yaml.safe_load(("symbol: __alloc_pages_nodemask\n"
                                "file: include/linux/slab.h\n"
                                "line: 718\n"))
    call = Call.from_yaml(yaml_dict)

    assert call.symbol_name == "__alloc_pages_nodemask"
    assert call.location.filename == "include/linux/slab.h"
    assert call.location.line == 718
