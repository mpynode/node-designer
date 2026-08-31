"""Pure, read-only outline index for the Script tab.

Parses the node's ``_methodsSource`` (a FLAT module of top-level ``def``s -- there
is NO ``class`` block) ONCE and returns a flat, group-ordered list of
``OutlineItem`` rows describing each top-level def. Dependency-light
(``ast``/``warnings`` only -- NO Maya, NO Qt) and never execs user code: the
whole model is derived from a single static AST walk.

Group semantics (a def is a "method" when its first param is ``self``/``cls`` or
it carries ``@classmethod``/``@staticmethod``; otherwise it is a free function):

  * ``Module``     -- module-level free functions (not method-like).
  * ``Commands``   -- ``@maya_command``-flagged defs (runnable), PLUS the node
    type's command TEMPLATES when ``native_type`` is given: offers, not code,
    carrying their ``CommandTemplate`` on ``template`` and ``run_kind
    ="template"``. See :func:`_template_items`.
  * ``Demos``      -- ``@maya_demo``-flagged defs (runnable).
  * ``Setup``      -- the instance ``setup(self, ...)`` def (runnable). A setup
    carrying ``@maya_command(..., creates=True)`` stays HERE rather than moving
    to Commands, and its ``command_name`` field names the create command the
    compile will ship; see :func:`build_outline`.
  * ``Instance``   -- other instance (``self``-first) methods.
  * ``Classmethod``-- ``@classmethod`` / ``cls``-first factory methods.
  * ``Static``     -- ``@staticmethod`` defs.

The command/demo detectors are the single source of truth for those two groups;
a def already claimed by one is skipped in the plain funcdef pass so it is not
double-counted.

``kind`` strings are STABLE identifiers (used for grouping/sorting and matched by
callers). ``GROUP_LABELS`` maps each kind to the human label the UI shows, so the
display wording can change without disturbing the semantic ``kind``.
``ALWAYS_SHOWN_GROUPS`` is the subset the Script-tab outline renders even when
empty (as a "(none)" placeholder), so a user always sees the full taxonomy of
what they can author.
"""
import ast
import warnings
from collections import namedtuple

from mpynode._common.methods.maya_command import (
    detect_commands, detect_demos, detect_tests, _is_static_def,
    _is_instance_def, _is_factory_def,
)
# The SAME classifier methods_split.py uses -- one source of truth for
# class-bound vs module-level scope.
from mpynode._common.io.py_export import _classify_funcdef

OUTLINE_GROUPS = ("Module", "Commands", "Demos", "Test", "Setup", "Instance",
                  "Classmethod", "Static")

# Display label per stable ``kind``. Every OUTLINE_GROUPS entry must appear here
# (a test enforces coverage). "Module" reads as "Functions", and the three method
# kinds are spelled out so instance / class / static are distinguishable.
GROUP_LABELS = {
    "Module": "Functions",
    "Commands": "Commands",
    "Demos": "Demos",
    "Test": "Tests",
    "Setup": "Setup",
    "Instance": "Instance Methods",
    "Classmethod": "Class Methods",
    "Static": "Static Methods",
}

# Categories the outline ALWAYS renders, empty ones as a dimmed "(none)" row, so
# the full authoring surface stays discoverable. Trim to hide an empty state.
ALWAYS_SHOWN_GROUPS = OUTLINE_GROUPS

OutlineItem = namedtuple(
    "OutlineItem",
    "kind name lineno runnable run_kind command_name params template is_used",
)
# ``template`` / ``is_used`` default so every existing positional construction
# below (and in callers) keeps working unchanged.
OutlineItem.__new__.__defaults__ = (None, False)

# Template rows sort AFTER every real def in their group: they are offers, not
# code, and the source they would be interleaved with has no line for them.
_TEMPLATE_LINENO = 1 << 30


def _template_items(native_type, taken, def_names=frozenset()):
    """Command TEMPLATE rows for ``native_type``, marked used when the buffer
    already carries that command.

    A type's plain commands are deliberately NOT merged onto the node -- naming
    them is the user's decision, since two node types shipping one plain command
    name is refused at mega-compile. They are offered here instead, in the same
    Commands group, distinguished by ``template`` being set. Import is local and
    guarded: the outline model is Maya-free and must stay importable headless
    even if the seeds directory is missing.

    "Already carries" is the SAME two-part identity the rest of the stack uses:
    ``call_command`` resolves by either name (``methods_registry.py:478``,
    ``if command_name in (c["name"], c["func_name"])``), and the compile refuses
    BOTH a duplicate command name and a duplicate def name
    (``command_companion.py:269-281``). So ``def_names`` catches a template
    whose def is in the buffer under a renamed command, and ``taken`` catches
    one whose command name is claimed by a renamed def. Matching ``taken``
    ALONE made a template re-appear the moment the user renamed its command --
    the rename the template's own comment asks for -- while its ``def`` sat
    right there in the buffer.

    ``def_names`` defaults empty so the no-source call site stays valid; that
    path has no AST to harvest, and _rebuild_outline is QTimer-driven with no
    try/except, so a missing argument would raise on every keystroke."""
    if not native_type:
        return []
    try:
        from mpynode._common.node_setups import command_templates_for_type

        templates = command_templates_for_type(native_type)
    except Exception:
        return []
    out = []
    for i, t in enumerate(templates):
        used = t.func_name in def_names or t.name in taken
        out.append(OutlineItem(
            "Commands", t.name, _TEMPLATE_LINENO + i, False, "template",
            t.name, tuple(t.params), t, used))
    return out


