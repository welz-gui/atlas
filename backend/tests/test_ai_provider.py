from pydantic import BaseModel
from app.ai.provider import NullProvider, AIRequest, AIProvider

# Note: DummyProvider from the issue description has been refactored to NullProvider
# in the current codebase. We test NullProvider (which is the current DummyProvider) here.
DummyProvider = NullProvider

class DummyOutputModel(BaseModel):
    test_field: str

def test_dummy_provider_complete():
    provider = DummyProvider()
    request = AIRequest(system="sys", prompt="prompt", output_model=DummyOutputModel)
    result = provider.complete(request)

    assert result.provider == "none"
    assert result.error is not None
    assert "Nenhum provedor de modelo configurado" in result.error

def test_dummy_provider_describe():
    provider = DummyProvider()
    description = provider.describe()

    assert description == "nenhum modelo configurado — busca determinística no catálogo"

def test_base_provider_describe():
    class TestProvider(AIProvider):
        name = "test_provider"
        def complete(self, request):
            pass

    provider = TestProvider()
    assert provider.describe() == "test_provider"
