import os
from typing import Optional

from autopub.exceptions import AutopubException, CommandFailed
from autopub.plugins import AutopubPlugin
from autopub.types import ReleaseInfo
from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository


class GithubPlugin(AutopubPlugin):
    def __init__(self) -> None:
        super().__init__()
        # Get GitHub token from environment
        self.github_token = os.environ.get("GITHUB_TOKEN")
        if not self.github_token:
            raise AutopubException("GITHUB_TOKEN environment variable is required")

        # Get repository and PR information from GitHub Actions environment
        self.repository = os.environ.get("GITHUB_REPOSITORY")
        self.pr_number = self._get_pr_number()

        if not self.repository or not self.pr_number:
            raise AutopubException("This plugin must be run in GitHub Actions context")

    def _get_pr_number(self) -> Optional[int]:
        """Extract PR number from GitHub Actions event context."""
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path:
            return None

        import json

        with open(event_path) as f:
            event = json.load(f)
            # Handle pull_request events
            if "pull_request" in event:
                return event["pull_request"]["number"]
            return None

    def _update_or_create_comment(self, text: str) -> None:
        """Update or create a comment on the current PR with the given text."""
        g = Github(self.github_token)
        repo: Repository = g.get_repo(self.repository)
        pr: PullRequest = repo.get_pull(self.pr_number)

        # Look for existing autopub comment
        comment_marker = "<!-- autopub-comment -->"
        comment_body = f"{comment_marker}\n{text}"

        # Search for existing comment
        for comment in pr.get_issue_comments():
            if comment_marker in comment.body:
                # Update existing comment
                comment.edit(comment_body)
                return

        # Create new comment if none exists
        pr.create_issue_comment(comment_body)

    def on_release_notes_valid(
        self, release_info: ReleaseInfo
    ) -> None:  # pragma: no cover
        self._update_or_create_comment(release_info.release_notes)

    def on_release_notes_invalid(
        self, exception: AutopubException
    ) -> None:  # pragma: no cover
        self._update_or_create_comment(str(exception))
