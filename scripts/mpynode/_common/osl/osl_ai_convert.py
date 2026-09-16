"""osl_ai_convert -- AI-assisted mPyFile *Compute* -> OSL translator (the AI arm
of the hybrid mPyFile->OSL conversion feature; increment 2).

The deterministic transpiler (:mod:`mpynode._common.osl.osl_convert`) is a BOUNDED
idiom recognizer: it raises ``UnsupportedComputeError`` the moment the Compute
look-math leaves its grammar (e.g. the full colour-management pipeline:
``_load_linear_pixels`` + colour-space matrices + prefilter kernels). This module
is the fallback: it asks an LLM to translate the look-math into OSL, then
structurally + (optionally) compile-validates the result, doing ONE self-repair
round -- re-prompting the model with the rejection reason -- before giving up.

Design (mirrors the porter's one-shot ``complete_fn`` injection so this stays
Qt-free, Maya-free, and unit-testable with fakes):

* ``build_osl_prompt(compute, init, shader_name, prior_error=None) -> (system, user)``
  builds the translator prompt. ``prior_error`` carries the previous rejection
  (structural problem or compiler error) for the self-repair round.
* ``ai_convert_compute_to_osl(compute, init, shader_name, complete_fn,
  validate_fn=None, max_repair=1) -> str`` runs the loop. ``complete_fn(system,
  user) -> str`` is the LLM transport (the real one is ``porter._complete`` /
  ``porter.make_cli_complete_fn``); ``validate_fn(osl) -> (ok, error)`` is the
  compile check (the real one is ``osl_targets.validate_osl_via_arnold``, which
  must run on Maya's main thread). On exhaustion it raises
  :class:`OslAiConvertError`.

NOTHING here writes the ``.osl`` plug or touches Maya/Qt -- the caller persists
the returned string and owns threading.
"""

from __future__ import annotations


class OslAiConvertError(Exception):
    """Raised when the AI translation never produced acceptable OSL."""


# ---- Prompt ----
_SYSTEM = """\
You are an expert Open Shading Language (OSL) shader author. You translate the \
*Compute look-math* of a Maya "mPyFile" texture node (written in Python/numpy) \
into a single, self-contained OSL shader that reproduces the SAME look an \
offline renderer (Arnold) needs.

Rules:
- Output ONLY the OSL shader source. No prose, no explanation, no markdown \
fences.
- Write ONE complete shader: `shader <name>(<params>, output color outColor = \
color(0)) { ...; outColor = ...; }`.
- OSL is C-like, NOT Python. Use OSL builtins (texture, noise, sin, cos, pow, \
mix, ...). Declare typed variables; there is no numpy.
- Image sampling: when the Compute reads a file texture, expose a `string \
filename` parameter and sample with `texture(filename, u, 1.0 - v)` -- Maya's V \
is bottom-up and the Compute applies the same `1 - v` flip. OSL's texture() \
does its own filtering and colour management, so you do NOT re-implement the \
prefilter kernels or colour-space matrices; sample the texture and apply the \
remaining per-pixel look-math (modulation, scanlines, tints, etc.).
- Every value the Compute reads from `self.<x>` should become a shader parameter \
with the SAME name and a sensible default (e.g. `self.tIn` -> `float tIn = \
0.0`).
- Reproduce the modulation / colour math faithfully and always write the final \
colour to `outColor`.
- You have NO tools and NO file, shell, or codebase access: do NOT try to \
search or read files. Produce the complete shader directly from the look-math \
below, in a single response.
"""


def build_osl_prompt(compute_src, init_src, shader_name, prior_error=None):
    """Return ``(system, user)`` prompt strings for the translator."""
    parts = [
        "Translate this mPyFile node's Compute look-math into ONE OSL shader "
        "named `%s`." % (shader_name or "mpyfile_shader"),
        "",
        "=== Init tier (context only: helper defs, colour-space catalogue, "
        "look constants) ===",
        (init_src or "(none)").strip() or "(none)",
        "",
        "=== Compute tier (THE look-math to translate) ===",
        (compute_src or "").strip() or "(empty)",
    ]
    if prior_error:
        parts += [
            "",
            "=== Your previous OSL output was REJECTED ===",
            str(prior_error).strip(),
            "",
            "Fix the problem and output the corrected, complete OSL shader "
            "(source only, no fences, no prose).",
        ]
    return _SYSTEM, "\n".join(parts)


