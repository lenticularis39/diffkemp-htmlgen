htmlgen_css = """
.diff-table pre {
    margin: 0;
}

.diff-table td.heading {
    text-align: center;
    vertical-align: middle;
    padding: .10rem;
    background-color: #f5f5f5;
}

.diff-table td.line {
    padding: 0;
    border-top: none;
    width: 50%;
}

.diff-table td.line.added {
    background-color: #e6ffed;
}

.diff-table td.line.removed {
    background-color: #ffeef0;
}

.diff-table td.line.empty {
    background-color: #f7f7f7;
}
"""


htmlgen_css_maxwidth = """
.container {
    max-width: 1500px;
}
"""
