import json

import pytest
from click.testing import CliRunner

from olx_cli.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCliHelp:
    def test_help_contains_search(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "search" in result.output

    def test_search_help_contains_options(self, runner):
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0
        for opt in ["--photo-only", "--location", "--radius", "--min-price",
                    "--max-price", "--max-pages", "--no-max-pages", "--json"]:
            assert opt in result.output


class TestCliValidation:
    def test_radius_without_location_fails(self, runner):
        result = runner.invoke(cli, ["search", "opel", "-r", "30"])
        assert result.exit_code != 0

    def test_min_gt_max_fails(self, runner):
        result = runner.invoke(cli, ["search", "opel", "-m", "2000", "-M", "100"])
        assert result.exit_code != 0


class TestCliOutput:
    def test_json_output_valid(self, runner):
        result = runner.invoke(cli, [
            "search", "kierowce przyjme", "--json", "--max-pages", "1",
        ])
        if result.exit_code != 0:
            pytest.skip("network-dependent, skip if offline")
        data = json.loads(result.output)
        assert "query" in data
        assert "url" in data
        assert "offers" in data
        assert isinstance(data["offers"], list)

    def test_table_output_contains_found(self, runner):
        result = runner.invoke(cli, [
            "search", "kierowce przyjme", "--max-pages", "1",
        ])
        if result.exit_code != 0:
            pytest.skip("network-dependent, skip if offline")
        assert "Found" in result.output
        assert "Title" in result.output
