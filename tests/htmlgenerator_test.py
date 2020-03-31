from diffkemp_htmlgen.htmlgen import *
import tempfile
import os
import pytest
from subprocess import call
import yaml
from yattag import Doc, indent


@pytest.fixture
def test_dir(request):
    """Gets the current test directory."""
    return request.fspath.dirname


@pytest.fixture
def htmlgen(test_dir):
    htmlgen = HTMLGenerator(os.path.join(test_dir, "differences"), "")
    htmlgen.doc, htmlgen.tag, htmlgen.text = Doc().tagtext()
    return htmlgen


@pytest.fixture
def difference():
    """A Difference object used for the purposes of testing."""
    location_old = Location("include/linux/slab.h", 541)
    location_new = Location("include/linux/slab.h", 578)
    symbol_old = InternalSymbol("kmalloc_node", InternalSymbol.Kind.FUNCTION,
                                location_old)
    symbol_new = InternalSymbol("kmalloc_node", InternalSymbol.Kind.FUNCTION,
                                location_new)
    diff = """
  *************** static __always_inline void *kmalloc_node(size_t size, gfp_t flags, int node)
  *** 544,546 ***
      if (__builtin_constant_p(size) &&
  !       size <= KMALLOC_MAX_CACHE_SIZE && !(flags & GFP_DMA)) {
          unsigned int i = kmalloc_index(size);
  --- 581,583 ---
      if (__builtin_constant_p(size) &&
  !       size <= KMALLOC_MAX_CACHE_SIZE) {
          unsigned int i = kmalloc_index(size);
  *************** static __always_inline void *kmalloc_node(size_t size, gfp_t flags, int node)
  *** 550,552 ***

  !       return kmem_cache_alloc_node_trace(kmalloc_caches[i],
                          flags, node, size);
  --- 587,590 ---

  !       return kmem_cache_alloc_node_trace(
  !               kmalloc_caches[kmalloc_type(flags)][i],
                          flags, node, size);
    """
    external_symbol = ExternalSymbol("__alloc_pages_nodemask",
                                     ExternalSymbol.Kind.FUNCTION)
    callstack_old = [Call("init_rescuer",
                          Location("kernel/workqueue.c", 4094))]
    callstack_new = [Call("init_rescuer",
                          Location("kernel/workqueue.c", 4117))]
    affection = Affection(external_symbol, callstack_old, callstack_new)
    difference = Difference(symbol_old, symbol_new, diff, [affection])
    return difference


def test__collect_differences(htmlgen):
    differences = htmlgen._collect_differences(htmlgen.input_dir)

    assert len(differences) == 1
    assert "kmalloc_node" in differences
    assert isinstance(differences["kmalloc_node"], Difference)


def test__collect_external_symbols(htmlgen, test_dir):
    with open(os.path.join(test_dir, "differences",
                           "kmalloc_node.diff.yaml"), "r") as diff_file:
        difference = Difference.from_yaml(
            yaml.safe_load(diff_file.read()))
        differences = {
            "kmalloc_node": difference
        }
        external_symbols = htmlgen._collect_external_symbols(differences)

        assert len(external_symbols.items()) == 1
        external_symbol, affections = list(external_symbols.items())[0]
        assert external_symbol.name == "__alloc_pages_nodemask"
        assert external_symbol.kind == ExternalSymbol.Kind.FUNCTION
        assert len(affections) == 1
        assert affections[0].symbol == difference.symbol_old
        assert (affections[0].callstack_old == difference.
                affected_symbols[0].callstack_old)
        assert (affections[0].callstack_new == difference.
                affected_symbols[0].callstack_new)


def test__difference_to_html(htmlgen, difference):
    htmlgen._difference_to_html(difference)
    html = indent(htmlgen.doc.getvalue())
    expected_html = """<h2>kmalloc_node</h2>
<p>
  <a href="index.html">go back</a>
</p>
<ul>
  <li>kind: function</li>
  <li>old location: include/linux/slab.h:541</li>
  <li>new location: include/linux/slab.h:578</li>
  <li>difference: <pre>
  *************** static __always_inline void *kmalloc_node(size_t size, gfp_t flags, int node)
  *** 544,546 ***
      if (__builtin_constant_p(size) &amp;&amp;
  !       size &lt;= KMALLOC_MAX_CACHE_SIZE &amp;&amp; !(flags &amp; GFP_DMA)) {
          unsigned int i = kmalloc_index(size);
  --- 581,583 ---
      if (__builtin_constant_p(size) &amp;&amp;
  !       size &lt;= KMALLOC_MAX_CACHE_SIZE) {
          unsigned int i = kmalloc_index(size);
  *************** static __always_inline void *kmalloc_node(size_t size, gfp_t flags, int node)
  *** 550,552 ***

  !       return kmem_cache_alloc_node_trace(kmalloc_caches[i],
                          flags, node, size);
  --- 587,590 ---

  !       return kmem_cache_alloc_node_trace(
  !               kmalloc_caches[kmalloc_type(flags)][i],
                          flags, node, size);
    </pre></li>
  <li>affects symbols:<ul><li><a href="kabi/__alloc_pages_nodemask-function.html">__alloc_pages_nodemask</a><ul><li>old callstack:<ul><li>init_rescuer at kernel/workqueue.c:4094</li></ul></li><li>new callstack:<ul><li>init_rescuer at kernel/workqueue.c:4117</li></ul></li></ul></li></ul></li>
</ul>"""
    assert html == expected_html


