import os
import asyncio
import re
from nio import AsyncClient, UploadResponse, UploadError, RoomSendError, RoomCreateError, RoomVisibility
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
from pydub import AudioSegment
import numpy as np

class UploadHandler(FileSystemEventHandler):
    def __init__(self, client, room_ids, loop):
        self.client = client
        self.room_ids = room_ids
        self.loop = loop

    async def upload_file(self, file_path, room_id):
        """
        Upload an audio file to the Matrix media repository and send it as a voice message to a room with waveform data.

        Args:
            file_path (str): The path to the audio file to upload.
            room_id (str): The ID of the Matrix room to send the file to.
        """
        logging.debug(f"Uploading {file_path} to room {room_id}")
        # Add a 1-second delay to ensure the file is fully written
        await asyncio.sleep(1)

        try:

            # Get minimum duration from environment variable (in milliseconds), default to 0
            min_duration = int(os.getenv('MIN_AUDIO_DURATION', '0'))

            # Calculate duration
            duration = get_mp3_duration(file_path)
            if duration is None:
                duration = 0  # Fallback value; adjust as needed
                logging.warning(f"Unable to calculate duration for {file_path}, using default duration ({duration}ms)")

            # Check if duration meets the minimum threshold
            if duration < min_duration:
                logging.info(f"Skipping upload of {file_path}: duration {duration}ms is less than minimum {min_duration}ms")
                return  # Exit early if too short

            # Generate waveform data
            waveform = generate_waveform(file_path)

            # Open the file in binary read mode
            with open(file_path, "rb") as f:
                # Upload the file to the Matrix media repository
                upload_response, maybe_keys = await self.client.upload(
                    f,
                    content_type="audio/mpeg",  # MIME type for MP3 audio files
                    filename=os.path.basename(file_path),  # Use the file's basename as the name
                    encrypt=False,  # Assuming no encryption for simplicity
                    filesize=os.path.getsize(file_path)  # If left as None, some servers might refuse the upload.
                )
            logging.debug(f"Upload response: {upload_response}")

            # Check if the upload failed
            if isinstance(upload_response, UploadResponse):
                logging.debug(f"Uploaded successfully: {upload_response.content_uri}")
            elif isinstance(upload_response, UploadError):
                logging.error(f"Upload failed: {upload_response.message}")
                return None
            else:
                logging.error(f"Unexpected response: {upload_response}")
                return None

            # Prepare the content for the audio message
            content = {
                "msgtype": "m.audio",  # Message type for audio files
                "body": os.path.basename(file_path),  # File name as the message body
                "url": upload_response.content_uri,  # URL of the uploaded file
                "info": {
                    "mimetype": "audio/mpeg",
                    "size": os.path.getsize(file_path),
                    "duration": duration  # Duration in milliseconds
                },
                "org.matrix.msc1767.audio": {
                    "duration": duration,
                    "waveform": waveform
                },
                "org.matrix.msc3245.voice": {}
            }

            # Send the message to the specified room
            send_response = await self.client.room_send(
                room_id=room_id,
                message_type="m.room.message",  # Standard message event type
                content=content
            )

            # Check if sending the message failed
            if isinstance(send_response, RoomSendError):
                logging.error(f"Failed to send message: {send_response.message}")
            else:
                logging.info(f"Successfully sent message for file: {file_path} to room {room_id}")

        except FileNotFoundError:
            logging.error(f"File not found: {file_path}")
        except Exception as e:
            logging.error(f"Upload failed for {file_path}: {e}")

    # Example of how this might be triggered (for context)
    def on_moved(self, event):
        """
        Handle the renaming of a file, processing it if it now ends with .mp3.
    
        Args:
            event: The filesystem event object.
        """
        if not event.is_directory:
            file_path = event.dest_path
            if file_path.endswith('.mp3'):
                frequency = self.extract_frequency(file_path)
                freq_str = f"{frequency / 1000000:.3f}MHz"
                logging.info(f"New recording found for {freq_str}: {file_path}")
                if frequency and frequency in self.room_ids:
                    room_id = self.room_ids[frequency]
                    asyncio.run_coroutine_threadsafe(self.upload_file(file_path, room_id), self.loop)
                    logging.debug(f"Added upload task for {file_path} to queue")
                else:
                    logging.warning(f"No room found for frequency in mp3 file: {file_path}")

    def extract_frequency(self, file_path: str) -> int:
        """
        Extract frequency from the filename (placeholder implementation).

        Args:
            file_path (str): Path to the file.

        Returns:
            int: Extracted frequency or None if not found.
        """
        import re
        filename = os.path.basename(file_path)
        match = re.search(r'_(\d+)\.mp3$', filename)
        return int(match.group(1)) if match else None

