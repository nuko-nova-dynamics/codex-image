"""Main entrypoint for the codex-image skill.

Composes auth.py + api_client.py + sse_parser.py + naming.py + sidecar.py.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import api_client
import auth as auth_mod
import naming
import redact
import retry as retry_mod
import sidecar
import sse_parser

VERSION = "0.1.5"


class CodexCliError(RuntimeError):
    """Raised when the installed Codex CLI version cannot be detected."""


def _codex_image_home() -> Path:
    return Path(os.environ.get("CODEX_IMAGE_HOME") or (Path.home() / ".codex-image"))


def _sidecar_safe_ref(ref: str) -> str:
    """Compress data: URLs for sidecar storage; pass through paths and http(s) URLs."""
    if ref.startswith("data:") and ";base64," in ref:
        prefix, b64 = ref.split(",", 1)
        return f"{prefix},<redacted, len={len(b64)}>"
    return ref


def _maybe_show_banner(summary: dict) -> None:
    """Show first-use account banner once per session (or on workspace change).

    Marker file: $CODEX_IMAGE_HOME/session-banner-shown
    Reset conditions: account_id changed, or marker is older than 6 hours.
    """
    marker = _codex_image_home() / "session-banner-shown"
    now = time.time()
    if marker.exists():
        try:
            data = json.loads(marker.read_text())
            if data.get("account_id") == summary["account_id"]:
                ts = data.get("ts", 0)
                if now - ts < 6 * 3600:
                    return
        except Exception:
            pass
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"account_id": summary["account_id"], "ts": now}))
    print(f"⌘ Codex • {summary['email']} • {summary['plan']}", file=sys.stderr)
    print("  → switch workspace: codex logout && codex login", file=sys.stderr)


def _detect_codex_cli_version() -> str:
    """Run `codex --version` and return its version string.

    Backend gates model access by the `version:` header, so detection failures
    must stop rather than fabricating a possibly stale version.
    """
    import re
    import subprocess
    try:
        out = subprocess.run(
            ["codex", "--version"], capture_output=True, text=True, timeout=5, check=True,
        ).stdout
    except Exception as e:
        raise CodexCliError(
            "Codex CLI is required, but 'codex --version' failed. Install or update "
            "Codex, ensure 'codex' is on PATH, then verify with: codex --version"
        ) from e
    m = re.search(r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?)\b", out)
    if not m:
        raise CodexCliError(
            "Codex CLI is required, but 'codex --version' returned an unrecognized "
            "version. Update Codex, then verify with: codex --version"
        )
    return m.group(1)


def post_responses(
    *,
    body: dict,
    headers: dict[str, str],
    endpoint: str = api_client.DEFAULT_ENDPOINT,
    timeout: int = 300,
) -> str:
    """POST to the Codex backend, return the full SSE body as text.

    Uses urllib (stdlib only) to keep dependencies minimal.
    """
    data = json.dumps(body).encode()
    req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        e.body_text = body_text  # type: ignore[attr-defined]
        raise


def _post_with_error_handling(
    *, body: dict, headers: dict[str, str]
) -> tuple[str | None, int | None]:
    """POST + retry. Returns (sse_text, None) on success, or (None, exit_code) on terminal HTTP error.

    Centralises HTTPError reporting so all POST sites (initial call + empty-SSE
    retry) surface 401/4xx/5xx with a clean redacted message instead of a raw
    traceback.
    """
    try:
        sse = retry_mod.call_with_retries(
            lambda: post_responses(body=body, headers=headers)
        )
        return sse, None
    except urllib.error.HTTPError as e:
        msg = redact.redact_text(getattr(e, "body_text", str(e)))
        print(f"✗ HTTP {e.code}: {msg}", file=sys.stderr)
        if e.code == 401:
            print("→ Run: codex login", file=sys.stderr)
        return None, 1
    except urllib.error.URLError as e:
        msg = redact.redact_text(str(e))
        print(f"✗ Network error: {msg}", file=sys.stderr)
        return None, 1
    except TimeoutError as e:
        msg = redact.redact_text(str(e))
        print(f"✗ Request timed out: {msg}", file=sys.stderr)
        return None, 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    import validation

    p = argparse.ArgumentParser(
        prog="codex-image",
        description="Generate images with gpt-image-2 via ChatGPT OAuth.",
    )
    p.add_argument("prompt", help="Text prompt")

    # Image-tool params
    def _size_type(v: str) -> str:
        try:
            return validation.validate_size(v)
        except validation.SizeError as e:
            raise argparse.ArgumentTypeError(str(e)) from e
    p.add_argument("--size", type=_size_type,
                   default=os.environ.get("CODEX_IMAGE_SIZE", "1024x1024"))
    p.add_argument("--quality", default=os.environ.get("CODEX_IMAGE_QUALITY", "high"),
                   choices=["low", "medium", "high", "auto"])
    p.add_argument("--format", dest="output_format",
                   default=os.environ.get("CODEX_IMAGE_FORMAT", "png"),
                   choices=["png", "jpeg", "webp"])

    def _comp(name):
        def _t(v: str) -> int:
            try:
                return validation.validate_compression(int(v), name)
            except (ValueError, TypeError) as e:
                raise argparse.ArgumentTypeError(str(e)) from e
        return _t
    p.add_argument("--quality-jpeg", type=_comp("--quality-jpeg"), default=90)
    p.add_argument("--quality-webp", type=_comp("--quality-webp"), default=80)
    p.add_argument("--moderation", default="auto", choices=["auto", "low"])
    p.add_argument("--background", default="opaque", choices=["opaque", "auto"],
                   help="(transparent rejected by backend; use --transparent flag instead)")
    p.add_argument("--transparent", action="store_true",
                   help="Generate with chroma-key + post-process to RGBA (spec §8)")
    p.add_argument("--key-color", default="auto",
                   help="auto or hex like #00ff00")
    p.add_argument("--bg-tool", default="auto",
                   choices=["auto", "chroma", "adobe", "none"],
                   help="Post-process strategy (the calling agent orchestrates adobe/auto via SKILL.md)")
    p.add_argument("--edge-contract", type=int, default=None, metavar="PX",
                   help="Chroma removal: shrink the alpha edge by N px to kill key-color fringe (0-16)")
    p.add_argument("--edge-feather", type=float, default=None, metavar="RADIUS",
                   help="Chroma removal: soften the alpha edge; for stair-stepped edges on matte subjects (0-64)")

    # Orchestrator params
    p.add_argument("--orchestrator", default="gpt-5.5",
                   choices=["gpt-5.5", "gpt-5.4", "gpt-5.4-mini"])
    p.add_argument("--effort", default="xhigh",
                   choices=["low", "medium", "high", "xhigh"],
                   help="(minimal/none rejected by backend for image_gen)")

    # I/O
    p.add_argument("--out", default=None)
    p.add_argument("--out-dir", default=os.environ.get("CODEX_IMAGE_OUT_DIR", "./generated_images"))
    p.add_argument("--input", action="append", default=[],
                   help="Reference image (path/URL/data: URL). Repeatable, max 16 (gpt-image-2 model limit).")
    p.add_argument("--from-last", action="store_true",
                   help="Prepend ~/.codex-image/last.json image as a reference")
    p.add_argument("--no-meta", action="store_true")

    # Diagnostics
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--whoami", action="store_true",
                   help="Print account info and exit (no generation)")

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    # Reject impossible combos BEFORE auth/POST so users don't burn credits.
    if args.transparent and args.output_format == "jpeg":
        print("✗ --transparent + --format jpeg: JPEG does not support alpha. "
              "Use --format png or --format webp.", file=sys.stderr)
        return 1

    # 1. Auth
    auth_path = auth_mod.discover_auth_file()
    if auth_path is None:
        print("✗ Codex CLI not signed in. Run: codex login", file=sys.stderr)
        return 2
    try:
        af = auth_mod.load_auth(auth_path)
    except auth_mod.AuthError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2

    summary = auth_mod.summarize_account(af)

    if args.whoami:
        print("⌘ ChatGPT account info")
        print(f"  email:        {summary['email']}")
        print(f"  plan:         {summary['plan']}")
        print(f"  organization: {summary['organization_id'] or '(personal)'}")
        print(f"  account_id:   {summary['account_id']}")
        print(f"  auth file:    {summary['auth_file']}")
        if exp := summary.get("exp"):
            ts = datetime.fromtimestamp(exp, tz=timezone.utc)
            print(f"  token expiry: {ts.strftime('%Y-%m-%d %H:%M UTC')}")
        return 0

    _maybe_show_banner(summary)

    # 2. Build request
    if args.quality == "high":
        print("ℹ --quality high: OAuth route caps to medium (true high requires API key)",
              file=sys.stderr)

    import input_refs

    refs: list[str] = []
    if args.from_last:
        last_path = _codex_image_home() / "last.json"
        last = sidecar.load_last(last_path)
        if last is None:
            print("✗ --from-last: no last image (run a generation first, "
                  "or the saved pointer references a missing file)", file=sys.stderr)
            return 1
        refs.append(last["image_path"])

    for raw in args.input:
        refs.append(raw)

    # De-duplicate by canonical absolute path (or as-is for data: / http:)
    seen: set[str] = set()
    unique_refs: list[str] = []
    unique_originals: list[str] = []  # parallel list of user-supplied refs for sidecar
    for r in refs:
        key = str(Path(r).resolve()) if not r.startswith(("data:", "http")) else r
        if key in seen:
            continue
        seen.add(key)
        unique_refs.append(r)
        unique_originals.append(r)

    if len(unique_refs) > 16:
        print(f"✗ --input/--from-last combined would send {len(unique_refs)} references; "
              f"max is 16 (gpt-image-2 model limit). Drop some references.", file=sys.stderr)
        return 1

    resolved: list[str] = []
    for raw in unique_refs:
        try:
            resolved.append(input_refs.resolve_to_data_url(raw))
        except input_refs.InputRefError as e:
            print(f"✗ {e}", file=sys.stderr)
            return 1

    import subprocess

    import transparency

    effective_prompt = args.prompt
    is_transparent = bool(args.transparent)

    if is_transparent:
        # Preflight Pillow only when fall-through to chroma is possible
        if args.bg_tool in ("auto", "chroma"):
            try:
                transparency.require_pillow_or_die("--transparent (chroma fallback)")
            except transparency.ChromaKeyError as e:
                print(f"✗ {e}", file=sys.stderr)
                return 2

    if args.output_format == "webp":
        try:
            transparency.require_pillow_or_die("--format webp")
        except transparency.ChromaKeyError as e:
            print(f"✗ {e}", file=sys.stderr)
            return 2

    if is_transparent:
        key = (args.key_color if args.key_color != "auto"
               else transparency.pick_key_color(args.prompt))
        if msg := transparency.warn_subject_key_conflict(args.prompt, key):
            print(f"⚠ {msg}", file=sys.stderr)
        print("⚠ transparent: chroma-key workaround — not native model transparency",
              file=sys.stderr)
        effective_prompt = transparency.apply_chroma_key_suffix(args.prompt, key)

    body = api_client.build_body(
        prompt=effective_prompt,
        size=args.size,
        quality=args.quality,
        output_format=args.output_format,
        background=args.background,
        moderation=args.moderation,
        quality_jpeg=args.quality_jpeg,
        input_images=resolved or None,
        orchestrator_model=args.orchestrator,
        reasoning_effort=args.effort,
    )
    try:
        cli_version = _detect_codex_cli_version()
    except CodexCliError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    headers = api_client.build_headers(
        access_token=af.access_token,
        account_id=af.account_id,
        codex_cli_version=cli_version,
    )

    # 3. POST + parse
    started = time.monotonic()
    sse, exit_code = _post_with_error_handling(body=body, headers=headers)
    if sse is None:
        return exit_code or 1

    try:
        b64, source = sse_parser.extract_image_b64(sse)
    except sse_parser.ParseError as first_err:
        if "no image" not in str(first_err):
            print(f"✗ {redact.redact_text(str(first_err))}", file=sys.stderr)
            return 1
        if resolved:
            print("✗ Edit produced no image; re-run the edit to try again.", file=sys.stderr)
            return 1
        print("⚠ first call returned no image; retrying once…", file=sys.stderr)
        sse, exit_code = _post_with_error_handling(body=body, headers=headers)
        if sse is None:
            return exit_code or 1
        try:
            b64, source = sse_parser.extract_image_b64(sse)
        except sse_parser.ParseError as e:
            print(f"✗ {redact.redact_text(str(e))}", file=sys.stderr)
            return 1

    meta = sse_parser.extract_response_metadata(sse)

    if args.verbose:
        # meta values are server-derived; redact before printing (spec: token-safe diagnostics)
        print(f"  response_id      = {meta.get('response_id')}", file=sys.stderr)
        print(f"  resolved_size    = {meta.get('resolved_size')}", file=sys.stderr)
        print(f"  resolved_quality = {meta.get('resolved_quality')}", file=sys.stderr)
        if rp := meta.get("revised_prompt"):
            rp = redact.redact_text(rp)
            print(f"  revised_prompt   = {rp[:120]}{'…' if len(rp) > 120 else ''}", file=sys.stderr)
        if usage := meta.get("usage"):
            print(f"  usage            = {redact.redact_text(str(usage))}", file=sys.stderr)

    # 4. Save
    fname = naming.output_filename(args.prompt, args.output_format)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = naming.resolve_collision(out_dir / fname)
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
    import postprocess
    raw = base64.b64decode(b64)

    if is_transparent:
        # Resolve --bg-tool. The calling agent normally resolves auto/adobe upstream;
        # if we see auto here, fall through to chroma. adobe direct = error.
        effective_bg = args.bg_tool
        if effective_bg == "auto":
            effective_bg = "chroma"
        elif effective_bg == "adobe":
            print(
                "✗ --bg-tool=adobe must be resolved by the calling agent via MCP before "
                "invoking this script. Use --bg-tool=chroma here, or rely on SKILL.md's "
                "Adobe-availability check.",
                file=sys.stderr,
            )
            return 2

        # Stage to a temporary PNG so the chroma script gets PNG input.
        stage_path = target.with_suffix(".stage.png")
        stage_path.write_bytes(raw)

        if effective_bg == "chroma":
            script = Path(__file__).parent / "remove_chroma_key.py"
            cmd = [
                sys.executable, str(script),
                "--input", str(stage_path),
                "--out", str(stage_path),
                "--auto-key", "border",
                "--soft-matte",
                "--transparent-threshold", "12",
                "--opaque-threshold", "220",
                "--despill",
                "--force",
            ]
            if args.edge_contract is not None:
                cmd += ["--edge-contract", str(args.edge_contract)]
            if args.edge_feather is not None:
                cmd += ["--edge-feather", str(args.edge_feather)]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"⚠ chroma-key removal failed: {e.stderr}", file=sys.stderr)
                stage_path.unlink(missing_ok=True)
                return 1
        # effective_bg == "none": leave the chroma-keyed PNG as-is.

        # Convert (or move) to the final format/path.
        if args.output_format == "png":
            stage_path.replace(target)
        elif args.output_format == "webp":
            try:
                postprocess.save_image(
                    raw_bytes=stage_path.read_bytes(),
                    target_path=target,
                    format="webp",
                    webp_quality=args.quality_webp,
                )
            except postprocess.PostprocessError as e:
                print(f"✗ {e}", file=sys.stderr)
                stage_path.unlink(missing_ok=True)
                return 1
            stage_path.unlink(missing_ok=True)
    else:
        # Non-transparent: save directly via postprocess (handles png/jpeg/webp).
        try:
            postprocess.save_image(
                raw_bytes=raw,
                target_path=target,
                format=args.output_format,
                webp_quality=args.quality_webp,
            )
        except postprocess.PostprocessError as e:
            print(f"✗ {e}", file=sys.stderr)
            return 1

    elapsed = time.monotonic() - started

    # 5. Sidecar
    record = sidecar.GenerationRecord(
        image_path=str(target.absolute()),
        prompt=args.prompt,
        revised_prompt=meta.get("revised_prompt") or "",
        size=args.size,
        quality=args.quality,
        format=args.output_format,
        is_transparent=is_transparent,
        input_image=_sidecar_safe_ref(unique_originals[0]) if unique_originals else None,
        response_id=meta.get("response_id") or "",
        ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        account_id=af.account_id,
    )
    last_path = _codex_image_home() / "last.json"
    sidecar.write_record(record, last_path,
                         per_image=not args.no_meta, update_last=not args.no_meta)

    print(f"✓ {target}  ({target.stat().st_size} bytes, {elapsed:.1f}s, source={source})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
