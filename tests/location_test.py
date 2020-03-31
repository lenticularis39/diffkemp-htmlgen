from diffkemp_htmlgen.htmlgen import Location
import yaml


def test__str__():
    location = Location("mm/page_alloc.c", 3083)
    assert str(location) == "mm/page_alloc.c:3083"


def test_from_yaml():
    yaml_dict = yaml.safe_load(("file: mm/page_alloc.c\n"
                                "line: 3083\n"))
    location = Location.from_yaml(yaml_dict)

    assert location.filename == "mm/page_alloc.c"
    assert location.line == 3083
