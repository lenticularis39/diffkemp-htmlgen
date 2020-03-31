import argparse
import os
import yaml
from enum import IntEnum
from yattag import Doc, indent


class InternalSymbol:
    """
    Represents the smallest unit for which differences are found by DiffKemp.
    This can be either a function, a macro or a structure type.
    """
    class Kind(IntEnum):
        FUNCTION = 0
        MACRO = 1
        TYPE = 2

        @classmethod
        def from_yaml(cls, yaml):
            dictionary = {
                "function": cls.FUNCTION,
                "macro": cls.MACRO,
                "type": cls.TYPE
            }
            return dictionary[yaml]

        def __str__(self):
            dictionary = {
                self.FUNCTION: "function",
                self.MACRO: "macro",
                self.TYPE: "type"
            }
            return dictionary[self]

    def __init__(self, name, kind, location):
        self.name = name
        self.kind = kind
        self.location = location

    @classmethod
    def from_yaml(cls, yaml):
        name = yaml["name"]
        kind = cls.Kind.from_yaml(yaml["kind"])
        location = Location.from_yaml(yaml["location"])

        return cls(name, kind, location)


class ExternalSymbol:
    """
    Represents an external symbol in the kernel that is requested by the user
    to be compared.
    This can be a function, global variable, module parameter or sysctl option.
    """
    class Kind(IntEnum):
        FUNCTION = 0
        GLOBAL_VAR = 1
        MODULE_PARAM = 2
        SYSCTL_OPT = 3

        @classmethod
        def from_yaml(cls, yaml):
            dictionary = {
                "function": cls.FUNCTION,
                "global-variable": cls.GLOBAL_VAR,
                "module-parameter": cls.MODULE_PARAM,
                "sysctl-option": cls.SYSCTL_OPT
            }
            return dictionary[yaml]

        def __str__(self):
            dictionary = {
                self.FUNCTION: "function",
                self.GLOBAL_VAR: "global variable",
                self.MODULE_PARAM: "module parameter",
                self.SYSCTL_OPT: "sysctl option"
            }
            return dictionary[self]

    def __init__(self, name, kind):
        self.name = name
        self.kind = kind

    def __eq__(self, other):
        return self.name == other.name and self.kind == other.kind

    def __hash__(self):
        return hash(self.name) ^ hash(str(self.kind))

    @classmethod
    def from_yaml(cls, yaml):
        name = yaml["name"]
        kind = cls.Kind.from_yaml(yaml["kind"])

        return cls(name, kind)


class Location:
    """Represents a line in a specific file in the kernel source code."""
    def __init__(self, filename, line):
        self.filename = filename
        self.line = line

    @classmethod
    def from_yaml(cls, yaml):
        filename = yaml["file"]
        line = int(yaml["line"])

        return cls(filename, line)

    def __str__(self):
        return self.filename + ":" + str(self.line)


class Difference:
    """
    Represents a difference in an internal symbol found by DiffKemp.
    """
    def __init__(self, symbol_old, symbol_new, diff, affected_symbols):
        self.symbol_old = symbol_old
        self.symbol_new = symbol_new
        self.diff = diff
        self.affected_symbols = affected_symbols

    @classmethod
    def from_yaml(cls, yaml):
        symbol_old = InternalSymbol(yaml["symbol"],
                                    InternalSymbol.Kind.from_yaml(
                                        yaml["diff-kind"]),
                                    Location.from_yaml(yaml["location-old"]))
        symbol_new = InternalSymbol(yaml["symbol"],
                                    InternalSymbol.Kind.from_yaml(
                                        yaml["diff-kind"]),
                                    Location.from_yaml(yaml["location-new"]))
        diff = yaml["diff"]
        affected_symbols = [Affection.from_yaml(aff)
                            for aff in yaml["affected-symbols"]]

        return cls(symbol_old, symbol_new, diff, affected_symbols)


class Affection:
    """
    Represents that a difference in an internal symbol has an effect on
    an external one or vice versa.
    """
    def __init__(self, symbol, callstack_old, callstack_new):
        self.symbol = symbol
        self.callstack_old = callstack_old
        self.callstack_new = callstack_new

    @classmethod
    def from_yaml(cls, yaml):
        symbol = ExternalSymbol.from_yaml(yaml["symbol"])
        callstack_old = [Call.from_yaml(call)
                         for call in yaml["callstack-old"]]
        callstack_new = [Call.from_yaml(call)
                         for call in yaml["callstack-new"]]

        return cls(symbol, callstack_old, callstack_new)


