import pytest
import asyncio
from app.services.events import mesh_events

@pytest.mark.asyncio
async def test_mesh_event_publisher():
    received_events = []
    
    async def mock_handler(event_name: str, payload: dict):
        received_events.append((event_name, payload))

    # Test Subscribe
    mesh_events.subscribe(mock_handler)
    assert mock_handler in mesh_events._subscribers
    
    # Test Notify Sync
    mesh_events.notify_sync("test_event", {"data": 123})
    
    # Give the event loop a moment to run the scheduled task
    await asyncio.sleep(0.01)
    
    assert len(received_events) == 1
    assert received_events[0] == ("test_event", {"data": 123})

    # Test Unsubscribe
    mesh_events.unsubscribe(mock_handler)
    assert mock_handler not in mesh_events._subscribers
    
    mesh_events.notify_sync("test_event_2", {"data": 456})
    await asyncio.sleep(0.01)
    
    # Should not receive the second event
    assert len(received_events) == 1
