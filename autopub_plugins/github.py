import json
import os
import pathlib
import textwrap
from functools import cached_property
from typing import Optional

from autopub.exceptions import AutopubException
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

    @cached_property
    def _github(self) -> Github:
        return Github(self.github_token)

    @cached_property
    def _event_data(self) -> Optional[dict]:
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path:
            return None

        with open(event_path) as f:
            return json.load(f)

    def _get_pr_number(self) -> Optional[int]:
        if not self._event_data:
            return None

        if self._event_data.get("event_name") in [
            "pull_request",
            "pull_request_target",
        ]:
            return self._event_data["pull_request"]["number"]

        if self._event_data.get("pull_request"):
            return self._event_data["pull_request"]["number"]

        sha = self._event_data["commits"][0]["id"]
        g = Github(self.github_token)
        repo: Repository = g.get_repo(self.repository)

        commit = repo.get_commit(sha)

        pulls = commit.get_pulls()

        try:
            first_pr = pulls[0]
        except IndexError:
            return None

        return first_pr.number

    def _update_or_create_comment(
        self, text: str, pr_number: int, marker: str = "<!-- autopub-comment -->"
    ) -> None:
        """Update or create a comment on the current PR with the given text."""
        print(f"Updating or creating comment on PR {pr_number} in {self.repository}")
        repo: Repository = self._github.get_repo(self.repository)
        pr: PullRequest = repo.get_pull(pr_number)

        # Look for existing autopub comment
        comment_body = f"{marker}\n{text}"

        # Search for existing comment
        for comment in pr.get_issue_comments():
            if marker in comment.body:
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

    def _create_release(self, release_info: ReleaseInfo) -> None:
        message = textwrap.dedent(
            f"""
            ## {release_info.version}

            {release_info.release_notes}

            This release was contributed by todo in #{self._get_pr_number()}
            """
        )
        repo: Repository = self._github.get_repo(self.repository)
        release = repo.create_git_release(
            tag=release_info.version,
            name=release_info.version,
            message=message,
        )

        for asset in pathlib.Path("dist").glob("*"):
            release.upload_asset(str(asset))

    def post_publish(self, release_info: ReleaseInfo) -> None:
        print("🔥 Post-publish")
        text = f"This PR was published as {release_info.version}"
        pr_number = self._get_pr_number()

        if pr_number is None:
            return

        self._update_or_create_comment(
            text, pr_number, marker="<!-- autopub-comment-published -->"
        )

        self._create_release(release_info)
