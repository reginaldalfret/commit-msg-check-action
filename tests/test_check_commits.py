# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch
from contextlib import redirect_stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import check_commits


class TestCheckCommits(unittest.TestCase):
    def setUp(self):
        self.valid_sample_commit = {
            "sha": "abc123",
            "message": (
                "Valid subject\n\n"
                "This is a valid description line.\n"
                "It continues here.\n\n"
                "Signed-off-by: Developer <dev@example.com>"
            ),
        }
        self.invalid_sample_commit = {
            "sha": "badcommit1234",
            "message": (
                "Invalid subject which is definitely longer than 50 characters"
                "This is a valid description line.\n"
                "It continues here."
                "Signed-off-by: Developer <dev@example.com>"
            ),
        }

    def test_parse_arguments_with_base_head(self):
        argv = [
            "check_commits.py",
            "--base",
            "1111111",
            "--head",
            "2222222",
            "--body-limit",
            "72",
            "--sub-limit",
            "50",
            "--check-blank-line",
            "true",
        ]
        with patch.object(sys, "argv", argv):
            args = check_commits.parse_arguments()
        self.assertEqual(args.base, "1111111")
        self.assertEqual(args.head, "2222222")
        self.assertEqual(args.body_limit, 72)
        self.assertEqual(args.sub_limit, 50)
        self.assertEqual(args.check_blank_line, "true")

    def test_validate_commit_message_valid(self):
        sha, errors = check_commits.validate_commit_message(
            self.valid_sample_commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertEqual(sha, "abc123")
        self.assertEqual(errors, [])

    def test_validate_commit_message_subject_too_long_no_blank_check(self):
        commit = {
            "sha": "def456",
            "message": (
                "This subject line is way too long and should definitely fail the check\n"
                "Body line.\n\n"
                "Signed-off-by: Developer <dev@example.com>"
            ),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="false",
            strict_line_length_check="true",
        )
        self.assertIn("Subject exceeds 50 characters!", errors)
        self.assertTrue(
            all(
                "Subject and body must be separated by a blank line" not in e
                for e in errors
            )
        )

    def test_validate_commit_message_subject_too_long_with_blank_check(self):
        commit = {
            "sha": "def456",
            "message": (
                "This subject line is way too long and should definitely fail the check\n"
                "Body line without blank separator\n\n"
                "Signed-off-by: Developer <dev@example.com>"
            ),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertIn("Subject exceeds 50 characters!", errors)
        self.assertIn("Subject and body must be separated by a blank line", errors)

    def test_process_commits_all_valid_prints_and_returns_zero(self):
        commits = [self.valid_sample_commit]
        buf = StringIO()
        with redirect_stdout(buf):
            failed = check_commits.process_commits(
                commits,
                sub_limit=50,
                body_limit=72,
                check_blank_line="true",
                strict_line_length_check="true",
            )
        out = buf.getvalue()
        self.assertEqual(failed, 0)
        self.assertIn("✅ Commit abc123 passed all checks.", out)

    def test_process_commits_mixed_failures(self):
        bad_commit = {
            "sha": "bad999",
            "message": (
                "Bad subject with excessive length that violates the rule right away\n"
                "Body line\n"
            ),
        }
        commits = [self.valid_sample_commit, bad_commit]
        buf = StringIO()
        with redirect_stdout(buf):
            failed = check_commits.process_commits(
                commits,
                sub_limit=50,
                body_limit=72,
                check_blank_line="true",
                strict_line_length_check="true",
            )
        out = buf.getvalue()
        self.assertEqual(failed, 1)
        self.assertIn("❌ Errors in commit bad999", out)
        self.assertIn("Subject exceeds 50 characters!", out)

    def test_commits_failures(self):
        commits = [self.invalid_sample_commit]
        buf = StringIO()
        with redirect_stdout(buf):
            failed = check_commits.process_commits(
                commits,
                sub_limit=50,
                body_limit=72,
                check_blank_line="true",
                strict_line_length_check="true",
            )
        out = buf.getvalue()
        self.assertEqual(failed, 1)
        self.assertIn("❌ Errors in commit badcommit1234", out)
        self.assertIn("Subject exceeds 50 characters!", out)
        self.assertIn("Subject and body must be separated by a blank line", out)

    def test_body_strict_true_long_line_fails(self):
        commit = {
            "sha": "long1",
            "message": ("Valid subject\n\n" + "a" * 80 + "\n"),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertIn("Line exceeds 72 characters", "".join(errors))

    def test_body_strict_false_single_long_word_passes(self):
        commit = {
            "sha": "long2",
            "message": ("Valid subject\n\n" + "a" * 80 + "\n"),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="false",
        )
        self.assertEqual(errors, [])

    def test_allow_empty_body_true_passes(self):
        commit = {
            "sha": "emptybody1",
            "message": "Valid subject line\n\nSigned-off-by: Dev <dev@example.com>\n",
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="false",
            allow_empty_body="true",
        )
        self.assertEqual(errors, [])

    def test_allow_empty_body_true_subject_only_passes(self):
        commit = {
            "sha": "emptybody2",
            "message": "Valid subject line only\n",
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="false",
            allow_empty_body="true",
        )
        self.assertEqual(errors, [])

    def test_allow_empty_body_default_missing_body_fails(self):
        commit = {
            "sha": "emptybody3",
            "message": "Valid subject line only\n",
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="false",
        )
        self.assertIn("Commit message is missing a body!", errors)

    def test_body_strict_false_new_word_after_limit_fails(self):
        line = "a" * 72 + " newword"
        commit = {
            "sha": "long3",
            "message": ("Valid subject\n\n" + line + "\n"),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="false",
        )
        self.assertIn("Line exceeds 72 characters", "".join(errors))

    def test_body_strict_false_long_url_passes(self):
        url = "https://example.com/" + "a" * 100
        commit = {
            "sha": "long4",
            "message": ("Valid subject\n\n" + url + "\n"),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="false",
        )
        self.assertEqual(errors, [])

    def test_body_strict_true_long_url_fails(self):
        url = "https://www.example.com/" + "a" * 100
        commit = {
            "sha": "long5",
            "message": ("Valid subject\n\n" + url + "\n"),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertIn("Line exceeds 72 characters", "".join(errors))

    def test_contiguous_trailer_block_passes(self):
        """Trailers form one block; no blank line is needed between them."""
        commit = {
            "sha": "trailer1",
            "message": (
                "Valid subject\n\n"
                "This is a valid description line.\n\n"
                'Fixes: 54a4f0239f2e ("Some earlier commit")\n'
                "Assisted-by: Claude Code:claude-opus-5\n"
                "Co-developed-by: Other Dev <other@example.com>\n"
                "Signed-off-by: Other Dev <other@example.com>\n"
                "Signed-off-by: Developer <dev@example.com>\n"
            ),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertEqual(errors, [])

    def test_unknown_trailer_is_not_body(self):
        """A trailer-shaped line in the block is not counted as the body."""
        commit = {
            "sha": "trailer2",
            "message": (
                "Valid subject\n\n"
                "Change-Id: I0123456789abcdef0123456789abcdef01234567\n"
                "Signed-off-by: Developer <dev@example.com>\n"
            ),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertIn("Commit message is missing a body!", errors)

    def test_long_trailer_exempt_from_line_length(self):
        commit = {
            "sha": "trailer3",
            "message": (
                "Valid subject\n\n"
                "This is a valid description line.\n\n"
                "Closes: https://example.com/issues/" + "1" * 80 + "\n"
                "Signed-off-by: Developer <dev@example.com>\n"
            ),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertEqual(errors, [])

    def test_trailers_directly_after_body_still_fails(self):
        commit = {
            "sha": "trailer4",
            "message": (
                "Valid subject\n\n"
                "This is a valid description line.\n"
                "Signed-off-by: Developer <dev@example.com>\n"
            ),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertIn("Body and trailers must be separated by a blank line", errors)

    def test_folded_trailer_value_passes(self):
        commit = {
            "sha": "trailer5",
            "message": (
                "Valid subject\n\n"
                "This is a valid description line.\n\n"
                "Acked-by: The Stakeholder <stakeholder@example.org>\n"
                "Link: https://lore.kernel.org/some-message-id\n"
                "  continued on an indented line\n"
                "Signed-off-by: Developer <dev@example.com>\n"
            ),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertEqual(errors, [])

    def test_body_line_with_colon_is_still_body(self):
        """A "Word: text" line above the trailer block stays body text."""
        commit = {
            "sha": "trailer6",
            "message": (
                "Valid subject\n\n"
                "Note: " + "a" * 80 + "\n\n"
                "Signed-off-by: Developer <dev@example.com>\n"
            ),
        }
        _sha, errors = check_commits.validate_commit_message(
            commit,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
            strict_line_length_check="true",
        )
        self.assertIn("Line exceeds 72 characters", "".join(errors))


if __name__ == "__main__":
    unittest.main()
