"""Tests for FileWriter summary and resource extraction functionality."""

import tempfile
from pathlib import Path

import pytest

from platform_generator.writers.filesystem import FileWriter, ResourceCreationInfo


class TestResourceExtraction:
    """Test resource type and name extraction from file paths."""

    def test_extract_namespace_info(self):
        """Test namespace resource extraction."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        path = Path(
            "generated/tenants/bar/namespaces/dev/foo-gitops-wus3-dev/namespace.yaml"
        )

        resource_type, resource_name = writer._extract_resource_info(path)

        assert resource_type == "namespace"
        assert resource_name == "foo-gitops-wus3-dev"

    def test_extract_resourcequota_info(self):
        """Test resource quota extraction."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        path = Path("generated/tenants/bar/resourcequotas/dev/resourcequota.yaml")

        resource_type, resource_name = writer._extract_resource_info(path)

        assert resource_type == "resourcequota"
        assert resource_name == "bar-dev"

    def test_extract_networkpolicy_info(self):
        """Test network policy extraction."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        path = Path("generated/tenants/bar/networkpolicies/dev/deny-all.yaml")

        resource_type, resource_name = writer._extract_resource_info(path)

        assert resource_type == "networkpolicy"
        assert resource_name == "deny-all"

    def test_extract_networkpolicy_custom(self):
        """Test custom network policy extraction."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        path = Path(
            "generated/tenants/bar/networkpolicies/dev/custom-allow-to-database.yaml"
        )

        resource_type, resource_name = writer._extract_resource_info(path)

        assert resource_type == "networkpolicy"
        assert resource_name == "custom-allow-to-database"

    def test_extract_appproject_info(self):
        """Test app project extraction."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        path = Path("generated/tenants/bar/argocd/appprojects/dev/appproject-bar.yaml")

        resource_type, resource_name = writer._extract_resource_info(path)

        assert resource_type == "appproject"
        assert resource_name == "bar"

    def test_extract_applicationset_info(self):
        """Test application set extraction."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        path = Path(
            "generated/tenants/bar/argocd/applicationsets/bar-mfe-frontend/dev/"
            "applicationset-bar-mfe-frontend.yaml"
        )

        resource_type, resource_name = writer._extract_resource_info(path)

        assert resource_type == "applicationset"
        assert resource_name == "bar-mfe-frontend"

    def test_extract_unknown_resource(self):
        """Test fallback for unknown resource types."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        path = Path("generated/unknown/path/somefile.yaml")

        resource_type, resource_name = writer._extract_resource_info(path)

        assert resource_type == "resource"
        assert resource_name == "somefile"


class TestPathHelpers:
    """Test path helper methods."""

    def test_get_tenant_from_path(self):
        """Test tenant extraction from path."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        parts = ("generated", "tenants", "bar", "namespaces", "dev")

        tenant = writer._get_tenant_from_path(parts)

        assert tenant == "bar"

    def test_get_tenant_from_path_missing(self):
        """Test tenant extraction when tenant is missing."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        parts = ("generated", "namespaces", "dev")

        tenant = writer._get_tenant_from_path(parts)

        assert tenant is None

    def test_get_env_from_resourcequota_path(self):
        """Test environment extraction from resourcequota path."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        parts = ("generated", "tenants", "bar", "resourcequotas", "dev")

        env = writer._get_env_from_path(parts)

        assert env == "dev"

    def test_get_env_from_namespace_path(self):
        """Test environment extraction from namespace path."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        parts = ("generated", "tenants", "bar", "namespaces", "dev", "cluster-name")

        env = writer._get_env_from_path(parts)

        assert env == "dev"

    def test_get_env_from_applicationset_path(self):
        """Test environment extraction from applicationset path."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        parts = (
            "generated",
            "tenants",
            "bar",
            "argocd",
            "applicationsets",
            "app-name",
            "dev",
        )

        env = writer._get_env_from_path(parts)

        assert env == "dev"


