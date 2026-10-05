# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import re
import sys
import argparse
import subprocess

# Trailers recognised anywhere in the message, not only in the trailing block.
TRAILER_PREFIXES = (
    "signed-off-by:",
    "co-authored-by:",
    "co-developed-by:",
    "reviewed-by:",
    "acked-by:",
    "tested-by:",
    "assisted-by:",
)

# A trailer (a.k.a. pseudo-header) is a "Token: value" line, where the token is
# made of letters, digits and dashes.  This mirrors git's own definition -- see
# git-interpret-trailers(1) -- so that project-specific trailers such as
# Assisted-by:, Change-Id:, Fixes: or Closes: are accepted without each having
# to be listed in TRAILER_PREFIXES above.
TRAILER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:(?:\s|$)")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Validate commit messages using local Git history (no API/token)."
    )
    parser.add_argument(
        "--base", required=True, help="Base SHA for the range (base..head)"
    )
    parser.add_argument(
        "--head", required=True, help="Head SHA for the range (or single ref)"
    )
    parser.add_argument("--body-limit", type=int, default=72)
    parser.add_argument("--sub-limit", type=int, default=72)
    parser.add_argument("--check-blank-line", type=str, default="true")
    parser.add_argument("--strict-line-length-check", type=str, default="true")
    parser.add_argument("--allow-empty-body", type=str, default="false")
    return parser.parse_args()


def fetch_commits(base, head):
    """
    Fetch commits between base..head from local repository.
    Returns a list of dicts with 'sha' and 'message' keys.
    """
    if not head:
        print("::error::Tokenless mode requires --head (and usually --base).")
        sys.exit(2)

    rev_range = f"{base}..{head}" if base else head
    try:
        shas = (
            subprocess.check_output(
                ["git", "rev-list", "--no-merges", rev_range], text=True
            )
            .strip()
            .splitlines()
        )
        if not shas:
            return []
        output = subprocess.check_output(
            ["git", "show", "-s", "--format=%H%x00%B%x00"] + shas, text=True
        )
        commits = []
        parts = output.split("\x00")
        for i in range(0, len(parts) - 1, 2):
            sha = parts[i].strip()
            message = parts[i + 1] if i + 1 < len(parts) else ""
            if sha:
                commits.append({"sha": sha, "message": message})
        return commits

    except subprocess.CalledProcessError as e:
        print(f"::error::Failed to fetch commits with git: {e}")
        sys.exit(2)


def is_trailer(line):
    """Return True if the line looks like a trailer, e.g. "Acked-by: A <a@b>"."""
    return bool(TRAILER_RE.match(line)) or line.lower().startswith(TRAILER_PREFIXES)


def find_trailer_block(lines):
    """
    Return the index of the first line of the trailing trailer block, or
    len(lines) if the message has no trailer block.

    Trailers form a single contiguous block at the end of the message, the way
    git itself parses them: a blank line separates the block from the body, but
    blank lines are not expected *between* individual trailers.
    """
    end = len(lines)
    while end > 0 and lines[end - 1].strip() == "":
        end -= 1

    start = end
    while start > 0:
        line = lines[start - 1]
        # A trailer value may be folded onto following indented lines.
        is_continuation = start < end and line.strip() and line[:1].isspace()
        if is_trailer(line) or is_continuation:
            start -= 1
        else:
            break

    # A folded continuation line cannot open the block.
    while start < end and not is_trailer(lines[start]):
        start += 1

    return start if start < end else len(lines)


def validate_subject(subject, sub_char_limit):
    """Validate the commit subject line."""
    errors = []
    if len(subject.strip()) == 0:
        errors.append("Commit message is missing subject!")
    if len(subject) > sub_char_limit:
        errors.append(f"Subject exceeds {sub_char_limit} characters!")
    return errors


def validate_body(
    lines,
    n,
    body_char_limit,
    check_blank_line,
    strict_line_length_check,
    allow_empty_body="false",
):
    """Validate the commit body."""
    errors = []

    body_index = 1
    if check_blank_line.lower() == "true":
        # Check for blank line after subject
        if n > 1 and lines[1].strip() != "":
            errors.append("Subject and body must be separated by a blank line")
        body_index = 2
    # Trailers are not body text: they are exempt from the line length limit.
    body_end = min(n, find_trailer_block(lines))
    body = [
        line.strip()
        for line in lines[body_index:body_end]
        if line.strip() and not line.lower().startswith(TRAILER_PREFIXES)
    ]
    if len(body) == 0 and allow_empty_body.lower() != "true":
        errors.append("Commit message is missing a body!")
    for line in body:
        if len(line) > body_char_limit:
            if strict_line_length_check.lower() == "true":
                errors.append(f"Line exceeds {body_char_limit} characters: {line}")
            else:
                index_of_last_space = line.rfind(" ")
                if index_of_last_space >= body_char_limit:
                    errors.append(f"Line exceeds {body_char_limit} characters: {line}")

    return errors, body


def validate_trailers(lines, body, check_blank_line):
    errors = []

    trailer_start = find_trailer_block(lines)

    if check_blank_line.lower() == "true" and body:
        if 0 < trailer_start < len(lines) and lines[trailer_start - 1].strip() != "":
            errors.append("Body and trailers must be separated by a blank line")

    return errors


def validate_commit_message(
    commit,
    sub_char_limit,
    body_char_limit,
    check_blank_line,
    strict_line_length_check,
    allow_empty_body="false",
):
    sha = commit["sha"]
    message = commit["message"]
    lines = message.splitlines()
    n = len(lines)
    subject = lines[0] if n >= 1 else ""

    errors = []
    subject_errors = validate_subject(subject, sub_char_limit)
    body_errors, body = validate_body(
        lines,
        n,
        body_char_limit,
        check_blank_line,
        strict_line_length_check,
        allow_empty_body,
    )
    trailer_errors = validate_trailers(lines, body, check_blank_line)

    errors.extend(subject_errors + body_errors + trailer_errors)

    return sha, errors


def process_commits(
    commits,
    sub_limit,
    body_limit,
    check_blank_line,
    strict_line_length_check,
    allow_empty_body="false",
):
    failed_count = 0
    for commit in commits:
        sha, errors = validate_commit_message(
            commit,
            sub_limit,
            body_limit,
            check_blank_line,
            strict_line_length_check,
            allow_empty_body,
        )
        if errors:
            print(f"::group:: ❌ Errors in commit {sha}")
            failed_count += 1
            for err in errors:
                print(f"::error:: {err}")
            print("::endgroup::")
        else:
            print(f"✅ Commit {sha} passed all checks.")
    return failed_count


def main():
    args = parse_arguments()
    commits = fetch_commits(args.base, args.head)
    failed_count = process_commits(
        commits,
        args.sub_limit,
        args.body_limit,
        args.check_blank_line,
        args.strict_line_length_check,
        args.allow_empty_body,
    )

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write("### Commit Validation Summary\n")
            if failed_count:
                f.write(f"- ❌ {failed_count} commit(s) failed validation.\n")
            else:
                f.write("- ✅ All commits passed validation.\n")

    sys.exit(1 if failed_count else 0)


if __name__ == "__main__":
    main()
