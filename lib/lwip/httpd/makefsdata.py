#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
#
# Regenerate the lwIP httpd recovery fsdata from the htdocs directory.
#
# The generated C file is what the recovery httpd serves: every page is stored
# as a byte array preceded by its name and a precomputed HTTP header.
# Regenerate instead of hand-editing so the pages and the image can never
# drift apart:
#
#   python3 lib/lwip/httpd/makefsdata.py
#
# The checked-in output is shared by every board that enables
# CONFIG_HTTPD_RECOVERY, so the pages must not contain board-specific text:
# the model is injected at run time from the /about endpoint.

import argparse
import pathlib
import sys

LWIP_VERSION = "2.2.0"

# File basenames that must be served with a status other than 200 OK.
STATUS_OVERRIDES = {
    "400": "400 Bad Request",
}


def symbol(name):
    return name.replace(".", "_").replace("-", "_")


def status_line(path):
    code = path.name.split(".")[0]
    text = STATUS_OVERRIDES.get(code)
    if text is None:
        text = "200 OK"
    return "HTTP/1.0 %s\r\n" % text


def header_comment(text, size, exact=True):
    suffix = " (%d bytes) */" % size if exact else " (%d+ bytes) */" % size
    return "/* \"%s\"%s" % (text, suffix)


def byte_lines(data, out):
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        out.append(",".join("0x%02x" % b for b in chunk) + ",")


def build_header(path, body):
    parts = []
    line = status_line(path)
    parts.append((header_comment(line, len(line)), line.encode("ascii")))

    server = ("Server: lwIP/%s (http://savannah.nongnu.org/projects/lwip)\r\n"
              % LWIP_VERSION)
    parts.append((header_comment(server, len(server)), server.encode("ascii")))

    length = "Content-Length: %d\r\n" % len(body)
    # The comment counts the fixed part only; the digit count varies.
    fixed = len(length) - len(str(len(body)))
    parts.append((header_comment(length, fixed, exact=False),
                  length.encode("ascii")))

    ctype = "Content-Type: text/html\r\n\r\n"
    parts.append((header_comment(ctype, len(ctype)), ctype.encode("ascii")))

    return parts


def name_area_size(path):
    size = len("/" + path.name) + 1
    while size % 4:
        size += 1
    return size


def render(files):
    out = []
    out.append("#include \"lwip/apps/fs.h\"")
    out.append("#include \"lwip/def.h\"")
    out.append("")
    out.append("")
    out.append("#define file_NULL (struct fsdata_file *) NULL")
    out.append("")
    out.append("")
    out.append("#ifndef FS_FILE_FLAGS_HEADER_INCLUDED")
    out.append("#define FS_FILE_FLAGS_HEADER_INCLUDED 1")
    out.append("#endif")
    out.append("#ifndef FS_FILE_FLAGS_HEADER_PERSISTENT")
    out.append("#define FS_FILE_FLAGS_HEADER_PERSISTENT 0")
    out.append("#endif")
    out.append("/* FSDATA_FILE_ALIGNMENT: 0=off, 1=by variable, 2=by include */")
    out.append("#ifndef FSDATA_FILE_ALIGNMENT")
    out.append("#define FSDATA_FILE_ALIGNMENT 0")
    out.append("#endif")
    out.append("#ifndef FSDATA_ALIGN_PRE")
    out.append("#define FSDATA_ALIGN_PRE")
    out.append("#endif")
    out.append("#ifndef FSDATA_ALIGN_POST")
    out.append("#define FSDATA_ALIGN_POST")
    out.append("#endif")
    out.append("#if FSDATA_FILE_ALIGNMENT==2")
    out.append("#include \"fsdata_alignment.h\"")
    out.append("#endif")

    for index, path in enumerate(files):
        out.append("#if FSDATA_FILE_ALIGNMENT==1")
        out.append("static const unsigned int dummy_align__%s = %d;"
                   % (symbol(path.name), index))
        out.append("#endif")

        body = path.read_bytes()
        name = "/" + path.name
        name_bytes = name.encode("ascii") + b"\0"
        area = name_area_size(path)

        sym = symbol(path.name)
        out.append("static const unsigned char FSDATA_ALIGN_PRE data__%s[] "
                   "FSDATA_ALIGN_POST = {" % sym)
        out.append("/* %s (%d chars) */" % (name, len(name_bytes)))
        byte_lines(name_bytes + b"\0" * (area - len(name_bytes)), out)
        out.append("")
        out.append("/* HTTP header */")
        for comment, payload in build_header(path, body):
            out.append(comment)
            byte_lines(payload, out)
        out.append("/* raw file data (%d bytes) */" % len(body))
        byte_lines(body, out)
        out[-1] = out[-1] + "};"
        out.append("")

    previous = "file_NULL"
    for path in files:
        sym = symbol(path.name)
        out.append("const struct fsdata_file file__%s[] = { {" % sym)
        out.append(previous + ",")
        out.append("data__%s," % sym)
        out.append("data__%s + %d," % (sym, name_area_size(path)))
        out.append("sizeof(data__%s) - %d," % (sym, name_area_size(path)))
        out.append("FS_FILE_FLAGS_HEADER_INCLUDED | "
                   "FS_FILE_FLAGS_HEADER_PERSISTENT,")
        out.append("}};")
        out.append("")
        previous = "file__%s" % sym

    if files:
        out.append("#define FS_ROOT file__%s" % symbol(files[-1].name))
    else:
        out.append("#define FS_ROOT file_NULL")
    out.append("#define FS_NUMFILES %d" % len(files))
    out.append("")

    # The checked-in fsdata uses CRLF line endings throughout.
    return "\r\n".join(out)


def main():
    here = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--htdocs", default=here / "htdocs_recovery",
                        type=pathlib.Path,
                        help="directory holding the recovery web pages")
    parser.add_argument("--output", default=here / "fsdata_recovery.c",
                        type=pathlib.Path,
                        help="fsdata C file to write")
    args = parser.parse_args()

    if not args.htdocs.is_dir():
        sys.exit("htdocs directory not found: %s" % args.htdocs)

    files = sorted((p for p in args.htdocs.iterdir() if p.is_file()),
                   key=lambda p: p.name)
    if not files:
        sys.exit("no files found in %s" % args.htdocs)

    text = render(files)
    # Write bytes: the embedded HTTP headers contain CRLF, and text mode
    # would translate them a second time on some platforms.
    data = text.encode("ascii")
    if args.output.exists() and args.output.read_bytes() == data:
        print("%s is already up to date" % args.output)
        return
    args.output.write_bytes(data)
    print("wrote %s (%d files)" % (args.output, len(files)))


if __name__ == "__main__":
    main()
