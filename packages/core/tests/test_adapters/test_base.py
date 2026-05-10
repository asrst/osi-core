import pytest
from osi_core.adapters.base import BaseAdapter
from osi_core.models import ResolvedModel
from osi_core.models.types import ParseResult


class TestBaseAdapter:
    def test_adapter_is_abstract(self):
        with pytest.raises(TypeError):
            BaseAdapter()

    

    def test_adapter_has_parse_method(self):
        assert hasattr(BaseAdapter, 'parse')

    def test_adapter_has_translate_method(self):
        assert hasattr(BaseAdapter, 'translate')

    def test_subclass_must_implement_methods(self):
        class IncompleteAdapter(BaseAdapter):
            format_name = "test"

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_complete_subclass(self):
        class CompleteAdapter(BaseAdapter):
            format_name = "test"

            def parse(self, source, version=None):
                return ParseResult(raw={}, source_format="test", source_version="1.0")

            def translate(self, model, target_version=None):
                return "test output"

        adapter = CompleteAdapter()
        assert adapter.format_name == "test"
        result = adapter.parse("source")
        assert isinstance(result, ParseResult)
        output = adapter.translate(ResolvedModel(name="test", semantic_models=[]))
        assert output == "test output"