class Call:
    """
    Represents a call to a function or macro.
    """
    def __init__(self, symbol_name, location):
        self.symbol_name = symbol_name
        self.location = location

    @classmethod
    def from_yaml(cls, yaml):
        symbol_name = yaml["symbol"]
        location = Location(yaml["file"], int(yaml["line"]))

        return Call(symbol_name, location)


class HTMLGenerator:
    """
    Converts output from DiffKemp in YAML format into human-readable HTML.
    """
    bootstrap = ("https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/"
                 "bootstrap.min.css")
    main_page_title = "DiffKemp results"
    home_link_text = "go back"
    internal_symbol_heading = "differing symbols:"
    external_symbol_heading = "affected KABI symbols:"

    def __init__(self, input_dir, output_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir

    def _collect_differences(self, directory):
        """
        Parses all YAML files in the given directory into a map whose keys
        are symbols and values are Difference objects.
        """
        differences = dict()
        for filename in os.listdir(directory):
            with open(os.path.join(directory, filename), "r") as file:
                parsed_file = yaml.safe_load(file)
                difference = Difference.from_yaml(parsed_file)
                differences[difference.symbol_old.name] = difference

        return differences

    def _collect_external_symbols(self, differences):
        """
        Converts a symbol to Difference map to a map with ExternalSymbols
        as keys and Affection objects containing InternalSymbols that affect
        the ExternalSymbol as values.
        """
        external_symbol_map = dict()
        for difference in differences.values():
            for affection in difference.affected_symbols:
                external_symbol = affection.symbol

                if external_symbol not in external_symbol_map:
                    external_symbol_map[external_symbol] = []
                external_symbol_map[external_symbol].append(
                    Affection(difference.symbol_old, affection.callstack_old,
                              affection.callstack_new))

        return external_symbol_map

    def _difference_to_html(self, difference):
        """Converts a Difference object into HTML."""
        tag, text = self.tag, self.text

        with tag("h2"):
            text(difference.symbol_old.name)
        with tag("p"):
            with tag("a", href="index.html"):
                text(self.home_link_text)

        with tag("ul"):
            with tag("li"):
                text("kind: " + str(difference.symbol_old.kind))
            with tag("li"):
                text("old location: " + str(difference.symbol_old.location))
            with tag("li"):
                text("new location: " + str(difference.symbol_new.location))
            with tag("li"):
                text("difference: ")
                with tag("pre"):
                    text(difference.diff)
            with tag("li"):
                text("affects symbols:")
                with tag("ul"):
                    for affection in difference.affected_symbols:
                        with tag("li"):
                            self._affection_external_to_html(affection)

    def _affection_external_to_html(self, affection):
        """
        Converts an Affection object whose symbol is a ExternalSymbol into
        HTML.
        """
        tag, text = self.tag, self.text

        href = ("kabi/" + affection.symbol.name + "-" +
                str(affection.symbol.kind) + ".html")
        with tag("a", href=href):
            text(affection.symbol.name)
        with tag("ul"):
            with tag("li"):
                text("old callstack:")
                self._callstack_to_html(affection.callstack_old)
            with tag("li"):
                text("new callstack:")
                self._callstack_to_html(affection.callstack_new)

    def _affection_internal_to_html(self, affection):
        """
        Converts an Affection object whose symbol is a InternalSymbol into
        HTML.
        """
        tag, text = self.tag, self.text

        href = "../" + affection.symbol.name + ".html"
        with tag("a", href=href):
            text(affection.symbol.name)
        with tag("ul"):
            with tag("li"):
                text("location: " + str(affection.symbol.location))
            with tag("li"):
                text("old callstack:")
                self._callstack_to_html(affection.callstack_old)
            with tag("li"):
                text("new callstack:")
                self._callstack_to_html(affection.callstack_new)

    def _callstack_to_html(self, callstack):
        """Converts a callstack (i.e. a list of Call objects) into HTML."""
        tag, text = self.tag, self.text

        with tag("ul"):
            for call in callstack:
                with tag("li"):
                    text(call.symbol_name + " at " + str(call.location))

    def _external_symbol_to_html(self, symbol, affections):
        """
        Converts an external symbol to HTML, including links to pages of
        internal symbols affecting it.
        """
        tag, text = self.tag, self.text

        with tag("h2"):
            text(symbol.name)
        with tag("p"):
            with tag("a", href="../index.html"):
                text(self.home_link_text)

        with tag("ul"):
            with tag("li"):
                text("kind: " + str(symbol.kind))
            with tag("li"):
                text("affected by symbols:")
                with tag("ul"):
                    for affection in affections:
                        with tag("li"):
                            self._affection_internal_to_html(affection)

    def _generate_head(self):
        """Generates meta tags and the stylesheet link."""
        self.doc.stag("meta", charset="utf-8")
        self.doc.stag("link", rel="stylesheet", href=self.bootstrap)

    def _generate_internal_symbol_table(self, differences):
        """Generates a table listing all differences with links to them."""
        line, tag = self.doc.line, self.tag

        with tag("table", klass="table"):
            with tag("thead"):
                with tag("tr"):
                    line("th", "symbol", scope="col")
                    line("th", "kind", scope="col")
            with tag("tbody"):
                for difference in differences.values():
                    href = difference.symbol_old.name + ".html"
                    with tag("tr"):
                        with tag("td"):
                            line("a", difference.symbol_old.name, href=href)
                        line("td", difference.symbol_old.kind)

    def _generate_external_symbol_table(self, external_symbols):
        line, tag = self.doc.line, self.tag

        with tag("table", klass="table"):
            with tag("thead"):
                with tag("tr"):
                    line("th", "symbol", scope="col")
                    line("th", "kind", scope="col")
            with tag("tbody"):
                for symbol in external_symbols.keys():
                    href = ("kabi/" + symbol.name + "-" + str(symbol.kind) +
                            ".html")
                    with tag("tr"):
                        with tag("td"):
                            line("a", symbol.name, href=href)
                        line("td", symbol.kind)

    def generate(self):
        """
        Converts YAMLs in self.input_dir into HTML files and puts them into
        self.output_dir.
        """
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)
        kabi_output_dir = os.path.join(self.output_dir, "kabi")
        if not os.path.exists(kabi_output_dir):
            os.mkdir(kabi_output_dir)

        # Create pages with found differences.
        differences = self._collect_differences(self.input_dir)
        for difference in differences.values():
            self.doc, self.tag, self.text = Doc().tagtext()

            self.doc.asis('<!DOCTYPE html>')
            with self.tag("html", lang="en"):
                with self.tag("head"):
                    with self.tag("title"):
                        self.text(difference.symbol_old.name)
                    self._generate_head()
                with self.tag("body", klass="py-4"):
                    with self.tag("div", klass="container"):
                        self._difference_to_html(difference)

            with open(os.path.join(self.output_dir,
                                   difference.symbol_old.name + ".html"),
                      "w") as f:
                f.write(indent(self.doc.getvalue()))

        # Create pages with KABI symbols.
        external_symbols = self._collect_external_symbols(differences)
        for symbol, affections in external_symbols.items():
            self.doc, self.tag, self.text = Doc().tagtext()

            self.doc.asis('<!DOCTYPE html>')
            with self.tag("html", lang="en"):
                with self.tag("head"):
                    with self.tag("title"):
                        self.text(symbol.name)
                    self._generate_head()
                with self.tag("body", klass="py-4"):
                    with self.tag("div", klass="container"):
                        self._external_symbol_to_html(symbol, affections)

            with open(os.path.join(kabi_output_dir, symbol.name + "-" +
                                   str(symbol.kind) + ".html"),
                      "w") as f:
                f.write(indent(self.doc.getvalue()))

        # Create main page.
        self.doc, self.tag, self.text = Doc().tagtext()

        with self.tag("html", lang="en"):
            with self.tag("head"):
                with self.tag("title"):
                    self.text(self.main_page_title)
                self._generate_head()
            with self.tag("body", klass="py-4"):
                with self.tag("div", klass="container"):
                    with self.tag("h1"):
                        self.text(self.main_page_title)
                    with self.tag("ul"):
                        with self.tag("li"):
                            self.text(self.internal_symbol_heading)
                            self._generate_internal_symbol_table(differences)
                        with self.tag("li"):
                            self.text(self.external_symbol_heading)
                            self._generate_external_symbol_table(
                                external_symbols)

        with open(os.path.join(self.output_dir, "index.html"), "w") as f:
            f.write(indent(self.doc.getvalue()))


def run_from_cli():
    parser = argparse.ArgumentParser(description="Converts YAML files" +
                                     " generated by DiffKemp into " +
                                     "human-readable HTML pages.")
    parser.add_argument("input_dir", help="directory containing YAML files" +
                                          " generated by DiffKemp")
    parser.add_argument("output_dir", help="directory where the HTML output" +
                                           " will be generated")
    args = parser.parse_args()

    generator = HTMLGenerator(args.input_dir, args.output_dir)
    generator.generate()
