from unittest.mock import patch, MagicMock
from rag.generator import generate


@patch("rag.generator.client")
def test_generate_returns_answer(mock_client):
    mock_message = MagicMock()
    mock_message.content = "RAG stands for Retrieval Augmented Generation."
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    result = generate([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is RAG?"},
    ])

    assert result == "RAG stands for Retrieval Augmented Generation."
    mock_client.chat.completions.create.assert_called_once()


@patch("rag.generator.client")
def test_generate_passes_messages_through(mock_client):
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "answer"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]
    result = generate(msgs)

    assert result == "answer"
    call_args = mock_client.chat.completions.create.call_args
    assert call_args.kwargs["messages"] == msgs
