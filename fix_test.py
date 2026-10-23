with open("backend/tests/test_regulatory_engine.py", "r") as f:
    content = f.read()

content = content.replace("import uuid\ndef test_get_analysis_run_not_found(", "def test_get_analysis_run_not_found(")

with open("backend/tests/test_regulatory_engine.py", "w") as f:
    f.write(content)