def build_outline(source, native_type=None):
    """Parse ``source`` ONCE; return a flat ``list[OutlineItem]`` sorted by
    ``(group order, lineno)``. Return ``None`` on ``SyntaxError`` so callers keep
    their last-good outline. Never execs. Warnings from the command detector
    (non-literal decorator args) are suppressed.

    ``native_type`` is optional: pass it to have the node type's command
    TEMPLATES listed alongside the real commands (see :func:`_template_items`).
    Omitting it yields exactly the old, source-only outline."""
    if not source or not source.strip():
        return _template_items(native_type, frozenset())
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        commands = detect_commands(source, tree=tree)
        demos = detect_demos(source, tree=tree)
        tests = detect_tests(source, tree=tree)
    # A ``creates=True`` def named ``setup`` is BOTH the reserved setup hook and
    # a command. It stays in the Setup group with run_kind="setup": the Script
    # tab's Run must keep going through _RunSetupCommand, which passes
    # ``selection=``; _RunCommandCommand does not, so routing it there makes the
    # setup adopt nothing and silently succeed. The row still carries the
    # command NAME so the model can report what cmds.<name>() the compile ships.
    creates_setup = next(
        (c for c in commands
         if c.get("creates") and c["func_name"] == "setup"), None)
    # Only an EXPLICIT literal is reportable here. An un-named creates= command
    # takes the compiled node TYPE's name, which is bound during spec extraction
    # -- the outline is given source and nothing else, so it cannot know it and
    # must not guess (the un-resolved fallback is the def name, "setup", which
    # would be a lie).
    setup_cmd_name = (creates_setup["name"]
                      if creates_setup and creates_setup.get("name_explicit")
                      else None)
    cmd_funcs = {c["func_name"] for c in commands
                 if not (creates_setup is not None
                         and c["func_name"] == "setup")}
    demo_funcs = {d["func_name"] for d in demos}
    test_funcs = {t["func_name"] for t in tests}
    items = []
    for c in commands:
        if creates_setup is not None and c["func_name"] == "setup":
            continue        # emitted by the Setup branch below instead
        items.append(OutlineItem("Commands", c["name"], c["lineno"], True,
                                 "command", c["name"], tuple(c["params"])))
    for d in demos:
        items.append(OutlineItem("Demos", d["label"], d["lineno"], True,
                                 "demo", d["func_name"], ()))
    for t in tests:
        items.append(OutlineItem("Test", t["label"], t["lineno"], True,
                                 "test", t["func_name"], ()))
    for stmt in tree.body:
        if not isinstance(stmt, ast.FunctionDef):
            continue
        if (stmt.name in cmd_funcs or stmt.name in demo_funcs
                or stmt.name in test_funcs):
            continue
        is_method_like = _classify_funcdef(stmt)[0] == "class"
        if not is_method_like:
            items.append(OutlineItem("Module", stmt.name, stmt.lineno,
                                     False, None, None, ()))
        elif stmt.name == "setup" and _is_instance_def(stmt):
            items.append(OutlineItem("Setup", stmt.name, stmt.lineno,
                                     True, "setup", setup_cmd_name, ()))
        elif _is_static_def(stmt):
            items.append(OutlineItem("Static", stmt.name, stmt.lineno,
                                     False, None, None, ()))
        elif _is_factory_def(stmt):
            # @classmethod or a cls-first factory-by-convention. Checked AFTER
            # static (a @staticmethod is never a factory) and setup so those
            # keep their dedicated buckets; only leaves genuine class methods.
            items.append(OutlineItem("Classmethod", stmt.name, stmt.lineno,
                                     False, None, None, ()))
        else:
            items.append(OutlineItem("Instance", stmt.name, stmt.lineno,
                                     False, None, None, ()))
    # Built FRESH, not harvested from the funcdef loop above: that loop
    # ``continue``s past any def already claimed by a command, so for
    # ``@maya_command(name="x") def load_target_cmd`` it would be EMPTY --
    # exactly the case this set exists to catch. ``tree.body`` only, so a
    # nested or class-scoped def of the same name does NOT count.
    def_names = {stmt.name for stmt in tree.body
                 if isinstance(stmt, ast.FunctionDef)}
    items.extend(_template_items(
        native_type, {c["name"] for c in commands}, def_names))
    order = {g: i for i, g in enumerate(OUTLINE_GROUPS)}
    items.sort(key=lambda it: (order[it.kind], it.lineno))
    return items