def test__affection_external_to_html(htmlgen, difference):
    affection = difference.affected_symbols[0]

    htmlgen._affection_external_to_html(affection)
    html = indent(htmlgen.doc.getvalue())
    expected_html = """<a href="kabi/__alloc_pages_nodemask-function.html">__alloc_pages_nodemask</a>
<ul>
  <li>old callstack:<ul><li>init_rescuer at kernel/workqueue.c:4094</li></ul></li>
  <li>new callstack:<ul><li>init_rescuer at kernel/workqueue.c:4117</li></ul></li>
</ul>"""
    assert html == expected_html


def test__affection_internal_to_html(htmlgen, difference):
    affections = htmlgen._collect_external_symbols(
        {"kmalloc_node": difference})
    affection = list(affections.values())[0][0]

    htmlgen._affection_internal_to_html(affection)
    html = indent(htmlgen.doc.getvalue())
    expected_html = """<a href="../kmalloc_node.html">kmalloc_node</a>
<ul>
  <li>location: include/linux/slab.h:541</li>
  <li>old callstack:<ul><li>init_rescuer at kernel/workqueue.c:4094</li></ul></li>
  <li>new callstack:<ul><li>init_rescuer at kernel/workqueue.c:4117</li></ul></li>
</ul>"""
    assert html == expected_html


def test__callstack_to_html(htmlgen, difference):
    callstack = difference.affected_symbols[0].callstack_old

    htmlgen._callstack_to_html(callstack)
    html = indent(htmlgen.doc.getvalue())
    expected_html = """<ul>
  <li>init_rescuer at kernel/workqueue.c:4094</li>
</ul>"""
    assert html == expected_html


def test__external_symbol_to_html(htmlgen, difference):
    external_symbols = htmlgen._collect_external_symbols(
        {"kmalloc_node": difference})
    external_symbol = list(external_symbols.keys())[0]
    affections = list(external_symbols.values())[0]

    htmlgen._external_symbol_to_html(external_symbol, affections)
    html = indent(htmlgen.doc.getvalue())
    expected_html = """<h2>__alloc_pages_nodemask</h2>
<p>
  <a href="../index.html">go back</a>
</p>
<ul>
  <li>kind: function</li>
  <li>affected by symbols:<ul><li><a href="../kmalloc_node.html">kmalloc_node</a><ul><li>location: include/linux/slab.h:541</li><li>old callstack:<ul><li>init_rescuer at kernel/workqueue.c:4094</li></ul></li><li>new callstack:<ul><li>init_rescuer at kernel/workqueue.c:4117</li></ul></li></ul></li></ul></li>
</ul>"""
    assert html == expected_html


def test__generate_head(htmlgen):
    htmlgen._generate_head()
    html = indent(htmlgen.doc.getvalue())
    expected_html = """<meta charset="utf-8" />
<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" />"""
    assert html == expected_html


def test__generate_internal_symbol_table(htmlgen, difference):
    htmlgen._generate_internal_symbol_table({"kmalloc_node": difference})
    html = indent(htmlgen.doc.getvalue())
    expected_html = """<table class="table">
  <thead>
    <tr>
      <th scope="col">symbol</th>
      <th scope="col">kind</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <a href="kmalloc_node.html">kmalloc_node</a>
      </td>
      <td>function</td>
    </tr>
  </tbody>
</table>"""
    assert html == expected_html


def test__generate_external_symbol_table(htmlgen, difference):
    external_symbols = htmlgen._collect_external_symbols(
        {"kmalloc_node": difference})

    htmlgen._generate_external_symbol_table(external_symbols)
    html = indent(htmlgen.doc.getvalue())
    expected_html = """<table class="table">
  <thead>
    <tr>
      <th scope="col">symbol</th>
      <th scope="col">kind</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <a href="kabi/__alloc_pages_nodemask-function.html">__alloc_pages_nodemask</a>
      </td>
      <td>function</td>
    </tr>
  </tbody>
</table>"""
    assert html == expected_html


def test_generate(test_dir):
    with tempfile.TemporaryDirectory() as tmpdir:
        htmlgen = HTMLGenerator(os.path.join(test_dir, "differences"),
                                os.path.join(tmpdir, "output_html"))
        htmlgen.generate()
        assert call(["diff", "-r", os.path.join(tmpdir, "output_html"),
                     os.path.join(test_dir, "output_html")]) == 0
