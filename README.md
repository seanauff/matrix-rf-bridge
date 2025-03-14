# RTL-Airband Matrix Uploader

## Overview

The RTLSDR-Airband Matrix Uploader is a Python-based tool designed to upload recordings from an `RTLSDR-Airband` instance to a Matrix server (e.g., Synapse). Each frequency is mapped to its own room within a Matrix space, allowing users to browse and listen to recordings via a Matrix client like Element. The project leverages `RTLSDR-Airband` for radio monitoring and `matrix-nio` for Matrix interactions, all running within Docker containers for easy deployment.

### Features

- **Multi-Frequency Monitoring**: Monitors multiple frequencies within the SDR’s bandwidth simultaneously (RTLSDR-Airband multichannel mode).
- **Automatic Recording**: Records transmissions into `.mp3` files when squelch is broken, with filenames including the frequency in Hz.
- **Matrix Integration**: Uploads recordings to dedicated Matrix rooms, organized by frequency.
- **Configurable**: Uses an `rtl_airband.conf` file to define channels, with optional skipping of disabled channels via an environment variable.
- **Dockerized**: Runs in Docker containers, accessing the SDR via pass through.

## What It Does

This tool relies on `RTLSDR-Airband` for all demodulation and recording. These recordings are uploaded to a Matrix server, where each frequency has its own room (e.g., `#145.145MHz:yourdomain.com`). Users can access these rooms using a Matrix client like Element to listen to the recordings.

## Requirements

### Hardware

- SDR supported by `RTLSDR-Airband`.
- Computer or server with access to the SDR and network connectivity.

### Software

- **Operating System**: Linux (recommended), macOS, or Windows (with Docker Desktop).
- **Docker**: Docker and Docker Compose for containerized deployment.
- **Python**: Python 3.9+ (if running outside Docker).

### Dependencies

- **Matrix Server**: A running Synapse server (or another Matrix homeserver) with a registered bot user.
- **Libraries** (installed via Docker):
  - `matrix-nio`: For Matrix interactions.
  - `watchdog`: For filesystem monitoring.
  - `RTLSDR-Airband`: For RTL-SDR frequency monitoring and recording.

## Installation Instructions

### Prerequisites

1. **Install Docker**:
   - See instructions at [docker.com](https://www.docker.com/get-started).

2. **Set Up Synapse**:
   - Follow the [Synapse installation guide](https://matrix-org.github.io/synapse/latest/setup/installation.html).
   - Register a bot user: `register_new_matrix_user -u bot_user -p <password> -a -c /path/to/homeserver.yaml`.

### Clone the Repository

```bash
git clone https://github.com/seanauff/rtl-airband-matrix-uploader.git
cd rtl-airband-matrix-uploader
```

## Build Instructions

1. **Prepare Configuration**:
   - Copy the example `rtl_airband.conf` to the `rtl_airband` directory:
     ```bash
     cp example_rtl_airband.conf rtl_airband/rtl_airband.conf
     ```
   - Edit `rtl_airband/rtl_airband.conf` to specify your frequencies (e.g., `freq = 145.145;`).
2. **Create Docker Compose File**:
