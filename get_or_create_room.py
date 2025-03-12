from nio import AsyncClient, RoomCreateError

async def get_or_create_room(client, frequency, domain):
    """
    Get or create a Matrix room for the given frequency.
    Returns the room ID.
    """
    # Convert frequency (in Hz) to a readable string (e.g., "145.500MHz")
    freq_str = f"{frequency / 1000000:.3f}MHz"
    full_alias = f"#{freq_str}:{domain}"
    
    # Check if the room alias exists
    response = await client.room_resolve_alias(full_alias)
    if hasattr(response, 'room_id') and response.room_id:
        return response.room_id
    
    # Room doesn’t exist, create it
    create_response = await client.room_create(
        alias_name=freq_str,  # Local part of the alias (e.g., "145.500MHz")
        name=f"Recordings for {freq_str}",
        topic=f"Audio recordings for frequency {freq_str}",
        visibility="public"  # Optional: makes the room joinable without invite
    )
    if isinstance(create_response, RoomCreateError):
        raise Exception(f"Failed to create room for {freq_str}: {create_response.message}")
    return create_response.room_id