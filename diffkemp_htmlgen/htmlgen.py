import argparse
import os
import yaml
from diffkemp_htmlgen import css
from enum import IntEnum
from typing import List, Dict, Any, Union, Optional
from pygments import highlight, lexers  # type: ignore
from pygments.formatters.html import HtmlFormatter  # type: ignore
from yattag import Doc, indent  # type: ignore


class Location:
    """Represents a line in a specific file in the kernel source code."""
    def __init__(self, filename: str, line: int):
        self.filename = filename
        self.line = line

    @classmethod
    def from_yaml(cls, yaml: Dict[str, Any]) -> 'Location':
        filename = yaml["file"]
        line = int(yaml["line"])

        return cls(filename, line)

    def __str__(self) -> str:
        return self.filename + ":" + str(self.line)


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
        def from_yaml(cls, yaml: str) -> 'InternalSymbol.Kind':
            dictionary = {
                "function": cls.FUNCTION,
                "macro": cls.MACRO,
                "type": cls.TYPE
            }
            return dictionary[yaml]

        def __str__(self) -> str:
            dictionary = {
                self.FUNCTION: "function",
                self.MACRO: "macro",
                self.TYPE: "type"
            }
            return dictionary[self]

    def __init__(self, name: str, kind: 'InternalSymbol.Kind',
                 location: Location):
        self.name = name
        self.kind = kind
        self.location = location

    @classmethod
    def from_yaml(cls, yaml: Dict[str, Any]) -> 'InternalSymbol':
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
        def from_yaml(cls, yaml: str) -> 'ExternalSymbol.Kind':
            dictionary = {
                "function": cls.FUNCTION,
                "global-variable": cls.GLOBAL_VAR,
                "module-parameter": cls.MODULE_PARAM,
                "sysctl-option": cls.SYSCTL_OPT
            }
            return dictionary[yaml]

        def __str__(self) -> str:
            dictionary = {
                self.FUNCTION: "function",
                self.GLOBAL_VAR: "global variable",
                self.MODULE_PARAM: "module parameter",
                self.SYSCTL_OPT: "sysctl option"
            }
            return dictionary[self]

    def __init__(self, name: str, kind: 'ExternalSymbol.Kind'):
        self.name = name
        self.kind = kind

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExternalSymbol):
            return NotImplemented
        return self.name == other.name and self.kind == other.kind

    def __hash__(self) -> int:
        return hash(self.name) ^ hash(str(self.kind))

    @classmethod
    def from_yaml(cls, yaml: Dict[str, Any]) -> 'ExternalSymbol':
        name = yaml["name"]
        kind = cls.Kind.from_yaml(yaml["kind"])

        return cls(name, kind)


class Difference:
    """
    Represents a difference in an internal symbol found by DiffKemp.
    """
    def __init__(self,
                 symbol_old: InternalSymbol,
                 symbol_new: InternalSymbol,
                 diff: str,
                 affected_symbols: List['Affection']):
        self.symbol_old = symbol_old
        self.symbol_new = symbol_new
        self.diff = diff
        self.affected_symbols = affected_symbols

    @classmethod
    def from_yaml(cls, yaml: Dict[str, Any]) -> 'Difference':
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


class Call:
    """
    Represents a call to a function or macro.
    """
    def __init__(self, symbol_name: str, location: Location):
        self.symbol_name = symbol_name
        self.location = location

    @classmethod
    def from_yaml(cls, yaml: Dict[str, Any]) -> 'Call':
        symbol_name = yaml["symbol"]
        location = Location(yaml["file"], int(yaml["line"]))

        return Call(symbol_name, location)


class Affection:
    """
    Represents that a difference in an internal symbol has an effect on
    an external one or vice versa.
    """
    def __init__(self, symbol: Union[ExternalSymbol, InternalSymbol],
                 callstack_old: List[Call], callstack_new: List[Call]):
        self.symbol = symbol
        self.callstack_old = callstack_old
        self.callstack_new = callstack_new

    @classmethod
    def from_yaml(cls, yaml: Dict[str, Any]) -> 'Affection':
        symbol = ExternalSymbol.from_yaml(yaml["symbol"])
        callstack_old = [Call.from_yaml(call)
                         for call in yaml["callstack-old"]]
        callstack_new = [Call.from_yaml(call)
                         for call in yaml["callstack-new"]]

        return cls(symbol, callstack_old, callstack_new)