def get_mp3_duration(file_path):
    """
    Calculate the duration of an MP3 file in milliseconds using pydub.
    
    Args:
        file_path (str): Path to the MP3 file.
    
    Returns:
        int: Duration in milliseconds, or None if calculation fails.
    """
    try:
        audio = AudioSegment.from_mp3(file_path)
        duration_milliseconds = len(audio)  # pydub returns duration in ms
        logging.debug(f"Calculated duration for {file_path}: {duration_milliseconds}ms")
        return duration_milliseconds
    except Exception as e:
        logging.warning(f"Failed to calculate duration for {file_path}: {e}")
        return None

def generate_waveform(file_path, num_points=100):
    """
    Generate a waveform representation of the audio file as a list of 100 integers.

    Args:
        file_path (str): Path to the MP3 file.
        num_points (int): Number of points in the waveform (default: 100).

    Returns:
        list: List of 100 integers representing the waveform, scaled to 0-1000.
    """
    try:
        # Load the MP3 file
        audio = AudioSegment.from_mp3(file_path)
        # Convert to mono for simplicity
        audio = audio.set_channels(1)
        # Get raw audio samples as a numpy array
        samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
        logging.debug(f"Sample count: {len(samples)}, max: {np.max(samples)}, min: {np.min(samples)}")
        
        # Ensure samples are valid
        if len(samples) == 0:
            logging.warning(f"No samples found in {file_path}")
            return [0] * num_points
        
        # Divide into 100 segments and calculate RMS for each
        segment_size = max(1, len(samples) // num_points)
        rms_values = []
        for i in range(num_points):
            start = i * segment_size
            end = min(start + segment_size, len(samples))
            segment = samples[start:end]
            if len(segment) > 0:
                rms = np.sqrt(np.mean(segment**2))
                rms_values.append(0 if np.isnan(rms) else rms)
            else:
                rms_values.append(0)

        # Scale waveform to 0-1000 based on maximum RMS
        max_rms = max(rms_values) if rms_values else 1  # Avoid division by zero
        waveform = [int((rms / max_rms) * 1000) if max_rms > 0 else 0 for rms in rms_values]
        logging.debug(f"Waveform for {file_path}: max RMS={max_rms}, values={waveform[:10]}...")
        return waveform
    except Exception as e:
        logging.warning(f"Failed to generate waveform for {file_path}: {e}")
        return [0] * num_points  # Fallback to flat waveform

def extract_channels_content(content):
    # Find the start of the channels section
    channels_start = content.find("channels:")
    if channels_start == -1:
        logging.warning("No 'channels:' section found in config.")
        return None
    
    # Find the opening '(' after 'channels:'
    paren_start = content.find("(", channels_start)
    if paren_start == -1:
        logging.warning("No opening '(' found after 'channels:'.")
        return None
    
    # Find the matching ');' considering nested parentheses
    count = 0
    for i in range(paren_start, len(content)):
        if content[i] == '(':
            count += 1
        elif content[i] == ')':
            count -= 1
            if count == 0:
                # Found the matching ')', check for ';'
                if i + 1 < len(content) and content[i + 1] == ';':
                    return content[paren_start + 1:i].strip()
                else:
                    logging.warning("No ';' found after closing ')'.") 
                    return None
    logging.warning("No matching ');' found for 'channels: ('.") 
    return None

def parse_channels(config_path):
    """
    Parse the channels from rtl_airband.conf and return a list of frequencies in Hz.
    
    Args:
        config_path (str): Path to the configuration file.
    
    Returns:
        list: List of frequencies in Hertz (integers).
    """
    # Get the environment variable, defaulting to 'true' (skip disabled channels)
    skip_disabled = os.getenv('SKIP_DISABLED_CHANNELS', 'true').lower() == 'true'
    
    frequencies = []
    non_disabled_count = 0
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
    
        # Extract the channels content
        channels_content = extract_channels_content(content)
        if channels_content is None:
            return []
        
        # Log the extracted content for debugging
        logging.debug(f"Channels content extracted: {channels_content}")
        
        # Find all channel blocks within '{}'
        channel_blocks = re.findall(r'\{.*?\}', channels_content, re.DOTALL)
        logging.info(f"Found {len(channel_blocks)} channel blocks.")
        
        # Iterate through each channel block
        for block in channel_blocks:
            # Check if the channel is disabled
            is_disabled = 'disable = true;' in block
            
            # Increment counter if the channel is not disabled
            if not is_disabled:
                non_disabled_count += 1
            
            # Include the channel's frequency if we're not skipping disabled channels,
            # or if the channel is not disabled
            if not skip_disabled or not is_disabled:
                freq_match = re.search(r'freq\s*=\s*(.*?);', block)
                if freq_match:
                    freq_str = freq_match.group(1).strip()
                    try:
                        freq_hz = parse_frequency(freq_str)
                        frequencies.append(freq_hz)
                    except ValueError as e:
                        logging.warning(f"Failed to parse frequency '{freq_str}': {e}")

        # Log the number of non-disabled channels
        logging.info(f"Number of non-disabled channels: {non_disabled_count}")
    
    except FileNotFoundError:
        logging.error(f"Config file not found: {config_path}")
        return []
    except Exception as e:
        logging.error(f"Error reading config file: {e}")
        return []
    
    return frequencies

def parse_frequency(value_str):
    """
    Parse a frequency string into an integer in Hertz.
    
    Args:
        value_str (str): The frequency value (e.g., '121500000', '121.5', '"121.5M"').
    
    Returns:
        int: Frequency in Hertz.
    
    Raises:
        ValueError: If the frequency format is invalid.
    """
    value_str = value_str.strip()
    
    # Check if the value is a quoted string
    if value_str.startswith('"') and value_str.endswith('"'):
        # Remove quotes
        value_str = value_str[1:-1]
        # Match numeric part and optional multiplier (e.g., '121.5M', '121500k', '121500000')
        match = re.match(r'(\d+\.?\d*)([kKmMgG]?)$', value_str)
        if not match:
            raise ValueError(f"Invalid frequency string: {value_str}")
        
        num_part = float(match.group(1))  # Convert numeric part to float
        multiplier = match.group(2).lower() if match.group(2) else ''
        
        # Apply multiplier
        if multiplier == 'k':
            return int(num_part * 1000)
        elif multiplier == 'm':
            return int(num_part * 1000000)
        elif multiplier == 'g':
            return int(num_part * 1000000000)
        else:
            return int(num_part)  # No multiplier, assume Hz
    else:
        # It's a number (not quoted)
        if '.' in value_str:
            # Float in MHz
            return int(float(value_str) * 1000000)
        else:
            # Integer in Hz
            return int(value_str)

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
        alias=freq_str,  # Local part of the alias (e.g., "145.500MHz")
        name=f"Recordings for {freq_str}",
        topic=f"Audio recordings for frequency {freq_str}",
        visibility=RoomVisibility.public  # Optional: makes the room joinable without invite
    )
    if isinstance(create_response, RoomCreateError):
        raise Exception(f"Failed to create room for {freq_str}: {create_response.message}")
    return create_response.room_id

