from dataclasses import dataclass

import pytest

from unstructured.ingest.doc_processor.generalized import (
    process_document,
    session_handle_var,
)
from unstructured.ingest.interfaces import BaseIngestDoc, IngestDocSessionHandleMixin


@dataclass
class IngestDocWithSessionHandle(IngestDocSessionHandleMixin, BaseIngestDoc):
    pass

@pytest.fixture(autouse=True)
def _reset_session_handle():
    session_handle_var.set(None)

def test_process_document_with_session_handle(mocker):
    """Test that the process_document function calls the doc_processor_fn with the correct
    arguments, assigns the session handle, and returns the correct results."""
    mock_session_handle = mocker.MagicMock()
    session_handle_var.set(mock_session_handle)
    mock_doc = mocker.MagicMock(spec=(IngestDocWithSessionHandle))

    result = process_document(mock_doc)
    
    mock_doc.get_file.assert_called_once_with()
    mock_doc.write_result.assert_called_with()
    mock_doc.cleanup_file.assert_called_once_with()
    assert result == mock_doc.process_file.return_value 
    assert mock_doc.session_handle == mock_session_handle


def test_process_document_no_session_handle(mocker):
    """Test that the process_document function calls does not assign session handle the IngestDoc
    does not have the session handle mixin."""
    session_handle_var.set(mocker.MagicMock())
    mock_doc = mocker.MagicMock(spec=(BaseIngestDoc))

    process_document(mock_doc)

    assert not hasattr(mock_doc, "session_handle")