class Diff:
    """Represents a source code difference."""
    class Fragment:
        """
        Represents a diff fragment, i.e. a continuous section of corresponding
        lines in both modules.
        """
        def __init__(self, function_name: str,
                     start_line_left: int = -1,
                     start_line_right: int = -1):
            self.function_name = function_name
            self.start_line_left = start_line_left
            self.start_line_right = start_line_right
            self.lines_left: List[str] = []
            self.lines_right: List[str] = []

    def __init__(self, input: str):
        lines = input.split("\n")
        current_fragment = None
        state: Optional[str] = None
        self.fragments: List['Diff.Fragment'] = []

        for line in lines:
            sline = line.lstrip()

            if sline.startswith("*************** "):
                # New fragment.
                current_fragment = Diff.Fragment(
                    sline[len("*************** "):])
                self.fragments.append(current_fragment)
                continue

            if current_fragment is None:
                raise ValueError("Invalid diff format")

            if sline.startswith("***"):
                # Start and end of left diff.
                line_nums = sline[len("*** "):-len(" ***")]
                current_fragment.start_line_left = int(
                    line_nums.split(",")[0])
                state = "left_line"
                offset = len(line) - len(sline)
                continue

            if sline.startswith("---"):
                # Start and end of right diff.
                line_nums = sline[len("--- "):-len(" ---")]
                current_fragment.start_line_right = int(
                    line_nums.split(",")[0])
                state = "right_line"
                offset = len(line) - len(sline)
                continue

            if state is None:
                raise ValueError("Invalid diff format")

            if state == "left_line":
                current_fragment.lines_left.append(line[offset:])
            if state == "right_line":
                current_fragment.lines_right.append(line[offset:])


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
    htmlgen_style = "htmlgen.css"
    pygments_style = "pygments.css"

    def __init__(self, input_dir: str, output_dir: str,
                 graphical_diff: bool = False, highlight_syntax: bool = False):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.graphical_diff = graphical_diff
        self.highlight_syntax = highlight_syntax
        self.lexer = lexers.get_lexer_by_name("c", stripnl=False)
        self.formatter = HtmlFormatter()

    def _format_source(self, text: str) -> None:
        """
        Formats C code using pre and highlights it if highlighting is enabled.
        """
        if not self.highlight_syntax:
            # Do not highlight syntax, use a simple pre block instead.
            with self.tag("pre"):
                self.text(text)
            return

        txt = highlight(text, self.lexer, self.formatter).rstrip()

        # Replace spaces outside tags with &#32; and EOLs with &#10; to protect
        # them from yattag's indent function, which would otherwise destroy
        # them.
        txt_parsed = []
        tags = 0
        for ch in txt:
            if ch == "<":
                tags += 1
            elif ch == ">":
                tags -= 1
            if ch == " " and tags == 0:
                txt_parsed.append("&#32;")
            elif ch == "\n" and tags == 0:
                txt_parsed.append("&#10;")
            else:
                txt_parsed.append(ch)

        self.doc.asis("".join(txt_parsed))

    def _collect_differences(self, directory: str) -> Dict[str, Difference]:
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

    def _collect_external_symbols(self, differences: Dict[str, Difference])\
            -> Dict[ExternalSymbol, List[Affection]]:
        """
        Converts a symbol to Difference map to a map with ExternalSymbols
        as keys and Affection objects containing InternalSymbols that affect
        the ExternalSymbol as values.
        """
        external_symbol_map: Dict[ExternalSymbol, List[Affection]] = dict()
        for difference in differences.values():
            for affection in difference.affected_symbols:
                external_symbol = affection.symbol
                assert isinstance(external_symbol, ExternalSymbol)

                if external_symbol not in external_symbol_map:
                    external_symbol_map[external_symbol] = []
                external_symbol_map[external_symbol].append(
                    Affection(difference.symbol_old, affection.callstack_old,
                              affection.callstack_new))

        return external_symbol_map

    def _difference_to_html(self, difference: Difference) -> None:
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
                self._diff_to_html(difference.diff.strip())
            with tag("li"):
                text("affects symbols:")
                with tag("ul"):
                    for affection in difference.affected_symbols:
                        with tag("li"):
                            self._affection_external_to_html(affection)

    def _affection_external_to_html(self, affection: Affection) -> None:
        """
        Converts an Affection object whose symbol is a ExternalSymbol into
        HTML.
        """
        tag, text = self.tag, self.text
        if not isinstance(affection.symbol, ExternalSymbol):
            raise ValueError("Affection not external")

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

    def _affection_internal_to_html(self, affection: Affection) -> None:
        """
        Converts an Affection object whose symbol is a InternalSymbol into
        HTML.
        """
        tag, text = self.tag, self.text
        if not isinstance(affection.symbol, InternalSymbol):
            raise ValueError("Incorrent affection type")

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

    def _callstack_to_html(self, callstack: List[Call]) -> None:
        """Converts a callstack (i.e. a list of Call objects) into HTML."""
        tag, text = self.tag, self.text

        with tag("ul"):
            for call in callstack:
                with tag("li"):
                    text(call.symbol_name + " at " + str(call.location))

    def _external_symbol_to_html(
            self, symbol: ExternalSymbol,
            affections: List[Affection]) -> None:
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

    def _diff_to_html(self, diff_str: str) -> None:
        """Converts a diff to a graphical representation."""
        tag = self.tag

        if not self.graphical_diff:
            # Use the original diff output.
            self._format_source(diff_str)
            return

        def format(line: int) -> str:
            return "{:4}".format(line)

        with tag("table", klass="table diff-table"):
            diff = Diff(diff_str)
            for fragment in diff.fragments:
                # Heading
                with tag("tr"):
                    with tag("td", klass="heading", colspan="2"):
                        self._format_source(fragment.function_name)
                # The actual diff
                index_left = 0
                index_right = 0
                while (index_left < len(fragment.lines_left) or
                       index_right < len(fragment.lines_right)):
                    line_idx_left = fragment.start_line_left + index_left
                    line_idx_right = fragment.start_line_right + index_right

                    if index_left < len(fragment.lines_left):
                        line_left = fragment.lines_left[index_left]
                    else:
                        line_left = ""
                    if index_right < len(fragment.lines_right):
                        line_right = fragment.lines_right[index_right]
                    else:
                        line_right = ""

                    if (line_left.startswith("!") and
                            line_right.startswith("!")):
                        with tag("tr"):
                            with tag("td", klass="line removed"):
                                self._format_source(" " + format(line_idx_left)
                                                    + " - " + line_left[1:])
                            with tag("td", klass="line added"):
                                self._format_source(" " +
                                                    format(line_idx_right) +
                                                    " + " + line_right[1:])
                        index_left += 1
                        index_right += 1
                        continue

                    if len(line_left) and line_left[0] in ["!", "-"]:
                        with tag("tr"):
                            with tag("td", klass="line removed"):
                                self._format_source(" " +
                                                    format(line_idx_left) +
                                                    " - " + line_left[1:])
                            with tag("td", klass="line empty"):
                                pass
                        index_left += 1
                        continue

                    if len(line_right) and line_right[0] in ["!", "+"]:
                        with tag("tr"):
                            with tag("td", klass="line empty"):
                                pass
                            with tag("td", klass="line added"):
                                self._format_source(" " +
                                                    format(line_idx_right) +
                                                    " + " + line_right[1:])
                        index_right += 1
                        continue

                    # Handle cases when the context line is only on one side.
                    if index_left >= len(fragment.lines_left):
                        with tag("td", klass="line"):
                            self._format_source(" " + format(line_idx_left) +
                                                "  " + line_right)
                        with tag("td", klass="line"):
                            self._format_source(" " + format(line_idx_right) +
                                                "  " + line_right)
                        index_left += 1
                        index_right += 1
                        continue
                    if index_right >= len(fragment.lines_right):
                        with tag("td", klass="line"):
                            self._format_source(" " + format(line_idx_left) +
                                                "  " + line_left)
                        with tag("td", klass="line"):
                            self._format_source(" " + format(line_idx_right) +
                                                "  " + line_left)
                        index_left += 1
                        index_right += 1
                        continue

                    # Regular line (diff context)
                    with tag("tr"):
                        with tag("td", klass="line"):
                            self._format_source(" " + format(line_idx_left) +
                                                "  " + line_left)
                        with tag("td", klass="line"):
                            self._format_source(" " + format(line_idx_right) +
                                                "  " + line_right)

                    index_left += 1
                    index_right += 1

    def _generate_head(self, path: str = "") -> None:
        """Generates meta tags and the stylesheet link."""
        self.doc.stag("meta", charset="utf-8")
        self.doc.stag("link", rel="stylesheet", href=self.bootstrap)
        self.doc.stag("link", rel="stylesheet",
                      href=os.path.join(path, self.pygments_style))
        self.doc.stag("link", rel="stylesheet",
                      href=os.path.join(path, self.htmlgen_style))

    def _generate_internal_symbol_table(
            self, differences: Dict[str, Difference]) -> None:
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

    def _generate_external_symbol_table(
            self,
            external_symbols: Dict[ExternalSymbol, List[Affection]]) -> None:
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

    def generate(self) -> None:
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
                    self._generate_head(path="..")
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

        # Create index page.
        with open(os.path.join(self.output_dir, "index.html"), "w") as f:
            f.write(indent(self.doc.getvalue()))

        # Generate pygments style.
        with open(os.path.join(self.output_dir, self.pygments_style),
                  "w") as f:
            style = self.formatter.get_style_defs('.highlight').split("\n")
            # Remove lines with background-color since we want to set that
            # separately.
            style = list(filter(lambda x: "background:" not in x, style))
            f.write("\n".join(style))

        # Write htmlgen style.
        with open(os.path.join(self.output_dir, self.htmlgen_style),
                  "w") as f:
            f.write(css.htmlgen_css)
            if self.graphical_diff:
                f.write(css.htmlgen_css_maxwidth)


def run_from_cli() -> None:
    parser = argparse.ArgumentParser(description="Converts YAML files" +
                                     " generated by DiffKemp into " +
                                     "human-readable HTML pages.")
    parser.add_argument("input_dir", help="directory containing YAML files" +
                                          " generated by DiffKemp")
    parser.add_argument("output_dir", help="directory where the HTML output" +
                                           " will be generated")
    parser.add_argument("--graphical-diffs", help="parse and format diffs",
                        action="store_true")
    parser.add_argument("--highlight-syntax",
                        help="enable diff syntax highlighting",
                        action="store_true")
    args = parser.parse_args()

    generator = HTMLGenerator(args.input_dir, args.output_dir,
                              args.graphical_diffs, args.highlight_syntax)
    generator.generate()