async def main():
    """Main function to set up and run the uploader."""
    logging.basicConfig(level=logging.INFO)
    
    # Initialize Matrix client
    client = AsyncClient(
        os.getenv("SYNAPSE_URL"),
        f"@{os.getenv('BOT_USER')}:{os.getenv('MATRIX_DOMAIN')}"
    )
    await client.login(os.getenv("BOT_PASSWORD"))
    
    # Parse frequencies from config
    config_path = "/etc/rtl_airband.conf"
    frequencies = parse_channels(config_path)
    if not frequencies:
        logging.error("No frequencies found in config file")
        await client.close()
        return
    
    # Map frequencies to room IDs
    room_ids = {}
    domain = os.getenv("MATRIX_DOMAIN")
    for frequency in frequencies:
        # Assume get_or_create_room is defined elsewhere
        room_id = await get_or_create_room(client, frequency, domain)
        room_ids[frequency] = room_id
        logging.info(f"Mapped frequency {frequency} Hz to room {room_id}")
    
    # Set up the recordings directory observer
    recordings_path = "/recordings"
    if not os.path.exists(recordings_path):
        os.makedirs(recordings_path)
        logging.info(f"Created directory {recordings_path}")
    
    # Get the current event loop
    loop = asyncio.get_running_loop()

    # Initialize handler with the loop instead of a queue
    handler = UploadHandler(client, room_ids, loop)

    # Set up the watchdog observer
    observer = Observer()
    observer.schedule(handler, recordings_path, recursive=False)
    observer.start()
    logging.info(f"Started observer for {recordings_path}")
    
    # Keep the script running
    try:
        while True:
            await asyncio.sleep(1)  # Keep the event loop alive
    except asyncio.CancelledError:  # Handle shutdown gracefully
        logging.info("Shutting down")
    finally:
        observer.stop()
        observer.join()
        await client.close()  # Clean up your client

if __name__ == "__main__":
    asyncio.run(main())