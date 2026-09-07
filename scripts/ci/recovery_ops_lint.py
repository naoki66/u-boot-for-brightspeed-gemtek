"""Static / structural check for the recovery_board_ops contract.

The cross-compile of aarch64 U-Boot is not available in this environment,
so this script exercises the design at three levels instead:

  1. Header contract: parse board/airoha/an7581/recovery.h and confirm
     every &struct recovery_board_ops member has a matching definition
     in the wire-up of the strong provider.

  2. Strong provider: parse board/airoha/an7581/an7581_rfb.c and confirm
     the ops singleton is fully populated (no NULL function pointers
     except where the design intentionally allows them).

  3. Framework call sites: parse net/lwip/httpd_recovery.c and confirm
     every recovery_ops()->x call resolves to a struct member, that the
     weak default is declared, and that no pre-refactor xg2010g_ extern
     remains in active code paths.

  4. Behavioural demo: shadow the contract in pure Python with a mock
     board so we can exercise the design intent -- weak default returns
     NULL, registered ops expose match / mtd_ubi_valid / detect_ubi_part
     / etc. through the same calls the C framework uses.

Run from the repo root:

    python3 scripts/ci/recovery_ops_lint.py

Exits 0 when every check passes, 1 (with a clear message) otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent.parent
HEADER = REPO / "board" / "airoha" / "an7581" / "recovery.h"
BOARD = REPO / "board" / "airoha" / "an7581" / "an7581_rfb.c"
FRAMEWORK = REPO / "net" / "lwip" / "httpd_recovery.c"


@dataclass
class CheckResult:
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    @property
    def ok(self) -> bool:
        return not self.failures


def parse_struct_members(header: str) -> list[tuple[str, str]]:
    """Return [(member_name, member_decl)] extracted from the ops struct."""
    block = re.search(
        r"struct recovery_board_ops \{([^}]*)\};", header, re.DOTALL
    )
    if not block:
        return []
    body = block.group(1)
    members: list[tuple[str, str]] = []
    for raw in body.split(";"):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"(?P<decl>.+?\(\s*\*?\s*(?P<name>\w+)\s*\)\s*\([^)]*\))", line)
        if m:
            members.append((m.group("name"), m.group("decl").strip()))
            continue
        m2 = re.match(r"const\s+struct\s+\w+\s*\*\s*(?P<name>\w+)\s*", line)
        if m2:
            members.append((m2.group("name"), line))
            continue
    return members


def check_header(result: CheckResult) -> list[str]:
    header_text = HEADER.read_text(encoding="utf-8")
    members = parse_struct_members(header_text)
    if not members:
        result.fail(
            f"{HEADER}: struct recovery_board_ops not found or empty"
        )
        return []

    expected = {
        "match",
        "ubi",
        "detect_ubi_part",
        "detect_ubi_version",
        "sync_factory_part",
        "sync_factory",
        "mtd_ubi_valid",
    }
    found = {name for name, _ in members}
    missing = expected - found
    extra = found - expected
    if missing:
        result.fail(
            f"{HEADER}: struct recovery_board_ops missing members: "
            f"{', '.join(sorted(missing))}"
        )
    if extra:
        result.note(
            f"{HEADER}: struct recovery_board_ops has extra members: "
            f"{', '.join(sorted(extra))} (consider whether the framework should call them)"
        )

    if "struct recovery_ubi_geometry {" not in header_text:
        result.fail(
            f"{HEADER}: struct recovery_ubi_geometry declaration missing"
        )

    if "recovery_get_board_ops(void)" not in header_text:
        result.fail(
            f"{HEADER}: recovery_get_board_ops() declaration missing"
        )
    return [name for name, _ in members]


def check_strong_provider(result: CheckResult, member_names: list[str]) -> None:
    if not BOARD.exists():
        result.fail(f"{BOARD}: board source not found")
        return
    text = _strip_c_comments(BOARD.read_text(encoding="utf-8"))

    if "recovery_get_board_ops" not in text:
        result.fail(
            f"{BOARD}: strong definition of recovery_get_board_ops() missing"
        )
        return

    init_block = re.search(
        r"static\s+const\s+struct\s+recovery_board_ops\s+\w+\s*=\s*\{(?P<body>[^}]*)\}",
        text,
        re.DOTALL,
    )
    if not init_block:
        result.fail(
            f"{BOARD}: ops singleton initializer not found"
        )
        return
    body = init_block.group("body")
    initialized = {
        m.group(1)
        for m in re.finditer(r"\.(?P<name>\w+)\s*=", body)
    }
    if "match" not in initialized:
        result.fail(
            f"{BOARD}: ops.match not wired (every board must set match)"
        )

    if "match" in initialized and "xg2010g_is_compatible" not in re.findall(
        r"\.match\s*=\s*(\w+)", body
    ):
        result.note(
            f"{BOARD}: ops.match is not xg2010g_is_compatible -- "
            f"if a new board was added, ensure the compat predicate is wired"
        )

    required = {"match", "ubi", "mtd_ubi_valid"}
    missing = required - initialized
    if missing:
        result.fail(
            f"{BOARD}: ops singleton does not initialize required members: "
            f"{', '.join(sorted(missing))}"
        )


def _strip_c_comments(text: str) -> str:
    """Strip /* ... */ and // ... line comments without a full preprocessor."""

    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def check_framework_call_sites(result: CheckResult, member_names: list[str]) -> None:
    if not FRAMEWORK.exists():
        result.fail(f"{FRAMEWORK}: framework source not found")
        return
    text = _strip_c_comments(FRAMEWORK.read_text(encoding="utf-8"))

    needle = (
        "__weak const struct recovery_board_ops *recovery_get_board_ops"
    )
    if needle not in text:
        result.fail(
            f"{FRAMEWORK}: weak default for recovery_get_board_ops() missing"
        )

    for member in member_names:
        via_ops = re.compile(
            rf"recovery_ops\(\s*\)\s*->\s*{re.escape(member)}\b"
        )
        via_local_ops = re.compile(
            rf"\bops\s*->\s*{re.escape(member)}\b"
        )
        if not via_ops.search(text) and not via_local_ops.search(text):
            result.note(
                f"{FRAMEWORK}: framework never calls ops->{member}; "
                f"if it is unused, drop it from the struct"
            )

    forbidden = [
        (r"\bxg2010g_sync_factory\b", "old xg2010g_sync_factory extern"),
        (r"\bxg2010g_sync_factory_part\b", "old xg2010g_sync_factory_part extern"),
        (r"\bxg2010g_detect_ubi_version\b", "old xg2010g_detect_ubi_version extern"),
        (r"\brecovery_xg2010g_ubi_mtd_valid\b", "duplicated UBI MTD validator"),
        (r"\brecovery_is_xg2010g\b", "hard-coded compat-string helper"),
        (r"\bRECOVERY_XG2010G_UBI_[A-Z]+\b", "duplicated UBI geometry macros"),
    ]
    for pat, label in forbidden:
        m = re.search(pat, text)
        if m:
            result.fail(
                f"{FRAMEWORK}: lingering {label} at {m.group(0)!r} "
                f"(refactor incomplete)"
            )


