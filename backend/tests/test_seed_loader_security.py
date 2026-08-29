import pytest
from app.regulatory.catalog import RegulatoryCatalog

def test_load_seed_files_path_traversal():
    """Ensure load_seed_files is resilient against path traversal if malicious path is provided."""
    with pytest.raises(ValueError, match="data_dir must be within"):
        RegulatoryCatalog.load_seed_files(data_dir="../../../etc")