# ---- Output cleanup + structural gate ----
def _strip_fences(text):
    """Strip a leading/trailing markdown code fence (```osl ... ```)."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip("\n").strip()


def _structural_check(osl):
    """Cheap, renderer-free sanity gate. Returns ``(ok, error)``. This is NOT a
    compiler -- it only rejects output that is obviously not an OSL shader (e.g.
    the model apologising in prose), so a real compile error is surfaced by
    ``validate_fn`` instead of silently persisting garbage."""
    if not osl or not osl.strip():
        return False, "the output was empty"
    if "shader" not in osl:
        return False, "the output is not an OSL shader (no `shader` declaration)"
    open_b, close_b = osl.count("{"), osl.count("}")
    if open_b == 0 or open_b != close_b:
        return False, ("unbalanced braces (%d '{' vs %d '}') -- the shader body "
                       "is incomplete" % (open_b, close_b))
    if "outColor" not in osl:
        return False, "the shader never writes the required `outColor` output"
    return True, ""


# ---- The translate + validate + self-repair loop ----
def ai_convert_compute_to_osl(compute_src, init_src, shader_name, complete_fn,
                              validate_fn=None, max_repair=1, log_cb=None):
    """Translate ``compute_src`` to OSL via the injected ``complete_fn``.

    ``complete_fn(system, user) -> str``: the LLM transport (one-shot).
    ``validate_fn(osl) -> (ok, error)``: optional compile check; when omitted,
    the structural gate is the only acceptance test.
    ``max_repair``: number of self-repair rounds (default 1 => up to 2 LLM
    calls). Each rejected attempt re-prompts the model with the reason.
    ``log_cb(line)``: optional progress sink -- receives an "Attempt N/M ..."
    line per round and the rejection reason when an attempt is refused, so the
    UI's activity strip shows real progress instead of a silent multi-minute
    wait ("the log does not say much" fix). Never raises through log_cb.

    Returns the accepted OSL string. Raises :class:`OslAiConvertError` if no
    attempt is accepted within the budget, or if ``complete_fn`` itself errors
    (a transport failure is not a "fix your OSL" situation -- abort immediately).
    """
    def _log(msg):
        if log_cb is not None and msg:
            try:
                log_cb(msg)
            except Exception:
                pass

    total       = max_repair + 1
    prior_error = None
    last_error  = "no attempts were made"
    for i in range(total):
        _log("Attempt %d/%d: generating OSL%s..." % (
            i + 1, total, " (repair)" if prior_error else ""))
        system, user = build_osl_prompt(compute_src, init_src, shader_name,
                                        prior_error=prior_error)
        try:
            raw = complete_fn(system, user)
        except OslAiConvertError:
            raise
        except Exception as exc:
            # A provider/network error won't be fixed by re-prompting -- abort.
            raise OslAiConvertError(
                "AI provider call failed: %s" % exc) from exc

        osl = _strip_fences(raw)
        ok, why = _structural_check(osl)
        if not ok:
            prior_error = last_error = why
            _log("Attempt %d rejected: %s" % (i + 1, why))
            continue
        if validate_fn is None:
            _log("Attempt %d accepted." % (i + 1))
            return osl
        try:
            valid, verr = validate_fn(osl)
        except Exception as exc:
            # A validator that itself errors shouldn't mask the OSL; treat it as
            # "could not validate" and accept the structurally-sound OSL.
            _log("Attempt %d accepted (compile validation unavailable)."
                 % (i + 1))
            return osl
        if valid:
            _log("Attempt %d accepted (compiled)." % (i + 1))
            return osl
        prior_error = last_error = verr or "the OSL failed to compile"
        _log("Attempt %d rejected: %s" % (i + 1, prior_error))

    raise OslAiConvertError(
        "AI translation did not produce valid OSL after %d attempt(s): %s"
        % (total, last_error))