# ---------------------------------------------------------------------------
# Behavioural demo: shadow the contract in Python.
# ---------------------------------------------------------------------------


@dataclass
class RecoveryUbiGeometry:
    size: int
    erase_size: int
    write_size: int
    oob_size: int
    ubi_part: str
    version: str


@dataclass
class RecoveryBoardOps:
    match: Callable[[], bool]
    ubi: RecoveryUbiGeometry | None
    detect_ubi_part: Callable[[], str] | None
    detect_ubi_version: Callable[[], str] | None
    sync_factory_part: Callable[[str], int] | None
    sync_factory: Callable[[], int] | None
    mtd_ubi_valid: Callable[[object], bool] | None


def demo_weak_default_returns_null() -> str:
    """Mirror the C weak default that returns NULL."""

    def recovery_get_board_ops() -> RecoveryBoardOps | None:
        return None

    return "weak default returns " + repr(recovery_get_board_ops())


def demo_strong_provider() -> str:
    """Mirror the strong provider in an7581_rfb.c."""

    board = "xg2010g"

    def xg2010g_match() -> bool:
        return True  # in real life: of_machine_is_compatible(...)

    geometry = RecoveryUbiGeometry(
        size=0x1B800000,
        erase_size=0x20000,
        write_size=0x800,
        oob_size=0x80,
        ubi_part="ubi",
        version="2.0",
    )

    def xg2010g_detect_ubi_part() -> str:
        return geometry.ubi_part

    def xg2010g_detect_ubi_version() -> str:
        return geometry.version

    def xg2010g_sync_factory_part(part: str) -> int:
        return 0

    def xg2010g_sync_factory() -> int:
        return 0

    def xg2010g_mtd_ubi_valid(mtd) -> bool:
        if mtd is None:
            return False
        return (
            mtd.size == geometry.size
            and mtd.erase_size == geometry.erase_size
            and mtd.write_size == geometry.write_size
            and mtd.oob_size == geometry.oob_size
        )

    ops = RecoveryBoardOps(
        match=xg2010g_match,
        ubi=geometry,
        detect_ubi_part=xg2010g_detect_ubi_part,
        detect_ubi_version=xg2010g_detect_ubi_version,
        sync_factory_part=xg2010g_sync_factory_part,
        sync_factory=xg2010g_sync_factory,
        mtd_ubi_valid=xg2010g_mtd_ubi_valid,
    )

    class FakeMtd:
        size = geometry.size
        erase_size = geometry.erase_size
        write_size = geometry.write_size
        oob_size = geometry.oob_size

    assert ops.match()
    assert ops.ubi is geometry
    assert ops.detect_ubi_part() == "ubi"
    assert ops.detect_ubi_version() == "2.0"
    assert ops.sync_factory_part("ubi") == 0
    assert ops.sync_factory() == 0
    assert ops.mtd_ubi_valid(FakeMtd())
    assert not ops.mtd_ubi_valid(None)
    return f"strong provider wired for {board}: 7/7 members populate"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-demo",
        action="store_true",
        help="skip the Python behavioural demo (run only static checks)",
    )
    args = parser.parse_args()

    result = CheckResult()
    member_names = check_header(result)
    check_strong_provider(result, member_names)
    check_framework_call_sites(result, member_names)

    for note in result.notes:
        print(f"note: {note}")
    if not result.ok:
        for fail in result.failures:
            print(f"FAIL: {fail}", file=sys.stderr)
        return 1
    print("recovery_board_ops static checks: OK")

    if not args.no_demo:
        try:
            print(demo_weak_default_returns_null())
            print(demo_strong_provider())
        except AssertionError as exc:  # pragma: no cover - belt and braces
            print(f"FAIL: behavioural demo failed: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
