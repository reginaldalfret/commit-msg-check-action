# commit-msg-check-action
This GitHub Action enforces consistent commit message formatting for Qualcomm projects. It currently supports the following validations:

- Commit Subject : Verifies that a subject line is present and does not exceed the specified character limit.
- Commit Body : Ensures a body is provided and that each line adheres to the defined word wrap limit.
- Check Blank Line Flag: When true, ensures a blank line between the commit subject, body, and the trailer block (`Signed-off-by:`, `Co-developed-by:`, `Assisted-by:`, …) for better readability. Trailers are recognised by shape (`Token: value`), so project-specific ones need no configuration, and — as with `git interpret-trailers` — they are expected to form one contiguous block with no blank lines between individual trailers.
- Strict Line Length Check Flag: When false, allows exceeding the character limit if the last word is a single token.
- Allow Empty Body Flag: Optional (default: false). When true, allows commit messages with only a subject line (and optional trailers such as `Signed-off-by:`), omitting a body. When false, the commit body requirement remains active.

# Usage
Create a new GitHub Actions workflow in your project, e.g. at .github/workflows/commit-check.yml

    name: Commit Msg Check Action

    on:
      pull_request:
        types: [opened, synchronize, reopened]

    jobs:
      check-commits:
        runs-on: ubuntu-latest
        permissions:
          contents: read
          pull-requests: read
        steps:
          - name: Check out repository
            uses: actions/checkout@v4
            with:
              ref: ${{ github.event.pull_request.head.sha }}
              fetch-depth: 0

          - name: Commit Check
            uses: qualcomm/commit-msg-check-action@v2
            with:
              base: ${{ github.event.pull_request.base.sha }}
              head: ${{ github.event.pull_request.head.sha }}
              body-char-limit: 72
              sub-char-limit: 72
              check-blank-line: true
              strict-line-length-check: true
              allow-empty-body: false


## Getting in Contact

If you have questions, suggestions, or issues related to this project, there are several ways to reach out:

* [Report an Issue on GitHub](../../issues)
* [Open a Discussion on GitHub](../../discussions)
* [E-mail us](mailto:ynancher@qti.qualcomm.com,lint.core@qti.qualcomm.com) for general questions

## License

commit-msg-check-action is licensed under the [BSD-3-Clause-Clear License](https://spdx.org/licenses/BSD-3-Clause-Clear.html). See [LICENSE.txt](LICENSE.txt) for the full license text.
