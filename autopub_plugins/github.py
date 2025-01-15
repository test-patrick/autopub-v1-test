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

    def _update_or_create_comment(self, text: str, pr_number: int) -> None:
        """Update or create a comment on the current PR with the given text."""
        print(f"Updating or creating comment on PR {pr_number} in {self.repository}")
        g = Github(self.github_token)
        repo: Repository = g.get_repo(self.repository)
        pr: PullRequest = repo.get_pull(pr_number)

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
        pr_number = self._get_pr_number()

        if pr_number is None:
            return

        self._update_or_create_comment(release_info.release_notes, pr_number)

    def on_release_notes_invalid(
        self, exception: AutopubException
    ) -> None:  # pragma: no cover
        pr_number = self._get_pr_number()

        if pr_number is None:
            return

        self._update_or_create_comment(str(exception), pr_number)

    def _get_pr_number_from_commit(self) -> Optional[int]:
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path:
            return None

        import json

        with open(event_path) as f:
            event = json.load(f)

            # Handle pull_request events directly
            if event.get("event_name") in ["pull_request", "pull_request_target"]:
                return event["pull_request"]["number"]

            # For other events, need to query GitHub API
            sha = event["commits"][0]["id"]
            g = Github(self.github_token)
            repo: Repository = g.get_repo(self.repository)

            # Get PRs associated with this commit
            pulls = repo.get_commits_pulls(sha)

            # Get first PR if any exist
            try:
                first_pr = next(pulls)
                return first_pr.number
            except StopIteration:
                return None

    def post_publish(self, release_info: ReleaseInfo) -> None:
        text = f"This PR was published as {release_info.version}"
        pr_number = self._get_pr_number_from_commit()

        if pr_number is None:
            return

        self._update_or_create_comment(text, pr_number)
