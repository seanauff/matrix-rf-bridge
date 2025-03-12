import os
import asyncio
import re
from nio import AsyncClient, UploadError, RoomSendError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import get_or_create_room
import parse_channels

class UploadHandler(FileSystemEventHandler):
    def __init__(self, client: AsyncClient, room_ids: dict):
        """
        Initialize the UploadHandler.

        Args:
            client (AsyncClient): The Matrix client instance.
            room_ids (dict): Dictionary mapping frequencies to room IDs.
        """
        self.client = client
        self.room_ids = room_ids

    async def upload_file(self, file_path: str, room_id: str):
        """
        Upload an audio file to the Matrix media repository and send it as a message to a room.

        Args:
            file_path (str): The path to the audio file to upload.
            room_id (str): The ID of the Matrix room to send the file to.
        """
        logging.info(f"Preparing to upload file: {file_path} to room: {room_id}")
        # Add a 1-second delay to ensure the file is fully written
        await asyncio.sleep(1)

        try:
            # Open the file in binary read mode
            with open(file_path, "rb") as f:
                # Upload the file to the Matrix media repository
                upload_response = await self.client.upload(
                    file=f,
                    content_type="audio/mpeg",  # MIME type for MP3 audio files
                    filename=os.path.basename(file_path),  # Use the file's basename as the name
                    encrypt=False  # Assuming no encryption for simplicity
                )

                # Check if the upload failed
                if isinstance(upload_response, UploadError):
                    logging.error(f"Failed to upload file: {upload_response.message}")
                    return

                # Get the MXC URI of the uploaded file
                mxc_uri = upload_response.content_uri
                logging.info(f"File uploaded successfully: {mxc_uri}")

                # Prepare the content for the audio message
                content = {
                    "msgtype": "m.audio",  # Message type for audio files
                    "body": os.path.basename(file_path),  # File name as the message body
                    "url": mxc_uri  # URL of the uploaded file
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
                    logging.info(f"Successfully sent message for file: {file_path}")

        except FileNotFoundError:
            logging.error(f"File not found: {file_path}")
        except Exception as e:
            logging.error(f"Error in upload_file: {e}")

    # Example of how this might be triggered (for context)
    def on_created(self, event):
        """
        Handle the creation of a new file by scheduling an upload task.

        Args:
            event: The filesystem event object.
        """
        if not event.is_directory:
            file_path = event.src_path
            logging.info(f"New file detected: {file_path}")
            # Extract frequency from filename (implementation not shown)
            frequency = self.extract_frequency(file_path)
            if frequency and frequency in self.room_ids:
                room_id = self.room_ids[frequency]
                # Schedule the upload asynchronously
                asyncio.create_task(self.upload_file(file_path, room_id))
            else:
                logging.warning(f"No room found for frequency in file: {file_path}")

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
        match = re.search(r'_(\d+)\.wav$', filename)
        return int(match.group(1)) if match else None

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
    
    handler = UploadHandler(client, room_ids)
    observer = Observer()
    observer.schedule(handler, recordings_path, recursive=False)
    observer.start()
    logging.info(f"Started observer for {recordings_path}")
    
    # Keep the script running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())