class TestDetailedSummary:
    """Test detailed summary generation."""

    def test_get_detailed_summary_empty(self):
        """Test detailed summary with no files."""
        writer = FileWriter(output_directory="./generated", dry_run=True)

        summary = writer.get_detailed_summary()

        assert summary == []
        assert isinstance(summary, list)

    def test_get_detailed_summary_with_files(self):
        """Test detailed summary with multiple files."""
        writer = FileWriter(output_directory="./generated", dry_run=True)

        # Simulate writing files in dry-run mode
        writer.files_written = [
            Path("generated/tenants/bar/namespaces/dev/foo-wus3-dev/namespace.yaml"),
            Path("generated/tenants/bar/resourcequotas/dev/resourcequota.yaml"),
            Path("generated/tenants/bar/networkpolicies/dev/deny-all.yaml"),
        ]

        summary = writer.get_detailed_summary()

        assert len(summary) == 3
        assert all(isinstance(item, ResourceCreationInfo) for item in summary)

        # Check first item (namespace)
        assert summary[0].resource_type == "namespace"
        assert summary[0].resource_name == "foo-wus3-dev"
        assert summary[0].relative_path == Path(
            "tenants/bar/namespaces/dev/foo-wus3-dev/namespace.yaml"
        )

        # Check second item (resourcequota)
        assert summary[1].resource_type == "resourcequota"
        assert summary[1].resource_name == "bar-dev"

        # Check third item (networkpolicy)
        assert summary[2].resource_type == "networkpolicy"
        assert summary[2].resource_name == "deny-all"

    def test_get_detailed_summary_dataclass_fields(self):
        """Test that ResourceCreationInfo has all expected fields."""
        writer = FileWriter(output_directory="./generated", dry_run=True)
        writer.files_written = [
            Path("generated/tenants/bar/namespaces/dev/cluster/namespace.yaml")
        ]

        summary = writer.get_detailed_summary()

        assert len(summary) == 1
        item = summary[0]

        # Verify all dataclass fields are present
        assert hasattr(item, "resource_type")
        assert hasattr(item, "resource_name")
        assert hasattr(item, "file_path")
        assert hasattr(item, "relative_path")

        assert isinstance(item.file_path, Path)
        assert isinstance(item.relative_path, Path)


class TestQuietMode:
    """Test quiet mode functionality."""

    def test_quiet_mode_suppresses_output(self, capsys):
        """Test that quiet mode suppresses file write messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FileWriter(output_directory=tmpdir, dry_run=False, quiet=True)

            writer.write_file(
                content="test: content",
                path_template="test",
                variables={},
                filename="test.yaml",
            )

            captured = capsys.readouterr()
            # Should not contain the "✓ Wrote" message
            assert "✓" not in captured.out
            assert "Wrote" not in captured.out

    def test_non_quiet_mode_shows_output(self, capsys):
        """Test that non-quiet mode shows file write messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FileWriter(output_directory=tmpdir, dry_run=False, quiet=False)

            writer.write_file(
                content="test: content",
                path_template="test",
                variables={},
                filename="test.yaml",
            )

            captured = capsys.readouterr()
            # Should contain the "✓ Wrote" message
            assert "✓" in captured.out or "Wrote" in captured.out


class TestDryRunTracking:
    """Test that dry-run mode tracks files for summary."""

    def test_dry_run_tracks_files(self):
        """Test that files are tracked even in dry-run mode."""
        writer = FileWriter(output_directory="./generated", dry_run=True, quiet=True)

        result = writer.write_file(
            content="test: content",
            path_template="tenants/{{tenant}}/test",
            variables={"tenant": "bar"},
            filename="test.yaml",
        )

        # Should return None in dry-run mode
        assert result is None

        # But should track the file
        assert len(writer.files_written) == 1
        assert "bar" in str(writer.files_written[0])

    def test_dry_run_detailed_summary(self):
        """Test that detailed summary works with dry-run tracked files."""
        writer = FileWriter(output_directory="./generated", dry_run=True, quiet=True)

        writer.write_file(
            content="namespace",
            path_template="tenants/{{tenant}}/namespaces/{{env}}/{{cluster}}",
            variables={"tenant": "bar", "env": "dev", "cluster": "foo-wus3-dev"},
            filename="namespace.yaml",
        )

        summary = writer.get_detailed_summary()

        assert len(summary) == 1
        assert summary[0].resource_type == "namespace"
        assert summary[0].resource_name == "foo-wus3-dev"


class TestOutputSummaryBackwardCompatibility:
    """Test that existing get_output_summary still works."""

    def test_get_output_summary_counts(self):
        """Test that get_output_summary returns correct counts."""
        writer = FileWriter(output_directory="./generated", dry_run=True)

        writer.files_written = [
            Path("generated/tenants/bar/namespaces/dev/ns1/namespace.yaml"),
            Path("generated/tenants/bar/namespaces/dev/ns2/namespace.yaml"),
            Path("generated/tenants/bar/resourcequotas/dev/resourcequota.yaml"),
            Path("generated/tenants/bar/networkpolicies/dev/deny-all.yaml"),
            Path("generated/tenants/bar/networkpolicies/dev/allow-ingress.yaml"),
            Path("generated/tenants/bar/argocd/appprojects/dev/appproject-bar.yaml"),
        ]

        summary = writer.get_output_summary()

        assert summary["namespaces"] == 2
        assert summary["resource-quotas"] == 1
        assert summary["network-policies"] == 2
        assert summary["app-projects"] == 1
